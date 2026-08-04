"""Executable checks for the Local Web wire contract."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from job_analysis_contract import (
    ConsultationView,
    DocumentReadinessView,
    EmployeeTurnWrite,
    JdHeaderView,
    JdHeaderWrite,
    JdTaskWrite,
    OpksItemView,
    OpksItemWrite,
    OpksGenerationView,
    OpksProposalDecisionWrite,
    OpksProposalView,
    ProblemDetail,
    ProposalDecisionWrite,
    ProposalView,
    ReadinessIssueView,
)


PACKAGE_ROOT = Path(__file__).parents[1]
SCHEMA_PATH = PACKAGE_ROOT / "schema" / "job-analysis-workspace.schema.json"
PROBLEM_TYPES = {
    "https://caliburn.dev/problems/job-analysis/document-not-found",
    "https://caliburn.dev/problems/job-analysis/task-not-found",
    "https://caliburn.dev/problems/job-analysis/idempotency-conflict",
    "https://caliburn.dev/problems/job-analysis/authority-conflict",
    "https://caliburn.dev/problems/job-analysis/invalid-task-order",
    "https://caliburn.dev/problems/job-analysis/invalid-request",
    "https://caliburn.dev/problems/job-analysis/proposal-not-found",
    "https://caliburn.dev/problems/job-analysis/consultant-unavailable",
    "https://caliburn.dev/problems/job-analysis/opks-item-not-found",
}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_owns_only_the_workspace_wire_contract():
    """Replacing the schema with an old OCS/user contract must fail."""

    schema = _schema()

    assert schema["$id"] == (
        "https://caliburn.dev/schema/job-analysis-workspace.schema.json"
    )
    assert set(schema["$defs"]) == {
        "DocumentMetadataWrite",
        "DocumentMetadataView",
        "DocumentSummary",
        "DocumentView",
        "ActiveQuestionView",
        "ConsultationView",
        "ConversationTurnView",
        "EmployeeTurnWrite",
        "DocumentReadinessView",
        "Enabler",
        "JdHeaderView",
        "JdHeaderWrite",
        "JdTaskWrite",
        "JdTaskView",
        "ReadinessIssueView",
        "OpksItemView",
        "OpksItemWrite",
        "OpksGenerationView",
        "OpksProposalDecisionWrite",
        "OpksProposalView",
        "ProblemDetail",
        "ProblemFieldError",
        "ProposalDecisionWrite",
        "ProposalJdEntryView",
        "ProposalView",
        "TaskOrderWrite",
    }


def test_problem_type_is_the_nine_value_machine_identifier():
    """Adding an untyped error branch must change the generated consumers."""

    problem = _schema()["$defs"]["ProblemDetail"]

    assert set(problem["properties"]["type"]["enum"]) == PROBLEM_TYPES
    assert problem["additionalProperties"] is True


def test_consultation_contract_exposes_only_product_views_and_supported_decisions():
    schema = _schema()
    consultation = schema["$defs"]["ConsultationView"]
    decision = schema["$defs"]["ProposalDecisionWrite"]

    assert consultation["additionalProperties"] is False
    assert set(consultation["properties"]) == {
        "document",
        "conversation",
        "active_question",
        "proposals",
        "tasks",
        "opks_items",
        "opks_proposals",
    }
    assert set(decision["properties"]["decision"]["enum"]) == {
        "accepted",
        "edited",
        "rejected",
        "deferred",
    }
    assert "revision_requested" not in decision["properties"]["decision"]["enum"]
    opks_decision = schema["$defs"]["OpksProposalDecisionWrite"]
    assert set(opks_decision["properties"]["decision"]["enum"]) == {
        "accepted",
        "edited",
        "rejected",
        "deferred",
    }


def test_proposal_view_can_preserve_null_snapshots_edits_stale_reason_and_quotes():
    validator = Draft202012Validator(_schema())
    proposal = {
        "proposal_id": "proposal-1",
        "action": "withdraw",
        "status": "stale",
        "jd_before": [
            {
                "task_id": "task-1",
                "value": {
                    "task_id": "task-1",
                    "statement": "處理客戶退貨",
                    "purpose_result": None,
                    "context": None,
                    "frequency_text": None,
                    "responsibility_role": None,
                    "enablers": [],
                    "display_order": 0,
                },
            }
        ],
        "jd_after": [{"task_id": "task-1", "value": None}],
        "edited_jd_after": None,
        "rejection_reason": None,
        "stale_reason": "Current JD 已由員工修改",
        "evidence_quotes": ["那其實是別人在做"],
    }

    errors = validator.evolve(
        schema={"$ref": "#/$defs/ProposalView"}
    ).iter_errors(proposal)
    assert list(errors) == []


def test_opks_proposal_view_preserves_operation_grouping_and_snapshots():
    validator = Draft202012Validator(_schema())
    proposal = {
        "proposal_id": "opks-proposal-1",
        "operation_id": "opks-operation-1",
        "entity_id": "knowledge-1",
        "entity_kind": "knowledge",
        "action": "revise",
        "status": "pending",
        "before": {
            "entity_id": "knowledge-1",
            "entity_kind": "knowledge",
            "text": "營運資料",
            "task_refs": [],
            "indicator_refs": [],
            "evidence_quotes": ["我會整理營運資料"],
        },
        "after": {
            "entity_id": "knowledge-1",
            "entity_kind": "knowledge",
            "text": "營運資料定義",
            "task_refs": [],
            "indicator_refs": [],
            "evidence_quotes": ["我會整理營運資料"],
        },
        "edited_after": None,
        "rejection_reason": None,
        "stale_reason": None,
    }

    assert list(
        validator.evolve(
            schema={"$ref": "#/$defs/OpksProposalView"}
        ).iter_errors(proposal)
    ) == []


def test_optional_task_text_can_reach_the_mapper_as_blank_or_null():
    """Schema-level minLength would reject a value the mapper must normalize."""

    task = _schema()["$defs"]["JdTaskWrite"]

    for field in (
        "purpose_result",
        "context",
        "frequency_text",
        "responsibility_role",
    ):
        assert set(task["properties"][field]["type"]) == {"string", "null"}
        assert "minLength" not in task["properties"][field]

    assert "" in task["properties"]["responsibility_role"]["enum"]
    assert "" not in _schema()["$defs"]["JdTaskView"]["properties"][
        "responsibility_role"
    ]["enum"]


_EMPTY_JD_HEADER = {
    "competency_name": None,
    "occupation_category_name": None,
    "occupation_name": None,
    "occupation_code": None,
    "industry_name": None,
    "industry_code": None,
    "work_description": None,
    "competency_level": None,
    "notes": None,
}


def test_document_view_accepts_one_complete_task_without_extra_fields():
    """A closed allOf branch must not reject fields inherited by JdTaskView."""

    validator = Draft202012Validator(_schema())
    document = {
        "document_id": "00000000-0000-0000-0000-000000000045",
        "title": "門市營運專員",
        "updated_at": "2026-07-30T09:00:00Z",
        "jd_header": _EMPTY_JD_HEADER,
        "readiness": {"issues": []},
        "tasks": [
            {
                "task_id": "task-1",
                "statement": "每週彙整營運週報",
                "purpose_result": None,
                "context": "每週",
                "frequency_text": "每週一次",
                "responsibility_role": "primary",
                "enablers": [{"kind": "tool_system", "name": "Excel"}],
                "display_order": 0,
            }
        ],
        "opks_items": [],
    }

    assert list(
        validator.evolve(schema={"$ref": "#/$defs/DocumentView"}).iter_errors(
            document
        )
    ) == []


def test_jd_header_has_no_icap_assigned_code_field():
    """ADR 0052 決定 8：`職能基準代碼`／`職類別代碼` 由 iCAP 配發，wire 契約不得開欄位。"""

    for def_name in ("JdHeaderView", "JdHeaderWrite"):
        header = _schema()["$defs"][def_name]
        fields = set(header["properties"])
        assert "competency_code" not in fields
        assert "occupation_category_code" not in fields
        assert fields - {"occupation_code", "industry_code"} == {
            name for name in fields if not name.endswith("_code")
        }


def test_jd_header_every_field_is_nullable():
    for def_name in ("JdHeaderView", "JdHeaderWrite"):
        header = _schema()["$defs"][def_name]
        assert set(header["required"]) == set(header["properties"])
        for name, field in header["properties"].items():
            if name == "competency_level":
                assert set(field["type"]) == {"integer", "null"}
                assert field["minimum"] == 1
                assert field["maximum"] == 6
            else:
                assert set(field["type"]) == {"string", "null"}


def test_readiness_issue_codes_match_the_first_version_header_checks():
    issue = _schema()["$defs"]["ReadinessIssueView"]

    assert set(issue["properties"]["code"]["enum"]) == {
        "competency_name_missing",
        "work_description_missing",
        "competency_level_missing",
    }


def test_document_readiness_view_carries_no_completion_verdict():
    """ADR 0053 決定 6：第一版不回 is_complete／ready／百分比。"""

    readiness = _schema()["$defs"]["DocumentReadinessView"]

    assert set(readiness["properties"]) == {"issues"}


def test_document_view_requires_jd_header_and_readiness():
    validator = Draft202012Validator(_schema())
    document = {
        "document_id": "00000000-0000-0000-0000-000000000045",
        "title": "門市營運專員",
        "updated_at": "2026-07-30T09:00:00Z",
        "readiness": {"issues": []},
        "tasks": [],
        "opks_items": [],
    }

    errors = list(
        validator.evolve(schema={"$ref": "#/$defs/DocumentView"}).iter_errors(
            document
        )
    )
    assert any("jd_header" in str(error) for error in errors)


def test_generated_models_keep_normalization_and_problem_extension_boundaries():
    task = JdTaskWrite(
        statement="每週彙整營運週報",
        purpose_result="",
        context=None,
        frequency_text="",
        responsibility_role="",
        enablers=[],
    )
    problem = ProblemDetail.model_validate(
        {
            "type": "https://caliburn.dev/problems/job-analysis/invalid-request",
            "title": "Request failed",
            "status": 422,
            "future_extension": {"ignored_by_old_consumers": True},
        }
    )

    assert task.responsibility_role.value == ""
    assert problem.model_extra == {
        "future_extension": {"ignored_by_old_consumers": True}
    }


def test_generated_consultation_models_are_exported_from_the_package():
    assert ConsultationView.__name__ == "ConsultationView"
    assert ProposalView.__name__ == "ProposalView"
    assert EmployeeTurnWrite(text="我每週彙整營運週報").text.startswith("我")
    assert ProposalDecisionWrite(decision="accepted").decision.value == "accepted"
    assert (
        OpksProposalDecisionWrite(decision="deferred").decision.value
        == "deferred"
    )
    write = OpksItemWrite(
        entity_kind="knowledge",
        text="營運資料定義",
        task_refs=[],
        indicator_refs=[],
    )
    assert write.entity_kind.value == "knowledge"
    assert OpksItemView.__name__ == "OpksItemView"
    assert OpksProposalView.__name__ == "OpksProposalView"


def test_jd_header_and_readiness_models_are_exported_from_the_package():
    header = JdHeaderView(**_EMPTY_JD_HEADER)
    write = JdHeaderWrite(**_EMPTY_JD_HEADER)
    issue = ReadinessIssueView(
        code="work_description_missing", field="work_description"
    )
    readiness = DocumentReadinessView(issues=[issue])

    assert header.competency_level is None
    assert write.competency_level is None
    assert readiness.issues[0].code.value == "work_description_missing"


def test_opks_generation_view_exposes_only_the_durable_product_result():
    view = OpksGenerationView(
        outcome="proposed",
        proposal_ids=["opks-operation-1-op0"],
    )

    assert view.model_dump(mode="json") == {
        "outcome": "proposed",
        "proposal_ids": ["opks-operation-1-op0"],
    }
