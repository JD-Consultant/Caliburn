"""Post-run integrity and usage checks; this does not grade JD semantics."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path, PureWindowsPath

HERE = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def audit_run(run_dir):
    manifest = read_json(run_dir / "manifest.json")
    result = read_json(run_dir / "result.json")
    metrics = read_json(run_dir / "metrics.json")
    instructions = read_json(run_dir / "instructions.json")
    rows = [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    scheduled = {cell["cell_id"]: cell for cell in manifest["schedule"]}
    for index, (name, digest) in enumerate(manifest["source_sha256"].items()):
        source = run_dir / "source-files" / f"{index:02d}-{PureWindowsPath(name).name}"
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert {key: fingerprint(value) for key, value in instructions.items()} == manifest[
        "instructions_sha256"
    ]
    assert (
        fingerprint(read_json(run_dir / "tools-raw_memory.json"))
        == manifest["tools_sha256"]["raw_memory"]
    )
    for case_id, digest in manifest["initial_sha256"].items():
        assert fingerprint(read_json(run_dir / f"initial-{case_id}.json")) == digest
    generation = [row for row in rows if row["event"] == "generation_response"]
    assert (
        len(generation)
        == result["generation_calls"]
        == sum(len(cell["usage"]) for cell in result["results"])
    )
    cost = sum(
        (
            Decimal(usage["estimated_usd"])
            for cell in result["results"]
            for usage in cell["usage"]
        ),
        Decimal(0),
    )
    pending = sum(map(Decimal, result["pending"].values()), Decimal(0))
    assert cost + pending == Decimal(result["occupied_usd"])
    assert Decimal(manifest["prior_occupied_usd"]) + cost + pending == Decimal(
        result["cumulative_occupied_usd"]
    )
    assert Decimal(result["occupied_usd"]) <= Decimal(manifest["max_estimated_usd"])
    assert result["seconds"] <= manifest["max_seconds"] + 2
    assert result["generation_calls"] <= 32
    assert result["outbound_calls"] <= 64
    assert not any(key.startswith("model-") for key in result["pending"])
    original_start = manifest.get("transport_recovery", {}).get(
        "original_paid_start", rows[0]["at"]
    )
    batch_seconds = (
        datetime.fromisoformat(rows[-1]["at"]) - datetime.fromisoformat(original_start)
    ).total_seconds()
    original_attempts = manifest.get("transport_recovery", {}).get(
        "original_outbound_attempts", 0
    )
    assert batch_seconds <= 900
    assert result["outbound_calls"] + original_attempts <= 64
    previous_outputs = {}
    continuation_requests = 0
    for row in rows:
        cell_id = row.get("cell_id")
        if row["event"] == "generation_request":
            selection = scheduled[cell_id]
            request = row["request"]
            assert request["instructions"] == instructions[selection["prompt_variant"]]
            assert request["model"] == manifest["model"]
            assert request["reasoning"]["effort"] == manifest["effort"]
            assert (
                fingerprint(request["tools"]) == manifest["tools_sha256"]["raw_memory"]
            )
            if cell_id not in previous_outputs:
                assert request["input"] == read_json(
                    run_dir / f"initial-{selection['case_id']}.json"
                )
            else:
                continuation_requests += 1
                for item in previous_outputs[cell_id]:
                    if item["type"] in ("message", "reasoning", "function_call"):
                        assert item in request["input"], (
                            "Previous native item changed or missing"
                        )
                        if item["type"] == "function_call":
                            assert any(
                                entry.get("type") == "function_call_output"
                                and entry.get("call_id") == item["call_id"]
                                for entry in request["input"]
                            )
        elif row["event"] == "generation_response":
            previous_outputs[cell_id] = row["response"]["output"]
    for cell in result["results"]:
        initial = read_json(run_dir / f"initial-{cell['case_id']}.json")
        fields = json.loads(initial[0]["content"])["jd_draft"]["work_tasks"][0][
            "fields"
        ]
        expected = {field["target_ref"]: field["text"] for field in fields}
        if cell["proposal"]:
            expected.update(
                {
                    change["target_ref"]: change["value"]
                    for change in cell["proposal"]["changes"]
                }
            )
        assert expected == read_json(run_dir / f"after-{cell['cell_id']}.json")
    return {
        "frozen_sources_verified": len(manifest["source_sha256"]),
        "scheduled_cells": len(scheduled),
        "saved_cells": len(result["results"]),
        "completed_cells": sum(
            cell["status"] == "completed" for cell in result["results"]
        ),
        "http_statuses": dict(
            Counter(row["status"] for row in rows if row["event"] == "http_response")
        ),
        "generation_estimated_usd": str(cost),
        "count_allowance_usd": str(pending),
        "cumulative_occupied_usd": result["cumulative_occupied_usd"],
        "continuation_requests": continuation_requests,
        "batch_seconds_from_first_attempt": batch_seconds,
        "totals": {
            field: sum(cell[field] for cell in metrics["cells"])
            for field in (
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "cached_tokens",
                "cache_write_tokens",
                "reads",
                "read_characters",
            )
        },
        "trace_sha256": hashlib.sha256(
            (run_dir / "trace.jsonl").read_bytes()
        ).hexdigest(),
        "result_sha256": hashlib.sha256(
            (run_dir / "result.json").read_bytes()
        ).hexdigest(),
        "note": "Post-run structural audit, not pre-registered semantic grading. Use without python -O.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_run(args.run_dir), ensure_ascii=False, indent=2))
