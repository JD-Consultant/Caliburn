"""Duty persistence contracts that remain valid across authority reloads."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import get_type_hints
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.adapters.job_analysis_postgres import serialization as ser
from app.job_analysis.application import (
    DIRECT_EDIT_SCHEMA_ID,
    DUTY_DIRECT_EDIT_SCHEMA_ID,
    DirectEditPayload,
    DutyDirectEditPayload,
    DutyRepository,
    JournalEntry,
    JobAnalysisUnitOfWork,
    PROPOSAL_SCHEMA_ID,
)
from app.job_analysis.domain import (
    Duty,
    JdEntry,
    JdTask,
    Proposal,
    ProposalAction,
    ProposalStatus,
    SingleTaskTarget,
)


def _task(*, duty_id: str | None = "duty-1", level: int | None = 3) -> JdTask:
    return JdTask(
        task_id="task-1",
        statement="彙整門市營運週報",
        duty_id=duty_id,
        competency_level=level,
        display_order=0,
    )


def _proposal(task: JdTask) -> Proposal:
    return Proposal(
        proposal_id="proposal-1",
        target=SingleTaskTarget(action=ProposalAction.REVISE, task_id=task.task_id),
        jd_before=(JdEntry(task_id=task.task_id, value=task),),
        jd_after=(
            JdEntry(
                task_id=task.task_id,
                value=task.model_copy(update={"statement": "檢核門市營運週報"}),
            ),
        ),
    )


def test_duty_direct_edit_payload_enforces_action_snapshot_shapes():
    """Removing the payload validator would permit unreplayable Duty receipts."""

    duty = Duty(duty_id="duty-1", statement="門市營運管理", display_order=0)

    assert DutyDirectEditPayload(action="add", after=duty).after == duty
    assert DutyDirectEditPayload(action="edit", before=duty, after=duty).before == duty
    assert DutyDirectEditPayload(action="delete", before=duty).after is None
    assert DutyDirectEditPayload(
        action="reorder", ordered_duty_ids=("duty-2", "duty-1")
    ).ordered_duty_ids == ("duty-2", "duty-1")

    with pytest.raises(ValidationError, match="add"):
        DutyDirectEditPayload(action="add", before=duty)
    with pytest.raises(ValidationError, match="preserve"):
        DutyDirectEditPayload(
            action="edit",
            before=duty,
            after=duty.model_copy(update={"duty_id": "duty-2"}),
        )
    with pytest.raises(ValidationError, match="delete"):
        DutyDirectEditPayload(action="delete", after=duty)
    with pytest.raises(ValidationError, match="distinct"):
        DutyDirectEditPayload(
            action="reorder", ordered_duty_ids=("duty-1", "duty-1")
        )


def test_duty_direct_edit_receipt_is_a_direct_edit_not_task_evidence():
    """Changing the journal contract must not mint a Task SourceRef by accident."""

    duty = Duty(duty_id="duty-1", statement="門市營運管理", display_order=0)
    entry = JournalEntry(
        document_id=uuid4(),
        entry_id="duty-add",
        kind="direct_edit",
        payload_schema_id=DUTY_DIRECT_EDIT_SCHEMA_ID,
        payload=DutyDirectEditPayload(action="add", after=duty),
        created_at=datetime(2026, 8, 9),
    )

    assert entry.kind == "direct_edit"
    assert entry.payload.model_dump() == {
        "action": "add",
        "before": None,
        "after": duty.model_dump(),
        "ordered_duty_ids": (),
    }


def test_task_row_round_trips_employee_duty_and_level():
    """Dropping either SQL column would erase employee-owned Task structure."""

    loaded = ser.load_jd_task(
        SimpleNamespace(
            task_id="task-1",
            statement="彙整門市營運週報",
            purpose_result=None,
            context=None,
            frequency_text=None,
            responsibility_role=None,
            enablers_json=[],
            duty_id="duty-1",
            competency_level=3,
            display_order=0,
        )
    )

    assert loaded.duty_id == "duty-1"
    assert loaded.competency_level == 3


def test_legacy_task_and_proposal_payloads_default_new_employee_fields_to_none():
    """Adding optional fields must not strand existing Task/Proposal receipts."""

    legacy_task = _task().model_dump(mode="json")
    legacy_task.pop("duty_id")
    legacy_task.pop("competency_level")
    direct_row = SimpleNamespace(
        document_id=uuid4(),
        entry_id="task-edit",
        kind="direct_edit",
        payload_schema_id=DIRECT_EDIT_SCHEMA_ID,
        payload={
            "edit_kind": "edit",
            "task_id": "task-1",
            "after": legacy_task,
            "ordered_task_ids": [],
        },
        created_at=datetime(2026, 8, 9),
    )
    loaded_direct = ser.load_journal(direct_row)

    proposal = _proposal(_task())
    legacy_proposal_payload = ser.dump_proposal_payload(proposal)
    for entry in (*legacy_proposal_payload["jd_before"], *legacy_proposal_payload["jd_after"]):
        if entry["value"] is not None:
            entry["value"].pop("duty_id")
            entry["value"].pop("competency_level")
    proposal_row = SimpleNamespace(
        proposal_schema_id=PROPOSAL_SCHEMA_ID,
        proposal_payload=legacy_proposal_payload,
        proposal_id=proposal.proposal_id,
        status=ProposalStatus.PENDING.value,
        caused_by_decision_id=None,
    )
    loaded_proposal = ser.load_proposal(proposal_row)

    assert isinstance(loaded_direct.payload, DirectEditPayload)
    assert loaded_direct.payload.after is not None
    assert loaded_direct.payload.after.duty_id is None
    assert loaded_direct.payload.after.competency_level is None
    assert loaded_proposal.jd_after[0].value is not None
    assert loaded_proposal.jd_after[0].value.duty_id is None
    assert loaded_proposal.jd_after[0].value.competency_level is None


def test_uow_protocol_exposes_a_duty_repository_port():
    """Removing the port would force authority code to import a Postgres adapter."""

    annotations = get_type_hints(JobAnalysisUnitOfWork)

    assert "duties" in annotations
    assert DutyRepository is not None
