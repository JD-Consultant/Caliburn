"""Read native PostgreSQL saver channels without invoking or rewriting the graph.

Any is confined to deserializing native checkpoint JSON. Only JSON inspection channels
are decoded; prepared commands and custom executable objects are deliberately excluded.
"""

from collections import defaultdict
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import psycopg
from pydantic import JsonValue, TypeAdapter, ValidationError

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.diagnostics.projection import role_for_thread

CHANNELS = (
    "request_id",
    "operation_seed",
    "request_snapshot",
    "response_snapshot",
    "tool_results",
    "binding",
    "jd_read_max_result_characters",
)
JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def read_checkpoint_records(
    connection: psycopg.Connection[Any], *, job_file_id: UUID, execution_id: UUID
) -> Iterator[dict[str, Any]]:
    prefix = f"{job_file_id}:{execution_id}:"
    threads = connection.execute(
        "SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns='' AND thread_id LIKE %s",
        (prefix + "%",),
    )
    for (thread_id,) in threads.fetchall():
        role = role_for_thread(thread_id, prefix)
        if thread_id == f"{prefix}job_consultant:initial_context":
            role = "job_consultant"
        if role is not None:
            yield from _read_thread(connection, thread_id, role)


def _read_thread(
    connection: psycopg.Connection[Any], thread_id: str, role: str
) -> Iterator[dict[str, Any]]:
    serializer = create_graph_serializer()
    decoded: dict[tuple[str, str], Any] = {}
    blobs = {
        (channel, version): (kind, bytes(blob) if blob is not None else b"")
        for channel, version, kind, blob in connection.execute(
            "SELECT channel,version,type,blob FROM checkpoint_blobs "
            "WHERE thread_id=%s AND checkpoint_ns='' AND channel=ANY(%s)",
            (thread_id, list(CHANNELS)),
        )
    }
    pending: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
    for checkpoint_id, task_id, channel, kind, blob in connection.execute(
        "SELECT checkpoint_id,task_id,channel,type,blob FROM checkpoint_writes "
        "WHERE thread_id=%s AND checkpoint_ns='' AND channel=ANY(%s) "
        "ORDER BY checkpoint_id,task_id,idx",
        (thread_id, list(CHANNELS)),
    ):
        pending[checkpoint_id][task_id][channel] = _decode(serializer, kind, bytes(blob), channel)
    for checkpoint_id, checkpoint in connection.execute(
        "SELECT checkpoint_id,checkpoint FROM checkpoints "
        "WHERE thread_id=%s AND checkpoint_ns='' ORDER BY checkpoint_id",
        (thread_id,),
    ):
        values = {
            key: value for key, value in checkpoint["channel_values"].items() if key in CHANNELS
        }
        for channel in CHANNELS:
            version = checkpoint.get("channel_versions", {}).get(channel)
            if version is None or channel in values:
                continue
            key = (channel, str(version))
            if key not in blobs:
                raise ValueError("A referenced checkpoint channel blob is missing")
            kind, blob = blobs[key]
            if kind == "empty":
                continue
            if key not in decoded:
                decoded[key] = _decode(serializer, kind, blob, channel)
            values[channel] = decoded[key]
        base = {
            "thread_id": thread_id,
            "role": role,
            "checkpoint_id": checkpoint_id,
            "checkpoint_time": checkpoint["ts"],
            "source": "checkpoint",
            "values": values,
        }
        yield base
        # Keep writes from separate tasks separate. A response pending write is paired with
        # the checkpoint's request, never a later newly assembled request.
        for update in pending[checkpoint_id].values():
            yield {**base, "source": "pending_write", "values": {**values, **update}}


def _decode(serializer: Any, kind: str, blob: bytes, channel: str) -> JsonValue:
    if channel == "operation_seed" and kind == "null" and not blob:
        return None
    if kind not in {"json", "msgpack"}:
        raise ValueError("Unsupported checkpoint encoding for diagnostic JSON")
    try:
        value = serializer.loads_typed((kind, blob))
        # logical request 使用原生 UUID channel；只在已知欄位轉成 JSON 字串。
        if channel in {"request_id", "operation_seed"} and isinstance(value, UUID):
            return str(value)
        if channel == "operation_seed" and value is None:
            return None
        if value is None:
            raise ValueError("Saved diagnostic channel is unavailable")
        return JSON_VALUE.validate_python(value)
    except (ValidationError, TypeError, ValueError) as error:
        # Keep private payloads out of CLI output; the caller rolls back the whole refresh.
        raise ValueError("Cannot decode a saved diagnostic channel") from error
