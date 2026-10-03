"""Public consultant status assembled from existing owners, without granting source rights."""

from dataclasses import dataclass, replace
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.reasoning_summaries import PublicReasoningSummary
from caliburn.agent_execution.public_messages import (
    PublicCommentary,
    read_public_commentary,
    read_public_reasoning_summaries,
)
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionInfo,
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews import service as interview_service
from caliburn.features.interviews.models import InterviewInputNotFoundError
from caliburn.features.job_description import candidate_service
from caliburn.features.job_description.candidate_service import JdCandidatePreview
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.features.job_files import queries as job_files


@dataclass(frozen=True, slots=True)
class ConsultantTurnStatus:
    job_file_id: UUID
    execution_id: UUID
    status: ExecutionStatus
    input_text: str
    candidate: JdCandidatePreview | None = None
    commentary: tuple[PublicCommentary, ...] | None = None
    pause_requested: bool = False


class ConsultantTurnUnavailableError(RuntimeError):
    """Stored completion cannot currently be reconciled with its formal result."""


class ConsultantStatusWorkflow:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        checkpointer: BaseCheckpointSaver[str] | None = None,
    ) -> None:
        self.sessions = sessions
        self.checkpointer = checkpointer

    async def read(self, job_file_id: UUID, execution_id: UUID) -> ConsultantTurnStatus:
        async with self.sessions.begin() as session:
            scope = ExecutionScope(job_file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
            status = await _read_status(session, await executions.read_execution(session, scope))
        return await self._with_commentary(status)

    async def read_current(self, job_file_id: UUID) -> ConsultantTurnStatus | None:
        """Discover the admitted nonterminal Turn without claiming or resuming execution."""
        async with self.sessions.begin() as session:
            await job_files.read_job_file(session, job_file_id)
            execution = await executions.read_current_consultant(session, job_file_id)
            if execution is None:
                return None
            status = await _read_status(session, execution)
        return await self._with_commentary(status)

    async def read_reasoning_summaries(
        self, job_file_id: UUID, execution_id: UUID
    ) -> tuple[PublicReasoningSummary, ...]:
        scope = ExecutionScope(job_file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        async with self.sessions.begin() as session:
            await executions.read_execution(session, scope)
            await interviews.read_execution_input(
                session, job_file_id=job_file_id, execution_id=execution_id
            )
        if self.checkpointer is None:
            raise ConsultantTurnUnavailableError("Saved public history is unavailable")
        return await read_public_reasoning_summaries(
            self.checkpointer,
            thread_id=context_thread_id(
                scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.COMPLETED_WORK
            ),
        )

    async def read_by_command(self, job_file_id: UUID, command_id: UUID) -> ConsultantTurnStatus:
        async with self.sessions.begin() as session:
            accepted = await interviews.read_accepted_input(
                session, job_file_id=job_file_id, command_id=command_id
            )
            if accepted is None:
                raise InterviewInputNotFoundError("No accepted command exists in this job file")
            scope = ExecutionScope(
                job_file_id, accepted.execution_id, ExecutionKind.CONSULTANT_TURN
            )
            status = await _read_status(session, await executions.read_execution(session, scope))
        return await self._with_commentary(status)

    async def _with_commentary(self, status: ConsultantTurnStatus) -> ConsultantTurnStatus:
        if self.checkpointer is None:
            return status
        scope = ExecutionScope(
            status.job_file_id, status.execution_id, ExecutionKind.CONSULTANT_TURN
        )
        messages = await read_public_commentary(
            self.checkpointer,
            thread_id=context_thread_id(
                scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.COMPLETED_WORK
            ),
        )
        return replace(status, commentary=messages)


async def _read_status(session: AsyncSession, execution: ExecutionInfo) -> ConsultantTurnStatus:
    job_file_id, execution_id = execution.scope.job_file_id, execution.scope.execution_id
    original = await interviews.read_execution_input(
        session, job_file_id=job_file_id, execution_id=execution_id
    )
    if execution.status == ExecutionStatus.COMPLETED:
        exchange = await interview_service.read_formal_exchange(
            session, job_file_id=job_file_id, execution_id=execution_id
        )
        if exchange is None:
            raise ConsultantTurnUnavailableError("Formal completion is unavailable")
    candidate = None
    if execution.status in (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED):
        try:
            candidate = await candidate_service.read_preview(session, job_file_id, execution_id)
        except CandidateStateError:
            # Admission precedes initialization; cancellation may also close the draft
            # after the status read. Neither grants a preview or invents empty JD content.
            pass
    return ConsultantTurnStatus(
        job_file_id,
        execution_id,
        execution.status,
        original.interview_text,
        candidate,
        pause_requested=execution.pause_requested,
    )
