from __future__ import annotations

import json
from uuid import UUID, uuid5

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
    EmployeeSource,
    EmployeeSourceKind,
)
from app.consultant.workspace_resources import (
    WorkspaceTaskResource,
    WorkspaceCatalog,
    WorkspaceResourceError,
    parse_workspace_files,
    project_workspace_files,
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
COLLISION_ID = UUID("00000000-0000-0000-0000-000000000111")


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
    catalog = WorkspaceCatalog.from_snapshot(document)

    assert catalog.handle_for_id(DUTY_ID) == "duty-001"
    assert catalog.handle_for_id(TASK_ID) == "task-001"
    assert catalog.handle_for_id(OUTPUT_ID) == "o-001"
    assert catalog.handle_for_id(INDICATOR_ID) == "p-001"
    assert catalog.handle_for_id(KNOWLEDGE_ID) == "k-001"
    assert catalog.handle_for_id(SKILL_ID) == "s-001"
    assert catalog.handle_for_id(SOURCE_ID) == "source-001"

    projection = project_workspace_files(
        catalog.document,
        handle_registry=catalog.handle_to_stable,
    )
    files = dict(projection.files)
    task_path = "/workspace/tasks/task-001.json"
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
        "display_order",
    ]
    assert "competency_level" not in files[task_path]
    assert "/opks/a/" not in "\n".join(files)
    assert "00000000-0000-0000-0000-000000000102" not in files[task_path]
    assert files["/workspace/header.json"].endswith("\n")
    assert "採購專員" in files["/workspace/header.json"]

    parsed = parse_workspace_files(
        DOCUMENT_ID,
        files,
        handle_registry=projection.handle_registry,
        baseline_document=document,
    )

    assert parsed.approved_document == document
    assert parsed.approved_document.competency_level == 5
    assert parsed.approved_document.tasks[0].competency_level == 4
    assert parsed.approved_document.opks[-1].kind.value == "attitude"


def test_workspace_resource_models_are_frozen_and_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        WorkspaceTaskResource(
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


def test_workspace_draft_keeps_evidence_owner_for_each_opks_handle() -> None:
    catalog = WorkspaceCatalog.from_snapshot(_document())
    projection = project_workspace_files(
        catalog.document,
        handle_registry=catalog.handle_to_stable,
    )
    files = dict(projection.files)
    output_path = "/workspace/opks/o/o-001.json"
    skill_path = "/workspace/opks/s/s-001.json"
    output_payload = json.loads(files[output_path])
    skill_payload = json.loads(files[skill_path])
    output_payload["evidence"] = [
        {
            "source_handle": "source-001",
            "quote": "輸出原話",
            "skill_ids": ["output"],
        }
    ]
    skill_payload["evidence"] = [
        {
            "source_handle": "source-001",
            "quote": "技能原話",
            "skill_ids": ["skill"],
        }
    ]
    files[output_path] = json.dumps(output_payload, ensure_ascii=False)
    files[skill_path] = json.dumps(skill_payload, ensure_ascii=False)

    draft = parse_workspace_files(
        DOCUMENT_ID,
        files,
        handle_registry=projection.handle_registry,
        baseline_document=catalog.document,
    )

    assert [binding.opks_handle for binding in draft.opks_evidence] == [
        "o-001",
        "s-001",
    ]
    assert [
        (binding.references[0].quote, binding.references[0].skill_ids)
        for binding in draft.opks_evidence
    ] == [("輸出原話", ("output",)), ("技能原話", ("skill",))]


def test_new_workspace_entity_id_is_stable_per_handle() -> None:
    catalog = WorkspaceCatalog.from_snapshot(_document())

    def files_for(handle: str) -> dict[str, str]:
        projection = project_workspace_files(
            catalog.document,
            handle_registry=catalog.handle_to_stable,
        )
        files = dict(projection.files)
        files[f"/workspace/duties/{handle}.json"] = json.dumps(
            {"handle": handle, "statement": "新增職責"},
            ensure_ascii=False,
        )
        return files

    first_files = files_for("duty-new-001")
    first = parse_workspace_files(
        DOCUMENT_ID,
        first_files,
        handle_registry=catalog.handle_to_stable,
        baseline_document=catalog.document,
    )
    same = parse_workspace_files(
        DOCUMENT_ID,
        files_for("duty-new-001"),
        handle_registry=catalog.handle_to_stable,
        baseline_document=catalog.document,
    )
    second = parse_workspace_files(
        DOCUMENT_ID,
        files_for("duty-new-002"),
        handle_registry=catalog.handle_to_stable,
        baseline_document=catalog.document,
    )
    first_id = next(
        duty.duty_id
        for duty in first.approved_document.duties
        if duty.statement == "新增職責"
    )
    same_id = next(
        duty.duty_id
        for duty in same.approved_document.duties
        if duty.statement == "新增職責"
    )
    second_id = next(
        duty.duty_id
        for duty in second.approved_document.duties
        if duty.statement == "新增職責"
    )

    assert first_id == same_id
    assert first_id != second_id


def test_catalog_rejects_cross_kind_stable_id_collision() -> None:
    document = ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        duties=(ApprovedDuty(duty_id=COLLISION_ID, statement="同一 ID 職責", display_order=0),),
        tasks=(
            ApprovedTask(
                task_id=COLLISION_ID,
                statement="同一 ID 工作",
                action="執行",
                object="工作",
                display_order=0,
            ),
        ),
    )

    with pytest.raises(WorkspaceResourceError, match="stable ID collision"):
        WorkspaceCatalog.from_snapshot(document)


def test_catalog_deduplicates_exact_repeated_source_facts_before_mapping() -> None:
    source = EmployeeSource.pending(
        source_id=SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="員工原話",
    )

    catalog = WorkspaceCatalog.from_snapshot(
        _document(),
        sources=(source, source),
    )

    assert catalog.source_ids == (SOURCE_ID,)


def test_provider_evidence_reference_rejects_invalid_handle() -> None:
    with pytest.raises(ValidationError):
        OutputEvidenceReference(
            source_handle="not-a-local-handle",
            quote="核對訂單",
            occurrence=0,
            skill_ids=("task-boundary",),
        )


def _files_with_new_workspace_task(handle: str) -> dict[str, str]:
    projection = project_workspace_files(_document(), handle_registry={})
    files = dict(projection.files)
    files[f"/workspace/tasks/{handle}.json"] = json.dumps(
        WorkspaceTaskResource(
            handle=handle,
            statement="處理退貨申請",
            action="處理",
            object="退貨申請",
        ).model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    return files


def test_workspace_projection_has_one_run_independent_root() -> None:
    projection = project_workspace_files(_document(), handle_registry={})

    assert "/workspace/header.json" in projection.files
    assert all(path.startswith("/workspace/") for path in projection.files)
    assert not any("/review/" in path for path in projection.files)


def test_new_workspace_handle_keeps_the_same_stable_id_after_restart() -> None:
    first = parse_workspace_files(
        DOCUMENT_ID,
        _files_with_new_workspace_task("task-new-001"),
        handle_registry={},
    )
    second = parse_workspace_files(
        DOCUMENT_ID,
        _files_with_new_workspace_task("task-new-001"),
        handle_registry=first.handle_registry,
    )

    assert first.document.tasks[-1].task_id == second.document.tasks[-1].task_id
    assert first.document.tasks[-1].task_id == uuid5(
        DOCUMENT_ID,
        "workspace:task:task-new-001",
    )


def test_accepted_new_task_keeps_its_handle_and_uuid_when_reprojected() -> None:
    first = parse_workspace_files(
        DOCUMENT_ID,
        _files_with_new_workspace_task("task-new-001"),
        handle_registry={},
    )
    accepted_task = ApprovedTask(
        task_id=first.document.tasks[-1].task_id,
        statement="處理退貨申請",
        action="處理",
        object="退貨申請",
        display_order=1,
    )
    accepted_document = _document().model_copy(
        update={"tasks": _document().tasks + (accepted_task,)}
    )

    projection = project_workspace_files(
        accepted_document,
        handle_registry=first.handle_registry,
    )
    reparsed = parse_workspace_files(
        DOCUMENT_ID,
        projection.files,
        handle_registry=projection.handle_registry,
    )

    assert "/workspace/tasks/task-new-001.json" in projection.files
    assert reparsed.document.tasks[-1].task_id == accepted_task.task_id


def test_workspace_resources_round_trip_editable_fields_without_a_or_levels() -> None:
    document = _document().model_copy(
        update={
            "opks": tuple(
                item.model_copy(update={"indicator_ids": (INDICATOR_ID,)})
                if item.item_id == KNOWLEDGE_ID
                else item
                for item in _document().opks
            )
        }
    )
    projection = project_workspace_files(document, handle_registry={})
    draft = parse_workspace_files(
        DOCUMENT_ID,
        projection.files,
        handle_registry=projection.handle_registry,
    )

    assert draft.document.duties[0].statement == "管理採購作業"
    assert draft.document.tasks[0].model_dump() == {
        "task_id": TASK_ID,
        "duty_id": None,
        "statement": "核對訂單內容",
        "action": "核對",
        "object": "訂單內容",
        "purpose_result": "避免錯誤出貨",
        "context": "接獲訂單後",
        "frequency_text": "每日",
        "responsibility_role": "primary",
        "enablers": (
            {"kind": "tool_system", "name": "ERP"},
        ),
        "display_order": 0,
    }
    assert [
        (
            item.item_id,
            item.kind.value,
            item.text,
            item.task_ids,
            item.indicator_ids,
        )
        for item in draft.document.opks
    ] == [
        (OUTPUT_ID, "output", "完成正確訂單", (TASK_ID,), ()),
        (INDICATOR_ID, "indicator", "訂單錯誤率低", (TASK_ID,), ()),
        (KNOWLEDGE_ID, "knowledge", "訂單規則", (TASK_ID,), (INDICATOR_ID,)),
        (SKILL_ID, "skill", "細節核對", (TASK_ID,), ()),
    ]
    assert all("competency_level" not in value for value in projection.files.values())
    assert "/workspace/opks/a/" not in "\n".join(projection.files)


def test_workspace_canonical_json_is_utf8_ordered_indented_and_newline_terminated() -> None:
    projection = project_workspace_files(_document(), handle_registry={})

    assert projection.files["/workspace/header.json"] == (
        "{\n"
        '  "job_title": "採購專員",\n'
        '  "occupation_category_name": "採購",\n'
        '  "occupation_name": "採購人員",\n'
        '  "occupation_code": "A-001",\n'
        '  "industry_name": "製造業",\n'
        '  "industry_code": "M-001",\n'
        '  "work_description": "維持採購作業順暢。",\n'
        '  "notes": "保留基線備註。"\n'
        "}\n"
    )
