"""Read-only background admission projections owned by executions, not Memory SQL joins."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions.models import (
    ExecutionInfo,
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
)
from caliburn.features.executions.persistence import ExecutionRecord


async def list_active_memory(session: AsyncSession) -> tuple[ExecutionInfo, ...]:
    records = await session.scalars(
        select(ExecutionRecord)
        .where(
            ExecutionRecord.kind == ExecutionKind.MEMORY_BATCH,
            ExecutionRecord.status == ExecutionStatus.ACTIVE,
        )
        .order_by(ExecutionRecord.created_at, ExecutionRecord.execution_id)
    )
    return tuple(
        ExecutionInfo(
            ExecutionScope(row.job_file_id, row.execution_id, ExecutionKind.MEMORY_BATCH),
            ExecutionStatus(row.status),
            row.writer_id,
        )
        for row in records
    )


async def read_active_memory(session: AsyncSession, job_file_id: UUID) -> ExecutionInfo | None:
    record = await session.scalar(
        select(ExecutionRecord).where(
            ExecutionRecord.kind == ExecutionKind.MEMORY_BATCH,
            ExecutionRecord.status == ExecutionStatus.ACTIVE,
            ExecutionRecord.job_file_id == job_file_id,
        )
    )
    if record is None:
        return None
    return ExecutionInfo(
        ExecutionScope(job_file_id, record.execution_id, ExecutionKind.MEMORY_BATCH),
        ExecutionStatus.ACTIVE,
        record.writer_id,
    )
