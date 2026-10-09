"""Formal reference state bounded by the caller's existing interview read scope."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import queries as executions
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.occupation_references import queries as references
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
    formal = interviews.formal_exchange_positions_projection(scope).subquery(
        "formal_reference_turns"
    )
    completed = executions.completed_consultant_executions_projection(scope.job_file_id).subquery(
        "completed_reference_turns"
    )
    heads = references.candidate_heads_projection(scope.job_file_id).subquery("reference_heads")
    row = (
        await session.execute(
            select(heads.c.execution_id, heads.c.generation_id, heads.c.current_revision_id)
            .select_from(formal)
            .join(completed, completed.c.execution_id == formal.c.execution_id)
            .join(heads, heads.c.execution_id == formal.c.execution_id)
            .order_by(formal.c.employee_input_sequence.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return OccupationReferenceState()
    return await references.read_head_state(session, scope.job_file_id, *row)
