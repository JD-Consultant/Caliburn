"""Memory intents and stage dispositions reuse Memory's existing operation owner.

No queue or mutable progress copy: eligibility is derived with the A completion owner,
coverage from published snapshots, and candidate coordinates from memory_batches.
Caller holds the job-file lock for changes and owns the transaction.
"""

from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import batch_persistence, candidate_operations
from caliburn.features.work_memory.batch_models import MemoryConsolidationIntent
from caliburn.features.work_memory.candidates import MemoryCommandConflictError


async def record_operation(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    execution_id: UUID,
    command_id: UUID,
    kind: str,
    payload: dict[str, object],
    result: dict[str, object],
) -> dict[str, object]:
    original = await candidate_operations.recover(
        session, job_file_id, execution_id, command_id, kind, payload
    )
    if original is not None:
        return original
    session.add(
        batch_persistence.MemoryOperationRecord(
            job_file_id=job_file_id,
            execution_id=execution_id,
            command_id=command_id,
            kind=kind,
            request_payload=payload,
            result_payload=result,
        )
    )
    await session.flush()
    return result


async def list_intents(
    session: AsyncSession, job_file_id: UUID | None = None
) -> tuple[MemoryConsolidationIntent, ...]:
    statement = select(batch_persistence.MemoryOperationRecord).where(
        batch_persistence.MemoryOperationRecord.kind == "consolidation_intent"
    )
    if job_file_id is not None:
        statement = statement.where(
            batch_persistence.MemoryOperationRecord.job_file_id == job_file_id
        )
    records = await session.scalars(statement)
    return tuple(
        MemoryConsolidationIntent(
            row.job_file_id,
            row.execution_id,
            candidate_operations.stored_uuid(_payload(row.result_payload), "source_id"),
        )
        for row in records
    )


async def read_block(session: AsyncSession, job_file_id: UUID) -> str | None:
    records = await session.scalars(
        select(batch_persistence.MemoryOperationRecord).where(
            batch_persistence.MemoryOperationRecord.job_file_id == job_file_id,
            batch_persistence.MemoryOperationRecord.kind == "batch_failure",
        )
    )
    for row in records:
        released = await batch_persistence.read_operation(
            session, job_file_id, uuid5(row.execution_id, "memory.release_block")
        )
        if released is None:
            return candidate_operations.stored_text(_payload(row.result_payload), "reason")
    return None


async def list_stage_results(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> tuple[dict[str, object], ...]:
    records = await session.scalars(
        select(batch_persistence.MemoryOperationRecord).where(
            batch_persistence.MemoryOperationRecord.job_file_id == job_file_id,
            batch_persistence.MemoryOperationRecord.execution_id == execution_id,
            batch_persistence.MemoryOperationRecord.kind == "stage_completion",
        )
    )
    return tuple(_payload(row.result_payload) for row in records)


async def read_batch_result(
    session: AsyncSession, job_file_id: UUID, execution_id: UUID
) -> batch_persistence.MemorySnapshotRecord | None:
    return await session.scalar(
        select(batch_persistence.MemorySnapshotRecord).where(
            batch_persistence.MemorySnapshotRecord.job_file_id == job_file_id,
            batch_persistence.MemorySnapshotRecord.execution_id == execution_id,
        )
    )


def _payload(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MemoryCommandConflictError("Invalid saved Memory disposition")
    return {key: item for key, item in value.items()}
