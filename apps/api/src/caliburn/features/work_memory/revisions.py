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


def _require_layer_references(
    layer: MemoryLayer,
    interview_references: frozenset[UUID],
    work_situation_references: frozenset[MemoryRevisionReference],
) -> None:
    if not isinstance(layer, MemoryLayer):
        raise InvalidMemoryChangeError("Select a defined Memory layer")
    if layer == MemoryLayer.WORK_SITUATION and work_situation_references:
        raise InvalidMemoryChangeError("Work situations may reference interviews only")
    if layer == MemoryLayer.WORK_UNDERSTANDING and interview_references:
        raise InvalidMemoryChangeError("Work understandings may reference situations only")
    if len({ref.object_id for ref in work_situation_references}) != len(work_situation_references):
        raise InvalidMemoryChangeError("Select one fixed revision for each source situation")


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
        _require_layer_references(
            self.layer, self.interview_references, self.work_situation_references
        )

    @property
    def header(self) -> MemoryRevisionHeader:
        return MemoryRevisionHeader(
            self.object_id,
            self.revision_id,
            self.body_id,
            self.layer,
            self.content.title,
            self.content.description,
            self.interview_references,
            self.work_situation_references,
        )


@dataclass(frozen=True, slots=True)
class MemoryRevisionHeader:
    """Fixed content identity and bindings; collection decisions do not need Markdown."""

    object_id: UUID
    revision_id: UUID
    body_id: UUID
    layer: MemoryLayer
    title: str
    description: str
    interview_references: frozenset[UUID]
    work_situation_references: frozenset[MemoryRevisionReference]

    def __post_init__(self) -> None:
        _require_layer_references(
            self.layer, self.interview_references, self.work_situation_references
        )

    def with_body(self, body: str) -> MemoryObjectRevision:
        return MemoryObjectRevision(
            self.object_id,
            self.revision_id,
            self.body_id,
            self.layer,
            MemoryContent(self.title, self.description, body),
            self.interview_references,
            self.work_situation_references,
        )
