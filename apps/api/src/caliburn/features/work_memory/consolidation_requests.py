"""Memory intents and stage dispositions reuse Memory's existing operation owner.

No queue or mutable progress copy: eligibility is derived with the A completion owner,
coverage from published snapshots, and candidate coordinates from memory_batches.
Caller holds the job-file lock for changes and owns the transaction.
"""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.work_memory import batch_persistence, candidate_operations
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
    if kind in {"consolidation_intent", "batch_failure"}:
        raise ValueError("Scheduling evidence requires its typed recorder")
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


async def record_intent(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    execution_id: UUID,
    command_id: UUID,
    source_id: UUID,
) -> UUID:
    """Persist the original input before A completes; same command retains its kind."""
    original = await batch_persistence.read_operation(session, job_file_id, command_id)
    if original is not None:
        if (
            original.execution_id != execution_id
            or original.kind != "consolidation_intent"
            or original.intent_source_id != source_id
        ):
            raise MemoryCommandConflictError("command_id was used for another Memory operation")
        return source_id
    session.add(
        batch_persistence.MemoryOperationRecord(
            job_file_id=job_file_id,
            execution_id=execution_id,
            command_id=command_id,
            kind="consolidation_intent",
            intent_source_id=source_id,
        )
    )
    await session.flush()
    return source_id


async def recover_failure(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    execution_id: UUID,
    command_id: UUID,
    reason: str,
) -> int | None:
    """Replay the first observation, even after the formal interview has advanced."""
    original = await batch_persistence.read_operation(session, job_file_id, command_id)
    if original is None:
        return None
    if (
        original.execution_id != execution_id
        or original.kind != "batch_failure"
        or original.failure_reason != reason
        or original.failure_frontier is None
    ):
        raise MemoryCommandConflictError("command_id was used for another Memory operation")
    return original.failure_frontier


async def record_failure(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    execution_id: UUID,
    command_id: UUID,
    reason: str,
    frontier: int,
) -> int:
    if not reason or len(reason) > 100 or type(frontier) is not int or frontier < 0:
        raise ValueError("A failure requires a short reason and nonnegative formal frontier")
    original = await recover_failure(
        session,
        job_file_id=job_file_id,
        execution_id=execution_id,
        command_id=command_id,
        reason=reason,
    )
    if original is not None:
        return original
    session.add(
        batch_persistence.MemoryOperationRecord(
            job_file_id=job_file_id,
            execution_id=execution_id,
            command_id=command_id,
            kind="batch_failure",
            failure_reason=reason,
            failure_frontier=frontier,
        )
    )
    await session.flush()
    return frontier


def intents_projection(job_file_id: UUID | None = None) -> Select[UUID, UUID, UUID, UUID | None]:
    record = batch_persistence.MemoryOperationRecord
    statement = select(
        record.job_file_id, record.execution_id, record.command_id, record.intent_source_id
    ).where(record.kind == "consolidation_intent")
    return statement.where(record.job_file_id == job_file_id) if job_file_id else statement


def failures_projection(
    job_file_id: UUID | None = None,
) -> Select[UUID, UUID, UUID, str | None, int | None]:
    record = batch_persistence.MemoryOperationRecord
    statement = select(
        record.job_file_id,
        record.execution_id,
        record.command_id,
        record.failure_reason,
        record.failure_frontier,
    ).where(record.kind == "batch_failure")
    return statement.where(record.job_file_id == job_file_id) if job_file_id else statement


def published_coverage_projection() -> Select[UUID, int]:
    return select(
        batch_persistence.MemoryHeadRecord.job_file_id,
        batch_persistence.MemorySnapshotRecord.covered_through_sequence,
    ).join(batch_persistence.MemorySnapshotRecord)


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
