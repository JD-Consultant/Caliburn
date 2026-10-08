"""Immutable references to native saver windows; no context payload or persistence."""

from dataclasses import dataclass
from enum import StrEnum

from caliburn.features.executions.models import ExecutionScope


class AgentRole(StrEnum):
    JOB_CONSULTANT = "job_consultant"
    WORK_SITUATION_ANALYST = "work_situation_analyst"
    WORK_UNDERSTANDING_ANALYST = "work_understanding_analyst"


class HistoryWindowKind(StrEnum):
    PREPARED_HISTORY = "prepared_history"
    COMPLETED_WORK = "completed_work"


class HistoryConflictError(RuntimeError):
    """A context reference conflicts with the execution's fixed history or adopted head."""


@dataclass(frozen=True, slots=True)
class ContextPosition:
    thread_id: str
    checkpoint_id: str
    kind: HistoryWindowKind

    def __post_init__(self) -> None:
        if not self.thread_id.strip() or not self.checkpoint_id.strip():
            raise ValueError("Context thread and checkpoint identities must be nonempty")
        if not isinstance(self.kind, HistoryWindowKind):
            raise ValueError("Expected a history window kind")


@dataclass(frozen=True, slots=True)
class ContextBinding:
    role: AgentRole
    base: ContextPosition | None
    prepared: ContextPosition | None
    completed: ContextPosition | None

    def __post_init__(self) -> None:
        if not isinstance(self.role, AgentRole):
            raise ValueError("Expected an agent role")


def context_thread_id(scope: ExecutionScope, role: AgentRole, kind: HistoryWindowKind) -> str:
    if not scope.job_file_id or not scope.execution_id:
        raise ValueError("Context scope identities must be nonempty")
    if not isinstance(role, AgentRole) or not isinstance(kind, HistoryWindowKind):
        raise ValueError("Expected an agent role and history window kind")
    return f"{scope.job_file_id}:{scope.execution_id}:{role.value}:{kind.value}"
