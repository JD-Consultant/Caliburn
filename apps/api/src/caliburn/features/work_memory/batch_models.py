"""Small parent/role handoff contract; native contents remain in the role's saver."""

from dataclasses import dataclass

from caliburn.features.executions.models import ExecutionWriter
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.models import MemorySourceWindow


@dataclass(frozen=True, slots=True)
class MemoryBatchWork:
    writer: ExecutionWriter
    position: MemoryBatchPosition
    source_window: MemorySourceWindow
