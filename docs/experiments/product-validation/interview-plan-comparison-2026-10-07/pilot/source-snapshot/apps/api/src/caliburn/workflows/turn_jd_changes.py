"""Public completed-Turn JD comparison, without a new history store or write effect."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.features.job_description.change_queries import (
    JdChangeSnapshot,
    read_adopted_turn_changes,
)


class TurnJdChangesWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read(
        self, job_file_id: UUID, execution_id: UUID
    ) -> tuple[JdChangeSnapshot, JdChangeSnapshot]:
        scope = ExecutionScope(job_file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        async with self.sessions() as session:
            execution = await executions.read_execution(session, scope)
            if execution.status != ExecutionStatus.COMPLETED:
                raise ExecutionStateError("Only completed Turns expose formal JD changes")
            return await read_adopted_turn_changes(session, job_file_id, execution_id)
