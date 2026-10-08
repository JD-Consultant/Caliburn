"""Fixed Memory object revisions; candidate membership and publication are separate."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from caliburn.features.work_memory.models import InvalidMemoryChangeError, MemoryContent


class MemoryLayer(StrEnum):
    WORK_SITUATION = "work_situation"
    WORK_UNDERSTANDING = "work_understanding"


class MemoryRevisionNotFoundError(LookupError):
    """The requested fixed revision does not exist in this job file."""


@dataclass(frozen=True, slots=True, order=True)
class MemoryRevisionReference:
    object_id: UUID
    revision_id: UUID


@dataclass(frozen=True, slots=True)
class MemoryObjectRevision:
    object_id: UUID
    revision_id: UUID
    body_id: UUID
    layer: MemoryLayer
    content: MemoryContent
    interview_references: frozenset[UUID] = frozenset()
    work_situation_references: frozenset[MemoryRevisionReference] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.layer, MemoryLayer):
            raise InvalidMemoryChangeError("Select a defined Memory layer")
        if self.layer == MemoryLayer.WORK_SITUATION and self.work_situation_references:
            raise InvalidMemoryChangeError("Work situations may reference interviews only")
        if self.layer == MemoryLayer.WORK_UNDERSTANDING and self.interview_references:
            raise InvalidMemoryChangeError("Work understandings may reference situations only")
        if len({ref.object_id for ref in self.work_situation_references}) != len(
            self.work_situation_references
        ):
            raise InvalidMemoryChangeError("Select one fixed revision for each source situation")
