"""Typed error contract for the Job Authoring Core (plan §8).

The application never leaks SQLAlchemy/Pydantic exceptions to callers. Every
validation/conflict raises ``AuthoringError`` with a stable ``code``; the
committed business outcomes (revision committed, proposal created/rejected/
staled, no-op) are the discriminated result union added alongside the digest.
"""

from __future__ import annotations

from enum import StrEnum


class AuthoringErrorCode(StrEnum):
    DOCUMENT_NOT_FOUND = "authoring_document_not_found"
    DOCUMENT_ALREADY_EXISTS = "authoring_document_already_exists"
    REVISION_CONFLICT = "authoring_revision_conflict"
    TASK_NOT_FOUND = "authoring_task_not_found"
    TASK_VERSION_CONFLICT = "authoring_task_version_conflict"
    OUTPUT_SCOPE_INVALID = "authoring_output_scope_invalid"
    CAPACITY_EXCEEDED = "authoring_capacity_exceeded"
    NO_SEMANTIC_CHANGE = "authoring_no_semantic_change"
    PROPOSAL_NOT_FOUND = "authoring_proposal_not_found"
    PROPOSAL_ALREADY_DECIDED = "authoring_proposal_already_decided"
    PROPOSAL_STALE = "authoring_proposal_stale"
    EVIDENCE_INVALID = "authoring_evidence_invalid"
    IDEMPOTENCY_CONFLICT = "authoring_idempotency_conflict"
    PERSISTED_CORRUPTION = "persisted_authoring_corruption"


class AuthoringError(Exception):
    """Typed application error carrying a stable code and optional details."""

    def __init__(self, code: AuthoringErrorCode | str, message: str = "", **details):
        self.code = AuthoringErrorCode(code)
        self.details = details
        super().__init__(message or self.code.value)


class PersistedAuthoringCorruption(AuthoringError):
    """Raised when persisted bytes/hash/scope disagree with the payload.

    Fail closed (plan §6.3): never self-repair or skip a corrupt row.
    """

    def __init__(self, message: str = "", **details):
        super().__init__(AuthoringErrorCode.PERSISTED_CORRUPTION, message, **details)
