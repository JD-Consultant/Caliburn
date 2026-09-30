"""Bind one item's changes, then join existing JD editors and source owner atomically."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import (
    candidate_service,
    revision_editing,
    source_persistence,
    work_queries,
)
from caliburn.features.job_description.areas import (
    AreaField,
    AreaFieldChange,
    EditJdAreas,
    ResponsibilityArea,
    ReviseArea,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityField,
    CapabilityFieldChange,
    EditJdCapabilities,
    ReorderTaskCapability,
    ReviseCapability,
    SetTaskCapability,
)
from caliburn.features.job_description.capability_changes import apply_capability_change
from caliburn.features.job_description.collaborators import (
    Collaborator,
    CollaboratorField,
    CollaboratorFieldChange,
    EditJdCollaborators,
    ReviseCollaborator,
)
from caliburn.features.job_description.conditions import (
    ConditionFieldChange,
    ConditionKind,
    ConditionKindChange,
    ConditionTextChange,
    EditJdConditions,
    JobCondition,
    ReviseCondition,
)
from caliburn.features.job_description.navigation import JdReadTarget, resolve_jd_read_ref
from caliburn.features.job_description.sources import (
    AddJdSource,
    AlignJdSource,
    InvalidJdSourceError,
    JdSource,
    JdSourceChange,
    JdSourceTarget,
    RemoveJdSource,
    ReviseJdSources,
    SourceTargetKind,
    validate_source_changes,
)
from caliburn.features.job_description.tasks import (
    AddTaskDetail,
    DetailKind,
    EditJdTasks,
    RemoveTaskDetail,
    ReviseTask,
    ReviseTaskDetail,
    SetTaskField,
    TaskChange,
    TaskDetail,
    TaskField,
    WorkTask,
)
from caliburn.features.job_description.work_queries import JdWorkRevision
from caliburn.features.job_files import service as job_files
from caliburn.workflows.jd_candidates import JdCandidateEdit, apply_candidate_edit
from caliburn.workflows.jd_sources import (
    JdSourceSelection,
    resolve_aligned_jd_source,
    resolve_jd_source,
)
from caliburn.workflows.memory_reads import PublishedMemoryRead


class InvalidItemRevisionError(ValueError):
    """A model selected incompatible actions or a target outside the chosen item."""


@dataclass(frozen=True, slots=True)
class ItemFieldChange:
    field: str
    value: str | None


@dataclass(frozen=True, slots=True)
class AddItemDetail:
    kind: DetailKind
    text: str
    sources: tuple[JdSourceSelection, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviseItemDetail:
    detail_read_ref: str
    text: str


@dataclass(frozen=True, slots=True)
class RemoveItemDetail:
    detail_read_ref: str


@dataclass(frozen=True, slots=True)
class SetItemCapability:
    capability_read_ref: str
    linked: bool
    sources: tuple[JdSourceSelection, ...] = ()


@dataclass(frozen=True, slots=True)
class ReorderItemCapability:
    capability_read_ref: str
    position: Literal["first", "last", "before", "after"]
    neighbor_read_ref: str | None = None


@dataclass(frozen=True, slots=True)
class ItemSourceTarget:
    pass


@dataclass(frozen=True, slots=True)
class DetailSourceTarget:
    detail_read_ref: str


@dataclass(frozen=True, slots=True)
class CapabilitySourceTarget:
    capability_read_ref: str


type ItemSourceSelection = ItemSourceTarget | DetailSourceTarget | CapabilitySourceTarget


@dataclass(frozen=True, slots=True)
class AddItemSource:
    target: ItemSourceSelection
    source: JdSourceSelection


@dataclass(frozen=True, slots=True)
class RemoveItemSource:
    target: ItemSourceSelection
    citation_ref: str


@dataclass(frozen=True, slots=True)
class AlignItemSource:
    target: ItemSourceSelection
    citation_ref: str


type ItemSourceIntent = AddItemSource | RemoveItemSource | AlignItemSource
type ItemRevisionChange = (
    ItemFieldChange
    | AddItemDetail
    | ReviseItemDetail
    | RemoveItemDetail
    | SetItemCapability
    | ReorderItemCapability
    | ItemSourceIntent
)
type ItemContentRevision = (
    ReviseArea | ReviseTask | ReviseCapability | ReviseCollaborator | ReviseCondition
)


@dataclass(frozen=True, slots=True)
class ReviseItemInput:
    read_ref: str
    changes: tuple[ItemRevisionChange, ...]


@dataclass(frozen=True, slots=True)
class BoundItemSources:
    target: JdSourceTarget
    changes: tuple[JdSourceChange, ...]


@dataclass(frozen=True, slots=True)
class AddedDetailSources:
    kind: DetailKind
    sources: tuple[JdSource, ...]


@dataclass(frozen=True, slots=True)
class PreparedItemRevision:
    command_id: UUID
    candidate: JdCandidateScope
    expected_revision_id: UUID
    content: ItemContentRevision | None
    capabilities: tuple[SetTaskCapability | ReorderTaskCapability, ...]
    sources: tuple[BoundItemSources, ...]
    added_details: tuple[AddedDetailSources, ...]


class JdItemRevisionWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self,
        binding: PublishedMemoryRead,
        *,
        command_id: UUID,
        intent: ReviseItemInput,
    ) -> PreparedItemRevision:
        if not intent.changes:
            raise InvalidItemRevisionError("Choose at least one item change")
        async with self.sessions() as session:
            if (
                await executions.read_execution(session, binding.scope)
            ).status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This Turn cannot prepare JD changes")
            preview = await candidate_service.read_preview(
                session, binding.scope.job_file_id, binding.scope.execution_id
            )
            work = preview.work
            item = resolve_jd_read_ref(work, intent.read_ref)
            if isinstance(item, TaskDetail):
                raise InvalidItemRevisionError("Revise details through their containing task")
            content = _content_revision(work, item, intent.changes)
            capabilities = _capability_changes(work, item, intent.changes)
            references = await source_persistence.read_source_references(
                session, binding.scope.job_file_id, preview.position.revision_id
            )
            grouped: dict[JdSourceTarget, list[JdSourceChange]] = {}
            added_details = []
            for change in intent.changes:
                if isinstance(change, AddItemDetail):
                    added_details.append(
                        AddedDetailSources(
                            change.kind, await _sources(session, binding, change.sources)
                        )
                    )
                elif isinstance(change, SetItemCapability):
                    if not change.linked and change.sources:
                        raise InvalidItemRevisionError("Unlink cannot add evidence")
                    if change.sources:
                        target = _source_target(
                            work, item, CapabilitySourceTarget(change.capability_read_ref)
                        )
                        grouped.setdefault(target, []).extend(
                            AddJdSource(source)
                            for source in await _sources(session, binding, change.sources)
                        )
                elif isinstance(change, AddItemSource | RemoveItemSource | AlignItemSource):
                    target = _source_target(work, item, change.target)
                    if isinstance(change, AddItemSource):
                        bound: JdSourceChange = AddJdSource(
                            await resolve_jd_source(session, binding, change.source)
                        )
                    else:
                        reference = next(
                            (
                                ref
                                for ref in references
                                if ref.target == target
                                and f"citation_{ref.citation_id.hex}" == change.citation_ref
                            ),
                            None,
                        )
                        if reference is None:
                            raise InvalidJdSourceError(
                                "The citation does not belong to the selected source target"
                            )
                        if isinstance(change, RemoveItemSource):
                            bound = RemoveJdSource(reference.citation_id)
                        else:
                            bound = AlignJdSource(
                                reference.citation_id,
                                await resolve_aligned_jd_source(session, binding, reference.source),
                            )
                    grouped.setdefault(target, []).append(bound)
            removed = _removed_targets(item, content, capabilities)
            if any(target in removed for target in grouped):
                raise InvalidItemRevisionError(
                    "A removed detail or relationship cannot also change evidence"
                )
            for values in grouped.values():
                validate_source_changes(tuple(values))
            return PreparedItemRevision(
                command_id,
                preview.position.scope,
                preview.position.revision_id,
                content,
                capabilities,
                tuple(
                    BoundItemSources(target, tuple(values)) for target, values in grouped.items()
                ),
                tuple(added_details),
            )

    async def execute(self, writer: ExecutionWriter, prepared: PreparedItemRevision) -> str:
        if writer.scope.execution_id != prepared.candidate.execution_id:
            raise ExecutionStateError("This prepared edit belongs to a different Turn")
        async with self.sessions.begin() as session:
            file_id = writer.scope.job_file_id
            await job_files.lock_job_file(session, file_id)
            await executions.lock_active_writer(session, writer)
            await revision_editing.require_open_candidate(session, file_id, prepared.candidate)
            revision = prepared.expected_revision_id
            if prepared.content is not None:
                revision = await apply_candidate_edit(
                    session,
                    file_id,
                    prepared.candidate,
                    _content_command(
                        uuid5(prepared.command_id, "content"), revision, prepared.content
                    ),
                )
            # New detail IDs come from the original owner's result, including on replay.
            detail_sources = await _added_detail_sources(session, file_id, prepared, revision)
            for index, change in enumerate(prepared.capabilities):
                revision = await apply_candidate_edit(
                    session,
                    file_id,
                    prepared.candidate,
                    EditJdCapabilities(
                        uuid5(prepared.command_id, f"capability:{index}"), revision, change
                    ),
                )
            for index, group in enumerate((*prepared.sources, *detail_sources)):
                revision = await apply_candidate_edit(
                    session,
                    file_id,
                    prepared.candidate,
                    ReviseJdSources(
                        uuid5(prepared.command_id, f"source:{index}"),
                        revision,
                        group.target,
                        group.changes,
                    ),
                )
            if revision == prepared.expected_revision_id:
                return "unchanged"
            if (
                prepared.content is None
                and not prepared.capabilities
                and all(
                    isinstance(change, AlignJdSource)
                    for group in prepared.sources
                    for change in group.changes
                )
            ):
                return "aligned"
            return "updated"


def _content_revision(
    work: JdWorkRevision, item: JdReadTarget, changes: tuple[ItemRevisionChange, ...]
) -> ItemContentRevision | None:
    fields = tuple(change for change in changes if isinstance(change, ItemFieldChange))
    details = tuple(
        change
        for change in changes
        if isinstance(change, AddItemDetail | ReviseItemDetail | RemoveItemDetail)
    )
    if details and not isinstance(item, WorkTask):
        raise InvalidItemRevisionError("Only a task has editable details")
    if not fields and not details:
        return None
    try:
        if isinstance(item, ResponsibilityArea):
            return ReviseArea(
                item.area_id,
                tuple(AreaFieldChange(AreaField(change.field), change.value) for change in fields),
            )
        if isinstance(item, Capability):
            return ReviseCapability(
                item.capability_id,
                tuple(
                    CapabilityFieldChange(CapabilityField(change.field), change.value)
                    for change in fields
                ),
            )
        if isinstance(item, Collaborator):
            return ReviseCollaborator(
                item.collaborator_id,
                tuple(
                    CollaboratorFieldChange(CollaboratorField(change.field), change.value)
                    for change in fields
                ),
            )
        if isinstance(item, JobCondition):
            condition_changes: list[ConditionFieldChange] = []
            for change in fields:
                if change.value is None:
                    raise InvalidItemRevisionError("A condition's text and kind cannot be cleared")
                if change.field == "text":
                    condition_changes.append(ConditionTextChange(change.value))
                elif change.field == "kind":
                    condition_changes.append(ConditionKindChange(ConditionKind(change.value)))
                else:
                    raise InvalidItemRevisionError("Choose a condition field")
            return ReviseCondition(item.condition_id, tuple(condition_changes))
        if isinstance(item, WorkTask):
            task_changes: list[TaskChange] = [
                SetTaskField(TaskField(change.field), change.value) for change in fields
            ]
            for detail_change in details:
                if isinstance(detail_change, AddItemDetail):
                    task_changes.append(AddTaskDetail(detail_change.kind, detail_change.text))
                else:
                    detail = _detail(work, item, detail_change.detail_read_ref)
                    task_changes.append(
                        ReviseTaskDetail(detail.detail_id, detail_change.text)
                        if isinstance(detail_change, ReviseItemDetail)
                        else RemoveTaskDetail(detail.detail_id)
                    )
            return ReviseTask(item.task_id, tuple(task_changes))
    except ValueError as error:
        raise InvalidItemRevisionError(str(error)) from error
    raise InvalidItemRevisionError("Choose an editable JD item")


def _capability_changes(
    work: JdWorkRevision, item: JdReadTarget, changes: tuple[ItemRevisionChange, ...]
) -> tuple[SetTaskCapability | ReorderTaskCapability, ...]:
    selected = tuple(
        change
        for change in changes
        if isinstance(change, SetItemCapability | ReorderItemCapability)
    )
    if not selected:
        return ()
    task = _task(item)
    result: list[SetTaskCapability | ReorderTaskCapability] = []
    keys: set[tuple[type, UUID]] = set()
    unlinked: set[UUID] = set()
    links = work.task_links
    for choice in selected:
        capability = _capability(work, choice.capability_read_ref)
        key = (type(choice), capability.capability_id)
        if key in keys:
            raise InvalidItemRevisionError("Change each capability link or order only once")
        keys.add(key)
        if isinstance(choice, SetItemCapability):
            edit: SetTaskCapability | ReorderTaskCapability = SetTaskCapability(
                task.task_id, capability.capability_id, choice.linked
            )
            if not choice.linked:
                unlinked.add(capability.capability_id)
        else:
            group = tuple(
                link.capability_id
                for link in links
                if link.task_id == task.task_id
                and any(
                    c.capability_id == link.capability_id and c.kind == capability.kind
                    for c in work.capabilities
                )
            )
            before = _order_before(work, capability.capability_id, group, choice)
            edit = ReorderTaskCapability(task.task_id, capability.capability_id, before)
        _, links, _ = apply_capability_change(
            work.capabilities, links, tuple(t.task_id for t in work.tasks), edit
        )
        result.append(edit)
    if any(
        isinstance(edit, ReorderTaskCapability) and edit.capability_id in unlinked
        for edit in result
    ):
        raise InvalidItemRevisionError("An unlinked capability cannot also be reordered")
    return tuple(result)


def _order_before(
    work: JdWorkRevision, identity: UUID, group: tuple[UUID, ...], choice: ReorderItemCapability
) -> UUID | None:
    if identity not in group:
        raise InvalidItemRevisionError("Reorder an existing relationship in this task")
    remaining = tuple(value for value in group if value != identity)
    if choice.position in {"first", "last"}:
        if choice.neighbor_read_ref is not None:
            raise InvalidItemRevisionError("First and last do not take a neighbour")
        return remaining[0] if choice.position == "first" and remaining else None
    if choice.position not in {"before", "after"} or choice.neighbor_read_ref is None:
        raise InvalidItemRevisionError("Choose a relative position and its neighbour")
    neighbor = _capability(work, choice.neighbor_read_ref).capability_id
    if neighbor not in group:
        raise InvalidItemRevisionError("Ordering neighbour must be a same-kind link in this task")
    if neighbor == identity or choice.position == "before":
        return neighbor
    index = remaining.index(neighbor) + 1
    return remaining[index] if index < len(remaining) else None


def _task(item: JdReadTarget) -> WorkTask:
    if not isinstance(item, WorkTask):
        raise InvalidItemRevisionError("Details and capability relationships require a task")
    return item


def _detail(work: JdWorkRevision, item: JdReadTarget, read_ref: str) -> TaskDetail:
    task = _task(item)
    detail = resolve_jd_read_ref(work, read_ref)
    if not isinstance(detail, TaskDetail) or detail not in task.details:
        raise InvalidItemRevisionError("Detail must belong to the selected task")
    return detail


def _capability(work: JdWorkRevision, read_ref: str) -> Capability:
    item = resolve_jd_read_ref(work, read_ref)
    if not isinstance(item, Capability):
        raise InvalidItemRevisionError("Select an existing knowledge or skill definition")
    return item


def _source_target(
    work: JdWorkRevision, item: JdReadTarget, choice: ItemSourceSelection
) -> JdSourceTarget:
    if isinstance(choice, DetailSourceTarget):
        return JdSourceTarget(
            SourceTargetKind.DETAIL,
            _detail(work, item, choice.detail_read_ref).detail_id,
            task_id=_task(item).task_id,
        )
    if isinstance(choice, CapabilitySourceTarget):
        return JdSourceTarget(
            SourceTargetKind.TASK_CAPABILITY,
            _capability(work, choice.capability_read_ref).capability_id,
            task_id=_task(item).task_id,
        )
    match item:
        case ResponsibilityArea():
            return JdSourceTarget(SourceTargetKind.AREA, item.area_id)
        case WorkTask():
            return JdSourceTarget(SourceTargetKind.TASK, item.task_id)
        case Capability():
            return JdSourceTarget(SourceTargetKind.CAPABILITY, item.capability_id)
        case Collaborator():
            return JdSourceTarget(SourceTargetKind.COLLABORATOR, item.collaborator_id)
        case JobCondition():
            return JdSourceTarget(SourceTargetKind.CONDITION, item.condition_id)
    raise InvalidItemRevisionError("Select the item or its owned evidence target")


def _removed_targets(
    item: JdReadTarget,
    content: ItemContentRevision | None,
    capabilities: tuple[SetTaskCapability | ReorderTaskCapability, ...],
) -> set[JdSourceTarget]:
    if not isinstance(item, WorkTask):
        return set()
    removed = {
        JdSourceTarget(SourceTargetKind.TASK_CAPABILITY, change.capability_id, task_id=item.task_id)
        for change in capabilities
        if isinstance(change, SetTaskCapability) and not change.linked
    }
    if isinstance(content, ReviseTask):
        removed.update(
            JdSourceTarget(SourceTargetKind.DETAIL, change.detail_id, task_id=item.task_id)
            for change in content.changes
            if isinstance(change, RemoveTaskDetail)
        )
    return removed


async def _sources(
    session: AsyncSession, binding: PublishedMemoryRead, choices: tuple[JdSourceSelection, ...]
) -> tuple[JdSource, ...]:
    sources = tuple([await resolve_jd_source(session, binding, choice) for choice in choices])
    if sources:
        validate_source_changes(tuple(AddJdSource(source) for source in sources))
    return sources


def _content_command(
    command_id: UUID, revision: UUID, content: ItemContentRevision
) -> JdCandidateEdit:
    match content:
        case ReviseArea():
            return EditJdAreas(command_id, revision, content)
        case ReviseTask():
            return EditJdTasks(command_id, revision, content)
        case ReviseCapability():
            return EditJdCapabilities(command_id, revision, content)
        case ReviseCollaborator():
            return EditJdCollaborators(command_id, revision, content)
        case ReviseCondition():
            return EditJdConditions(command_id, revision, content)


async def _added_detail_sources(
    session: AsyncSession, file_id: UUID, prepared: PreparedItemRevision, content_revision: UUID
) -> tuple[BoundItemSources, ...]:
    if not prepared.added_details:
        return ()
    if not isinstance(prepared.content, ReviseTask):
        raise TypeError("Added detail evidence requires a bound task revision")
    before = await work_queries.read_work_at(session, file_id, prepared.expected_revision_id)
    after = await work_queries.read_work_at(session, file_id, content_revision)
    original = next(t for t in before.tasks if t.task_id == prepared.content.task_id)
    revised = next(t for t in after.tasks if t.task_id == original.task_id)
    previous_ids = {d.detail_id for d in original.details}
    new = tuple(d for d in revised.details if d.detail_id not in previous_ids)
    choices = tuple(
        choice for kind in DetailKind for choice in prepared.added_details if choice.kind == kind
    )
    if len(new) != len(choices):
        raise RuntimeError("Original detail result does not match its bound evidence")
    return tuple(
        BoundItemSources(
            JdSourceTarget(SourceTargetKind.DETAIL, detail.detail_id, task_id=original.task_id),
            tuple(AddJdSource(source) for source in choice.sources),
        )
        for detail, choice in zip(new, choices, strict=True)
        if choice.sources
    )
