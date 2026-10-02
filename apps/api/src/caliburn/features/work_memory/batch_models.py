"""Small parent/role handoff contract; native contents remain in the role's saver."""

from dataclasses import dataclass
from uuid import UUID

from caliburn.features.executions.models import ExecutionWriter
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.models import MemorySourceWindow


@dataclass(frozen=True, slots=True)
class MemoryBatchWork:
    writer: ExecutionWriter
    position: MemoryBatchPosition
    source_window: MemorySourceWindow


@dataclass(frozen=True, slots=True)
class MemoryConsolidationIntent:
    job_file_id: UUID
    execution_id: UUID
    source_id: UUID
