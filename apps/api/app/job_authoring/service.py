"""Application use cases for the minimal Job Authoring product loop.

The service owns short transactions and lock ordering.  Pure transitions own
document semantics; repositories own canonical persistence.  There is no HTTP,
provider, editor, organization, or SaaS policy in this module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import Field

from .canonical import canonical_hash
from .commands import (
    CreateJobDocumentCommand,
    CreateTaskProposalCommand,
    EmployeeProposalDecisionCommand,
    EmployeeTaskBundleCommand,
)
from .contracts import (
    AuthoringModel,
    JobDocumentRevision,
    JobStateDigest,
    ProposalStaleReason,
    TaskProposalView,
)
from .digest import build_job_state_digest
from .errors import AuthoringError, AuthoringErrorCode
from .ports import (
    AuthoringDocumentRecord,
    AuthoringRevisionRecord,
    AuthoringUnitOfWork,
    EvidenceSourceSnapshot,
    ProposalStatus,
)
from .transitions import (
    apply_direct_add,
    apply_direct_replace,
    build_proposal,
    build_reject_decision,
    create_initial_document,
    materialize_accept,
    materialize_edit,
)


UowFactory: TypeAlias = Callable[[], AuthoringUnitOfWork]
ALL_PROPOSAL_STATUSES: tuple[ProposalStatus, ...] = (
    "pending",
    "accepted",
    "edited",
    "rejected",
    "stale",
)


class AuthoringRevisionCommitted(AuthoringModel):
    outcome: Literal["revision_committed"] = "revision_committed"
    revision: JobDocumentRevision
    digest: JobStateDigest
    proposal: TaskProposalView | None = None


class AuthoringProposalCreated(AuthoringModel):
    outcome: Literal["proposal_created"] = "proposal_created"
    proposal: TaskProposalView
    digest: JobStateDigest


class AuthoringProposalRejected(AuthoringModel):
    outcome: Literal["proposal_rejected"] = "proposal_rejected"
    proposal: TaskProposalView
    digest: JobStateDigest


class AuthoringProposalStaled(AuthoringModel):
    outcome: Literal["proposal_staled"] = "proposal_staled"
    proposal: TaskProposalView
    digest: JobStateDigest
    reason_code: ProposalStaleReason


class AuthoringNoSemanticChange(AuthoringModel):
    outcome: Literal["no_semantic_change"] = "no_semantic_change"
    revision: JobDocumentRevision
    digest: JobStateDigest


AuthoringWriteResult = Annotated[
    AuthoringRevisionCommitted
    | AuthoringProposalCreated
    | AuthoringProposalRejected
    | AuthoringProposalStaled
    | AuthoringNoSemanticChange,
    Field(discriminator="outcome"),
]


def _active_map(snapshot: EvidenceSourceSnapshot) -> dict[UUID, str]:
    return {item.evidence_id: item.evidence_hash for item in snapshot.active_evidence}


async def _head_revision(
    uow: AuthoringUnitOfWork,
    tenant_id: UUID,
    record: AuthoringDocumentRecord,
) -> JobDocumentRevision:
    stored = await uow.revisions.get(tenant_id, record.head_revision_id)
    if stored is None:
        # documents.get already performs this closure check; keep the service
        # fail-closed if a fake/custom repository violates the port contract.
        raise AuthoringError(AuthoringErrorCode.PERSISTED_CORRUPTION)
    return stored.revision


async def _digest(
    uow: AuthoringUnitOfWork, tenant_id: UUID, revision: JobDocumentRevision
) -> JobStateDigest:
    summary = await uow.proposals.list_for_digest(tenant_id, revision.document_id)
    return build_job_state_digest(
        revision,
        pending_proposals=summary.pending,
        pending_proposal_count=summary.pending_count,
        stale_proposal_count=summary.stale_count,
    )


def _require_same_command(
    stored: AuthoringRevisionRecord,
    command: CreateJobDocumentCommand
    | EmployeeTaskBundleCommand
    | EmployeeProposalDecisionCommand,
) -> None:
    if (
        stored.command_schema_id != command.schema_version
        or stored.command_hash != canonical_hash(command)
    ):
        raise AuthoringError(AuthoringErrorCode.IDEMPOTENCY_CONFLICT)


def _proposal_claimed_evidence(command: CreateTaskProposalCommand) -> dict[UUID, str]:
    refs = list(command.draft.evidence_basis)
    for output in command.draft.outputs:
        refs.extend(output.evidence_basis)
    return {ref.evidence_id: ref.evidence_hash for ref in refs}


def _proposal_from_command(command: CreateTaskProposalCommand):
    """Deterministic payload for idempotency checks, without reasserting liveness."""

    return build_proposal(command, _proposal_claimed_evidence(command))


async def create_job_document(
    uow_factory: UowFactory, command: CreateJobDocumentCommand
) -> AuthoringRevisionCommitted:
    expected = create_initial_document(command)
    async with uow_factory() as uow:
        existing = await uow.revisions.get_by_command_id(
            command.tenant_id, command.command_id
        )
        if existing is not None:
            _require_same_command(existing, command)
            digest = await _digest(uow, command.tenant_id, existing.revision)
            return AuthoringRevisionCommitted(revision=existing.revision, digest=digest)

        # The session row is the existing local-workspace authority and gives
        # the document FK a stable parent. No organization/SaaS behavior lives here.
        await uow.evidence.lock_session_state(command.tenant_id, command.session_id)
        existing_document = await uow.documents.get_by_session(
            command.tenant_id, command.session_id, lock="update"
        )
        if existing_document is not None:
            raise AuthoringError(AuthoringErrorCode.DOCUMENT_ALREADY_EXISTS)

        record = AuthoringDocumentRecord(
            document_id=expected.document_id,
            tenant_id=command.tenant_id,
            session_id=command.session_id,
            head_revision_id=expected.revision_id,
            head_revision_number=expected.revision_number,
            head_revision_hash=expected.snapshot_hash,
            created_at=command.occurred_at,
            updated_at=command.occurred_at,
        )
        await uow.documents.add(record)
        await uow.revisions.add(command.tenant_id, expected, command)
        digest = await _digest(uow, command.tenant_id, expected)
        await uow.commit()
        return AuthoringRevisionCommitted(revision=expected, digest=digest)


async def get_job_document(
    uow_factory: UowFactory, tenant_id: UUID, document_id: UUID
) -> JobDocumentRevision:
    async with uow_factory() as uow:
        document = await uow.documents.get(tenant_id, document_id, lock="share")
        if document is None:
            raise AuthoringError(AuthoringErrorCode.DOCUMENT_NOT_FOUND)
        return await _head_revision(uow, tenant_id, document)


async def get_job_state_digest(
    uow_factory: UowFactory, tenant_id: UUID, document_id: UUID
) -> JobStateDigest:
    async with uow_factory() as uow:
        document = await uow.documents.get(tenant_id, document_id, lock="share")
        if document is None:
            raise AuthoringError(AuthoringErrorCode.DOCUMENT_NOT_FOUND)
        revision = await _head_revision(uow, tenant_id, document)
        return await _digest(uow, tenant_id, revision)


async def apply_employee_task_bundle(
    uow_factory: UowFactory, command: EmployeeTaskBundleCommand
) -> AuthoringRevisionCommitted | AuthoringNoSemanticChange:
    async with uow_factory() as uow:
        existing = await uow.revisions.get_by_command_id(
            command.tenant_id, command.command_id
        )
        if existing is not None:
            _require_same_command(existing, command)
            digest = await _digest(uow, command.tenant_id, existing.revision)
            return AuthoringRevisionCommitted(revision=existing.revision, digest=digest)

        document = await uow.documents.get(
            command.tenant_id, command.document_id, lock="update"
        )
        if document is None:
            raise AuthoringError(AuthoringErrorCode.DOCUMENT_NOT_FOUND)
        head = await _head_revision(uow, command.tenant_id, document)
        try:
            revision = (
                apply_direct_add(head, command)
                if command.action == "add"
                else apply_direct_replace(head, command)
            )
        except AuthoringError as exc:
            if exc.code != AuthoringErrorCode.NO_SEMANTIC_CHANGE:
                raise
            return AuthoringNoSemanticChange(
                revision=head,
                digest=await _digest(uow, command.tenant_id, head),
            )

        await uow.revisions.add(command.tenant_id, revision, command)
        updated = await uow.documents.compare_and_set_head(
            command.tenant_id,
            command.document_id,
            expected_revision_id=head.revision_id,
            expected_revision_number=head.revision_number,
            expected_revision_hash=head.snapshot_hash,
            new_revision_id=revision.revision_id,
            new_revision_number=revision.revision_number,
            new_revision_hash=revision.snapshot_hash,
            updated_at=command.occurred_at,
        )
        if not updated:
            raise AuthoringError(AuthoringErrorCode.REVISION_CONFLICT)
        await uow.proposals.mark_other_pending_stale(
            command.tenant_id,
            command.document_id,
            keep_proposal_id=None,
            reason=ProposalStaleReason.DOCUMENT_REVISION_ADVANCED,
            resolved_at=command.occurred_at,
            updated_at=command.occurred_at,
        )
        digest = await _digest(uow, command.tenant_id, revision)
        await uow.commit()
        return AuthoringRevisionCommitted(revision=revision, digest=digest)


async def create_task_proposal(
    uow_factory: UowFactory, command: CreateTaskProposalCommand
) -> AuthoringProposalCreated:
    candidate = _proposal_from_command(command)
    async with uow_factory() as uow:
        existing = await uow.proposals.get(command.tenant_id, command.proposal_id)
        if existing is not None:
            if existing.proposal_hash != canonical_hash(candidate):
                raise AuthoringError(AuthoringErrorCode.IDEMPOTENCY_CONFLICT)
            document = await uow.documents.get(
                command.tenant_id, command.document_id, lock="share"
            )
            if document is None:
                raise AuthoringError(AuthoringErrorCode.DOCUMENT_NOT_FOUND)
            head = await _head_revision(uow, command.tenant_id, document)
            return AuthoringProposalCreated(
                proposal=existing.view,
                digest=await _digest(uow, command.tenant_id, head),
            )

        evidence = await uow.evidence.lock_session_state(
            command.tenant_id, command.session_id
        )
        if (
            evidence.state_version != command.evidence_state_version
            or evidence.state_hash != command.evidence_state_hash
        ):
            raise AuthoringError(AuthoringErrorCode.EVIDENCE_INVALID)
        document = await uow.documents.get(
            command.tenant_id, command.document_id, lock="update"
        )
        if document is None:
            raise AuthoringError(AuthoringErrorCode.DOCUMENT_NOT_FOUND)
        if document.session_id != command.session_id:
            raise AuthoringError(AuthoringErrorCode.EVIDENCE_INVALID)
        head = await _head_revision(uow, command.tenant_id, document)
        if (
            head.revision_id != command.base_revision_id
            or head.snapshot_hash != command.base_revision_hash
        ):
            raise AuthoringError(AuthoringErrorCode.REVISION_CONFLICT)
        proposal = build_proposal(command, _active_map(evidence))
        await uow.proposals.add(command.tenant_id, proposal)
        stored = await uow.proposals.get(
            command.tenant_id, proposal.proposal_id
        )
        if stored is None:
            raise AuthoringError(AuthoringErrorCode.PERSISTED_CORRUPTION)
        digest = await _digest(uow, command.tenant_id, head)
        await uow.commit()
        return AuthoringProposalCreated(proposal=stored.view, digest=digest)


async def list_task_proposals(
    uow_factory: UowFactory,
    tenant_id: UUID,
    document_id: UUID,
    *,
    statuses: tuple[ProposalStatus, ...] = ALL_PROPOSAL_STATUSES,
) -> tuple[TaskProposalView, ...]:
    async with uow_factory() as uow:
        document = await uow.documents.get(tenant_id, document_id, lock="share")
        if document is None:
            raise AuthoringError(AuthoringErrorCode.DOCUMENT_NOT_FOUND)
        records = await uow.proposals.list(
            tenant_id, document_id, statuses=statuses
        )
        return tuple(record.view for record in records)


async def _terminal_replay(
    uow: AuthoringUnitOfWork,
    command: EmployeeProposalDecisionCommand,
) -> AuthoringRevisionCommitted | AuthoringProposalRejected | None:
    revision_record = await uow.revisions.get_by_command_id(
        command.tenant_id, command.command_id
    )
    if revision_record is not None:
        _require_same_command(revision_record, command)
        proposal_record = await uow.proposals.get(
            command.tenant_id, command.proposal_id
        )
        if (
            proposal_record is None
            or proposal_record.view.decision is None
            or proposal_record.view.decision.command_id != command.command_id
        ):
            raise AuthoringError(AuthoringErrorCode.IDEMPOTENCY_CONFLICT)
        return AuthoringRevisionCommitted(
            revision=revision_record.revision,
            digest=await _digest(uow, command.tenant_id, revision_record.revision),
            proposal=proposal_record.view,
        )

    proposal_record = await uow.proposals.get_by_decision_command_id(
        command.tenant_id, command.command_id
    )
    if proposal_record is None:
        return None
    if proposal_record.view.proposal.proposal_id != command.proposal_id:
        raise AuthoringError(AuthoringErrorCode.IDEMPOTENCY_CONFLICT)
    base = await uow.revisions.get(
        command.tenant_id, proposal_record.view.proposal.base_revision_id
    )
    if base is None or proposal_record.view.decision is None:
        raise AuthoringError(AuthoringErrorCode.PERSISTED_CORRUPTION)
    try:
        expected = build_reject_decision(
            base.revision, proposal_record.view.proposal, command
        )
    except AuthoringError as exc:
        raise AuthoringError(AuthoringErrorCode.IDEMPOTENCY_CONFLICT) from exc
    if canonical_hash(expected) != canonical_hash(proposal_record.view.decision):
        raise AuthoringError(AuthoringErrorCode.IDEMPOTENCY_CONFLICT)
    return AuthoringProposalRejected(
        proposal=proposal_record.view,
        digest=await _digest(uow, command.tenant_id, base.revision),
    )


async def _stale_and_commit(
    uow: AuthoringUnitOfWork,
    command: EmployeeProposalDecisionCommand,
    head: JobDocumentRevision,
    reason: ProposalStaleReason,
) -> AuthoringProposalStaled:
    changed = await uow.proposals.decide(
        command.tenant_id,
        command.proposal_id,
        status="stale",
        decision=None,
        result_revision_id=None,
        stale_reason=reason,
        resolved_at=command.occurred_at,
        updated_at=command.occurred_at,
    )
    if not changed:
        raise AuthoringError(AuthoringErrorCode.PROPOSAL_ALREADY_DECIDED)
    stored = await uow.proposals.get(command.tenant_id, command.proposal_id)
    if stored is None:
        raise AuthoringError(AuthoringErrorCode.PERSISTED_CORRUPTION)
    digest = await _digest(uow, command.tenant_id, head)
    await uow.commit()
    return AuthoringProposalStaled(
        proposal=stored.view,
        digest=digest,
        reason_code=reason,
    )


async def decide_task_proposal(
    uow_factory: UowFactory, command: EmployeeProposalDecisionCommand
) -> AuthoringRevisionCommitted | AuthoringProposalRejected | AuthoringProposalStaled:
    async with uow_factory() as uow:
        replay = await _terminal_replay(uow, command)
        if replay is not None:
            return replay

        observed = await uow.proposals.get(command.tenant_id, command.proposal_id)
        if observed is None:
            raise AuthoringError(AuthoringErrorCode.PROPOSAL_NOT_FOUND)
        if observed.view.status != "pending":
            raise AuthoringError(AuthoringErrorCode.PROPOSAL_ALREADY_DECIDED)

        evidence: EvidenceSourceSnapshot | None = None
        if command.action in ("accept", "edit"):
            evidence = await uow.evidence.lock_session_state(
                command.tenant_id, observed.view.proposal.session_id
            )
        document = await uow.documents.get(
            command.tenant_id, command.document_id, lock="update"
        )
        if document is None:
            raise AuthoringError(AuthoringErrorCode.DOCUMENT_NOT_FOUND)
        head = await _head_revision(uow, command.tenant_id, document)
        proposal_record = await uow.proposals.get(
            command.tenant_id, command.proposal_id, for_update=True
        )
        if proposal_record is None:
            raise AuthoringError(AuthoringErrorCode.PROPOSAL_NOT_FOUND)
        if proposal_record.view.status != "pending":
            concurrent = await _terminal_replay(uow, command)
            if concurrent is not None:
                return concurrent
            raise AuthoringError(AuthoringErrorCode.PROPOSAL_ALREADY_DECIDED)
        proposal = proposal_record.view.proposal
        if proposal.document_id != command.document_id:
            raise AuthoringError(AuthoringErrorCode.PROPOSAL_NOT_FOUND)
        if (
            proposal.base_revision_id != head.revision_id
            or proposal.base_revision_hash != head.snapshot_hash
        ):
            return await _stale_and_commit(
                uow,
                command,
                head,
                ProposalStaleReason.BASE_REVISION_CHANGED,
            )

        if command.action == "reject":
            decision = build_reject_decision(head, proposal, command)
            changed = await uow.proposals.decide(
                command.tenant_id,
                command.proposal_id,
                status="rejected",
                decision=decision,
                result_revision_id=None,
                stale_reason=None,
                resolved_at=command.occurred_at,
                updated_at=command.occurred_at,
            )
            if not changed:
                raise AuthoringError(AuthoringErrorCode.PROPOSAL_ALREADY_DECIDED)
            stored = await uow.proposals.get(command.tenant_id, command.proposal_id)
            if stored is None:
                raise AuthoringError(AuthoringErrorCode.PERSISTED_CORRUPTION)
            digest = await _digest(uow, command.tenant_id, head)
            await uow.commit()
            return AuthoringProposalRejected(proposal=stored.view, digest=digest)

        assert evidence is not None
        active = _active_map(evidence)
        try:
            if command.action == "accept":
                revision, decision = materialize_accept(
                    head, proposal, command, active
                )
                terminal_status: ProposalStatus = "accepted"
            else:
                revision, decision = materialize_edit(
                    head, proposal, command, active
                )
                terminal_status = "edited"
        except AuthoringError as exc:
            if exc.code != AuthoringErrorCode.PROPOSAL_STALE:
                raise
            reason = exc.details.get("stale_reason")
            if not isinstance(reason, ProposalStaleReason):
                raise AuthoringError(AuthoringErrorCode.PERSISTED_CORRUPTION) from exc
            return await _stale_and_commit(
                uow, command, head, reason
            )

        await uow.revisions.add(command.tenant_id, revision, command)
        changed = await uow.proposals.decide(
            command.tenant_id,
            command.proposal_id,
            status=terminal_status,
            decision=decision,
            result_revision_id=revision.revision_id,
            stale_reason=None,
            resolved_at=command.occurred_at,
            updated_at=command.occurred_at,
        )
        if not changed:
            raise AuthoringError(AuthoringErrorCode.PROPOSAL_ALREADY_DECIDED)
        updated = await uow.documents.compare_and_set_head(
            command.tenant_id,
            command.document_id,
            expected_revision_id=head.revision_id,
            expected_revision_number=head.revision_number,
            expected_revision_hash=head.snapshot_hash,
            new_revision_id=revision.revision_id,
            new_revision_number=revision.revision_number,
            new_revision_hash=revision.snapshot_hash,
            updated_at=command.occurred_at,
        )
        if not updated:
            raise AuthoringError(AuthoringErrorCode.REVISION_CONFLICT)
        await uow.proposals.mark_other_pending_stale(
            command.tenant_id,
            command.document_id,
            keep_proposal_id=command.proposal_id,
            reason=ProposalStaleReason.DOCUMENT_REVISION_ADVANCED,
            resolved_at=command.occurred_at,
            updated_at=command.occurred_at,
        )
        stored = await uow.proposals.get(command.tenant_id, command.proposal_id)
        if stored is None:
            raise AuthoringError(AuthoringErrorCode.PERSISTED_CORRUPTION)
        digest = await _digest(uow, command.tenant_id, revision)
        await uow.commit()
        return AuthoringRevisionCommitted(
            revision=revision,
            digest=digest,
            proposal=stored.view,
        )
