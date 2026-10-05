"""Offline projections of saved pilot evidence; never print raw request lines."""

import argparse
import hashlib
import json
from decimal import Decimal
from itertools import chain
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit(run_dir):
    manifest = load(run_dir / "manifest.json")
    result = load(run_dir / "result.json")
    cases = load(run_dir / "cases.json")
    capture = result["capture_usage"]
    summaries = {}
    for arm in ("memory", "flat"):
        cells = [c for c in result["results"] if c["arm"] == arm]
        usages = [u for c in cells for u in c["usage"]]
        summaries[arm] = {
            "completed_cells": sum(c["status"] == "completed" for c in cells),
            "initial_input_tokens": [
                c["usage"][0]["counted_input_tokens"] for c in cells if c["usage"]
            ],
            "input_tokens": sum(u["usage"]["input_tokens"] for u in usages),
            "output_tokens": sum(u["usage"]["output_tokens"] for u in usages),
            "reasoning_tokens": sum(
                u["usage"]["output_tokens_details"]["reasoning_tokens"] for u in usages
            ),
            "cached_tokens": sum(
                u["usage"]["input_tokens_details"]["cached_tokens"] for u in usages
            ),
            "estimated_generation_usd": str(
                sum((Decimal(u["estimated_usd"]) for u in usages), Decimal(0))
            ),
            "model_calls": len(usages),
            "read_calls": sum(len(c["reads"]) for c in cells),
            "raw_read_calls": sum(
                r["name"] == "read_interview" for c in cells for r in c["reads"]
            ),
        }
    counts = []
    responses = []
    tools = []
    requests = []
    trace_dirs = (
        [run_dir.parent / manifest["continuation_of"], run_dir]
        if manifest.get("continuation_of")
        else [run_dir]
    )
    for line in chain.from_iterable(
        (folder / "trace.jsonl").open(encoding="utf-8") for folder in trace_dirs
    ):
        item = json.loads(line)
        if item["event"] == "count_response":
            counts.append(item["input_tokens"])
        elif item["event"] == "generation_response":
            responses.append(
                {"at": item["at"], "phase": item["phase"], "id": item["response"]["id"]}
            )
        elif item["event"] == "tool_result":
            tools.append(
                {
                    "arm": item["arm"],
                    "case_id": item["case_id"],
                    "repeat": item["repeat"],
                    "name": item["name"],
                    "arguments": item["arguments"],
                }
            )
        elif item["event"] == "generation_request":
            requests.append(
                {
                    "phase": item["phase"],
                    "input_items": len(item["request"]["input"]),
                    "previous_response_id": item["request"].get("previous_response_id"),
                    "native_compaction_items": sum(
                        i.get("type") == "compaction" for i in item["request"]["input"]
                    ),
                }
            )
    if any(r["previous_response_id"] or r["native_compaction_items"] for r in requests):
        raise ValueError("unexpected_prior_state")
    costs = sum((Decimal(u["estimated_usd"]) for u in capture), Decimal(0))
    costs += sum(
        (Decimal(u["estimated_usd"]) for u in result.get("failed_usage", [])),
        Decimal(0),
    )
    costs += sum(
        (Decimal(a["estimated_generation_usd"]) for a in summaries.values()), Decimal(0)
    )
    pending = sum((Decimal(v) for v in result["pending"].values()), Decimal(0))
    if costs + pending != Decimal(result["occupied_usd"]):
        raise ValueError("cost_ledger_mismatch")
    if Decimal(result["occupied_usd"]) > Decimal(manifest["max_estimated_usd"]):
        raise ValueError("exceeded_budget")
    if len(responses) != result["generation_calls"]:
        raise ValueError("missing_response_or_unknown_generation")
    projection = {
        "kind": "offline_usage_audit_not_quality_grade",
        "arms": summaries,
        "capture": {
            "batches": len(capture),
            "input_tokens": sum(u["usage"]["input_tokens"] for u in capture),
            "output_tokens": sum(u["usage"]["output_tokens"] for u in capture),
            "estimated_generation_usd": str(
                sum((Decimal(u["estimated_usd"]) for u in capture), Decimal(0))
            ),
        },
        "grading_items": sum(len(c["criteria"]) for c in cases),
        "generation_calls": result["generation_calls"],
        "failed_generation_calls": len(result.get("failed_usage", [])),
        "failed_generation_usd": str(
            sum(
                (Decimal(u["estimated_usd"]) for u in result.get("failed_usage", [])),
                Decimal(0),
            )
        ),
        "outbound_calls": result["outbound_calls"],
        "counts_min": min(counts),
        "counts_max": max(counts),
        "seconds": result["seconds"],
        "occupied_usd": result["occupied_usd"],
        "cumulative_occupied_usd": result["cumulative_occupied_usd"],
        "pending_administrative_usd": str(pending),
        "tool_sequence": tools,
        "result_sha256": hashlib.sha256(
            (run_dir / "result.json").read_bytes()
        ).hexdigest(),
        "trace_sha256": hashlib.sha256(
            (run_dir / "trace.jsonl").read_bytes()
        ).hexdigest(),
        "quality": "Separate semantic assessment required; no keyword auto-grading.",
    }
    (run_dir / "usage-audit.json").write_text(
        json.dumps(projection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return projection


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    data = audit(args.run_dir)
    print(
        json.dumps(
            {key: value for key, value in data.items() if key != "tool_sequence"},
            ensure_ascii=False,
            indent=2,
        )
    )
