"""Safe identities for damaged consolidation evidence; never execution retry authority."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

type MemoryEvidenceReason = Literal[
    "invalid_intent_payload",
    "missing_consultant_turn",
    "formal_source_mismatch",
    "invalid_failure_payload",
]


@dataclass(frozen=True, slots=True)
class MemoryConsolidationIntent:
    source_id: UUID


@dataclass(frozen=True, slots=True)
class MemoryEvidenceIssue:
    job_file_id: UUID
    execution_id: UUID
    command_id: UUID
    reason: MemoryEvidenceReason


class MemoryEvidenceError(RuntimeError):
    """Known file-scoped evidence damage; callers must let admission roll back first."""

    def __init__(self, issue: MemoryEvidenceIssue) -> None:
        super().__init__(issue.reason)
        self.issue = issue
