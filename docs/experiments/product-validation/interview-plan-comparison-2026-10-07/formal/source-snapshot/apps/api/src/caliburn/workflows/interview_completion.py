"""Interview participant of the future atomic A completion, not a standalone finish API."""

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews import service as interviews
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.features.job_files import service as job_files


async def record_formal_interview(
    session: AsyncSession, writer: ExecutionWriter, *, reply_text: str
) -> FormalInterviewExchange:
    """Join the caller's completion transaction; never commit or finish the entire Turn.

    T08 must adopt JD, current-input citations and background intent in that transaction.
    Replaying an already completed exchange reads its original result without new effects.
    """
    if writer.scope.kind != ExecutionKind.CONSULTANT_TURN:
        raise ExecutionStateError("Only a consultant turn can produce a formal exchange")
    await job_files.lock_job_file(session, writer.scope.job_file_id)
    original = await interviews.read_formal_exchange(
        session,
        job_file_id=writer.scope.job_file_id,
        execution_id=writer.scope.execution_id,
    )
    if original is not None:
        interviews.require_same_reply(original, reply_text)
        execution = await executions.read_execution(session, writer.scope)
        if execution.status == ExecutionStatus.COMPLETED:
            return original
    await executions.lock_active_writer(session, writer)
    return await interviews.formalize_exchange(
        session,
        job_file_id=writer.scope.job_file_id,
        execution_id=writer.scope.execution_id,
        reply_text=reply_text,
    )
