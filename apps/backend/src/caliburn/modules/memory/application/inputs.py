"""Memory 內部寫入的必要座標。"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MemoryWriteContext:
    workspace_id: UUID
    expected_version: int
    analysis_id: UUID
