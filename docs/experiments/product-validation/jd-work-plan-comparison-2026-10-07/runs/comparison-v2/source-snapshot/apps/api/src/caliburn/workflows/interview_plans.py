"""Scope/writer checks and formal plan qualification through public typed owner interfaces."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interview_plans import service
from caliburn.features.interview_plans.models import (
    PlanEdit,
    PlanEditResult,
    PlanSnapshot,
    PlanStateError,
    QualifiedPlanTurn,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.job_files import queries as job_file_queries
from caliburn.features.job_files import service as job_files


async def read_adopted_plan(
    session: AsyncSession, scope: InterviewReadScope
) -> PlanSnapshot | None:
    """Latest plan within the fixed formal employee-input frontier; null/empty winners remain."""
    positions = await interviews.list_formal_exchange_positions(session, scope)
    completed = await executions.read_completed_consultant_execution_ids(
        session, scope.job_file_id, tuple(position.execution_id for position in positions)
    )
    qualified = tuple(
        QualifiedPlanTurn(position.execution_id, position.employee_input_sequence)
        for position in positions
        if position.execution_id in completed
    )
    return await service.read_qualified_plan(session, scope.job_file_id, qualified)


async def start_interview_plan(
    session: AsyncSession, writer: ExecutionWriter, scope: InterviewReadScope
) -> PlanSnapshot:
    """Join initial context capture's transaction; never refresh a previously saved start."""
    _require_consultant(writer.scope)
    if scope.job_file_id != writer.scope.job_file_id:
        raise PlanStateError("The fixed plan frontier belongs to another job file")
    await job_files.lock_job_file(session, writer.scope.job_file_id)
    await executions.lock_active_writer(session, writer)
    existing = await service.read_base(session, scope.job_file_id, writer.scope.execution_id)
    if existing is not None:
        return existing
    base = await read_adopted_plan(session, scope)
    return await service.start_candidate(
        session,
        scope.job_file_id,
        writer.scope.execution_id,
        base.body if base is not None else None,
    )


class InterviewPlanWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_current(self, scope: ExecutionScope) -> PlanSnapshot | None:
        """Read a known Turn's retained head, including terminal recovery and UI preview."""
        _require_consultant(scope)
        async with self.sessions() as session:
            await executions.read_execution(session, scope)
            return await service.read_current(session, scope.job_file_id, scope.execution_id)

    async def read_active(self, writer: ExecutionWriter) -> PlanSnapshot | None:
        """Read for a live capture; the active-writer fence is established in this boundary."""
        _require_consultant(writer.scope)
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            return await service.read_current(
                session, writer.scope.job_file_id, writer.scope.execution_id
            )

    async def apply(self, writer: ExecutionWriter, edit: PlanEdit) -> PlanEditResult:
        _require_consultant(writer.scope)
        if (edit.position.job_file_id, edit.position.execution_id) != (
            writer.scope.job_file_id,
            writer.scope.execution_id,
        ):
            raise PlanStateError("The prepared plan edit belongs to another Turn")
        async with self.sessions.begin() as session:
            await job_files.lock_job_file(session, writer.scope.job_file_id)
            original = await executions.read_execution(session, writer.scope)
            if original.status == ExecutionStatus.COMPLETED:
                await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
                recovered = await service.recover_prepared(session, edit)
                if recovered is None:
                    raise ExecutionStateError(
                        "A completed Turn cannot produce a new plan operation"
                    )
                return recovered
            await executions.lock_active_writer(session, writer)
            return await service.apply_prepared(session, edit)


class InterviewPlanReadWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_adopted(self, job_file_id: UUID) -> PlanSnapshot | None:
        """File UI reads use the current formal frontier rather than a model's captured frontier."""
        async with self.sessions() as session:
            await job_file_queries.read_job_file(session, job_file_id)
            frontier = await interviews.read_history_frontier(session, job_file_id)
            return await read_adopted_plan(session, InterviewReadScope(job_file_id, frontier))


def _require_consultant(scope: ExecutionScope) -> None:
    if scope.kind != ExecutionKind.CONSULTANT_TURN:
        raise ExecutionStateError("Only consultant Turns use interview plans")
