"""Trace arithmetic and original C adoption witnesses; no quality scoring engine."""

import json
from pathlib import Path


def read_lines(path):
    return (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if path.exists()
        else []
    )


def measure(directory):
    trace = read_lines(directory / "provider-trace.jsonl")
    checkpoints = read_lines(directory / "checkpoint-witness.jsonl")
    admits = {row["attempt"]: row for row in trace if row["event"] == "admitted"}
    received = [row for row in trace if row["event"] == "received"]
    result = {
        "input_tokens": 0,
        "output_tokens": 0,
        "counts": 0,
        "max_counted_input": 0,
        "generation_attempts": 0,
        "compact_attempts": 0,
        "roles": {},
        "A_compact_adoptions": [],
    }
    for row in trace:
        if row["event"] == "count":
            result["counts"] += 1
            result["max_counted_input"] = max(
                result["max_counted_input"], row["input_tokens"]
            )
        if row["event"] == "admitted":
            key = (
                "compact_attempts"
                if row["endpoint"].endswith("/compact")
                else "generation_attempts"
            )
            result[key] += 1
    for row in received:
        usage = row.get("usage")
        if usage:
            actor = row.get("role") or "unknown"
            role_usage = result["roles"].setdefault(
                actor, {"input_tokens": 0, "output_tokens": 0}
            )
            for kind in ["input_tokens", "output_tokens"]:
                result[kind] += usage[kind]
                role_usage[kind] += usage[kind]
        if row["endpoint"].endswith("/compact") and row.get("role") == "A":
            full_c = row["output_item_sha256"]
            all_adopted = [
                checkpoint
                for checkpoint in checkpoints
                if checkpoint.get("adopted") is True
                and checkpoint.get("compaction_item_sha256") == full_c
            ]
            adopted = [
                item for item in all_adopted if item.get("preparation_policy") is None
            ]
            next_requests = [
                request
                for request in admits.values()
                if request.get("role") == "A"
                and request["endpoint"] == "/v1/responses"
                and request["time"] > row["time"]
                and request["input_item_sha256"][: len(full_c)] == full_c
                and bool(full_c)
            ]
            projections = [
                item
                for item in checkpoints
                if item.get("projection") is not None
                and any(
                    item.get("input_binding", {}).get("compact_position")
                    == {
                        "thread_id": saved["thread_id"],
                        "checkpoint_id": saved["checkpoint_id"],
                    }
                    for saved in adopted
                )
            ]
            from guard import digest

            projected_next = [
                request
                for request in next_requests
                if any(
                    len(request["input_item_sha256"]) > len(full_c)
                    and request["input_item_sha256"][len(full_c)]
                    == digest(item["projection"]["plan_item"])
                    for item in projections
                )
            ]
            witness = {
                "response_id": row.get("response_id"),
                "all_C_items": len(full_c),
                "boundary": "mid-work"
                if adopted
                else "pre-work"
                if all_adopted
                else "unknown",
                "checkpoint_adopted": bool(adopted),
                "any_boundary_checkpoint_adopted": bool(all_adopted),
                "subsequent_A_exact_C_prefix": bool(next_requests),
                "exact_bound_plan_projection_checkpoint": bool(projections),
                "next_A_exact_saved_plan_item": bool(projected_next),
                "checkpoint_ids": [item["checkpoint_id"] for item in adopted],
                "next_attempts": [item["attempt"] for item in next_requests],
            }
            if next_requests:
                witness["post_C_public_items"] = next_requests[0]["input"][
                    len(full_c) :
                ]
            result["A_compact_adoptions"].append(witness)
    return result


if __name__ == "__main__":
    import sys

    print(json.dumps(measure(Path(sys.argv[1])), ensure_ascii=False, indent=2))
