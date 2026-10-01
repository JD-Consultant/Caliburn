"""Memory intents and stage dispositions reuse Memory's existing operation owner.

No queue or mutable progress copy: eligibility is derived with the A completion owner,
coverage from published snapshots, and candidate coordinates from memory_batches.
Caller holds the job-file lock for changes and owns the transaction.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.interviews import queries as interviews
from caliburn.features.work_memory import batch_persistence, candidate_operations
from caliburn.features.work_memory.batch_models import MemoryConsolidationIntent
from caliburn.features.work_memory.candidates import MemoryCommandConflictError

# A final failure blocks new batches until the interview has advanced this far past the
# frontier recorded with it: three completed exchanges, each an employee input and a reply.
# Only interview progress releases it; a new request or the passage of time does not.
RETRY_AFTER_NEW_MESSAGES = 6


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
    """The reason of a final failure still in force, or None when a new batch may start."""
    records = await session.scalars(
        select(batch_persistence.MemoryOperationRecord).where(
            batch_persistence.MemoryOperationRecord.job_file_id == job_file_id,
            batch_persistence.MemoryOperationRecord.kind == "batch_failure",
        )
    )
    for row in records:
        failure = _payload(row.result_payload)
        if not await _interview_advanced(session, job_file_id, failure):
            return candidate_operations.stored_text(failure, "reason")
    return None


async def _interview_advanced(
    session: AsyncSession, job_file_id: UUID, failure: dict[str, object]
) -> bool:
    recorded = failure.get("formal_frontier")
    if type(recorded) is not int:
        return False  # An older failure recorded no frontier and never releases by itself.
    frontier = await interviews.read_history_frontier(session, job_file_id)
    return frontier - recorded >= RETRY_AFTER_NEW_MESSAGES


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
