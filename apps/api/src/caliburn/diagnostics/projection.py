"""Project native JSON checkpoints for inspection, not for replay or business decisions.

Any is limited to the native serialization boundary. These objects never enter domain code.
"""

from collections.abc import Iterable
from copy import deepcopy
from typing import Any
from uuid import UUID

from caliburn.agent_execution.native_observations import (
    collect_steps as collect_steps,
)
from caliburn.agent_execution.native_observations import (
    collect_tool_calls as collect_tool_calls,
)
from caliburn.agent_execution.native_observations import (
    redact as redact,
)
from caliburn.features.executions.history_models import AgentRole, parse_stage_thread_id


def role_for_thread(thread_id: str, prefix: str) -> str | None:
    if not thread_id.startswith(prefix):
        return None
    capture = thread_id.endswith(":context")
    root = thread_id.removesuffix(":context") if capture else thread_id
    root, separator, compact_id = root.partition(":compact:")
    if separator:
        try:
            if str(UUID(compact_id)) != compact_id:
                return None
        except ValueError:
            return None
    stage = parse_stage_thread_id(root)
    if capture and stage is None:
        return None
    root = stage.root_thread_id if stage is not None else root
    parts = root[len(prefix) :].split(":")
    if (
        len(parts) != 2
        or parts[0] not in AgentRole
        or parts[1] not in {"completed_work", "prepared_history"}
    ):
        return None
    if capture and parts[0] == "job_consultant":
        return None
    return parts[0]


def collect_compactions(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """W and C are evidence; pending C does not qualify as a completed adopted window."""
    boundaries: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        thread = record["thread_id"]
        if ":prepared_history" not in thread and ":compact:" not in thread:
            continue
        values = record["values"]
        request = values.get("request_snapshot")
        if not request:
            continue
        key = (thread, str(values.get("request_id", record["checkpoint_id"])))
        if key not in boundaries:
            boundaries[key] = {
                "thread_id": thread,
                "role": record["role"],
                "request_id": values.get("request_id"),
                "request": deepcopy(request),
                "compaction": None,
                "adopted": False,
                "preparation_policy": values.get("preparation_policy"),
                "input_count": values.get("input_count"),
                "capacity_limits": values.get("capacity_limits"),
            }
        boundary = boundaries[key]
        if boundary["request"] != request:
            raise ValueError("Conflicting original windows for one compaction")
        compact = values.get("compaction_snapshot")
        if compact:
            if boundary["compaction"] not in (None, compact):
                raise ValueError("Conflicting saved compaction results")
            boundary.update(
                compaction=deepcopy(compact),
                compaction_attempt_id=values.get("compaction_attempt_id"),
                compaction_source=record["source"],
                checkpoint_id=record["checkpoint_id"],
            )
        # Only the persisted checkpoint can establish completion; never merge task writes
        # into a second task's adoption or count boundary.
        if record["source"] == "checkpoint" and values.get("adopted") is True:
            boundary.update(adopted=True, adopted_checkpoint_id=record["checkpoint_id"])
        if values.get("input_count") is not None:
            boundary["input_count"] = values["input_count"]
    return [redact(boundary) for boundary in boundaries.values()]


def collect_analysis_contexts(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose B capture observations separately; a saved template/pending write is not delivery."""
    contexts = {}
    for record in records:
        if not record["thread_id"].endswith(":context"):
            continue
        values = record["values"]
        if not values.get("request_snapshot"):
            continue
        contexts[record["thread_id"]] = {
            **{key: value for key, value in record.items() if key != "values"},
            "request": deepcopy(values["request_snapshot"]),
            "situation_changes": deepcopy(values.get("situation_changes")),
        }
    return [redact(context) for context in contexts.values()]


def collect_initial_context(records: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """保留最早捕捉觀察；準備歷史可補前綴，不代表請求已外送或工具已讀正文。"""
    captured = None
    # Native checkpoint IDs carry the saver order. Pending writes observe work after
    # their base checkpoint; callers need not supply records in that order.
    observations = sorted(
        (
            record
            for record in records
            if record["thread_id"].endswith(":job_consultant:initial_context")
        ),
        key=lambda record: (record["checkpoint_id"], record["source"] != "checkpoint"),
    )
    for record in observations:
        values = record["values"]
        binding = values.get("binding")
        request = values.get("request_snapshot")
        if not binding or not request:
            continue
        if not isinstance(binding, dict) or not isinstance(request, dict):
            raise ValueError("Invalid saved initial context")
        tool_configuration = (
            {"jd_read_max_result_characters": values["jd_read_max_result_characters"]}
            if "jd_read_max_result_characters" in values
            else None
        )
        if captured is not None:
            original_request = captured["request"]
            original_input = original_request.get("input")
            current_input = request.get("input")
            preserves_input = current_input == original_input or (
                isinstance(original_input, list)
                and bool(original_input)
                and isinstance(current_input, list)
                and current_input[-len(original_input) :] == original_input
            )
            if (
                captured["binding"] != binding
                or {key: value for key, value in original_request.items() if key != "input"}
                != {key: value for key, value in request.items() if key != "input"}
                or not preserves_input
                or captured["tool_configuration"] != tool_configuration
            ):
                raise ValueError("Conflicting saved initial contexts")
            continue
        captured = {
            **{key: value for key, value in record.items() if key != "values"},
            "binding": deepcopy(binding),
            "request": deepcopy(request),
            "tool_configuration": deepcopy(tool_configuration),
        }
    return {key: redact(value) for key, value in captured.items()} if captured else None
