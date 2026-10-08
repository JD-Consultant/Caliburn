"""App-owned candidate coordinates; no model parameters or second JD body."""

from dataclasses import dataclass
from uuid import UUID


class CandidateStateError(RuntimeError):
    """The candidate is closed, outside scope or on a superseded recovery branch."""


@dataclass(frozen=True, slots=True)
class JdCandidateScope:
    execution_id: UUID
    generation_id: UUID


@dataclass(frozen=True, slots=True)
class JdCandidatePosition:
    scope: JdCandidateScope
    base_revision_id: UUID
    revision_id: UUID
