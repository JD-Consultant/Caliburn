"""Shared knowledge/skill definitions and task use are different JD values."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class InvalidCapabilityChangeError(ValueError):
    """An edit is ambiguous, crosses a kind boundary or leaves empty content."""


class CapabilityTargetNotFoundError(ValueError):
    """A selected definition, task or ordering neighbour is not in this JD."""


class CapabilityInUseError(ValueError):
    """Unlink the tasks deliberately before removing their shared definition."""


class CapabilityKind(StrEnum):
    KNOWLEDGE = "knowledge"
    SKILL = "skill"


class CapabilityField(StrEnum):
    NAME = "name"
    DESCRIPTION = "description"


def validate_capability_text(name: str | None, description: str | None) -> None:
    if name is None and description is None:
        raise InvalidCapabilityChangeError("A capability needs meaningful name or description")
    for value in (name, description):
        if value is not None and (not value.strip() or "\x00" in value):
            raise InvalidCapabilityChangeError("Capability text must be nonblank without NUL")


@dataclass(frozen=True, slots=True)
class Capability:
    capability_id: UUID
    content_revision_id: UUID
    kind: CapabilityKind
    name: str | None
    description: str | None

    def __post_init__(self) -> None:
        validate_capability_text(self.name, self.description)


@dataclass(frozen=True, slots=True)
class TaskCapabilityLink:
    task_id: UUID
    capability_id: UUID


@dataclass(frozen=True, slots=True)
class JdCapabilitiesRevision:
    revision_id: UUID
    capabilities: tuple[Capability, ...]
    task_links: tuple[TaskCapabilityLink, ...]


@dataclass(frozen=True, slots=True)
class CreateCapability:
    kind: CapabilityKind
    name: str | None
    description: str | None

    def __post_init__(self) -> None:
        validate_capability_text(self.name, self.description)


@dataclass(frozen=True, slots=True)
class CapabilityFieldChange:
    field: CapabilityField
    value: str | None


@dataclass(frozen=True, slots=True)
class ReviseCapability:
    capability_id: UUID
    changes: tuple[CapabilityFieldChange, ...]

    def __post_init__(self) -> None:
        fields = [change.field for change in self.changes]
        if not fields or len(fields) != len(set(fields)):
            raise InvalidCapabilityChangeError("Change at least one field, each field once")


@dataclass(frozen=True, slots=True)
class DeleteCapability:
    capability_id: UUID


@dataclass(frozen=True, slots=True)
class ReorderCapability:
    capability_id: UUID
    before_capability_id: UUID | None


@dataclass(frozen=True, slots=True)
class SetTaskCapability:
    task_id: UUID
    capability_id: UUID
    linked: bool


@dataclass(frozen=True, slots=True)
class ReorderTaskCapability:
    task_id: UUID
    capability_id: UUID
    before_capability_id: UUID | None


type CapabilityChange = (
    CreateCapability
    | ReviseCapability
    | DeleteCapability
    | ReorderCapability
    | SetTaskCapability
    | ReorderTaskCapability
)


@dataclass(frozen=True, slots=True)
class EditJdCapabilities:
    command_id: UUID
    expected_revision_id: UUID
    change: CapabilityChange
