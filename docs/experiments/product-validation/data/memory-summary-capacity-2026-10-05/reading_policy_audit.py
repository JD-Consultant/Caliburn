"""Offline paired-study accounting and context checks, not semantic grading."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "reading-policy-01"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit():
    manifest, result = load(RUN / "manifest.json"), load(RUN / "result.json")
    arms, requests, counts = {}, [], []
    for arm in ("control", "candidate"):
        cells = [cell for cell in result["results"] if cell["arm"] == arm]
        usage = [item for cell in cells for item in cell["usage"]]
        arms[arm] = {
            "completed_cells": sum(cell["status"] == "completed" for cell in cells),
            "input_tokens": sum(item["usage"]["input_tokens"] for item in usage),
            "cached_tokens": sum(
                item["usage"]["input_tokens_details"]["cached_tokens"] for item in usage
            ),
            "output_tokens": sum(item["usage"]["output_tokens"] for item in usage),
            "reasoning_tokens": sum(
                item["usage"]["output_tokens_details"]["reasoning_tokens"]
                for item in usage
            ),
            "model_calls": len(usage),
            "read_calls": sum(len(cell["reads"]) for cell in cells),
            "raw_read_calls": sum(
                read["name"] == "read_interview"
                for cell in cells
                for read in cell["reads"]
            ),
            "map_read_calls": sum(
                read["name"].endswith("_map")
                for cell in cells
                for read in cell["reads"]
            ),
            "initial_input_tokens": [
                cell["usage"][0]["counted_input_tokens"]
                for cell in cells
                if cell["usage"]
            ],
            "estimated_generation_usd": str(
                sum((Decimal(item["estimated_usd"]) for item in usage), Decimal(0))
            ),
        }
    for line in (RUN / "trace.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        if row["event"] == "generation_request":
            data = row["request"]
            if data.get("previous_response_id") or any(
                item.get("type") == "compaction" for item in data["input"]
            ):
                raise ValueError("unexpected_previous_state")
            if sum(item.get("role") == "user" for item in data["input"]) != 2:
                raise ValueError("unexpected_app_or_question_duplication")
            requests.append(
                {
                    "case_id": row["case_id"],
                    "arm": row["arm"],
                    "repeat": row["repeat"],
                    "step": row["step"],
                    "input_items": len(data["input"]),
                }
            )
        elif row["event"] == "count_response":
            counts.append(row["input_tokens"])
    paired_inputs = []
    for case in load(RUN / "cases.json"):
        for repeat in (1, 2):
            files = [
                RUN / f"initial-{case['case_id']}-{arm}-{repeat}.json"
                for arm in ("control", "candidate")
            ]
            if all(path.exists() for path in files):
                if load(files[0]) != load(files[1]):
                    raise ValueError("paired_context_changed")
                paired_inputs.append(
                    {"case_id": case["case_id"], "repeat": repeat, "equal": True}
                )
    paid = sum(
        (Decimal(arm["estimated_generation_usd"]) for arm in arms.values()), Decimal(0)
    )
    paid += sum(
        (Decimal(item["estimated_usd"]) for item in result["failed_usage"]), Decimal(0)
    )
    pending = sum((Decimal(value) for value in result["pending"].values()), Decimal(0))
    if paid + pending != Decimal(result["occupied_usd"]):
        raise ValueError("cost_ledger_mismatch")
    if Decimal(result["occupied_usd"]) > Decimal(manifest["max_estimated_usd"]):
        raise ValueError("exceeded_budget")
    if result["seconds"] > manifest["max_seconds"] + 5:
        raise ValueError("time_limit_not_respected")
    output = {
        "kind": "offline_accounting_and_context_audit_not_quality_grade",
        "arms": arms,
        "paired_initial_contexts": paired_inputs,
        "generation_requests": requests,
        "counted_input_range": [min(counts), max(counts)] if counts else [],
        "occupied_usd": result["occupied_usd"],
        "cumulative_occupied_usd": result["cumulative_occupied_usd"],
        "pending_administrative_or_unknown_usd": str(pending),
        "seconds": result["seconds"],
        "sha256": {
            name: hashlib.sha256((RUN / name).read_bytes()).hexdigest()
            for name in ("manifest.json", "result.json", "trace.jsonl")
        },
        "note": "Semantic quality and source support must be assessed separately; no keyword grading.",
    }
    (RUN / "usage-audit.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output


if __name__ == "__main__":
    data = audit()
    print(
        json.dumps(
            {
                key: data[key]
                for key in (
                    "arms",
                    "occupied_usd",
                    "cumulative_occupied_usd",
                    "seconds",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
