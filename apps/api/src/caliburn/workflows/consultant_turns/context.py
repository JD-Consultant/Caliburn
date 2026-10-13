"""Pin a consultant's initial product data; the role owns native capture and model format."""

from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import retry_database_operation
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
from caliburn.features.job_description.change_comparison import JdNetChanges, compare_jd_snapshots
from caliburn.features.job_description.change_queries import read_manual_change_endpoints
from caliburn.features.job_files import service as job_files
from caliburn.features.work_memory import candidate_queries as memory
from caliburn.features.work_memory import read_queries
from caliburn.features.work_memory.models import MemoryMapEntry
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.interview_plans import start_interview_plan
from caliburn.workflows.job_description.reads import JdSourceReading, read_jd_source_readings
from caliburn.workflows.work_memory.consolidation_queries import read_failure_reason
from caliburn.workflows.work_memory.reads import PublishedMemoryRead


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
    jd: candidate_service.JdCandidatePreview | None
    reset_history: bool
    jd_sources: tuple[JdSourceReading, ...]
    manual_changes: JdNetChanges | None
    manual_sources: tuple[JdSourceReading, ...]


class ConsultantContextWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    @retry_database_operation
    async def require_uncaptured_start(self, writer: ExecutionWriter) -> None:
        """Only before the role creates its first native context checkpoint."""
        scope = writer.scope
        async with self.sessions.begin() as session:
            await history.bind_context_history(session, writer, AgentRole.JOB_CONSULTANT)
            prior_plan = await plans.read_base(session, scope.job_file_id, scope.execution_id)
            if prior_plan is not None:
                raise ExecutionStateError(
                    "The Turn's plan start exists without a recoverable initial context"
                )

    async def capture(
        self,
        writer: ExecutionWriter,
        *,
        plan_enabled: bool,
        previous_memory: PublishedMemoryRead | None = None,
    ) -> ConsultantContextData:
        """Bind fixed reads and candidate starts under the same job-file/writer transaction."""
        scope = writer.scope
        captured: ConsultantContextData | None = None

        @retry_database_operation
        async def capture_original() -> ConsultantContextData:
            nonlocal captured
            async with self.sessions.begin() as session:
                await job_files.lock_job_file(session, scope.job_file_id)
                await executions.lock_active_writer(session, writer)
                if captured is not None:
                    position = await candidate_service.start_candidate(
                        session, scope.job_file_id, scope.execution_id
                    )
                    plan = (
                        await start_interview_plan(session, writer, captured.interview_scope)
                        if plan_enabled
                        else None
                    )
                    captured = replace(captured, candidate_position=position, plan=plan)
                    return captured
                snapshot = await memory.read_latest_snapshot(session, scope.job_file_id)
                snapshot_id = snapshot.snapshot_id if snapshot is not None else None
                reset_history = (
                    previous_memory is None or previous_memory.snapshot_id != snapshot_id
                )
                frontier = await interviews.read_history_frontier(session, scope.job_file_id)
                original = await interviews.read_execution_input(
                    session, job_file_id=scope.job_file_id, execution_id=scope.execution_id
                )
                position = await candidate_service.start_candidate(
                    session, scope.job_file_id, scope.execution_id
                )
                previous = await history.read_previous_completed_execution(
                    session, scope, AgentRole.JOB_CONSULTANT
                )
                before, after = await read_manual_change_endpoints(
                    session,
                    scope.job_file_id,
                    scope.execution_id,
                    start_revision_id=position.base_revision_id,
                    previous_completed_execution_id=previous.execution_id if previous else None,
                )
                net = compare_jd_snapshots(before, after)
                manual_changes = (
                    net if net.profile_fields or net.item_refs or net.citation_ids else None
                )
                maps: dict[MemoryLayer, tuple[MemoryMapEntry, ...]] = {}
                if reset_history:
                    for layer in MemoryLayer:
                        view = await read_queries.bind_published_view(
                            session, scope.job_file_id, snapshot_id, layer
                        )
                        maps[layer] = await read_queries.read_map(session, view)
                covered = snapshot.covered_through_sequence if snapshot is not None else 0
                interview_scope = InterviewReadScope(scope.job_file_id, frontier)
                recent = RecentInterviews(
                    tuple(
                        await interviews.read_interview_range(
                            session,
                            interview_scope,
                            start_sequence=covered + 1,
                            end_sequence=frontier,
                        )
                    )
                    if reset_history and covered < frontier
                    else (),
                    (),
                )
                memory_failure = (
                    await read_failure_reason(session, scope.job_file_id) if reset_history else None
                )
                plan = (
                    await start_interview_plan(session, writer, interview_scope)
                    if plan_enabled
                    else None
                )
                jd = (
                    await candidate_service.read_preview(
                        session, scope.job_file_id, scope.execution_id
                    )
                    if reset_history
                    else None
                )
                jd_sources = (
                    await read_jd_source_readings(
                        session,
                        job_file_id=scope.job_file_id,
                        revision_id=jd.position.revision_id,
                        snapshot_id=snapshot_id,
                        interview_through_sequence=frontier,
                        current_input_source_id=original.source_id,
                    )
                    if jd is not None
                    else ()
                )
                manual_sources: tuple[JdSourceReading, ...] = ()
                if net.citation_ids:
                    for endpoint in (before, after):
                        targets = tuple(
                            dict.fromkeys(
                                ref.target
                                for ref in endpoint.sources
                                if ref.citation_id in net.citation_ids
                            )
                        )
                        if not targets:
                            continue
                        readings = (
                            tuple(item for item in jd_sources if item.reference.target in targets)
                            if endpoint is after and jd is not None
                            else await read_jd_source_readings(
                                session,
                                job_file_id=scope.job_file_id,
                                revision_id=endpoint.work.revision_id,
                                snapshot_id=snapshot_id,
                                interview_through_sequence=frontier,
                                current_input_source_id=original.source_id,
                                targets=targets,
                            )
                        )
                        manual_sources += tuple(
                            item
                            for item in readings
                            if item.reference.citation_id in net.citation_ids
                        )
                captured = ConsultantContextData(
                    snapshot_id=snapshot_id,
                    interview_scope=interview_scope,
                    covered_through_sequence=covered,
                    current_input=original,
                    candidate_position=position,
                    situation_map=maps.get(MemoryLayer.WORK_SITUATION, ()),
                    understanding_map=maps.get(MemoryLayer.WORK_UNDERSTANDING, ()),
                    recent=recent,
                    memory_failure_reason=memory_failure,
                    plan=plan,
                    jd=jd,
                    reset_history=reset_history,
                    jd_sources=jd_sources,
                    manual_changes=manual_changes,
                    manual_sources=manual_sources,
                )
            return captured

        return await capture_original()
