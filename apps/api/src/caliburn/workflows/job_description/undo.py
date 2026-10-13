"""JD-only completed-Turn undo; no interview, Memory or execution-history rollback."""

from uuid import UUID

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.features.job_description import undo_service
from caliburn.features.job_description.models import JdProfileRevision
from caliburn.features.job_files import service as job_files


class JdUndoUnconfirmedError(RuntimeError):
    """The caller must retry the same Turn's undo, not choose a different baseline."""


class JdUndoWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def undo(self, job_file_id: UUID, execution_id: UUID) -> JdProfileRevision:
        """Replay an original undo or reverse JD only while its adopted base still holds."""
        scope = ExecutionScope(job_file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        try:
            async with self.sessions.begin() as session:
                await job_files.lock_job_file(session, job_file_id)
                execution = await executions.read_execution(session, scope)
                if execution.status != ExecutionStatus.COMPLETED:
                    raise ExecutionStateError("Only completed consultant Turns can undo their JD")
                original = await undo_service.recover_undo(session, job_file_id, execution_id)
                if original is not None:
                    return original
                await executions.require_manual_edit_allowed(session, job_file_id)
                return await undo_service.undo_completed_turn(session, job_file_id, execution_id)
        except OperationalError as error:
            raise JdUndoUnconfirmedError("Retry this Turn's original undo to confirm") from error
