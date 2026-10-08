"""Operational facts for a completed case, separate from blinded JD review."""

import json
from collections import Counter
from decimal import Decimal
from pathlib import Path


def collect(directory, baseline):
    rows = [
        json.loads(line)
        for line in (directory / "provider-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    rows.sort(key=lambda row: row["time"])
    admitted = [row for row in rows if row["event"] == "admitted"]
    received = [row for row in rows if row["event"] == "received"]
    if len({row["attempt"] for row in admitted}) != len(admitted):
        raise ValueError("Duplicate admitted attempt")
    if len({row["attempt"] for row in received}) != len(received):
        raise ValueError("Duplicate received attempt")
    if {row["attempt"] for row in received} != {row["attempt"] for row in admitted}:
        raise ValueError("Unsettled or foreign received attempt")
    cost = Counter()
    previous = Decimal(baseline)
    for row in received:
        current = Decimal(row["spent_usd"])
        if current < previous or row.get("usage") is None:
            raise ValueError("Missing exact usage or cumulative spent rollback")
        cost[row["role"]] += current - previous
        previous = current
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    state = result["guard"]
    if previous != Decimal(state["spent_usd"]):
        raise ValueError("Final case spent differs from exact received journal")
    witnesses = result["measurements"]["A_compact_adoptions"]
    return {
        "case": directory.name,
        "turns": len(result["turns"]),
        "completed_turns": sum(turn["status"] == "completed" for turn in result["turns"]),
        "closure_submitted": result["closure_submitted"],
        "mechanically_complete": result["closure_submitted"]
        and result["turns"][-1]["status"] == "completed",
        "driver_reminders": result["driver_reminders"],
        "turn_elapsed_seconds_sum": sum(turn["elapsed_seconds"] for turn in result["turns"]),
        "generation_attempts": sum(row["endpoint"] == "/v1/responses" for row in admitted),
        "compact_attempts": sum(row["endpoint"] == "/v1/responses/compact" for row in admitted),
        "count_attempts_observed": sum(row["event"] == "count" for row in rows),
        "counted_input_sum": sum(row["input_tokens"] for row in rows if row["event"] == "count"),
        "input_tokens": result["measurements"]["input_tokens"],
        "output_tokens": result["measurements"]["output_tokens"],
        "roles_usage": result["measurements"]["roles"],
        "cost_usd": str(previous - Decimal(baseline)),
        "role_cost_usd": {key: str(value) for key, value in cost.items()},
        "final_aggregate_guard": state,
        "memory_settlement": result["memory_settlement"],
        "compaction_witnesses": [
            {key: value for key, value in witness.items() if key != "post_C_public_items"}
            for witness in witnesses
        ],
    }


def main():
    import sys

    directory, baseline, output = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    if output.exists():
        raise RuntimeError("Completed operational evidence already exists")
    result = collect(directory, baseline)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
