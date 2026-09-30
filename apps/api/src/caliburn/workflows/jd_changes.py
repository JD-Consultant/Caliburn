"""Read-only JD comparisons, using fixed original evidence and the Turn's pinned view."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionKind, ExecutionStateError, ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.job_description import candidate_service, change_queries, source_persistence
from caliburn.features.job_description.change_queries import JdChangeSnapshot, ManualJdRange
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.navigation import resolve_jd_read_ref
from caliburn.features.job_description.sources import InterviewSource, JdSourceReference
from caliburn.features.job_description.work_queries import read_work_at
from caliburn.features.work_memory import candidate_queries as memory
from caliburn.features.work_memory.candidates import MemoryPermissionError
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryObjectRevision,
    MemoryRevisionNotFoundError,
)
from caliburn.workflows.jd_reads import resolve_jd_citation_ref
from caliburn.workflows.memory_reads import PublishedMemoryRead


class ManualJdArea(StrEnum):
    PROFILE = "profile"
    RESPONSIBILITY_AREAS = "responsibility_areas"
    UNASSIGNED_WORK_TASKS = "unassigned_work_tasks"
    REQUIRED_KNOWLEDGE = "required_knowledge"
    REQUIRED_SKILLS = "required_skills"
    MAIN_COLLABORATORS = "main_collaborators"
    JOB_WIDE_CONDITIONS = "job_wide_conditions"


@dataclass(frozen=True, slots=True)
class AllManualChanges:
    pass


@dataclass(frozen=True, slots=True)
class AreaManualChanges:
    view: ManualJdArea


@dataclass(frozen=True, slots=True)
class ItemManualChanges:
    read_ref: str


@dataclass(frozen=True, slots=True)
class ProfileManualChanges:
    field: ProfileField


type ManualChangeScope = (
    AllManualChanges | AreaManualChanges | ItemManualChanges | ProfileManualChanges
)


@dataclass(frozen=True, slots=True)
class ManualChangeQuery:
    scope: ManualChangeScope


@dataclass(frozen=True, slots=True)
class SourceChangeQuery:
    citation_ref: str


type JdChangeQuery = ManualChangeQuery | SourceChangeQuery


class UnsupportedJdSourceKindError(ValueError):
    """The safe message points back to current input or an authorized formal sequence."""


@dataclass(frozen=True, slots=True)
class MemorySourceChange:
    before: MemoryObjectRevision | None
    after: MemoryObjectRevision | None
    before_interviews: tuple[int, ...]
    after_interviews: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class JdSourceChanges:
    reference: JdSourceReference
    changes: tuple[MemorySourceChange, ...]


@dataclass(frozen=True, slots=True)
class JdManualChanges:
    interval: ManualJdRange
    snapshots: dict[UUID, JdChangeSnapshot]
    scope: ManualChangeScope


class JdChangesWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_manual(
        self,
        binding: PublishedMemoryRead,
        *,
        manual_jd_start_revision_id: UUID,
        scope: ManualChangeScope,
    ) -> JdManualChanges:
        async with self.sessions() as session:
            await _require_read(session, binding)
            file_id = binding.scope.job_file_id
            candidate = await candidate_service.read_position(
                session, file_id, binding.scope.execution_id
            )
            if candidate.base_revision_id != manual_jd_start_revision_id:
                raise ExecutionStateError("The supplied manual start does not belong to this Turn")
            if isinstance(scope, ItemManualChanges):
                # Only current surviving locators can request item scope. Historical
                # deletions remain readable by all/area, never as revived edit targets.
                current = await read_work_at(session, file_id, candidate.revision_id)
                resolve_jd_read_ref(current, scope.read_ref)
            previous = await history.read_previous_completed_execution(
                session,
                binding.scope,
                AgentRole.JOB_CONSULTANT,
            )
            interval = await change_queries.read_manual_change_range(
                session,
                file_id,
                binding.scope.execution_id,
                start_revision_id=manual_jd_start_revision_id,
                previous_completed_execution_id=previous.execution_id if previous else None,
            )
            positions = {interval.base_revision_id, interval.start_revision_id}
            for operation in interval.operations:
                positions.update((operation.before_revision_id, operation.after_revision_id))
            snapshots = {
                position: await change_queries.read_change_snapshot(session, file_id, position)
                for position in positions
            }
            return JdManualChanges(interval, snapshots, scope)

    async def read_source(self, binding: PublishedMemoryRead, citation_ref: str) -> JdSourceChanges:
        async with self.sessions() as session:
            await _require_read(session, binding)
            file_id = binding.scope.job_file_id
            candidate = await candidate_service.read_position(
                session, file_id, binding.scope.execution_id
            )
            references = await source_persistence.read_source_references(
                session, file_id, candidate.revision_id
            )
            reference = resolve_jd_citation_ref(references, citation_ref)
            source = reference.source
            if isinstance(source, InterviewSource):
                current = await interviews.read_execution_input(
                    session, job_file_id=file_id, execution_id=binding.scope.execution_id
                )
                if source.source_id == current.source_id:
                    raise UnsupportedJdSourceKindError(
                        "此引用是 current_input；請使用本輪已提供的原話，不製造歷史序號。"
                    )
                formal = await interviews.read_interview_sources(
                    session,
                    InterviewReadScope(file_id, binding.interview_through_sequence),
                    source_ids=(source.source_id,),
                )
                raise UnsupportedJdSourceKindError(
                    "此引用是不可變訪談；請用 read_interview 讀正式序號 "
                    f"{formal[0].interview_sequence}。"
                )
            if binding.snapshot_id is None:
                raise MemoryRevisionNotFoundError("No published comparison endpoint is pinned")
            old_snapshot = await memory.read_snapshot(session, file_id, source.snapshot_id)
            new_snapshot = await memory.read_snapshot(session, file_id, binding.snapshot_id)
            if (
                max(old_snapshot.covered_through_sequence, new_snapshot.covered_through_sequence)
                > binding.interview_through_sequence
            ):
                raise MemoryPermissionError("The source exceeds this Turn's interview boundary")
            old_members = await memory.read_members(session, file_id, old_snapshot.position_id)
            new_members = await memory.read_members(session, file_id, new_snapshot.position_id)
            before = await memory.read_selected(session, file_id, old_members, source.object_id)
            if before.revision_id != source.revision_id or before.layer.value != source.layer.value:
                raise MemoryRevisionNotFoundError("The citation does not match its fixed snapshot")
            after = (
                await memory.read_selected(session, file_id, new_members, source.object_id)
                if source.object_id in new_members
                else None
            )
            if after is not None and after.layer != before.layer:
                raise MemoryRevisionNotFoundError("The same source identity changed layer")
            changes = [await _source_change(session, binding, before, after)]
            # A changed understanding may retain the same text but depend on changed situations.
            old_links = {ref.object_id: ref for ref in before.work_situation_references}
            new_links = (
                {ref.object_id: ref for ref in after.work_situation_references} if after else {}
            )
            for object_id in sorted(old_links.keys() | new_links.keys()):
                old = (
                    await memory.read_selected(session, file_id, old_members, object_id)
                    if object_id in old_links
                    else None
                )
                new = (
                    await memory.read_selected(session, file_id, new_members, object_id)
                    if object_id in new_links
                    else None
                )
                for selected, links in ((old, old_links), (new, new_links)):
                    if selected is not None and (
                        selected.layer != MemoryLayer.WORK_SITUATION
                        or selected.revision_id != links[object_id].revision_id
                    ):
                        raise MemoryRevisionNotFoundError(
                            "The published source chain is incomplete"
                        )
                changes.append(await _source_change(session, binding, old, new))
            return JdSourceChanges(reference, tuple(changes))


async def _require_read(session: AsyncSession, binding: PublishedMemoryRead) -> None:
    if binding.scope.kind != ExecutionKind.CONSULTANT_TURN or (
        await executions.read_execution(session, binding.scope)
    ).status not in (ExecutionStatus.ACTIVE, ExecutionStatus.PAUSED):
        raise ExecutionStateError("This Turn cannot read JD changes")


async def _source_change(
    session: AsyncSession,
    binding: PublishedMemoryRead,
    before: MemoryObjectRevision | None,
    after: MemoryObjectRevision | None,
) -> MemorySourceChange:
    async def sequences(value: MemoryObjectRevision | None) -> tuple[int, ...]:
        if value is None or not value.interview_references:
            return ()
        selected = await interviews.read_interview_sources(
            session,
            InterviewReadScope(binding.scope.job_file_id, binding.interview_through_sequence),
            source_ids=tuple(value.interview_references),
        )
        return tuple(sorted(message.interview_sequence for message in selected))

    return MemorySourceChange(before, after, await sequences(before), await sequences(after))
