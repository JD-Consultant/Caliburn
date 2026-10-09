"""Facts from JD item deletion and movement; presentation belongs to adapters."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class JdItemDeletionResult:
    revision_id: UUID
    detached_task_count: int


@dataclass(frozen=True, slots=True)
class JdItemMovementResult:
    revision_id: UUID
    effect: Literal["moved", "unchanged"]
    detached_from_area: bool
