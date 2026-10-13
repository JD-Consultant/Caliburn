"""Pure JD item revision intents, owned target selection and change preparation."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from caliburn.features.job_description.areas import (
    AreaField,
    AreaFieldChange,
    ResponsibilityArea,
    ReviseArea,
)
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityField,
    CapabilityFieldChange,
    ReorderTaskCapability,
    ReviseCapability,
    SetTaskCapability,
)
from caliburn.features.job_description.capability_changes import apply_capability_change
from caliburn.features.job_description.collaborators import (
    Collaborator,
    CollaboratorField,
    CollaboratorFieldChange,
    ReviseCollaborator,
)
from caliburn.features.job_description.compound_edits import (
    BoundItemSources,
    ItemContentRevision,
)
from caliburn.features.job_description.conditions import (
    ConditionFieldChange,
    ConditionKind,
    ConditionKindChange,
    ConditionTextChange,
    JobCondition,
    ReviseCondition,
)
from caliburn.features.job_description.navigation import JdReadTarget, resolve_jd_read_ref
from caliburn.features.job_description.source_intents import JdSourceSelection
from caliburn.features.job_description.sources import (
    InvalidJdSourceError,
    JdSourceChange,
    JdSourceReference,
    JdSourceTarget,
    SourceTargetKind,
    validate_source_changes,
)
from caliburn.features.job_description.tasks import (
    AddTaskDetail,
    DetailKind,
    RemoveTaskDetail,
    ReviseTask,
    ReviseTaskDetail,
    SetTaskField,
    TaskChange,
    TaskDetail,
    TaskField,
    WorkTask,
)
from caliburn.features.job_description.work_models import JdWorkRevision


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


@dataclass(frozen=True, slots=True)
class ReorderItemCapability:
    capability_read_ref: str
    position: Literal["first", "last", "before", "after"]
    neighbor_read_ref: str | None = None


@dataclass(frozen=True, slots=True)
class ItemSourceTarget:
    pass


type ItemSourceSelection = ItemSourceTarget


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


@dataclass(frozen=True, slots=True)
class ReviseItemInput:
    read_ref: str
    changes: tuple[ItemRevisionChange, ...]


def content_revision(
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


def capability_changes(
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


def source_target(item: JdReadTarget) -> JdSourceTarget:
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


@dataclass(frozen=True, slots=True)
class ItemRevisionPreparation:
    item: JdReadTarget
    content: ItemContentRevision | None
    capabilities: tuple[SetTaskCapability | ReorderTaskCapability, ...]


def prepare_item_revision(work: JdWorkRevision, intent: ReviseItemInput) -> ItemRevisionPreparation:
    """Select one editable item and validate its content and relationship changes."""
    if not intent.changes:
        raise InvalidItemRevisionError("Choose at least one item change")
    item = resolve_jd_read_ref(work, intent.read_ref)
    if isinstance(item, TaskDetail):
        raise InvalidItemRevisionError("Revise details through their containing task")
    return ItemRevisionPreparation(
        item,
        content_revision(work, item, intent.changes),
        capability_changes(work, item, intent.changes),
    )


def bind_item_sources(
    grouped: dict[JdSourceTarget, list[JdSourceChange]],
) -> tuple[BoundItemSources, ...]:
    """驗證本項共用依據；子項內容變動不移除任務來源。"""
    for values in grouped.values():
        validate_source_changes(tuple(values))
    return tuple(BoundItemSources(target, tuple(values)) for target, values in grouped.items())


def select_item_citation(
    references: tuple[JdSourceReference, ...], target: JdSourceTarget, citation_ref: str
) -> JdSourceReference:
    """An existing citation must belong to the selected item's owned evidence target."""
    reference = next(
        (
            ref
            for ref in references
            if ref.target == target and f"citation_{ref.citation_id.hex}" == citation_ref
        ),
        None,
    )
    if reference is None:
        raise InvalidJdSourceError("The citation does not belong to the selected source target")
    return reference
