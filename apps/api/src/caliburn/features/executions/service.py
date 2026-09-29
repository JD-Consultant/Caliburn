"""Durable eligibility checks participate in the caller's short business transaction."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import persistence
from caliburn.features.executions.models import (
    ExecutionBusyError,
    ExecutionInfo,
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
    StaleWriterError,
)


def _project(record: persistence.ExecutionRecord, scope: ExecutionScope) -> ExecutionInfo:
    return ExecutionInfo(scope, ExecutionStatus(record.status), record.writer_id)


async def admit_execution(session: AsyncSession, scope: ExecutionScope) -> ExecutionInfo:
    """Unique active scope in the DB; replay an existing identity without reactivating it."""
    record = await persistence.insert_execution(session, scope)
    if record is None:
        record = await persistence.read_execution(session, scope)
        if record is None:
            raise ExecutionBusyError("The execution could not be admitted")
    return _project(record, scope)


async def read_execution(session: AsyncSession, scope: ExecutionScope) -> ExecutionInfo:
    record = await persistence.read_execution(session, scope)
    if record is None:
        raise ExecutionNotFoundError("Execution not found in the requested scope")
    return _project(record, scope)


async def claim_writer(
    session: AsyncSession,
    scope: ExecutionScope,
    *,
    writer_id: UUID,
    replaces_writer_id: UUID | None = None,
) -> ExecutionWriter:
    """CAS writer identity; replacement requires a supervisor's explicit recovery decision.

    This is fencing, not liveness detection or an automatic lease/timeout policy. The caller
    must retain the proposed writer_id across an uncertain commit. Never expose it to a model.
    """
    record = await _lock_execution(session, scope)
    if record.status != ExecutionStatus.ACTIVE:
        raise ExecutionStateError("Only an active execution can acquire a writer")
    if record.writer_id not in (replaces_writer_id, writer_id):
        raise StaleWriterError("The writer has already changed")
    record.writer_id = writer_id
    await session.flush()
    return ExecutionWriter(scope, writer_id)


async def lock_active_writer(session: AsyncSession, writer: ExecutionWriter) -> None:
    """Hold eligibility through the SAME transaction as the dependent business effect."""
    record = await _lock_writer(session, writer)
    if record.status != ExecutionStatus.ACTIVE:
        raise ExecutionStateError("The execution is no longer active")


async def lock_unfinished_writer(session: AsyncSession, writer: ExecutionWriter) -> None:
    """Control operations may discard a paused Turn; ordinary effects require active."""
    record = await _lock_writer(session, writer)
    if record.status not in (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED):
        raise ExecutionStateError("The execution has already finished")


async def pause_execution(session: AsyncSession, writer: ExecutionWriter) -> None:
    """Called after reaching a safe boundary, not on receipt of a UI pause request."""
    record = await _lock_writer(session, writer)
    if writer.scope.kind != ExecutionKind.CONSULTANT_TURN or record.status not in (
        ExecutionStatus.ACTIVE,
        ExecutionStatus.PAUSED,
    ):
        raise ExecutionStateError("This execution cannot pause")
    record.status = ExecutionStatus.PAUSED.value
    await session.flush()


async def resume_execution(session: AsyncSession, writer: ExecutionWriter) -> None:
    record = await _lock_writer(session, writer)
    if writer.scope.kind != ExecutionKind.CONSULTANT_TURN or record.status not in (
        ExecutionStatus.ACTIVE,
        ExecutionStatus.PAUSED,
    ):
        raise ExecutionStateError("This execution cannot resume")
    record.status = ExecutionStatus.ACTIVE.value
    await session.flush()


async def finish_execution(
    session: AsyncSession, writer: ExecutionWriter, outcome: ExecutionStatus
) -> None:
    """Only eligibility; completion/cancel workflows must commit all their effects together."""
    if outcome not in (
        ExecutionStatus.COMPLETED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.FAILED,
    ):
        raise ValueError("Expected a terminal outcome")
    if writer.scope.kind == ExecutionKind.MEMORY_BATCH and outcome == ExecutionStatus.CANCELLED:
        raise ExecutionStateError("Memory batches cannot be cancelled")
    record = await _lock_writer(session, writer)
    if record.status == outcome:
        return
    allowed = (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED)
    if record.status not in allowed or (
        record.status == ExecutionStatus.PAUSED and outcome == ExecutionStatus.COMPLETED
    ):
        raise ExecutionStateError("The requested terminal outcome cannot replace the current state")
    record.status = outcome.value
    await session.flush()


async def require_manual_edit_allowed(session: AsyncSession, job_file_id: UUID) -> None:
    """Caller first locks the job-file row, sharing the order used by A admission."""
    if await persistence.has_active_consultant(session, job_file_id):
        raise ExecutionBusyError("Manual edits are disabled while a consultant turn is active")


async def _lock_execution(
    session: AsyncSession, scope: ExecutionScope
) -> persistence.ExecutionRecord:
    record = await persistence.read_execution(session, scope, lock=True)
    if record is None:
        raise ExecutionNotFoundError("Execution not found in the requested scope")
    return record


async def _lock_writer(
    session: AsyncSession, writer: ExecutionWriter
) -> persistence.ExecutionRecord:
    record = await _lock_execution(session, writer.scope)
    if record.writer_id != writer.writer_id:
        raise StaleWriterError("The worker no longer owns this execution")
    return record
