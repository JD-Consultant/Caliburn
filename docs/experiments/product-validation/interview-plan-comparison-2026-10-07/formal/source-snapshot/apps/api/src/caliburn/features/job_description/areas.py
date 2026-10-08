"""Responsibility-area values and bounded edit intentions, independent of HTTP/SQL."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class InvalidAreaChangeError(ValueError):
    """An area edit would be ambiguous or leave an empty group."""


class AreaNotFoundError(ValueError):
    """An area or ordering neighbour is absent from this JD revision."""


class AreaField(StrEnum):
    TITLE = "title"
    SCOPE_TEXT = "scope_text"


def validate_area_text(title: str | None, scope_text: str | None) -> None:
    if title is None and scope_text is None:
        raise InvalidAreaChangeError("An area needs a title or meaningful scope text")
    for value in (title, scope_text):
        if value is not None and (not value.strip() or "\x00" in value):
            raise InvalidAreaChangeError("Area text must be nonblank without NUL")


@dataclass(frozen=True, slots=True)
class ResponsibilityArea:
    area_id: UUID
    content_revision_id: UUID
    title: str | None
    scope_text: str | None

    def __post_init__(self) -> None:
        validate_area_text(self.title, self.scope_text)


@dataclass(frozen=True, slots=True)
class JdAreasRevision:
    revision_id: UUID
    areas: tuple[ResponsibilityArea, ...]


@dataclass(frozen=True, slots=True)
class CreateArea:
    title: str | None
    scope_text: str | None

    def __post_init__(self) -> None:
        validate_area_text(self.title, self.scope_text)


@dataclass(frozen=True, slots=True)
class AreaFieldChange:
    field: AreaField
    value: str | None


@dataclass(frozen=True, slots=True)
class ReviseArea:
    area_id: UUID
    changes: tuple[AreaFieldChange, ...]

    def __post_init__(self) -> None:
        fields = [change.field for change in self.changes]
        if not fields or len(fields) != len(set(fields)):
            raise InvalidAreaChangeError("Choose at least one field, and change each field once")


@dataclass(frozen=True, slots=True)
class DeleteArea:
    area_id: UUID


@dataclass(frozen=True, slots=True)
class ReorderArea:
    area_id: UUID
    before_area_id: UUID | None


type AreaChange = CreateArea | ReviseArea | DeleteArea | ReorderArea


@dataclass(frozen=True, slots=True)
class EditJdAreas:
    command_id: UUID
    expected_revision_id: UUID
    change: AreaChange


def area_change_payload(change: AreaChange) -> list[dict[str, str | None]]:
    """Stable original intent for equality checks; never a second editable area collection."""
    match change:
        case CreateArea():
            return [
                {"action": "create_area", "title": change.title, "scope_text": change.scope_text}
            ]
        case ReviseArea():
            return [
                {"action": "revise_area", "area_id": str(change.area_id)},
                *[{"field": item.field.value, "value": item.value} for item in change.changes],
            ]
        case DeleteArea():
            return [{"action": "delete_area", "area_id": str(change.area_id)}]
        case ReorderArea():
            return [
                {
                    "action": "reorder_area",
                    "area_id": str(change.area_id),
                    "before_area_id": str(change.before_area_id) if change.before_area_id else None,
                }
            ]
