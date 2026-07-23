"""Application ports for the Job Authoring Core (plan §9.1, §22).

Pure Protocols + frozen records: no SQLAlchemy, no interview vNext domain. Raw
ORM rows, raw JSON, and the full ``InterviewState`` never cross this boundary —
records carry hydrated domain values plus the storage scope and the hashes the
service needs for idempotency.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from .commands import (
    CreateJobDocumentCommand,
    EmployeeProposalDecisionCommand,
    EmployeeTaskBundleCommand,
)
from .contracts import (
    AiTaskBundleProposal,
    AuthoringModel,
    EmployeeProposalDecision,
    EvidenceBasisRef,
    JobDocumentRevision,
    ProposalStaleReason,
    Sha256,
    TaskProposalView,
    UtcDatetime,
)

AuthoringCommand = (
    CreateJobDocumentCommand
    | EmployeeTaskBundleCommand
    | EmployeeProposalDecisionCommand
)
AuthoringDocumentLock = Literal["none", "share", "update"]
ProposalStatus = Literal["pending", "accepted", "edited", "rejected", "stale"]


# --- adapter-boundary records -----------------------------------------------


class AuthoringDocumentRecord(AuthoringModel):
    document_id: UUID
    tenant_id: UUID
    session_id: UUID
    head_revision_id: UUID
    head_revision_number: int
    head_revision_hash: Sha256
    created_at: UtcDatetime
    updated_at: UtcDatetime


class AuthoringRevisionRecord(AuthoringModel):
    tenant_id: UUID
    revision: JobDocumentRevision
    command_schema_id: str
    command_hash: Sha256
    created_at: UtcDatetime


class AuthoringProposalRecord(AuthoringModel):
    tenant_id: UUID
    view: TaskProposalView
    proposal_hash: Sha256
    created_at: UtcDatetime


class EvidenceSourceSnapshot(AuthoringModel):
    tenant_id: UUID
    session_id: UUID
    state_version: int
    state_hash: Sha256
    active_evidence: tuple[EvidenceBasisRef, ...]  # active only, sorted by id.bytes


class DigestProposalSummary(AuthoringModel):
    pending: tuple[tuple[UtcDatetime, UUID], ...]  # <=16, (created_at, proposal_id)
    pending_count: int
    stale_count: int


# --- repository / unit-of-work protocols ------------------------------------


class AuthoringDocumentRepository(Protocol):
    async def get(
        self, tenant_id: UUID, document_id: UUID, *, lock: AuthoringDocumentLock = "none"
    ) -> AuthoringDocumentRecord | None: ...

    async def get_by_session(
        self, tenant_id: UUID, session_id: UUID, *, lock: AuthoringDocumentLock = "none"
    ) -> AuthoringDocumentRecord | None: ...

    async def add(self, record: AuthoringDocumentRecord) -> None: ...

    async def compare_and_set_head(
        self,
        tenant_id: UUID,
        document_id: UUID,
        *,
        expected_revision_id: UUID,
        expected_revision_number: int,
        expected_revision_hash: str,
        new_revision_id: UUID,
        new_revision_number: int,
        new_revision_hash: str,
        updated_at: datetime,
    ) -> bool: ...


class AuthoringRevisionRepository(Protocol):
    async def get(
        self, tenant_id: UUID, revision_id: UUID
    ) -> AuthoringRevisionRecord | None: ...

    async def get_by_command_id(
        self, tenant_id: UUID, command_id: UUID
    ) -> AuthoringRevisionRecord | None: ...

    async def add(
        self,
        tenant_id: UUID,
        revision: JobDocumentRevision,
        command: AuthoringCommand,
    ) -> None: ...


class AuthoringProposalRepository(Protocol):
    async def get(
        self, tenant_id: UUID, proposal_id: UUID, *, for_update: bool = False
    ) -> AuthoringProposalRecord | None: ...

    async def get_by_decision_command_id(
        self, tenant_id: UUID, command_id: UUID
    ) -> AuthoringProposalRecord | None: ...

    async def add(
        self, tenant_id: UUID, proposal: AiTaskBundleProposal
    ) -> None: ...

    async def decide(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
        *,
        status: ProposalStatus,
        decision: EmployeeProposalDecision | None,
        result_revision_id: UUID | None,
        stale_reason: ProposalStaleReason | None,
        resolved_at: datetime,
        updated_at: datetime,
    ) -> bool: ...

    async def mark_other_pending_stale(
        self,
        tenant_id: UUID,
        document_id: UUID,
        *,
        keep_proposal_id: UUID | None,
        reason: ProposalStaleReason,
        resolved_at: datetime,
        updated_at: datetime,
    ) -> tuple[UUID, ...]: ...

    async def list(
        self,
        tenant_id: UUID,
        document_id: UUID,
        *,
        statuses: tuple[ProposalStatus, ...],
    ) -> tuple[AuthoringProposalRecord, ...]: ...

    async def list_for_digest(
        self, tenant_id: UUID, document_id: UUID
    ) -> DigestProposalSummary: ...


class AuthoringEvidenceReader(Protocol):
    async def lock_session_state(
        self, tenant_id: UUID, session_id: UUID
    ) -> EvidenceSourceSnapshot: ...


class AuthoringUnitOfWork(Protocol):
    documents: AuthoringDocumentRepository
    revisions: AuthoringRevisionRepository
    proposals: AuthoringProposalRepository
    evidence: AuthoringEvidenceReader

    async def commit(self) -> None: ...

    async def __aenter__(self) -> "AuthoringUnitOfWork": ...

    async def __aexit__(self, *exc: object) -> None: ...
