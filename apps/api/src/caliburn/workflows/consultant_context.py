"""Pin a consultant's initial product data; the role owns native capture and model format."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionStateError, ExecutionWriter
from caliburn.features.interview_plans import service as plans
from caliburn.features.interview_plans.models import PlanSnapshot
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import (
    InterviewReadScope,
    RecentInterviews,
    StoredInterviewInput,
)
from caliburn.features.job_description import candidate_service
from caliburn.features.job_description.candidates import JdCandidatePosition
from caliburn.features.job_files import service as job_files
from caliburn.features.work_memory import candidate_queries as memory
from caliburn.features.work_memory import read_queries
from caliburn.features.work_memory.models import MemoryMapEntry
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.interview_plans import start_interview_plan
from caliburn.workflows.memory_consolidation_queries import read_failure_reason


@dataclass(frozen=True, slots=True)
class ConsultantContextData:
    snapshot_id: UUID | None
    interview_scope: InterviewReadScope
    covered_through_sequence: int
    current_input: StoredInterviewInput
    candidate_position: JdCandidatePosition
    situation_map: tuple[MemoryMapEntry, ...]
    understanding_map: tuple[MemoryMapEntry, ...]
    recent: RecentInterviews
    memory_failure_reason: str | None
    plan: PlanSnapshot | None


class ConsultantContextWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def require_uncaptured_start(self, writer: ExecutionWriter) -> None:
        """Only before the role creates its first native context checkpoint."""
        scope = writer.scope
        async with self._sessions() as session:
            prepared = await history.read_context_history(session, scope, AgentRole.JOB_CONSULTANT)
            if prepared is None or prepared.prepared is None:
                raise ValueError("Adopt role history preparation before capturing new Turn data")
            prior_plan = await plans.read_base(session, scope.job_file_id, scope.execution_id)
            if prior_plan is not None:
                raise ExecutionStateError(
                    "The Turn's plan start exists without a recoverable initial context"
                )

    async def capture(
        self, writer: ExecutionWriter, *, plan_enabled: bool
    ) -> ConsultantContextData:
        """Bind fixed reads and candidate starts under the same job-file/writer transaction."""
        scope = writer.scope
        async with self._sessions.begin() as session:
            await job_files.lock_job_file(session, scope.job_file_id)
            await executions.lock_active_writer(session, writer)
            snapshot = await memory.read_latest_snapshot(session, scope.job_file_id)
            snapshot_id = snapshot.snapshot_id if snapshot is not None else None
            frontier = await interviews.read_history_frontier(session, scope.job_file_id)
            original = await interviews.read_execution_input(
                session, job_file_id=scope.job_file_id, execution_id=scope.execution_id
            )
            position = await candidate_service.start_candidate(
                session, scope.job_file_id, scope.execution_id
            )
            maps = {}
            for layer in MemoryLayer:
                view = await read_queries.bind_published_view(
                    session, scope.job_file_id, snapshot_id, layer
                )
                maps[layer] = await read_queries.read_map(session, view)
            covered = snapshot.covered_through_sequence if snapshot is not None else 0
            interview_scope = InterviewReadScope(scope.job_file_id, frontier)
            recent = await interviews.read_recent_interviews(
                session, interview_scope, covered_through_sequence=covered
            )
            memory_failure = await read_failure_reason(session, scope.job_file_id)
            plan = (
                await start_interview_plan(session, writer, interview_scope)
                if plan_enabled
                else None
            )
        return ConsultantContextData(
            snapshot_id=snapshot_id,
            interview_scope=interview_scope,
            covered_through_sequence=covered,
            current_input=original,
            candidate_position=position,
            situation_map=maps[MemoryLayer.WORK_SITUATION],
            understanding_map=maps[MemoryLayer.WORK_UNDERSTANDING],
            recent=recent,
            memory_failure_reason=memory_failure,
            plan=plan,
        )
