"""Focused real-PostgreSQL checks for the Authoring persistence boundary.

This is intentionally a small invariant suite: canonical round-trip, real row
locks, bounded digest projection, terminal decision identity, rollback, and one
representative corruption vector.  Product transaction paths live in the A3
vertical test rather than being duplicated here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from app.interview_vnext.domain.hashing import canonical_hash as vnext_hash
from app.interview_vnext.domain.session import session_at
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.persistence.unit_of_work import SqlAlchemyVNextUnitOfWork
from app.job_authoring.commands import (
    CreateJobDocumentCommand,
    EmployeeProposalDecisionCommand,
)
from app.job_authoring.contracts import (
    AiTaskBundleProposal,
    EmployeeProposalDecision,
    EvidenceBasisRef,
    ProposedJobOutput,
    ProposedJobTask,
)
from app.job_authoring.digest import build_job_state_digest
from app.job_authoring.errors import AuthoringError, PersistedAuthoringCorruption
from app.job_authoring.ports import AuthoringDocumentRecord
from app.job_authoring.postgres import SqlAlchemyAuthoringUnitOfWork
from app.job_authoring.transitions import create_initial_document


NOW = datetime(2026, 7, 23, 4, 0, tzinfo=UTC)
HASH = "sha256:" + "a" * 64


async def _bootstrap(factory, ids):
    state = InterviewState(
        session=session_at(
            session_id=ids.session_id,
            profile_id=ids.profile_id,
            tenant_id=ids.tenant_id,
            workflow_version="1.0.0",
            reference_snapshot_id="authoring-local-reference",
            now=NOW,
        )
    )
    async with SqlAlchemyVNextUnitOfWork(factory) as uow:
        await uow.sessions.create(tenant_id=ids.tenant_id, state=state)
        await uow.commit()

    command = CreateJobDocumentCommand(
        command_id=uuid4(),
        tenant_id=ids.tenant_id,
        session_id=ids.session_id,
        job_title="單機測試職務",
        occurred_at=NOW,
    )
    revision = create_initial_document(command)
    record = AuthoringDocumentRecord(
        document_id=revision.document_id,
        tenant_id=ids.tenant_id,
        session_id=ids.session_id,
        head_revision_id=revision.revision_id,
        head_revision_number=revision.revision_number,
        head_revision_hash=revision.snapshot_hash,
        created_at=NOW,
        updated_at=NOW,
    )
    async with SqlAlchemyAuthoringUnitOfWork(factory) as uow:
        await uow.documents.add(record)
        await uow.revisions.add(ids.tenant_id, revision, command)
        await uow.commit()
    return state, revision


def _proposal(ids, revision, *, proposal_id: UUID, created_at: datetime):
    task_basis = (EvidenceBasisRef(evidence_id=uuid4(), evidence_hash=HASH),)
    output_basis = (EvidenceBasisRef(evidence_id=uuid4(), evidence_hash=HASH),)
    return AiTaskBundleProposal(
        proposal_id=proposal_id,
        session_id=ids.session_id,
        document_id=revision.document_id,
        base_revision_id=revision.revision_id,
        base_revision_hash=revision.snapshot_hash,
        evidence_state_version=0,
        evidence_state_hash=HASH,
        operation="add_task",
        proposed_task=ProposedJobTask(
            task_id=uuid4(),
            statement="彙整缺貨明細並提出補貨建議",
            outputs=(
                ProposedJobOutput(
                    output_id=uuid4(),
                    statement="補貨建議表",
                    evidence_basis=output_basis,
                ),
            ),
            evidence_basis=task_basis,
        ),
        plain_language_reason="根據目前已確認的工作內容提出",
        limitations=(),
        source_kind="scripted",
        source_id=uuid4(),
        created_at=created_at,
    )


async def test_round_trip_evidence_bridge_and_real_share_lock(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    state, revision = await _bootstrap(postgres_session_factory, ids)

    async with SqlAlchemyAuthoringUnitOfWork(postgres_session_factory) as uow:
        document = await uow.documents.get(
            ids.tenant_id, revision.document_id, lock="share"
        )
        evidence = await uow.evidence.lock_session_state(
            ids.tenant_id, ids.session_id
        )
        assert document is not None and document.head_revision_hash == revision.snapshot_hash
        assert evidence.state_hash == vnext_hash(state)
        assert evidence.active_evidence == ()

        async with postgres_session_factory() as competing:
            await competing.execute(sa.text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(DBAPIError):
                await competing.execute(
                    sa.text(
                        "UPDATE job_authoring_documents SET updated_at=:updated "
                        "WHERE tenant_id=:tenant AND document_id=:document"
                    ),
                    {
                        "updated": NOW + timedelta(seconds=1),
                        "tenant": str(ids.tenant_id),
                        "document": str(revision.document_id),
                    },
                )
            await competing.rollback()


async def test_digest_query_is_bounded_but_keeps_total_and_list_order(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    _, revision = await _bootstrap(postgres_session_factory, ids)
    proposals = tuple(
        _proposal(
            ids,
            revision,
            proposal_id=UUID(int=index),
            created_at=NOW + timedelta(seconds=17 - index),
        )
        for index in range(1, 18)
    )
    async with SqlAlchemyAuthoringUnitOfWork(postgres_session_factory) as uow:
        for proposal in proposals:
            await uow.proposals.add(ids.tenant_id, proposal)
        summary = await uow.proposals.list_for_digest(
            ids.tenant_id, revision.document_id
        )
        listed = await uow.proposals.list(
            ids.tenant_id, revision.document_id, statuses=("pending",)
        )
        digest = build_job_state_digest(
            revision,
            pending_proposals=summary.pending,
            pending_proposal_count=summary.pending_count,
            stale_proposal_count=summary.stale_count,
        )
        await uow.commit()

    expected = sorted(proposals, key=lambda item: (item.created_at, item.proposal_id))
    assert summary.pending_count == 17 and len(summary.pending) == 16
    assert digest.pending_proposal_count == 17
    assert tuple(item.view.proposal.proposal_id for item in listed) == tuple(
        item.proposal_id for item in expected
    )


async def test_decision_identity_lookup_collision_and_zero_row(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    _, revision = await _bootstrap(postgres_session_factory, ids)
    first = _proposal(ids, revision, proposal_id=uuid4(), created_at=NOW)
    second = _proposal(
        ids, revision, proposal_id=uuid4(), created_at=NOW + timedelta(seconds=1)
    )
    command_id = uuid4()
    first_decision = EmployeeProposalDecision(
        command_id=command_id,
        proposal_id=first.proposal_id,
        action="reject",
        base_revision_id=revision.revision_id,
        base_revision_hash=revision.snapshot_hash,
        final_task=None,
        result_revision_id=None,
        decided_at=NOW + timedelta(seconds=2),
    )
    async with SqlAlchemyAuthoringUnitOfWork(postgres_session_factory) as uow:
        await uow.proposals.add(ids.tenant_id, first)
        await uow.proposals.add(ids.tenant_id, second)
        assert await uow.proposals.decide(
            ids.tenant_id,
            first.proposal_id,
            status="rejected",
            decision=first_decision,
            result_revision_id=None,
            stale_reason=None,
            resolved_at=first_decision.decided_at,
            updated_at=first_decision.decided_at,
        )
        assert not await uow.proposals.decide(
            ids.tenant_id,
            uuid4(),
            status="rejected",
            decision=first_decision,
            result_revision_id=None,
            stale_reason=None,
            resolved_at=first_decision.decided_at,
            updated_at=first_decision.decided_at,
        )
        await uow.commit()

    async with SqlAlchemyAuthoringUnitOfWork(postgres_session_factory) as uow:
        replay = await uow.proposals.get_by_decision_command_id(
            ids.tenant_id, command_id
        )
        assert replay is not None and replay.view.status == "rejected"
        collision = first_decision.model_copy(
            update={"proposal_id": second.proposal_id}
        )
        with pytest.raises(AuthoringError) as excinfo:
            await uow.proposals.decide(
                ids.tenant_id,
                second.proposal_id,
                status="rejected",
                decision=collision,
                result_revision_id=None,
                stale_reason=None,
                resolved_at=collision.decided_at,
                updated_at=collision.decided_at,
            )
        assert excinfo.value.code == "authoring_idempotency_conflict"


async def test_uow_without_commit_rolls_back_and_head_corruption_fails_closed(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    state = InterviewState(
        session=session_at(
            session_id=ids.session_id,
            profile_id=ids.profile_id,
            tenant_id=ids.tenant_id,
            workflow_version="1.0.0",
            reference_snapshot_id="authoring-local-reference",
            now=NOW,
        )
    )
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        await uow.sessions.create(tenant_id=ids.tenant_id, state=state)
        await uow.commit()
    command = CreateJobDocumentCommand(
        command_id=uuid4(), tenant_id=ids.tenant_id, session_id=ids.session_id,
        job_title="rollback", occurred_at=NOW
    )
    revision = create_initial_document(command)
    record = AuthoringDocumentRecord(
        document_id=revision.document_id,
        tenant_id=ids.tenant_id,
        session_id=ids.session_id,
        head_revision_id=revision.revision_id,
        head_revision_number=0,
        head_revision_hash=revision.snapshot_hash,
        created_at=NOW,
        updated_at=NOW,
    )
    async with SqlAlchemyAuthoringUnitOfWork(postgres_session_factory) as uow:
        await uow.documents.add(record)
        await uow.revisions.add(ids.tenant_id, revision, command)
        # no commit: both rows must disappear
    async with postgres_session_factory() as session:
        assert await session.scalar(
            sa.text(
                "SELECT count(*) FROM job_authoring_documents WHERE tenant_id=:tenant"
            ),
            {"tenant": str(ids.tenant_id)},
        ) == 0

    _, revision = await _bootstrap_fresh_document(
        postgres_session_factory, ids, state_already_exists=True
    )
    async with postgres_session_factory() as session:
        await session.execute(
            sa.text(
                "UPDATE job_authoring_documents SET head_revision_hash=:bad "
                "WHERE tenant_id=:tenant"
            ),
            {"bad": HASH, "tenant": str(ids.tenant_id)},
        )
        await session.commit()
    async with SqlAlchemyAuthoringUnitOfWork(postgres_session_factory) as uow:
        with pytest.raises(PersistedAuthoringCorruption):
            await uow.documents.get(ids.tenant_id, revision.document_id)


async def _bootstrap_fresh_document(factory, ids, *, state_already_exists: bool):
    if not state_already_exists:
        return await _bootstrap(factory, ids)
    command = CreateJobDocumentCommand(
        command_id=uuid4(), tenant_id=ids.tenant_id, session_id=ids.session_id,
        job_title="單機測試職務", occurred_at=NOW
    )
    revision = create_initial_document(command)
    record = AuthoringDocumentRecord(
        document_id=revision.document_id, tenant_id=ids.tenant_id,
        session_id=ids.session_id, head_revision_id=revision.revision_id,
        head_revision_number=0, head_revision_hash=revision.snapshot_hash,
        created_at=NOW, updated_at=NOW
    )
    async with SqlAlchemyAuthoringUnitOfWork(factory) as uow:
        await uow.documents.add(record)
        await uow.revisions.add(ids.tenant_id, revision, command)
        await uow.commit()
    return None, revision
