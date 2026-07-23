"""One representative real-PostgreSQL product loop for Job Authoring.

This deliberately stays small.  Pure transition and repository invariants have
their own focused suites; this test proves that production reducers, Evidence,
the Authoring service, and persistence compose into the employee-facing loop.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.interview_vnext.domain.commands import (
    ApplyTurnInterpretationCommand,
    AppendEmployeeTurnCommand,
    TransitionSessionCommand,
)
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceSubject,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.hashing import canonical_hash as vnext_hash
from app.interview_vnext.domain.interpretation import (
    DialogueAct,
    EpisodeSignal,
    TurnInterpretationRecord,
)
from app.interview_vnext.domain.reducers import (
    append_employee_turn,
    apply_turn_interpretation,
    transition_session,
)
from app.interview_vnext.domain.session import SessionStatus, session_at
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.support import LiteralEmployeeSpanSupport, QuoteSpan
from app.interview_vnext.domain.transcript import TranscriptRole, TranscriptTurn
from app.interview_vnext.domain.turn_identity import turn_interpretation_id
from app.interview_vnext.persistence.unit_of_work import SqlAlchemyVNextUnitOfWork
from app.job_authoring.commands import (
    CreateJobDocumentCommand,
    CreateTaskProposalCommand,
    EmployeeProposalDecisionCommand,
    EmployeeTaskBundleCommand,
)
from app.job_authoring.contracts import (
    EditableOutputValue,
    EvidenceBasisRef,
    ProposedOutputDraft,
    TaskBundleEditValue,
    TaskBundleProposalDraft,
)
from app.job_authoring.errors import AuthoringError, AuthoringErrorCode
from app.job_authoring.postgres import SqlAlchemyAuthoringUnitOfWork
from app.job_authoring.service import (
    apply_employee_task_bundle,
    create_job_document,
    create_task_proposal,
    decide_task_proposal,
    get_job_document,
    list_task_proposals,
)
from app.job_authoring.transitions import derive_output_id


NOW = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
WORK_FACT = "我每天彙整各門市缺貨明細，完成補貨建議表。"
TASK = "彙整各門市缺貨明細並提出補貨建議"
OUTPUT = "補貨建議表"
TEST_HASH = "sha256:" + "0" * 64


def _authoring_uow(factory):
    return lambda: SqlAlchemyAuthoringUnitOfWork(factory)


async def _persist_evidence_state(factory, ids, *, session_id: UUID, offset: int):
    at = NOW + timedelta(minutes=offset)
    state = InterviewState(
        session=session_at(
            session_id=session_id,
            profile_id=ids.profile_id,
            tenant_id=ids.tenant_id,
            workflow_version="1.0.0",
            reference_snapshot_id="authoring-local-reference",
            now=at,
        )
    )
    state = transition_session(
        state,
        TransitionSessionCommand(
            command_id=uuid4(),
            expected_state_version=0,
            occurred_at=at + timedelta(seconds=1),
            target_status=SessionStatus.ACTIVE,
        ),
    ).state
    turn = TranscriptTurn(
        turn_id=uuid4(),
        session_id=session_id,
        client_turn_id=f"employee-{session_id}",
        sequence=1,
        role=TranscriptRole.EMPLOYEE,
        text=WORK_FACT,
        previous_turn_id=None,
        occurred_at=at + timedelta(seconds=2),
        received_at=at + timedelta(seconds=2),
    )
    state = append_employee_turn(
        state,
        AppendEmployeeTurnCommand(
            command_id=uuid4(),
            expected_state_version=state.session.state_version,
            occurred_at=turn.occurred_at,
            turn=turn,
        ),
    ).state
    operation_id = uuid4()
    evidence = Evidence(
        evidence_id=uuid4(),
        session_id=session_id,
        subject=EvidenceSubject.EMPLOYEE,
        kind=EvidenceKind.ACTION,
        claim=TASK,
        support=LiteralEmployeeSpanSupport(
            employee_turn_id=turn.turn_id,
            quote=WORK_FACT,
            span=QuoteSpan(start=0, end=len(WORK_FACT)),
        ),
        qualifiers=EvidenceQualifiers(
            time_scope=TimeScope.CURRENT,
            typicality=Typicality.TYPICAL,
            polarity=Polarity.AFFIRMED,
            ownership=Ownership.OWNER,
        ),
        extractor_operation_id=operation_id,
    )
    applied_at = at + timedelta(seconds=3)
    receipt = TurnInterpretationRecord(
        interpretation_id=turn_interpretation_id(operation_id),
        session_id=session_id,
        employee_turn_id=turn.turn_id,
        operation_id=operation_id,
        context_packet_hash=TEST_HASH,
        output_hash=TEST_HASH,
        verification_report_hash=TEST_HASH,
        accepted_evidence_ids=(evidence.evidence_id,),
        dialogue_act=DialogueAct.STANDALONE_ANSWER,
        episode_signal=EpisodeSignal.CONTINUE,
        applied_at=applied_at,
    )
    state = apply_turn_interpretation(
        state,
        ApplyTurnInterpretationCommand(
            command_id=uuid4(),
            expected_state_version=state.session.state_version,
            occurred_at=applied_at,
            record=receipt,
            observations=(evidence,),
        ),
    ).state
    async with SqlAlchemyVNextUnitOfWork(factory) as uow:
        await uow.sessions.create(tenant_id=ids.tenant_id, state=state)
        await uow.commit()
    return state, evidence, at + timedelta(seconds=4)


async def _new_document(factory, ids, *, offset: int):
    session_id = uuid4()
    state, evidence, at = await _persist_evidence_state(
        factory, ids, session_id=session_id, offset=offset
    )
    command = CreateJobDocumentCommand(
        command_id=uuid4(),
        tenant_id=ids.tenant_id,
        session_id=session_id,
        job_title="門市補貨分析人員",
        occurred_at=at,
    )
    created = await create_job_document(_authoring_uow(factory), command)
    replay = await create_job_document(_authoring_uow(factory), command)
    assert replay.revision == created.revision
    return state, evidence, created.revision, at + timedelta(seconds=1)


async def _new_proposal(factory, ids, state, evidence, revision, *, at):
    basis = EvidenceBasisRef(
        evidence_id=evidence.evidence_id,
        evidence_hash=vnext_hash(evidence),
    )
    command = CreateTaskProposalCommand(
        proposal_id=uuid4(),
        tenant_id=ids.tenant_id,
        session_id=state.session.session_id,
        document_id=revision.document_id,
        base_revision_id=revision.revision_id,
        base_revision_hash=revision.snapshot_hash,
        evidence_state_version=state.session.state_version,
        evidence_state_hash=vnext_hash(state),
        source_kind="scripted",
        source_id=uuid4(),
        draft=TaskBundleProposalDraft(
            statement=TASK,
            evidence_basis=(basis,),
            outputs=(
                ProposedOutputDraft(statement=OUTPUT, evidence_basis=(basis,)),
            ),
            plain_language_reason="根據員工已確認的日常工作建立建議",
        ),
        created_at=at,
    )
    created = await create_task_proposal(_authoring_uow(factory), command)
    replay = await create_task_proposal(_authoring_uow(factory), command)
    assert replay.proposal == created.proposal
    assert created.digest.revision_number == 0
    return created, at + timedelta(seconds=1)


def _decision(ids, revision, proposal_id, *, action, at, edited_value=None):
    return EmployeeProposalDecisionCommand(
        command_id=uuid4(),
        tenant_id=ids.tenant_id,
        document_id=revision.document_id,
        proposal_id=proposal_id,
        expected_revision_id=revision.revision_id,
        expected_revision_hash=revision.snapshot_hash,
        action=action,
        edited_value=edited_value,
        occurred_at=at,
    )


async def test_employee_and_ai_build_a_document_through_proposals(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    uow_factory = _authoring_uow(postgres_session_factory)

    # Accept: an AI proposal is inert until the employee accepts it.
    state, evidence, revision0, at = await _new_document(
        postgres_session_factory, ids, offset=0
    )
    proposed, at = await _new_proposal(
        postgres_session_factory, ids, state, evidence, revision0, at=at
    )
    assert (await get_job_document(uow_factory, ids.tenant_id, revision0.document_id)).snapshot.tasks == ()
    accept = _decision(
        ids,
        revision0,
        proposed.proposal.proposal.proposal_id,
        action="accept",
        at=at,
    )
    accepted = await decide_task_proposal(uow_factory, accept)
    accepted_replay = await decide_task_proposal(uow_factory, accept)
    assert accepted_replay.revision == accepted.revision
    accepted_task = accepted.revision.snapshot.tasks[0]
    assert (accepted_task.statement, accepted_task.outputs[0].statement) == (TASK, OUTPUT)
    assert accepted_task.provenance.source_kind == "accepted_ai_proposal"

    # Edit: employee wording, not the AI draft, becomes the committed document.
    state, evidence, revision0, at = await _new_document(
        postgres_session_factory, ids, offset=10
    )
    proposed, at = await _new_proposal(
        postgres_session_factory, ids, state, evidence, revision0, at=at
    )
    proposed_output = proposed.proposal.proposal.proposed_task.outputs[0]
    edited_value = TaskBundleEditValue(
        statement="分析缺貨原因並提出各門市補貨建議",
        outputs=(
            EditableOutputValue(
                output_id=proposed_output.output_id,
                statement="經員工確認的補貨建議表",
            ),
        ),
    )
    edit = _decision(
        ids,
        revision0,
        proposed.proposal.proposal.proposal_id,
        action="edit",
        edited_value=edited_value,
        at=at,
    )
    edited = await decide_task_proposal(uow_factory, edit)
    assert edited.revision.snapshot.tasks[0].statement == edited_value.statement
    assert edited.revision.snapshot.tasks[0].provenance.source_kind == "employee_proposal_edit"

    # Reject: the proposal is remembered, while the document remains unchanged.
    state, evidence, revision0, at = await _new_document(
        postgres_session_factory, ids, offset=20
    )
    proposed, at = await _new_proposal(
        postgres_session_factory, ids, state, evidence, revision0, at=at
    )
    reject = _decision(
        ids,
        revision0,
        proposed.proposal.proposal.proposal_id,
        action="reject",
        at=at,
    )
    rejected = await decide_task_proposal(uow_factory, reject)
    rejected_replay = await decide_task_proposal(uow_factory, reject)
    assert rejected_replay.proposal == rejected.proposal
    assert (await get_job_document(uow_factory, ids.tenant_id, revision0.document_id)).revision_number == 0

    # Direct employee editing advances the document and safely invalidates an
    # older AI proposal. A later replace preserves task identity and position.
    state, evidence, revision0, at = await _new_document(
        postgres_session_factory, ids, offset=30
    )
    proposed, at = await _new_proposal(
        postgres_session_factory, ids, state, evidence, revision0, at=at
    )
    add = EmployeeTaskBundleCommand(
        command_id=uuid4(),
        tenant_id=ids.tenant_id,
        document_id=revision0.document_id,
        expected_revision_id=revision0.revision_id,
        expected_revision_hash=revision0.snapshot_hash,
        action="add",
        target_task_id=None,
        expected_target_version=None,
        value=TaskBundleEditValue(
            statement="由員工直接新增的盤點工作",
            outputs=(EditableOutputValue(output_id=None, statement="盤點紀錄"),),
        ),
        occurred_at=at,
    )
    added = await apply_employee_task_bundle(uow_factory, add)
    assert (await apply_employee_task_bundle(uow_factory, add)).revision == added.revision
    proposals = await list_task_proposals(
        uow_factory, ids.tenant_id, revision0.document_id
    )
    assert proposals[0].status == "stale"
    with pytest.raises(AuthoringError) as stale_decision:
        await decide_task_proposal(
            uow_factory,
            _decision(
                ids,
                revision0,
                proposed.proposal.proposal.proposal_id,
                action="accept",
                at=at + timedelta(seconds=1),
            ),
        )
    assert stale_decision.value.code == AuthoringErrorCode.PROPOSAL_ALREADY_DECIDED

    target = added.revision.snapshot.tasks[0]
    replace_command_id = uuid4()
    replace = EmployeeTaskBundleCommand(
        command_id=replace_command_id,
        tenant_id=ids.tenant_id,
        document_id=revision0.document_id,
        expected_revision_id=added.revision.revision_id,
        expected_revision_hash=added.revision.snapshot_hash,
        action="replace",
        target_task_id=target.task_id,
        expected_target_version=target.entity_version,
        value=TaskBundleEditValue(
            statement="由員工修訂的盤點與補貨工作",
            outputs=(
                EditableOutputValue(
                    output_id=target.outputs[0].output_id,
                    statement="盤點紀錄",
                ),
                EditableOutputValue(output_id=None, statement="補貨清單"),
            ),
        ),
        occurred_at=at + timedelta(seconds=2),
    )
    replaced = await apply_employee_task_bundle(uow_factory, replace)
    final_task = replaced.revision.snapshot.tasks[0]
    assert final_task.task_id == target.task_id
    assert final_task.entity_version == 2
    assert final_task.outputs[1].output_id == derive_output_id(replace_command_id, 2)
    reopened = await get_job_document(uow_factory, ids.tenant_id, revision0.document_id)
    assert reopened == replaced.revision
    assert replaced.digest.revision_number == 2
