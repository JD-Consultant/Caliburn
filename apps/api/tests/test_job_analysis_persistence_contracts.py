"""Greenfield persistence seam contracts.

These tests intentionally know nothing about SQLAlchemy or PostgreSQL rows.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import get_type_hints
from uuid import uuid4

import pytest
from pydantic import ValidationError

import app.job_analysis.application as application
from app.job_analysis.application import (
    ActiveQuestion,
    CompletedTurnPayload,
    ConversationTurn,
    DirectEditPayload,
    DocumentRecord,
    DocumentSummary,
    JobAnalysisState,
    JobAnalysisUnitOfWork,
    JournalEntry,
    OpksProposalRepository,
    OpksRepository,
    ProposalDecisionPayload,
    TurnSpeaker,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdTask,
    CurrentJdOpks,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    ProposalStatus,
    ResponsibilityRole,
    SourceKind,
    SourceRef,
)


NOW = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)


def jd_task(task_id: str = "task-1") -> JdTask:
    return JdTask(
        task_id=task_id,
        statement="每週彙整營運週報",
        frequency_text="每週一次",
        responsibility_role=ResponsibilityRole.PRIMARY,
        display_order=0,
    )


def employee_turn() -> ConversationTurn:
    return ConversationTurn(
        turn_id="turn-2",
        speaker=TurnSpeaker.EMPLOYEE,
        text="我每週會彙整營運週報",
    )


def consultant_turn() -> ConversationTurn:
    return ConversationTurn(
        turn_id="turn-3",
        speaker=TurnSpeaker.CONSULTANT,
        text="這份週報主要交給誰？",
    )


def output_item() -> OpksItem:
    return OpksItem(
        entity_id="output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=("task-1",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="turn-2",
                ),
                quote="我每週會彙整營運週報",
            ),
        ),
    )


def output_proposal() -> OpksProposal:
    return OpksProposal(
        proposal_id="opks-proposal-1",
        operation_id="opks-operation-1",
        entity_id="output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        action=OpksProposalAction.ADD,
        after=output_item(),
        base_authority_generation=0,
        created_at=NOW,
    )


def test_consultant_opening_is_a_typed_consultant_journal_payload():
    payload_type = getattr(application, "ConsultantOpeningPayload", None)
    assert payload_type is not None
    payload = payload_type(consultant_turn=consultant_turn())
    assert payload.consultant_turn == consultant_turn()

    with pytest.raises(ValidationError, match="consultant"):
        payload_type(consultant_turn=employee_turn())


def test_document_records_are_frozen_and_reject_negative_generation():
    document_id = uuid4()
    record = DocumentRecord(
        document_id=document_id,
        title="門市營運專員",
        work_model=CurrentWorkModel(),
        active_question=ActiveQuestion(
            turn_id="turn-3",
            text="這份週報主要交給誰？",
        ),
        authority_generation=0,
        created_at=NOW,
        updated_at=NOW,
    )
    summary = DocumentSummary(
        document_id=document_id,
        title=record.title,
        task_count=1,
        updated_at=NOW,
    )

    with pytest.raises(FrozenInstanceError):
        record.title = "被改掉"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        summary.task_count = 2  # type: ignore[misc]
    with pytest.raises(ValueError, match="authority_generation"):
        DocumentRecord(
            document_id=document_id,
            title="門市營運專員",
            work_model=CurrentWorkModel(),
            active_question=None,
            authority_generation=-1,
            created_at=NOW,
            updated_at=NOW,
        )


def test_loaded_state_keeps_complete_current_jd_and_opks_values():
    from app.job_analysis.application import LoadedDocument

    document = DocumentRecord(
        document_id=uuid4(),
        title="門市營運專員",
        work_model=CurrentWorkModel(),
        active_question=None,
        authority_generation=0,
        created_at=NOW,
        updated_at=NOW,
    )
    state = JobAnalysisState(
        current_jd=(jd_task(),),
        current_opks=CurrentJdOpks(items=(output_item(),)),
        opks_proposals=(output_proposal(),),
    )

    loaded = LoadedDocument(document=document, state=state, conversation_turns=())

    assert loaded.state.current_jd[0].frequency_text == "每週一次"
    assert loaded.state.current_opks.items == (output_item(),)
    assert loaded.state.opks_proposals == (output_proposal(),)


def test_completed_turn_payload_requires_employee_then_consultant_roles():
    payload = CompletedTurnPayload(
        operation_id="operation-1",
        employee_turn=employee_turn(),
        consultant_turn=consultant_turn(),
    )
    assert payload.consultant_turn.text == "這份週報主要交給誰？"

    with pytest.raises(ValidationError, match="employee_turn"):
        CompletedTurnPayload(
            operation_id="operation-1",
            employee_turn=consultant_turn(),
            consultant_turn=consultant_turn(),
        )
    with pytest.raises(ValidationError, match="consultant_turn"):
        CompletedTurnPayload(
            operation_id="operation-1",
            employee_turn=employee_turn(),
            consultant_turn=employee_turn(),
        )


@pytest.mark.parametrize(
    ("edit_kind", "task_id", "after", "ordered_task_ids"),
    [
        ("add", "task-1", jd_task(), ()),
        ("edit", "task-1", jd_task(), ()),
        ("reorder", None, None, ("task-2", "task-1")),
        ("delete", "task-1", None, ()),
    ],
)
def test_direct_edit_payload_preserves_the_completed_value(
    edit_kind,
    task_id,
    after,
    ordered_task_ids,
):
    payload = DirectEditPayload(
        edit_kind=edit_kind,
        task_id=task_id,
        after=after,
        ordered_task_ids=ordered_task_ids,
    )
    assert payload.after == after
    assert payload.ordered_task_ids == ordered_task_ids


def test_direct_edit_payload_rejects_an_impossible_kind_value_combination():
    with pytest.raises(ValidationError, match="delete"):
        DirectEditPayload(
            edit_kind="delete",
            task_id="task-1",
            after=jd_task(),
            ordered_task_ids=(),
        )
    with pytest.raises(ValidationError, match="requires the completed task"):
        DirectEditPayload(
            edit_kind="edit",
            task_id="task-1",
            after=None,
            ordered_task_ids=(),
        )
    with pytest.raises(ValidationError, match="task id"):
        DirectEditPayload(
            edit_kind="edit",
            task_id="task-1",
            after=jd_task("task-2"),
            ordered_task_ids=(),
        )
    with pytest.raises(ValidationError, match="reorder"):
        DirectEditPayload(
            edit_kind="reorder",
            task_id="task-1",
            after=None,
            ordered_task_ids=("task-1",),
        )
    with pytest.raises(ValidationError, match="distinct"):
        DirectEditPayload(
            edit_kind="reorder",
            task_id=None,
            after=None,
            ordered_task_ids=("task-1", "task-1"),
        )


def test_journal_kind_schema_and_payload_must_agree_and_round_trip():
    document_id = uuid4()
    completed = JournalEntry(
        document_id=document_id,
        entry_id="turn-entry-1",
        kind="employee_turn",
        payload_schema_id="job-analysis-completed-turn/1",
        payload=CompletedTurnPayload(
            operation_id="operation-1",
            employee_turn=employee_turn(),
            consultant_turn=consultant_turn(),
        ),
        created_at=NOW,
    )
    direct_edit = JournalEntry(
        document_id=document_id,
        entry_id="edit-entry-1",
        kind="direct_edit",
        payload_schema_id="job-analysis-direct-edit/1",
        payload=DirectEditPayload(
            edit_kind="edit",
            task_id="task-1",
            after=jd_task(),
        ),
        created_at=NOW,
    )
    decision = JournalEntry(
        document_id=document_id,
        entry_id="decision-entry-1",
        kind="proposal_decision",
        payload_schema_id="job-analysis-proposal-decision/1",
        payload=ProposalDecisionPayload(
            proposal_id="proposal-1",
            decision=ProposalStatus.REJECTED,
            reason="這其實是另一個部門的工作",
        ),
        created_at=NOW,
    )

    assert JournalEntry.model_validate(completed.model_dump()).payload == completed.payload
    assert direct_edit.payload_schema_id == "job-analysis-direct-edit/1"
    assert decision.payload.decision is ProposalStatus.REJECTED

    with pytest.raises(ValidationError, match="kind"):
        JournalEntry(
            **{
                **completed.model_dump(),
                "kind": "direct_edit",
            }
        )
    with pytest.raises(ValidationError, match="payload_schema_id"):
        JournalEntry(
            **{
                **completed.model_dump(),
                "payload_schema_id": "job-analysis-completed-turn/2",
            }
        )


def test_proposal_decision_payload_only_accepts_employee_decisions():
    for decision in (
        ProposalStatus.ACCEPTED,
        ProposalStatus.EDITED,
        ProposalStatus.REJECTED,
        ProposalStatus.DEFERRED,
        ProposalStatus.REVISION_REQUESTED,
    ):
        assert (
            ProposalDecisionPayload(
                proposal_id="proposal-1",
                decision=decision,
            ).decision
            is decision
        )

    for forbidden in (
        ProposalStatus.PENDING,
        ProposalStatus.STALE,
    ):
        with pytest.raises(ValidationError, match="employee decision"):
            ProposalDecisionPayload(
                proposal_id="proposal-1",
                decision=forbidden,
            )


def test_uow_protocol_exposes_only_application_ports():
    annotations = get_type_hints(JobAnalysisUnitOfWork)
    rendered = " ".join(repr(value) for value in annotations.values()).lower()

    assert {
        "documents",
        "tasks",
        "proposals",
        "opks",
        "opks_proposals",
        "journal",
    } <= set(annotations)
    assert "sqlalchemy" not in rendered

    assert OpksRepository is not None
    assert OpksProposalRepository is not None
