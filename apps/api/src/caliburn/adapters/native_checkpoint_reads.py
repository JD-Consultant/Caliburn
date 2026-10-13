"""Decode explicitly scoped native JSON channels in the caller's transaction.

Any is confined to this saver serialization boundary; no Graph is constructed.
"""

from collections import defaultdict
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Interrupt
from psycopg import AsyncConnection
from pydantic import JsonValue, TypeAdapter, ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.graph_checkpointer import create_graph_serializer

JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


async def read_native_records(
    session: AsyncSession,
    *,
    threads: Mapping[str, str],
    channels: tuple[str, ...],
    include_subgraphs: bool = False,
) -> list[dict[str, Any]]:
    if await session.scalar(text("SELECT to_regclass('checkpoints')")) is None:
        return []
    records = []
    for thread_id, role in threads.items():
        records.extend(await _read_thread(session, thread_id, role, channels, include_subgraphs))
    return sorted(
        records,
        key=lambda row: (
            row["checkpoint_time"],
            row["thread_id"],
            row["checkpoint_ns"],
            row["checkpoint_id"],
            row["source"] != "checkpoint",
            row.get("task_id", ""),
        ),
    )


async def _read_thread(
    session: AsyncSession,
    thread_id: str,
    role: str,
    channels: tuple[str, ...],
    include_subgraphs: bool,
) -> list[dict[str, Any]]:
    # Official alist silently omits missing referenced blobs. Preserve the selected
    # reader's fail-closed contract, while leaving inline null/empty blobs legal.
    missing = await session.scalar(
        text("""
        SELECT EXISTS (
            SELECT FROM checkpoints c
            CROSS JOIN LATERAL jsonb_each_text(c.checkpoint->'channel_versions') v
            LEFT JOIN checkpoint_blobs b ON b.thread_id=c.thread_id
              AND b.checkpoint_ns=c.checkpoint_ns AND b.channel=v.key AND b.version=v.value
            WHERE c.thread_id=:thread AND (:subgraphs OR c.checkpoint_ns='')
              AND v.key=ANY(:channels) AND v.value IS NOT NULL
              AND NOT (c.checkpoint->'channel_values' ? v.key) AND b.channel IS NULL
        )
    """),
        {"thread": thread_id, "channels": list(channels), "subgraphs": include_subgraphs},
    )
    if missing:
        raise ValueError("A referenced checkpoint channel blob is missing")
    connection = await session.connection()
    raw = await connection.get_raw_connection()
    driver = raw.driver_connection
    if not isinstance(driver, AsyncConnection):
        raise RuntimeError("Checkpoint reads require the configured psycopg driver")
    # Borrow, never close/commit/setup this caller-owned connection. The strict
    # serializer cannot construct product commands even in unselected channels.
    saver = AsyncPostgresSaver(driver, serde=create_graph_serializer())
    records = []
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    if not include_subgraphs:
        config["configurable"]["checkpoint_ns"] = ""
    async for saved in saver.alist(config):
        values = {
            key: _normalize(value, key)
            for key, value in saved.checkpoint["channel_values"].items()
            if key in channels
        }
        base = {
            "thread_id": thread_id,
            "checkpoint_ns": saved.config["configurable"]["checkpoint_ns"],
            "role": role,
            "checkpoint_id": saved.checkpoint["id"],
            "parent_checkpoint_id": (
                saved.parent_config["configurable"]["checkpoint_id"]
                if saved.parent_config is not None
                else None
            ),
            "checkpoint_time": saved.checkpoint["ts"],
            "source": "checkpoint",
            "values": values,
        }
        records.append(base)
        pending: dict[str, dict[str, JsonValue]] = defaultdict(dict)
        for task_id, channel, value in saved.pending_writes or ():
            if channel in channels:
                pending[task_id][channel] = _normalize(value, channel)
        # Each task sees only its own writes plus its checkpoint base.
        for task_id, update in pending.items():
            records.append(
                {
                    **base,
                    "source": "pending_write",
                    "task_id": task_id,
                    "values": {**values, **update},
                }
            )
    return records


def _normalize(value: Any, channel: str) -> JsonValue:
    try:
        if channel == "__interrupt__" and isinstance(value, (list, tuple)):
            value = [
                {"id": item.id, "value": item.value} if isinstance(item, Interrupt) else item
                for item in value
            ]
        if channel in {
            "request_id",
            "operation_seed",
            "compaction_attempt_id",
            "response_attempt_id",
            "compacted_request_id",
            "operation_id",
        } and isinstance(value, UUID):
            return str(value)
        if channel == "input_count" and isinstance(value, dict):
            value = {**value}
            if isinstance(value.get("attempt_id"), UUID):
                value["attempt_id"] = str(value["attempt_id"])
        if channel == "messages" and isinstance(value, list):
            value = [
                item.model_dump(mode="json") if isinstance(item, BaseMessage) else item
                for item in value
            ]
        return JSON_VALUE.validate_python(value)
    except (ValidationError, TypeError, ValueError) as error:
        raise ValueError("Cannot decode a saved diagnostic channel") from error
