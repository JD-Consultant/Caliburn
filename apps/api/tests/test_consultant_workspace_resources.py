from __future__ import annotations

import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.consultant.provider_wire import OutputEvidenceReference
from app.consultant.state import (
    ApprovedDuty,
    ApprovedEnabler,
    ApprovedEnablerKind,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
)
from app.consultant.workspace_resources import (
    CandidateTaskResource,
    WorkspaceCatalog,
    parse_candidate_files,
    project_candidate_files,
)


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000064")
DUTY_ID = UUID("00000000-0000-0000-0000-000000000101")
TASK_ID = UUID("00000000-0000-0000-0000-000000000102")
OUTPUT_ID = UUID("00000000-0000-0000-0000-000000000103")
INDICATOR_ID = UUID("00000000-0000-0000-0000-000000000104")
KNOWLEDGE_ID = UUID("00000000-0000-0000-0000-000000000105")
SKILL_ID = UUID("00000000-0000-0000-0000-000000000106")
ATTITUDE_ID = UUID("00000000-0000-0000-0000-000000000107")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000108")
RUN_ID = UUID("00000000-0000-0000-0000-000000000109")


def _document() -> ApprovedJobDocument:
    task = ApprovedTask(
        task_id=TASK_ID,
        statement="核對訂單內容",
        action="核對",
        object="訂單內容",
        purpose_result="避免錯誤出貨",
        context="接獲訂單後",
        frequency_text="每日",
        responsibility_role="primary",
        enablers=(
            ApprovedEnabler(kind=ApprovedEnablerKind.TOOL_SYSTEM, name="ERP"),
        ),
        display_order=0,
        competency_level=4,
    )
    evidence = (SOURCE_ID,)
    return ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        job_title="採購專員",
        occupation_category_name="採購",
        occupation_name="採購人員",
        occupation_code="A-001",
        industry_name="製造業",
        industry_code="M-001",
        work_description="維持採購作業順暢。",
        competency_level=5,
        notes="保留基線備註。",
        duties=(
            ApprovedDuty(duty_id=DUTY_ID, statement="管理採購作業", display_order=0),
        ),
        tasks=(task,),
        opks=(
            ApprovedOpksItem(
                item_id=OUTPUT_ID,
                kind=ApprovedOpksKind.OUTPUT,
                text="完成正確訂單",
                display_order=0,
                task_ids=(TASK_ID,),
                evidence_source_ids=evidence,
            ),
            ApprovedOpksItem(
                item_id=INDICATOR_ID,
                kind=ApprovedOpksKind.PERFORMANCE_INDICATOR,
                text="訂單錯誤率低",
                display_order=0,
                task_ids=(TASK_ID,),
                evidence_source_ids=evidence,
            ),
            ApprovedOpksItem(
                item_id=KNOWLEDGE_ID,
                kind=ApprovedOpksKind.KNOWLEDGE,
                text="訂單規則",
                display_order=0,
                task_ids=(TASK_ID,),
                evidence_source_ids=evidence,
            ),
            ApprovedOpksItem(
                item_id=SKILL_ID,
                kind=ApprovedOpksKind.SKILL,
                text="細節核對",
                display_order=0,
                task_ids=(TASK_ID,),
                evidence_source_ids=evidence,
            ),
            ApprovedOpksItem(
                item_id=ATTITUDE_ID,
                kind=ApprovedOpksKind.ATTITUDE,
                text="謹慎負責",
                display_order=0,
                evidence_source_ids=evidence,
            ),
        ),
    )


def test_workspace_resources_round_trip_editable_jd_without_exposing_a_or_level() -> None:
    document = _document()
    catalog = WorkspaceCatalog.from_snapshot(document, pending=())

    assert catalog.handle_for_id(DUTY_ID) == "duty-001"
    assert catalog.handle_for_id(TASK_ID) == "task-001"
    assert catalog.handle_for_id(OUTPUT_ID) == "o-001"
    assert catalog.handle_for_id(INDICATOR_ID) == "p-001"
    assert catalog.handle_for_id(KNOWLEDGE_ID) == "k-001"
    assert catalog.handle_for_id(SKILL_ID) == "s-001"
    assert catalog.handle_for_id(SOURCE_ID) == "source-001"

    files = project_candidate_files(catalog, run_id=RUN_ID)
    task_path = f"/candidate/{RUN_ID}/tasks/task-001.json"
    task_payload = json.loads(files[task_path])

    assert list(task_payload) == [
        "handle",
        "duty_handle",
        "statement",
        "action",
        "object",
        "purpose_result",
        "context",
        "frequency_text",
        "responsibility_role",
        "enablers",
    ]
    assert "competency_level" not in files[task_path]
    assert "/opks/a/" not in "\n".join(files)
    assert "00000000-0000-0000-0000-000000000102" not in files[task_path]
    assert files["/candidate/00000000-0000-0000-0000-000000000109/header.json"].endswith(
        "\n"
    )
    assert "採購專員" in files["/candidate/00000000-0000-0000-0000-000000000109/header.json"]

    parsed = parse_candidate_files(catalog, files)

    assert parsed.approved_document == document
    assert parsed.approved_document.competency_level == 5
    assert parsed.approved_document.tasks[0].competency_level == 4
    assert parsed.approved_document.opks[-1].kind.value == "attitude"


def test_workspace_resource_models_are_frozen_and_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CandidateTaskResource(
            handle="task-001",
            duty_handle=None,
            statement="核對訂單內容",
            action="核對",
            object="訂單內容",
            purpose_result=None,
            context=None,
            frequency_text=None,
            responsibility_role=None,
            enablers=(),
            competency_level=4,
        )


def test_model_evidence_reference_has_quote_occurrence_but_no_offsets() -> None:
    schema = OutputEvidenceReference.model_json_schema()

    assert set(schema["properties"]) == {
        "source_handle",
        "quote",
        "occurrence",
        "skill_ids",
    }
    reference = OutputEvidenceReference(
        source_handle="source-001",
        quote="核對訂單",
        occurrence=2,
        skill_ids=("task-boundary",),
    )
    assert reference.occurrence == 2
