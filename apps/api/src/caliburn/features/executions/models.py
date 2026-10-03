"""Execution identity and eligibility passed by the App, never supplied by a model."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ExecutionKind(StrEnum):
    CONSULTANT_TURN = "consultant_turn"
    MEMORY_BATCH = "memory_batch"


class ExecutionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ExecutionBusyError(RuntimeError):
    """This job file already has an active or paused execution of the same kind."""


class ExecutionNotFoundError(LookupError):
    """The execution does not belong to the requested scope."""


class ExecutionStateError(RuntimeError):
    """The requested operation cannot use this execution's current eligibility."""


class StaleWriterError(ExecutionStateError):
    """The worker was superseded; late results cannot produce business effects."""


@dataclass(frozen=True, slots=True)
class ExecutionScope:
    job_file_id: UUID
    execution_id: UUID
    kind: ExecutionKind


@dataclass(frozen=True, slots=True)
class ExecutionInfo:
    scope: ExecutionScope
    status: ExecutionStatus
    writer_id: UUID | None
    pause_requested: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionWriter:
    scope: ExecutionScope
    writer_id: UUID
