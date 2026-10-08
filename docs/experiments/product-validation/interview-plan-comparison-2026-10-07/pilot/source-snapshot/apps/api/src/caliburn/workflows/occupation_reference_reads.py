"""Formal reference state bounded by the caller's existing interview read scope."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.interviews import service as interview_service
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.occupation_references import service
from caliburn.features.occupation_references.models import OccupationReferenceState
from caliburn.workflows.memory_reads import MemoryReadBinding, resolve_interview_scope


class ExcludedWorkReadWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read(self, binding: MemoryReadBinding) -> tuple[str, ...]:
        async with self.sessions() as session:
            scope = await resolve_interview_scope(session, binding)
            state = await read_formal_reference_state(session, scope)
            return state.excluded_work


async def read_formal_reference_state(
    session: AsyncSession, scope: InterviewReadScope
) -> OccupationReferenceState:
    """Read the latest completed Turn at the caller's fixed employee-input frontier."""
    latest_sequence = 0
    state = OccupationReferenceState()
    for candidate in await service.list_candidates(session, scope.job_file_id):
        execution = await executions.read_execution(
            session,
            ExecutionScope(
                scope.job_file_id, candidate.execution_id, ExecutionKind.CONSULTANT_TURN
            ),
        )
        if execution.status != ExecutionStatus.COMPLETED:
            continue
        exchange = await interview_service.read_formal_exchange(
            session, job_file_id=scope.job_file_id, execution_id=candidate.execution_id
        )
        if exchange is None:
            continue
        sequence = exchange.employee_input.interview_sequence
        # F identifies the triggering employee message; its final reply is later than F.
        if latest_sequence < sequence <= scope.through_sequence:
            latest_sequence = sequence
            state = candidate.state
    return state
