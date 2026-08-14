from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from job_analysis_contract import (
    ApprovedJobDocumentWrite,
    ConsultantSnapshotEvent,
    ConsultantSnapshotView,
    DocumentReviewDecisionWrite,
    EmployeeAnswerWrite,
    RequiredClarificationAnswerWrite,
    UnderstandingCalibrationDecisionWrite,
)


SCHEMA_PATH = (
    Path(__file__).parents[1] / "schema" / "job-analysis-workspace.schema.json"
)
TYPESCRIPT_PATH = (
    Path(__file__).parents[1] / "types" / "job-analysis-workspace.ts"
)


def test_consultant_contract_covers_the_durable_employee_workspace() -> None:
    definitions = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$defs"]

    assert {
        "ConsultantDocumentCatalog",
        "EmployeeMessageView",
        "CurrentInterviewReasonView",
        "UnderstandingView",
        "VisibleWorkItemView",
        "SemanticProgressView",
        "SufficiencyView",
        "ConsultantMessageView",
        "DocumentChangeSetView",
        "DocumentReviewDecisionWrite",
        "RequiredClarificationView",
        "ApprovedJobDocumentView",
        "ExportReadinessView",
        "ConsultantSnapshotView",
        "ConsultantSnapshotEvent",
    } <= set(definitions)
    serialized = json.dumps(definitions, ensure_ascii=False).casefold()
    assert '"pause' not in serialized
    assert '"finish' not in serialized


def test_commands_are_typed_and_reject_untrusted_extra_fields() -> None:
    action_id = uuid4()
    decision = DocumentReviewDecisionWrite.model_validate(
        {
            "command": "edit_and_accept_changes",
            "action_ids": [str(action_id)],
            "edited_after_by_action_id": {str(action_id): "員工修正內容"},
            "rejection_reason": None,
        }
    )
    assert decision.action_ids == [action_id]

    with pytest.raises(ValidationError):
        EmployeeAnswerWrite.model_validate({"text": "回答", "role": "system"})
    with pytest.raises(ValidationError):
        RequiredClarificationAnswerWrite.model_validate(
            {"choice": "員工", "text": "我負責", "accept_changes": True}
        )
    with pytest.raises(ValidationError):
        UnderstandingCalibrationDecisionWrite.model_validate(
            {"decision": "confirm", "employee_text": "我確認", "finish": True}
        )


def test_review_edit_map_keeps_a_generated_json_value_index_signature() -> None:
    generated = TYPESCRIPT_PATH.read_text(encoding="utf-8")
    start = generated.index("export interface DocumentReviewDecisionWrite")
    end = generated.index("\n}\n", start)

    assert "[k: string]:" in generated[start:end]
    for member in ("| string", "| number", "| boolean", "| null", "| unknown[]"):
        assert member in generated[start:end]


def test_manual_document_surface_keeps_deferred_fields_without_official_codes() -> None:
    document_id = uuid4()
    task_id = uuid4()
    item_id = uuid4()
    document = ApprovedJobDocumentWrite.model_validate(
        {
            "document_id": str(document_id),
            "job_title": "採購專員",
            "occupation_category_name": "採購",
            "occupation_name": "採購人員",
            "occupation_code": "EMPLOYEE-CLASSIFICATION",
            "industry_name": "製造業",
            "industry_code": "EMPLOYEE-INDUSTRY",
            "work_description": None,
            "competency_level": 3,
            "notes": None,
            "duties": [],
            "tasks": [
                {
                    "task_id": str(task_id),
                    "duty_id": None,
                    "statement": "整理採購需求",
                    "action": "整理",
                    "object": "採購需求",
                    "purpose_result": None,
                    "context": None,
                    "frequency_text": None,
                    "responsibility_role": "primary",
                    "enablers": [],
                    "display_order": 0,
                    "competency_level": 2,
                }
            ],
            "opks": [
                {
                    "item_id": str(item_id),
                    "kind": "attitude",
                    "text": "謹慎",
                    "display_order": 0,
                    "task_ids": [],
                    "indicator_ids": [],
                }
            ],
        }
    )

    assert document.competency_level == 3
    assert document.tasks[0].competency_level == 2
    assert document.opks[0].kind == "attitude"
    assert "evidence_source_ids" not in type(document.opks[0]).model_fields
    assert "icap_code" not in ApprovedJobDocumentWrite.model_fields
    assert "competency_standard_code" not in ApprovedJobDocumentWrite.model_fields


def test_sse_event_is_refetch_only_and_snapshot_has_no_client_owned_history() -> None:
    event = ConsultantSnapshotEvent(
        event="snapshot_changed",
        document_id=uuid4(),
        revision=4,
        run_id=uuid4(),
    )

    assert set(event.model_dump()) == {"event", "document_id", "revision", "run_id"}
    assert "messages" not in ConsultantSnapshotEvent.model_fields
    assert "client_history" not in ConsultantSnapshotView.model_fields
    assert "employee_messages" in ConsultantSnapshotView.model_fields
    assert "pause" not in ConsultantSnapshotView.model_fields
    assert "finish" not in ConsultantSnapshotView.model_fields
