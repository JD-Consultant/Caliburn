"""Classify diagnostic native threads, then delegate neutral JSON decoding."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.native_checkpoint_reads import read_native_records
from caliburn.diagnostics.projection import role_for_thread

CHANNELS = (
    "__interrupt__",
    "request_id",
    "operation_seed",
    "request_snapshot",
    "response_snapshot",
    "tool_results",
    "binding",
    "jd_read_max_result_characters",
    "reset_history",
    "input_count",
    "capacity_limits",
    "preparation_policy",
    "compaction_snapshot",
    "compaction_attempt_id",
    "response_attempt_id",
    "adopted",
    "next_action",
    "completed_steps",
    "compacted_request_id",
    "situation_changes",
    "messages",
    "call",
    "output",
    "operation_id",
)


async def read_checkpoint_records(
    session: AsyncSession, *, job_file_id: UUID, execution_id: UUID
) -> list[dict[str, Any]]:
    prefix = f"{job_file_id}:{execution_id}:"
    if await session.scalar(text("SELECT to_regclass('checkpoints')")) is None:
        return []
    ids = await session.scalars(
        text(
            "SELECT DISTINCT thread_id FROM checkpoints "
            "WHERE checkpoint_ns='' AND thread_id LIKE :prefix ORDER BY thread_id"
        ),
        {"prefix": prefix + "%"},
    )
    threads = {}
    for thread_id in ids:
        role = role_for_thread(thread_id, prefix)
        if thread_id == f"{prefix}job_consultant:initial_context":
            role = "job_consultant"
        if role is not None:
            threads[thread_id] = role
    return await read_native_records(
        session, threads=threads, channels=CHANNELS, include_subgraphs=True
    )
