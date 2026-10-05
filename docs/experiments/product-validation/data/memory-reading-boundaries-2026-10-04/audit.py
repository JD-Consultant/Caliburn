"""Post-run structural audit; no provider calls or changes to original evidence."""

import hashlib
import json
from collections import Counter
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
    rows = [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    result = read_json(run_dir / "result.json")
    manifest = read_json(run_dir / "manifest.json")
    metrics = read_json(run_dir / "metrics.json")
    material = read_json(run_dir / "materials.json")
    previous = {}
    pairs = reasoning = phases = continuations = 0
    for row in rows:
        key = row.get("cell_id")
        if row["event"] == "generation_request" and key in previous:
            continuations += 1
            inputs = row["request"]["input"]
            for item in previous[key]:
                if item["type"] == "function_call":
                    assert any(
                        x.get("type") == "function_call"
                        and all(
                            x.get(k) == item.get(k)
                            for k in ("call_id", "name", "arguments")
                        )
                        for x in inputs
                    ), "Previous function call changed"
                    assert any(
                        x.get("type") == "function_call_output"
                        and x.get("call_id") == item["call_id"]
                        for x in inputs
                    ), "Previous tool result missing"
                    pairs += 1
                elif item["type"] == "reasoning":
                    assert any(
                        x.get("type") == "reasoning"
                        and all(
                            x.get(k) == item.get(k)
                            for k in (
                                "id",
                                "encrypted_sha256",
                                "encrypted_length",
                                "summary",
                            )
                        )
                        for x in inputs
                    ), "Reasoning identity or encrypted fingerprint changed"
                    reasoning += 1
                elif item["type"] == "message":
                    assert any(
                        x.get("type") == "message"
                        and all(
                            x.get(k) == item.get(k) for k in ("id", "phase", "content")
                        )
                        for x in inputs
                    ), "Assistant message or phase changed"
                    phases += 1
        elif row["event"] == "generation_response":
            previous[key] = row["response"]["output"]
    for index, (name, digest) in enumerate(manifest["source_sha256"].items()):
        source = run_dir / "source-files" / f"{index:02d}-{PureWindowsPath(name).name}"
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert sum(len(c["usage"]) for c in result["results"]) == result["generation_calls"]
    cost = sum(
        (Decimal(u["estimated_usd"]) for c in result["results"] for u in c["usage"]),
        Decimal(0),
    )
    count_allowance = sum(map(Decimal, result["pending"].values()), Decimal(0))
    assert cost + count_allowance == Decimal(result["occupied_usd"])
    assert not any(k.startswith("model-") for k in result["pending"])
    assert Decimal(result["occupied_usd"]) <= Decimal(manifest["max_estimated_usd"])
    assert result["seconds"] <= manifest["max_seconds"]
    for cell in manifest["schedule"]:
        window = read_json(run_dir / f"initial-{cell['cell_id']}.json")
        assert fingerprint(window) == manifest["initial_sha256"][cell["case_id"]]
        first = next(
            r
            for r in rows
            if r.get("cell_id") == cell["cell_id"]
            and r["event"] == "generation_request"
        )
        assert first["request"]["input"] == window
        assert first["request"]["model"] == manifest["model"]
        assert first["request"]["reasoning"]["effort"] == manifest["effort"]
    for cell in result["results"]:
        after = read_json(run_dir / f"after-{cell['cell_id']}.json")
        expected = dict(material["slots"])
        if cell["proposal"]:
            expected.update(
                {c["target_ref"]: c["value"] for c in cell["proposal"]["changes"]}
            )
        assert after == expected
    return {
        "http_statuses": dict(
            Counter(r["status"] for r in rows if r["event"] == "http_response")
        ),
        "continuation_requests": continuations,
        "prior_function_pairs": pairs,
        "reasoning_items_preserved": reasoning,
        "assistant_phase_items_preserved": phases,
        "frozen_sources_verified": len(manifest["source_sha256"]),
        "initial_windows_verified": len(manifest["schedule"]),
        "after_fields_verified": len(result["results"]),
        "generation_estimated_usd": str(cost),
        "count_allowance_usd": str(count_allowance),
        "totals": {
            field: sum(c[field] for c in metrics["cells"])
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
    }


if __name__ == "__main__":
    print(json.dumps(audit_run(HERE / "live-01"), ensure_ascii=False, indent=2))
