"""App-bound plan coordinates and prepared full effects; no transport or ORM types."""

from dataclasses import dataclass
from uuid import UUID


class PlanStateError(ValueError):
    """A plan candidate or retained position is invalid or unavailable."""


class PlanConflictError(PlanStateError):
    """An original operation identity was reused with another saved intent."""


class StalePlanPositionError(PlanStateError):
    """A new operation no longer addresses this Turn's current revision."""


@dataclass(frozen=True, slots=True)
class PlanPosition:
    job_file_id: UUID
    execution_id: UUID
    revision_id: UUID


@dataclass(frozen=True, slots=True)
class PlanSnapshot:
    position: PlanPosition
    body: str | None


@dataclass(frozen=True, slots=True)
class PlanEdit:
    operation_id: UUID
    position: PlanPosition
    diff: str
    next_plan: str | None
    result_text: str


@dataclass(frozen=True, slots=True)
class PlanEditResult:
    snapshot: PlanSnapshot
    result_text: str


@dataclass(frozen=True, slots=True)
class QualifiedPlanTurn:
    execution_id: UUID
    employee_input_sequence: int
