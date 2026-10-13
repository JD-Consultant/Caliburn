"""從原件投影暫停與後續進展，不建立控制事件。

checkpoint 時間早於其 pending interrupt，後代 checkpoint 也不代表 App 受理續作的時間。
Any 僅用於此診斷 JSON 邊界。
"""

from collections.abc import Iterable
from typing import Any


def collect_control_history(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    records = list(records)
    checkpoints = {
        (row["thread_id"], row.get("checkpoint_ns", ""), row["checkpoint_id"]): row
        for row in records
        if row["source"] == "checkpoint"
    }
    pauses = {}
    for row in records:
        for interrupt in row["values"].get("__interrupt__", []):
            value = interrupt["value"]
            if not isinstance(value, dict) or value.get("kind") != "step_pause":
                continue
            scope = (row["thread_id"], row.get("checkpoint_ns", ""))
            key = (*scope, row["checkpoint_id"], interrupt["id"])
            pauses[key] = {
                "kind": "step_pause",
                "interrupt_id": interrupt["id"],
                "completed_steps": value["completed_steps"],
                "thread_id": row["thread_id"],
                "checkpoint_ns": scope[1],
                "role": row["role"],
                "checkpoint_id": row["checkpoint_id"],
                "checkpoint_time": row["checkpoint_time"],
                "task_id": row.get("task_id"),
                "continuation": {"state": "not_observed"},
            }
    for key, pause in pauses.items():
        scope = key[:2]
        # 後代已提交完整 Step 邊界才證明進展；較新時間或其他 task 的 pending write 均不足。
        for candidate_key, candidate in sorted(checkpoints.items()):
            if candidate_key[:2] != scope or candidate_key[2] == pause["checkpoint_id"]:
                continue
            completed = candidate["values"].get("completed_steps", 0)
            if completed < pause["completed_steps"]:
                continue
            path = [candidate_key[2]]
            parent = candidate.get("parent_checkpoint_id")
            while parent is not None and parent not in path:
                path.append(parent)
                if parent == pause["checkpoint_id"]:
                    pause["continuation"] = {
                        "state": "observed",
                        "checkpoint_id": candidate_key[2],
                        "checkpoint_time": candidate["checkpoint_time"],
                        "checkpoint_path": list(reversed(path)),
                        "completed_steps": completed,
                        "request_id": candidate["values"].get("request_id"),
                        "next_action": candidate["values"].get("next_action"),
                    }
                    break
                ancestor = checkpoints.get((*scope, parent))
                parent = ancestor.get("parent_checkpoint_id") if ancestor is not None else None
            if pause["continuation"]["state"] == "observed":
                break
    return list(pauses.values())
