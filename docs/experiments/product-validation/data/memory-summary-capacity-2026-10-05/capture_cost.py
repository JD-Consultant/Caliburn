"""Offline cost projection for the four reused Memory batches, not a new run."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.response_serialization import restore_response

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "compaction-long-interview-2026-10-04"


def project():
    rates = model_profile("gpt-6-luna").pricing
    records = []
    traces = {}
    counts = 0
    for run in ("main-02", "main-03"):
        path = SOURCE / run / "trace.jsonl"
        traces[run] = hashlib.sha256(path.read_bytes()).hexdigest()
        for line in path.open(encoding="utf-8"):
            item = json.loads(line)
            if item.get("phase") != "memory" or item.get("after_event") not in (
                "e012",
                "e028",
                "e044",
                "e052",
            ):
                continue
            if (
                item["event"] == "request"
                and item["path"] == "/v1/responses/input_tokens"
            ):
                counts += 1
            if item["event"] != "response" or not item.get("payload", {}).get("usage"):
                continue
            payload = item["payload"]
            cost = rates.estimate_response_cost(restore_response(payload))
            if cost is None:
                raise ValueError("unknown_historical_usage")
            records.append(
                {
                    "run": run,
                    "after_event": item["after_event"],
                    "path": item["path"],
                    "response_id": payload["id"],
                    "status": payload["status"],
                    "usage": payload["usage"],
                    "estimated_usd": str(cost),
                }
            )
    if len({r["response_id"] for r in records}) != len(records):
        raise ValueError("duplicated_historical_response")
    output = {
        "kind": "historical_capture_projection_not_matched_pipeline_comparison",
        "pricing_basis": rates.cost_basis,
        "source_trace_sha256": traces,
        "records": records,
        "known_generation_usd": str(
            sum((Decimal(r["estimated_usd"]) for r in records), Decimal(0))
        ),
        "count_attempts": counts,
        "input_tokens": sum(r["usage"]["input_tokens"] for r in records),
        "output_tokens": sum(r["usage"]["output_tokens"] for r in records),
        "note": "Already in prior cumulative occupancy; do not add these dollars again. Historical product tool loops differ from the new flat capture. No new provider calls.",
    }
    (HERE / "historical-capture-cost.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in output.items() if k != "records"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    project()
