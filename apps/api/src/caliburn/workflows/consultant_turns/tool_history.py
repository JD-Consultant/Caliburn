"""Scope public tool evidence to one completed consultant Turn, without new storage."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import consistent_read_session
from caliburn.agent_execution.tool_observations import ToolObservation, read_tool_observations
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)


class TurnToolsWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read(self, job_file_id: UUID, execution_id: UUID) -> tuple[ToolObservation, ...]:
        scope = ExecutionScope(job_file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        async with consistent_read_session(self.sessions) as session:
            execution = await executions.read_execution(session, scope)
            if execution.status != ExecutionStatus.COMPLETED:
                raise ExecutionStateError("Only completed Turns expose public tool observations")
            thread_id = context_thread_id(
                scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.COMPLETED_WORK
            )
            return await read_tool_observations(session, thread_id=thread_id)
