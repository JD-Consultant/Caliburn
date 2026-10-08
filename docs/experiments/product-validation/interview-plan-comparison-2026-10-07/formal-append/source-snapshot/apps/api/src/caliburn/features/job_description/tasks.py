"""Task values and bounded intentions; no HTTP, database or provider dependencies."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class InvalidTaskChangeError(ValueError):
    """An edit has ambiguous effects or would leave invalid task content."""


class TaskTargetNotFoundError(ValueError):
    """A selected task, detail, group or ordering neighbour is not in scope."""


class TaskField(StrEnum):
    TITLE = "title"
    DESCRIPTION = "description"


class DetailKind(StrEnum):
    OUTCOME = "outcome"
    REQUIREMENT = "requirement"


def validate_text(value: str) -> None:
    if not value.strip() or "\x00" in value:
        raise InvalidTaskChangeError("Task text must be nonblank without NUL")


def validate_task_text(title: str | None, description: str | None) -> None:
    if title is None and description is None:
        raise InvalidTaskChangeError("A task needs a title or meaningful description")
    for value in (title, description):
        if value is not None:
            validate_text(value)


@dataclass(frozen=True, slots=True)
class TaskDetail:
    detail_id: UUID
    kind: DetailKind
    text: str

    def __post_init__(self) -> None:
        validate_text(self.text)


@dataclass(frozen=True, slots=True)
class WorkTask:
    task_id: UUID
    content_revision_id: UUID
    area_id: UUID | None
    title: str | None
    description: str | None
    details: tuple[TaskDetail, ...]

    def __post_init__(self) -> None:
        validate_task_text(self.title, self.description)
        if len({detail.detail_id for detail in self.details}) != len(self.details):
            raise InvalidTaskChangeError("A task cannot contain a detail twice")


@dataclass(frozen=True, slots=True)
class JdTasksRevision:
    revision_id: UUID
    tasks: tuple[WorkTask, ...]


@dataclass(frozen=True, slots=True)
class SetTaskField:
    field: TaskField
    value: str | None


@dataclass(frozen=True, slots=True)
class AddTaskDetail:
    kind: DetailKind
    text: str


@dataclass(frozen=True, slots=True)
class ReviseTaskDetail:
    detail_id: UUID
    text: str


@dataclass(frozen=True, slots=True)
class RemoveTaskDetail:
    detail_id: UUID


type TaskChange = SetTaskField | AddTaskDetail | ReviseTaskDetail | RemoveTaskDetail


@dataclass(frozen=True, slots=True)
class CreateTask:
    area_id: UUID | None
    title: str | None
    description: str | None
    outcomes: tuple[str, ...]
    requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_task_text(self.title, self.description)
        for text in (*self.outcomes, *self.requirements):
            validate_text(text)


def validate_changes(changes: tuple[TaskChange, ...]) -> None:
    keys: set[tuple[str, str]] = set()
    for change in changes:
        if isinstance(change, AddTaskDetail):
            validate_text(change.text)
            continue
        if isinstance(change, SetTaskField):
            if change.value is not None:
                validate_text(change.value)
            key = ("field", change.field.value)
        else:
            if isinstance(change, ReviseTaskDetail):
                validate_text(change.text)
            key = ("detail", str(change.detail_id))
        if key in keys:
            raise InvalidTaskChangeError("Change each field or existing detail only once")
        keys.add(key)


@dataclass(frozen=True, slots=True)
class ReviseTask:
    task_id: UUID
    changes: tuple[TaskChange, ...]

    def __post_init__(self) -> None:
        if not self.changes:
            raise InvalidTaskChangeError("Choose at least one task change")
        validate_changes(self.changes)


@dataclass(frozen=True, slots=True)
class MoveTask:
    task_id: UUID
    area_id: UUID | None
    before_task_id: UUID | None
    changes: tuple[TaskChange, ...] = ()

    def __post_init__(self) -> None:
        validate_changes(self.changes)


@dataclass(frozen=True, slots=True)
class ReorderTaskDetail:
    task_id: UUID
    detail_id: UUID
    before_detail_id: UUID | None


@dataclass(frozen=True, slots=True)
class DeleteTask:
    task_id: UUID


type TaskEdit = CreateTask | ReviseTask | MoveTask | ReorderTaskDetail | DeleteTask


@dataclass(frozen=True, slots=True)
class EditJdTasks:
    command_id: UUID
    expected_revision_id: UUID
    change: TaskEdit
