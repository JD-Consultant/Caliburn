"""Offline metrics and resulting JD fields, never automatic semantic grading."""

import argparse
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.response_serialization import restore_response


def memory_preprocessing() -> dict:
    source = Path(__file__).parent.parent / "compaction-long-interview-2026-10-04"
    totals = Counter()
    cost = Decimal(0)
    source_hashes = {}
    events = Counter()
    for name in ("main-02", "main-03"):
        path = source / name / "trace.jsonl"
        sha = hashlib.sha256()
        with path.open("rb") as stream:
            for line in stream:
                sha.update(line)
                row = json.loads(line)
                if row.get("phase") != "memory":
                    continue
                if (
                    row.get("event") == "request"
                    and row["path"] == "/v1/responses/input_tokens"
                ):
                    totals["count_requests"] += 1
                if row.get("event") != "response" or row["path"] != "/v1/responses":
                    continue
                response = restore_response(row["payload"])
                estimated = model_profile("gpt-6-luna").pricing.estimate_response_cost(
                    response
                )
                if estimated is None:
                    raise ValueError("Missing historical Memory usage")
                cost += estimated
                totals["generation_responses"] += 1
                totals["input_tokens"] += response.usage.input_tokens
                totals["output_tokens"] += response.usage.output_tokens
                totals["cached_tokens"] += (
                    response.usage.input_tokens_details.cached_tokens
                )
                totals["cache_write_tokens"] += (
                    response.usage.input_tokens_details.cache_write_tokens
                )
                events[f"{name}/{row['after_event']}"] += 1
        source_hashes[name] = sha.hexdigest()
    return {
        **dict(totals),
        "generation_estimated_usd": str(cost),
        "batches": dict(events),
        "trace_sha256": source_hashes,
        "scope": "Four naturally produced Memory batches through e052; already paid in prior runs, not charged again. Consultant generation, administrative count reserves and unrelated failed consultant candidates are excluded.",
    }


def analyze(run_dir: Path) -> dict:
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    material = json.loads((run_dir / "materials.json").read_text(encoding="utf-8"))
    cells = []
    for cell in result["results"]:
        usage = [entry["usage"] for entry in cell["usage"]]
        after = dict(material["slots"])
        if cell["proposal"] is not None:
            after.update(
                {
                    change["target_ref"]: change["value"]
                    for change in cell["proposal"]["changes"]
                }
            )
        read_counts = Counter(
            (
                entry["name"],
                json.dumps(entry["arguments"], ensure_ascii=False, sort_keys=True),
            )
            for entry in cell["reads"]
        )
        row = {
            "cell_id": cell["cell_id"],
            "arm": cell["arm"],
            "case_id": cell["case_id"],
            "repeat": cell["repeat"],
            "status": cell["status"],
            "model_calls": len(usage),
            "initial_input_tokens": usage[0]["input_tokens"] if usage else None,
            "input_tokens": sum(entry["input_tokens"] for entry in usage),
            "output_tokens": sum(entry["output_tokens"] for entry in usage),
            "cached_tokens": sum(
                entry["input_tokens_details"]["cached_tokens"] for entry in usage
            ),
            "cache_write_tokens": sum(
                entry["input_tokens_details"]["cache_write_tokens"] for entry in usage
            ),
            "reasoning_tokens": sum(
                entry["output_tokens_details"]["reasoning_tokens"] for entry in usage
            ),
            "reads": len(cell["reads"]),
            "repeat_reads": sum(n - 1 for n in read_counts.values()),
            "read_characters": sum(
                entry["result_characters"] for entry in cell["reads"]
            ),
            "generation_estimated_usd": str(
                sum(
                    (Decimal(entry["estimated_usd"]) for entry in cell["usage"]),
                    Decimal(0),
                )
            ),
            "seconds": cell.get("seconds"),
            "changes": len(cell["proposal"]["changes"]) if cell["proposal"] else 0,
        }
        cells.append(row)
        (run_dir / f"after-{cell['cell_id']}.json").write_text(
            json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return {
        "cells": cells,
        "occupied_usd": result["occupied_usd"],
        "cumulative_occupied_usd": result["cumulative_occupied_usd"],
        "outbound_calls": result["outbound_calls"],
        "elapsed_seconds": result["seconds"],
        "note": "Metrics are derived; correctness and citation support require separate semantic grading.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    metrics = analyze(args.run_dir)
    preprocessing = memory_preprocessing()
    (args.run_dir / "memory-preprocessing.json").write_text(
        json.dumps(preprocessing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.run_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
