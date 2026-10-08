"""App-bound Memory candidate coordinates and typed edit intent; no model wire."""

from dataclasses import dataclass
from uuid import UUID

from caliburn.features.work_memory.models import (
    InvalidMemoryChangeError,
    MemoryContent,
    MemoryContentChanges,
    ReferenceChanges,
)
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionReference


class MemoryCandidateStateError(RuntimeError):
    """The requested candidate, position or stage is unavailable or superseded."""


class MemoryPermissionError(PermissionError):
    """This analysis role cannot read or change the selected layer."""


class MemoryCommandConflictError(ValueError):
    """An original operation identity was reused with different intent."""


@dataclass(frozen=True, slots=True)
class MemoryBatchPosition:
    job_file_id: UUID
    execution_id: UUID
    generation_id: UUID
    stage_id: UUID
    phase: MemoryLayer
    position_id: UUID


@dataclass(frozen=True, slots=True)
class MemoryEditResult:
    position: MemoryBatchPosition
    object_id: UUID


@dataclass(frozen=True, slots=True)
class CreateMemoryObject:
    command_id: UUID
    position: MemoryBatchPosition
    layer: MemoryLayer
    content: MemoryContent
    reference_ids: frozenset[UUID] = frozenset()


@dataclass(frozen=True, slots=True)
class ReviseMemoryObject:
    command_id: UUID
    position: MemoryBatchPosition
    layer: MemoryLayer
    object_id: UUID
    content_changes: MemoryContentChanges | None = None
    reference_changes: ReferenceChanges | None = None

    def __post_init__(self) -> None:
        if self.content_changes is None and self.reference_changes is None:
            raise InvalidMemoryChangeError("Supply a content or reference change")


@dataclass(frozen=True, slots=True)
class DeleteMemoryObject:
    command_id: UUID
    position: MemoryBatchPosition
    layer: MemoryLayer
    object_id: UUID


type MemoryEdit = CreateMemoryObject | ReviseMemoryObject | DeleteMemoryObject


@dataclass(frozen=True, slots=True)
class MemoryCandidateObject:
    """Content revision plus bindings resolved at one current candidate position."""

    object_id: UUID
    content_revision_id: UUID
    layer: MemoryLayer
    content: MemoryContent
    interview_references: frozenset[UUID]
    work_situation_references: frozenset[MemoryRevisionReference]


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    job_file_id: UUID
    snapshot_id: UUID
    position_id: UUID
    through_source_id: UUID
    covered_through_sequence: int


def require_layer_read(role: MemoryLayer, layer: MemoryLayer) -> None:
    if not isinstance(role, MemoryLayer) or not isinstance(layer, MemoryLayer):
        raise MemoryPermissionError("A defined Memory role and layer are required")
    if role == MemoryLayer.WORK_SITUATION and layer == MemoryLayer.WORK_UNDERSTANDING:
        raise MemoryPermissionError("The situation analyst cannot read understandings")


def require_layer_write(role: MemoryLayer, layer: MemoryLayer) -> None:
    require_layer_read(role, layer)
    if role != layer:
        raise MemoryPermissionError("Each analyst may change only its own layer")
