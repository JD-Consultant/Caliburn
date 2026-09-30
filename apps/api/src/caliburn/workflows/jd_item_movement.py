"""Move a scoped JD candidate item without replacing identities or evidence."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_description import candidate_service, revision_editing
from caliburn.features.job_description.areas import (
    AreaField,
    AreaFieldChange,
    EditJdAreas,
    ReorderArea,
    ResponsibilityArea,
    ReviseArea,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.capabilities import (
    Capability,
    EditJdCapabilities,
    ReorderCapability,
)
from caliburn.features.job_description.collaborators import (
    Collaborator,
    EditJdCollaborators,
    ReorderCollaborator,
)
from caliburn.features.job_description.conditions import (
    EditJdConditions,
    JobCondition,
    ReorderCondition,
)
from caliburn.features.job_description.navigation import (
    JdReadTarget,
    jd_read_ref,
    resolve_jd_read_ref,
)
from caliburn.features.job_description.tasks import (
    AddTaskDetail,
    DetailKind,
    EditJdTasks,
    MoveTask,
    ReorderTaskDetail,
    ReviseTaskDetail,
    SetTaskField,
    TaskChange,
    TaskDetail,
    TaskField,
    WorkTask,
)
from caliburn.features.job_description.work_queries import JdWorkRevision
from caliburn.features.job_files import service as job_files
from caliburn.workflows.jd_candidates import apply_candidate_edit
from caliburn.workflows.memory_reads import PublishedMemoryRead


class InvalidItemMovementError(ValueError):
    """A move crosses an ownership boundary or includes unrelated content edits."""


@dataclass(frozen=True, slots=True)
class ItemPosition:
    kind: Literal["first", "last", "before", "after"]
    neighbor_read_ref: str | None = None


@dataclass(frozen=True, slots=True)
class CurrentItemContainer:
    pass


@dataclass(frozen=True, slots=True)
class TaskParentDestination:
    parent_read_ref: str | None


@dataclass(frozen=True, slots=True)
class MovementTextChange:
    read_ref: str
    field: str
    value: str | None


@dataclass(frozen=True, slots=True)
class MovementDetailAddition:
    kind: DetailKind
    text: str


@dataclass(frozen=True, slots=True)
class MoveItemInput:
    read_ref: str
    destination: CurrentItemContainer | TaskParentDestination
    position: ItemPosition
    content_changes: tuple[MovementTextChange | MovementDetailAddition, ...] = ()


type ItemMovement = (
    ReorderArea
    | MoveTask
    | ReorderTaskDetail
    | ReorderCapability
    | ReorderCollaborator
    | ReorderCondition
)
type MovementCommand = (
    EditJdAreas | EditJdTasks | EditJdCapabilities | EditJdCollaborators | EditJdConditions
)


@dataclass(frozen=True, slots=True)
class PreparedItemMovement:
    command_id: UUID
    candidate: JdCandidateScope
    expected_revision_id: UUID
    movement: ItemMovement
    area_revisions: tuple[ReviseArea, ...]
    result_message: str


class JdItemMovementWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def prepare(
        self, binding: PublishedMemoryRead, *, command_id: UUID, intent: MoveItemInput
    ) -> PreparedItemMovement:
        if binding.scope.kind != ExecutionKind.CONSULTANT_TURN:
            raise ExecutionStateError("Only a consultant Turn can move JD items")
        async with self.sessions() as session:
            if (
                await executions.read_execution(session, binding.scope)
            ).status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This Turn cannot prepare JD changes")
            preview = await candidate_service.read_preview(
                session,
                binding.scope.job_file_id,
                binding.scope.execution_id,
            )
            target = resolve_jd_read_ref(preview.work, intent.read_ref)
            movement, areas = _movement(preview.work, target, intent)
            message = "moved"
            if (
                isinstance(target, WorkTask)
                and isinstance(movement, MoveTask)
                and target.area_id is not None
                and movement.area_id is None
            ):
                message += " · 原所屬職責已解除，任務現在未歸屬"
            return PreparedItemMovement(
                command_id,
                preview.position.scope,
                preview.position.revision_id,
                movement,
                areas,
                message,
            )

    async def execute(self, writer: ExecutionWriter, prepared: PreparedItemMovement) -> str:
        """Apply related commands in one transaction; replay never rewinds the live candidate."""
        if (
            writer.scope.kind != ExecutionKind.CONSULTANT_TURN
            or writer.scope.execution_id != prepared.candidate.execution_id
        ):
            raise ExecutionStateError("This prepared move belongs to a different Turn")
        async with self.sessions.begin() as session:
            file_id = writer.scope.job_file_id
            await job_files.lock_job_file(session, file_id)
            await executions.lock_active_writer(session, writer)
            await revision_editing.require_open_candidate(session, file_id, prepared.candidate)
            revision = await apply_candidate_edit(
                session,
                file_id,
                prepared.candidate,
                _movement_command(
                    uuid5(prepared.command_id, "move"),
                    prepared.expected_revision_id,
                    prepared.movement,
                ),
            )
            for index, area in enumerate(prepared.area_revisions):
                revision = await apply_candidate_edit(
                    session,
                    file_id,
                    prepared.candidate,
                    EditJdAreas(uuid5(prepared.command_id, f"area:{index}"), revision, area),
                )
            return (
                "unchanged"
                if revision == prepared.expected_revision_id
                else prepared.result_message
            )


def _before_id(
    group: tuple[tuple[str, UUID], ...], target_ref: str, position: ItemPosition
) -> UUID | None:
    """Translate relative placement in the selected group, not in a global item registry."""
    remaining = tuple(pair for pair in group if pair[0] != target_ref)
    if position.kind in {"first", "last"}:
        if position.neighbor_read_ref is not None:
            raise InvalidItemMovementError("First and last do not take a neighbour")
        return remaining[0][1] if position.kind == "first" and remaining else None
    if position.kind not in {"before", "after"} or position.neighbor_read_ref is None:
        raise InvalidItemMovementError("Choose first, last, before or after with its neighbour")
    neighbor = next((pair for pair in group if pair[0] == position.neighbor_read_ref), None)
    if neighbor is None:
        raise InvalidItemMovementError("Choose a same-kind neighbour in the destination group")
    if neighbor[0] == target_ref or position.kind == "before":
        return neighbor[1]
    index = remaining.index(neighbor) + 1
    return remaining[index][1] if index < len(remaining) else None


def _movement(
    work: JdWorkRevision, target: JdReadTarget, intent: MoveItemInput
) -> tuple[ItemMovement, tuple[ReviseArea, ...]]:
    if isinstance(target, WorkTask):
        area_id = target.area_id
        if isinstance(intent.destination, TaskParentDestination):
            if intent.destination.parent_read_ref is None:
                area_id = None
            else:
                parent = resolve_jd_read_ref(work, intent.destination.parent_read_ref)
                if not isinstance(parent, ResponsibilityArea):
                    raise InvalidItemMovementError(
                        "A task parent must be a responsibility area or null"
                    )
                area_id = parent.area_id
        if intent.content_changes and target.area_id == area_id:
            raise InvalidItemMovementError(
                "Content adjustments accompany a task changing parent only"
            )
        changes, areas = _content_changes(work, target, area_id, intent.content_changes)
        group = tuple((jd_read_ref(t), t.task_id) for t in work.tasks if t.area_id == area_id)
        return MoveTask(
            target.task_id, area_id, _before_id(group, intent.read_ref, intent.position), changes
        ), areas
    if not isinstance(intent.destination, CurrentItemContainer):
        raise InvalidItemMovementError(
            "Only tasks can change container; reorder this item's current group"
        )
    if intent.content_changes:
        raise InvalidItemMovementError(
            "Reordering preserves content; use revise_jd_item for text edits"
        )
    match target:
        case ResponsibilityArea():
            group = tuple((jd_read_ref(a), a.area_id) for a in work.areas)
            movement: ItemMovement = ReorderArea(
                target.area_id, _before_id(group, intent.read_ref, intent.position)
            )
        case TaskDetail():
            task = next(task for task in work.tasks if target in task.details)
            group = tuple(
                (jd_read_ref(d), d.detail_id) for d in task.details if d.kind == target.kind
            )
            movement = ReorderTaskDetail(
                task.task_id, target.detail_id, _before_id(group, intent.read_ref, intent.position)
            )
        case Capability():
            group = tuple(
                (jd_read_ref(c), c.capability_id)
                for c in work.capabilities
                if c.kind == target.kind
            )
            movement = ReorderCapability(
                target.capability_id, _before_id(group, intent.read_ref, intent.position)
            )
        case Collaborator():
            group = tuple((jd_read_ref(c), c.collaborator_id) for c in work.collaborators)
            movement = ReorderCollaborator(
                target.collaborator_id, _before_id(group, intent.read_ref, intent.position)
            )
        case JobCondition():
            group = tuple(
                (jd_read_ref(c), c.condition_id) for c in work.conditions if c.kind == target.kind
            )
            movement = ReorderCondition(
                target.condition_id, _before_id(group, intent.read_ref, intent.position)
            )
    return movement, ()


def _content_changes(
    work: JdWorkRevision,
    task: WorkTask,
    destination_area_id: UUID | None,
    choices: tuple[MovementTextChange | MovementDetailAddition, ...],
) -> tuple[tuple[TaskChange, ...], tuple[ReviseArea, ...]]:
    """Select only the moved task, its details and the two related area summaries."""
    task_changes: list[TaskChange] = []
    area_changes: dict[UUID, list[AreaFieldChange]] = {}
    keys: set[tuple[str, str]] = set()
    for choice in choices:
        if isinstance(choice, MovementDetailAddition):
            task_changes.append(AddTaskDetail(choice.kind, choice.text))
            continue
        key = (choice.read_ref, choice.field)
        if key in keys:
            raise InvalidItemMovementError("Change each content field only once")
        keys.add(key)
        selected = resolve_jd_read_ref(work, choice.read_ref)
        if isinstance(selected, WorkTask) and selected.task_id == task.task_id:
            try:
                field = TaskField(choice.field)
            except ValueError as error:
                raise InvalidItemMovementError("Choose task title or description") from error
            task_changes.append(SetTaskField(field, choice.value))
        elif isinstance(selected, TaskDetail) and selected in task.details:
            if choice.field != "text" or choice.value is None:
                raise InvalidItemMovementError("An existing task detail needs its complete text")
            task_changes.append(ReviseTaskDetail(selected.detail_id, choice.value))
        elif isinstance(selected, ResponsibilityArea) and selected.area_id in {
            task.area_id,
            destination_area_id,
        }:
            if choice.field != "scope_text":
                raise InvalidItemMovementError(
                    "Only source and destination area scope_text can accompany a move"
                )
            area_changes.setdefault(selected.area_id, []).append(
                AreaFieldChange(AreaField.SCOPE_TEXT, choice.value)
            )
        else:
            raise InvalidItemMovementError("Content target is unrelated to this task move")
    return tuple(task_changes), tuple(
        ReviseArea(identity, tuple(changes)) for identity, changes in area_changes.items()
    )


def _movement_command(command_id: UUID, revision: UUID, movement: ItemMovement) -> MovementCommand:
    match movement:
        case ReorderArea():
            return EditJdAreas(command_id, revision, movement)
        case MoveTask() | ReorderTaskDetail():
            return EditJdTasks(command_id, revision, movement)
        case ReorderCapability():
            return EditJdCapabilities(command_id, revision, movement)
        case ReorderCollaborator():
            return EditJdCollaborators(command_id, revision, movement)
        case ReorderCondition():
            return EditJdConditions(command_id, revision, movement)
