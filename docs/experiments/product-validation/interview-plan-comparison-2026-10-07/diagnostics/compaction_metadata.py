"""Original hash vectors and scoped checkpoint witnesses, without model content."""

import json
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from guard import digest


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def plan_kind(item):
    plan = json.loads(item["content"])["plan"]
    if plan is None:
        return "null"
    if not isinstance(plan, str):
        raise ValueError("Saved projection plan has unexpected type")
    return "empty_string" if plan == "" else "nonempty_string"


def collect(directory):
    trace_path = directory / "provider-trace.jsonl"
    checkpoint_path = directory / "checkpoint-witness.jsonl"
    trace, checkpoints = read_rows(trace_path), read_rows(checkpoint_path)
    admitted = {row["attempt"]: row for row in trace if row["event"] == "admitted"}
    witnesses = []
    for row in trace:
        if row["event"] != "received" or row["endpoint"] != "/v1/responses/compact":
            continue
        original = row["output_item_sha256"]
        compact_request = admitted[row["attempt"]]
        if not original:
            raise ValueError("Native C received with no complete item hash vector")
        adopted = [
            saved
            for saved in checkpoints
            if saved.get("adopted") is True and saved.get("compaction_item_sha256") == original
        ]
        next_requests = [
            request
            for request in trace
            if request["event"] == "admitted"
            and request["endpoint"] == "/v1/responses"
            and request["role"] == row["role"]
            and request["time"] > row["time"]
            and request["input_item_sha256"][: len(original)] == original
        ]
        checkpoint_witnesses = []
        for saved in adopted:
            thread = saved["thread_id"]
            policy = saved.get("preparation_policy", "missing")
            original_request_equal = (
                saved.get("request_input_item_sha256") == compact_request["input_item_sha256"]
            )
            boundary = (
                "mid-work"
                if original_request_equal and policy is None and ":compact:" in thread
                else "pre-work"
                if original_request_equal
                and isinstance(policy, dict)
                and thread.endswith(":prepared_history")
                else "unknown"
            )
            position = {
                "thread_id": saved["thread_id"],
                "checkpoint_id": saved["checkpoint_id"],
            }
            projections = []
            for projection in checkpoints:
                if projection.get("projection") is None:
                    continue
                if projection.get("input_binding", {}).get("compact_position") != position:
                    continue
                item = projection["projection"]["plan_item"]
                item_hash = digest(item)
                matching = [
                    request["attempt"]
                    for request in next_requests
                    if len(request["input_item_sha256"]) > len(original)
                    and request["input_item_sha256"][len(original)] == item_hash
                ]
                projections.append(
                    {
                        "projection_thread_id": projection["thread_id"],
                        "projection_checkpoint_id": projection["checkpoint_id"],
                        "compact_position": position,
                        "source_request_id": projection["input_binding"]["source_request_id"],
                        "same_parent_request_thread": thread
                        == (
                            projection["thread_id"].split(":plan_projection:")[0]
                            + ":compact:"
                            + projection["input_binding"]["source_request_id"]
                        ),
                        "entire_plan_item_sha256": item_hash,
                        "plan_body_kind": plan_kind(item),
                        "next_exact_plan_item_attempts": matching,
                    }
                )
            checkpoint_witnesses.append(
                {
                    **position,
                    "saved_at": saved["saved_at"],
                    "boundary": boundary,
                    "preparation_policy": policy,
                    "original_compact_input_equal_saved_parent_request": original_request_equal,
                    "original_compact_input_item_sha256": compact_request["input_item_sha256"],
                    "saved_parent_request_item_sha256": saved.get("request_input_item_sha256"),
                    "original_C_items_equal_adopted_checkpoint": saved["compaction_item_sha256"]
                    == original,
                    "adopted_item_sha256": saved["compaction_item_sha256"],
                    "bound_plan_projections": projections,
                }
            )
        witnesses.append(
            {
                "attempt": row["attempt"],
                "response_id": row["response_id"],
                "role": row["role"],
                "original_complete_item_sha256": original,
                "original_complete_vector_sha256": digest(original),
                "adopted_checkpoints": checkpoint_witnesses,
                "subsequent_exact_prefix_requests": [
                    {
                        "attempt": request["attempt"],
                        "role": request["role"],
                        "complete_input_vector_sha256": digest(request["input_item_sha256"]),
                        "prefix_item_sha256": request["input_item_sha256"][: len(original)],
                        "all_original_C_items_in_order": True,
                        "first_post_C_item_sha256": request["input_item_sha256"][len(original)]
                        if len(request["input_item_sha256"]) > len(original)
                        else None,
                    }
                    for request in next_requests
                ],
            }
        )
    return {
        "case": directory.name,
        "sources": {
            path.name: sha256(path.read_bytes()).hexdigest()
            for path in [trace_path, checkpoint_path]
        },
        "native_compactions": witnesses,
        "scope_note": (
            "Original full-item hash vectors include encrypted content; "
            "public trace text alone is not rehashed as complete C."
        ),
    }


def main():
    directory, output = Path(sys.argv[1]), Path(sys.argv[2])
    if output.exists():
        raise RuntimeError("Compaction hash evidence already exists")
    result = collect(directory)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "case": result["case"],
                "native_compactions": len(result["native_compactions"]),
                "output": str(output),
                "sha256": sha256(output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
