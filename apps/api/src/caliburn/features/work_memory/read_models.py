"""One-read coordinates and typed content projections, not model-supplied handles."""

from dataclasses import dataclass
from uuid import UUID

from caliburn.features.work_memory.models import MemoryContent, MemoryMapEntry
from caliburn.features.work_memory.revisions import MemoryLayer


@dataclass(frozen=True, slots=True)
class MemoryReadView:
    job_file_id: UUID
    position_id: UUID | None
    layer: MemoryLayer
    through_sequence: int


@dataclass(frozen=True, slots=True)
class MemoryObjectReading:
    content: MemoryContent
    interview_source_ids: frozenset[UUID]
    work_situation_references: tuple[MemoryMapEntry, ...]


@dataclass(frozen=True, slots=True)
class MemoryObjectDetails:
    content: MemoryContent
    interview_references: tuple[int, ...]
    work_situation_references: tuple[MemoryMapEntry, ...]
