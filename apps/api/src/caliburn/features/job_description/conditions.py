"""Job-wide conditions are classified statements, never implicit task requirements."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class InvalidConditionChangeError(ValueError):
    """A condition must have meaningful text and unambiguous changes."""


class ConditionNotFoundError(ValueError):
    """A condition or ordering neighbour is absent from the selected group."""


class ConditionKind(StrEnum):
    WORK_ENVIRONMENT = "work_environment"
    SCHEDULE_TRAVEL = "schedule_travel"
    SHARED_AUTHORITY = "shared_authority"
    SHARED_COLLABORATION = "shared_collaboration"
    QUALIFICATION = "qualification"


def validate_condition_text(text: str) -> None:
    if not text.strip() or "\x00" in text:
        raise InvalidConditionChangeError("Condition text must be nonblank without NUL")


@dataclass(frozen=True, slots=True)
class JobCondition:
    condition_id: UUID
    content_revision_id: UUID
    kind: ConditionKind
    text: str

    def __post_init__(self) -> None:
        validate_condition_text(self.text)


@dataclass(frozen=True, slots=True)
class JdConditionsRevision:
    revision_id: UUID
    conditions: tuple[JobCondition, ...]


@dataclass(frozen=True, slots=True)
class CreateCondition:
    kind: ConditionKind
    text: str

    def __post_init__(self) -> None:
        validate_condition_text(self.text)


@dataclass(frozen=True, slots=True)
class ConditionTextChange:
    text: str

    def __post_init__(self) -> None:
        validate_condition_text(self.text)


@dataclass(frozen=True, slots=True)
class ConditionKindChange:
    kind: ConditionKind


type ConditionFieldChange = ConditionTextChange | ConditionKindChange


@dataclass(frozen=True, slots=True)
class ReviseCondition:
    condition_id: UUID
    changes: tuple[ConditionFieldChange, ...]

    def __post_init__(self) -> None:
        fields = [type(change) for change in self.changes]
        if not fields or len(fields) != len(set(fields)):
            raise InvalidConditionChangeError("Choose at least one field, and change each once")


@dataclass(frozen=True, slots=True)
class DeleteCondition:
    condition_id: UUID


@dataclass(frozen=True, slots=True)
class ReorderCondition:
    condition_id: UUID
    before_condition_id: UUID | None


type ConditionChange = CreateCondition | ReviseCondition | DeleteCondition | ReorderCondition


@dataclass(frozen=True, slots=True)
class EditJdConditions:
    command_id: UUID
    expected_revision_id: UUID
    change: ConditionChange


def condition_change_payload(change: ConditionChange) -> list[dict[str, str | None]]:
    match change:
        case CreateCondition():
            return [{"action": "create_condition", "kind": change.kind.value, "text": change.text}]
        case ReviseCondition():
            fields: list[dict[str, str | None]] = []
            for item in change.changes:
                match item:
                    case ConditionTextChange():
                        fields.append({"field": "text", "value": item.text})
                    case ConditionKindChange():
                        fields.append({"field": "kind", "value": item.kind.value})
            return [
                {"action": "revise_condition", "condition_id": str(change.condition_id)},
                *fields,
            ]
        case DeleteCondition():
            return [{"action": "delete_condition", "condition_id": str(change.condition_id)}]
        case ReorderCondition():
            return [
                {
                    "action": "reorder_condition",
                    "condition_id": str(change.condition_id),
                    "before_condition_id": str(change.before_condition_id)
                    if change.before_condition_id
                    else None,
                }
            ]
