"""Collaborator values and bounded edit intentions, independent of HTTP/SQL."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class InvalidCollaboratorChangeError(ValueError):
    """A collaborator edit would be ambiguous or leave an empty collaborator."""


class CollaboratorNotFoundError(ValueError):
    """A collaborator or ordering neighbour is absent from this JD revision."""


class CollaboratorField(StrEnum):
    NAME = "name"
    SCOPE_TEXT = "scope_text"


def validate_collaborator_text(name: str | None, scope_text: str | None) -> None:
    if name is None and scope_text is None:
        raise InvalidCollaboratorChangeError("A collaborator needs a name or meaningful scope text")
    for value in (name, scope_text):
        if value is not None and (not value.strip() or "\x00" in value):
            raise InvalidCollaboratorChangeError("Collaborator text must be nonblank without NUL")


@dataclass(frozen=True, slots=True)
class Collaborator:
    collaborator_id: UUID
    content_revision_id: UUID
    name: str | None
    scope_text: str | None

    def __post_init__(self) -> None:
        validate_collaborator_text(self.name, self.scope_text)


@dataclass(frozen=True, slots=True)
class JdCollaboratorsRevision:
    revision_id: UUID
    collaborators: tuple[Collaborator, ...]


@dataclass(frozen=True, slots=True)
class CreateCollaborator:
    name: str | None
    scope_text: str | None

    def __post_init__(self) -> None:
        validate_collaborator_text(self.name, self.scope_text)


@dataclass(frozen=True, slots=True)
class CollaboratorFieldChange:
    field: CollaboratorField
    value: str | None


@dataclass(frozen=True, slots=True)
class ReviseCollaborator:
    collaborator_id: UUID
    changes: tuple[CollaboratorFieldChange, ...]

    def __post_init__(self) -> None:
        fields = [change.field for change in self.changes]
        if not fields or len(fields) != len(set(fields)):
            raise InvalidCollaboratorChangeError(
                "Choose at least one field, and change each field once"
            )


@dataclass(frozen=True, slots=True)
class DeleteCollaborator:
    collaborator_id: UUID


@dataclass(frozen=True, slots=True)
class ReorderCollaborator:
    collaborator_id: UUID
    before_collaborator_id: UUID | None


type CollaboratorChange = (
    CreateCollaborator | ReviseCollaborator | DeleteCollaborator | ReorderCollaborator
)


@dataclass(frozen=True, slots=True)
class EditJdCollaborators:
    command_id: UUID
    expected_revision_id: UUID
    change: CollaboratorChange


def collaborator_change_payload(change: CollaboratorChange) -> list[dict[str, str | None]]:
    """Stable original intent; not a second editable collaborator collection."""
    match change:
        case CreateCollaborator():
            return [
                {
                    "action": "create_collaborator",
                    "name": change.name,
                    "scope_text": change.scope_text,
                }
            ]
        case ReviseCollaborator():
            return [
                {"action": "revise_collaborator", "collaborator_id": str(change.collaborator_id)},
                *[{"field": item.field.value, "value": item.value} for item in change.changes],
            ]
        case DeleteCollaborator():
            return [
                {"action": "delete_collaborator", "collaborator_id": str(change.collaborator_id)}
            ]
        case ReorderCollaborator():
            return [
                {
                    "action": "reorder_collaborator",
                    "collaborator_id": str(change.collaborator_id),
                    "before_collaborator_id": str(change.before_collaborator_id)
                    if change.before_collaborator_id
                    else None,
                }
            ]
