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
    ProposalDecisionPayload,
    TurnSpeaker,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdTask,
    ProposalStatus,
    ResponsibilityRole,
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


def test_loaded_state_keeps_complete_current_jd_values():
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
    state = JobAnalysisState(current_jd=(jd_task(),))

    loaded = LoadedDocument(document=document, state=state, recent_turns=())

    assert loaded.state.current_jd[0].frequency_text == "每週一次"


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
    ("edit_kind", "after"),
    [
        ("add", jd_task()),
        ("edit", jd_task()),
        ("reorder", jd_task()),
        ("delete", None),
    ],
)
def test_direct_edit_payload_preserves_the_completed_value(edit_kind, after):
    payload = DirectEditPayload(
        edit_kind=edit_kind,
        task_id="task-1",
        after=after,
    )
    assert payload.after == after


def test_direct_edit_payload_rejects_an_impossible_kind_value_combination():
    with pytest.raises(ValidationError, match="delete"):
        DirectEditPayload(
            edit_kind="delete",
            task_id="task-1",
            after=jd_task(),
        )
    with pytest.raises(ValidationError, match="requires the completed task"):
        DirectEditPayload(
            edit_kind="edit",
            task_id="task-1",
            after=None,
        )
    with pytest.raises(ValidationError, match="task id"):
        DirectEditPayload(
            edit_kind="edit",
            task_id="task-1",
            after=jd_task("task-2"),
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

    assert {"documents", "tasks", "proposals", "journal"} <= set(annotations)
    assert "sqlalchemy" not in rendered

