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
    DocumentChangeSet,
    DocumentPatchAction,
    DocumentPatchOperation,
    DocumentPathRead,
    EmployeeSource,
    EmployeeSourceKind,
)
from app.consultant.workspace_resources import (
    CandidateReviewGroupsResource,
    CandidateTaskResource,
    WorkspaceCatalog,
    WorkspaceResourceError,
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
SECOND_RUN_ID = UUID("00000000-0000-0000-0000-000000000110")
COLLISION_ID = UUID("00000000-0000-0000-0000-000000000111")
ACTION_ONE_ID = UUID("00000000-0000-0000-0000-000000000301")
ACTION_TWO_ID = UUID("00000000-0000-0000-0000-000000000302")
ACTION_THREE_ID = UUID("00000000-0000-0000-0000-000000000303")
ACTION_FOUR_ID = UUID("00000000-0000-0000-0000-000000000304")
ACTION_FIVE_ID = UUID("00000000-0000-0000-0000-000000000305")
EXTERNAL_ACTION_ID = UUID("00000000-0000-0000-0000-000000000399")


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


def _pending_action(
    action_id: UUID,
    *,
    depends_on_action_ids: tuple[UUID, ...] = (),
) -> DocumentPatchAction:
    return DocumentPatchAction(
        action_id=action_id,
        operation=DocumentPatchOperation.ADD,
        path="/tasks",
        target_key="task_id",
        after={"task_id": str(action_id), "statement": "新增工作"},
        source_ids=(SOURCE_ID,),
        read_set=(
            DocumentPathRead(
                path="/tasks",
                value_sha256="a" * 64,
            ),
        ),
        depends_on_action_ids=depends_on_action_ids,
    )


def _pending_bundle(
    changeset_id: UUID,
    actions: tuple[DocumentPatchAction, ...],
    *,
    external_dependency_action_ids: tuple[UUID, ...] = (),
) -> DocumentChangeSet:
    return DocumentChangeSet(
        changeset_id=changeset_id,
        summary="待審候選",
        actions=actions,
        source_ids=(SOURCE_ID,),
        created_revision=1,
        external_dependency_action_ids=external_dependency_action_ids,
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


def test_catalog_keeps_historical_opks_kind_for_pending_targets() -> None:
    historical_output_id = UUID("00000000-0000-0000-0000-000000000112")
    historical_indicator_id = UUID("00000000-0000-0000-0000-000000000113")
    withdraw = DocumentPatchAction(
        action_id=ACTION_ONE_ID,
        operation=DocumentPatchOperation.WITHDRAW,
        path=f"/opks/{historical_output_id}",
        target_key="withdraw:/opks:output",
        before={
            "item_id": str(historical_output_id),
            "kind": "output",
            "text": "歷史產出",
        },
        source_ids=(SOURCE_ID,),
        read_set=(
            DocumentPathRead(
                path=f"/opks/{historical_output_id}",
                value_sha256="b" * 64,
            ),
        ),
    )
    merge = DocumentPatchAction(
        action_id=ACTION_TWO_ID,
        operation=DocumentPatchOperation.MERGE,
        path="/opks",
        target_key="merge:/opks:indicator",
        before=[
            {"item_id": str(historical_indicator_id), "kind": "indicator"}
        ],
        after=[
            {"item_id": str(historical_indicator_id), "kind": "indicator"}
        ],
        source_ids=(SOURCE_ID,),
        read_set=(
            DocumentPathRead(
                path=f"/opks/{historical_indicator_id}",
                value_sha256="c" * 64,
            ),
        ),
        target_ids=(historical_indicator_id,),
    )
    catalog = WorkspaceCatalog.from_snapshot(
        _document(),
        pending=(
            _pending_bundle(
                UUID("00000000-0000-0000-0000-000000000114"),
                (withdraw, merge),
            ),
        ),
    )

    assert catalog.handle_for_id(historical_output_id) == "o-002"
    assert catalog.handle_for_id(historical_indicator_id) == "p-002"


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


def test_projected_review_groups_use_global_action_handles_and_dependencies() -> None:
    first_bundle = _pending_bundle(
        UUID("00000000-0000-0000-0000-000000000401"),
        (_pending_action(ACTION_ONE_ID), _pending_action(ACTION_TWO_ID)),
    )
    second_bundle = _pending_bundle(
        UUID("00000000-0000-0000-0000-000000000402"),
        (_pending_action(ACTION_THREE_ID, depends_on_action_ids=(ACTION_TWO_ID,)),),
        external_dependency_action_ids=(ACTION_TWO_ID,),
    )
    catalog = WorkspaceCatalog.from_snapshot(
        _document(),
        pending=(first_bundle, second_bundle),
    )

    files = project_candidate_files(catalog, run_id=RUN_ID)
    groups = json.loads(files[f"/candidate/{RUN_ID}/review-groups.json"])["groups"]

    assert groups == [
        {
            "handle": "review-001",
            "action_handles": ["action-001", "action-002"],
            "depends_on_handles": [],
        },
        {
            "handle": "review-002",
            "action_handles": ["action-003"],
            "depends_on_handles": ["action-002"],
        },
    ]


def test_projected_review_groups_allocate_repeated_external_dependencies() -> None:
    first_bundle = _pending_bundle(
        UUID("00000000-0000-0000-0000-000000000501"),
        (_pending_action(ACTION_FOUR_ID, depends_on_action_ids=(EXTERNAL_ACTION_ID,)),),
        external_dependency_action_ids=(EXTERNAL_ACTION_ID,),
    )
    second_bundle = _pending_bundle(
        UUID("00000000-0000-0000-0000-000000000502"),
        (_pending_action(ACTION_FIVE_ID, depends_on_action_ids=(EXTERNAL_ACTION_ID,)),),
        external_dependency_action_ids=(EXTERNAL_ACTION_ID,),
    )
    catalog = WorkspaceCatalog.from_snapshot(
        _document(),
        pending=(first_bundle, second_bundle),
    )

    files = project_candidate_files(catalog, run_id=RUN_ID)
    groups = json.loads(files[f"/candidate/{RUN_ID}/review-groups.json"])["groups"]

    assert groups == [
        {
            "handle": "review-001",
            "action_handles": ["action-001"],
            "depends_on_handles": ["action-003"],
        },
        {
            "handle": "review-002",
            "action_handles": ["action-002"],
            "depends_on_handles": ["action-003"],
        },
    ]


def test_candidate_draft_retains_parsed_review_groups_resource() -> None:
    catalog = WorkspaceCatalog.from_snapshot(_document(), pending=())
    files = project_candidate_files(catalog, run_id=RUN_ID)
    payload = {
        "groups": [
            {
                "handle": "review-009",
                "action_handles": ["action-777"],
                "depends_on_handles": ["action-003"],
            }
        ]
    }
    files[f"/candidate/{RUN_ID}/review-groups.json"] = json.dumps(payload)

    draft = parse_candidate_files(catalog, files)

    assert draft.review_groups == CandidateReviewGroupsResource.model_validate(payload)


def test_candidate_draft_keeps_evidence_owner_for_each_opks_handle() -> None:
    catalog = WorkspaceCatalog.from_snapshot(_document(), pending=())
    files = project_candidate_files(catalog, run_id=RUN_ID)
    output_path = f"/candidate/{RUN_ID}/opks/o/o-001.json"
    skill_path = f"/candidate/{RUN_ID}/opks/s/s-001.json"
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

    draft = parse_candidate_files(catalog, files)

    assert [binding.opks_handle for binding in draft.opks_evidence] == [
        "o-001",
        "s-001",
    ]
    assert [
        (binding.references[0].quote, binding.references[0].skill_ids)
        for binding in draft.opks_evidence
    ] == [("輸出原話", ("output",)), ("技能原話", ("skill",))]


def test_new_candidate_entity_id_includes_run_namespace() -> None:
    catalog = WorkspaceCatalog.from_snapshot(_document(), pending=())

    def files_for(run_id: UUID) -> dict[str, str]:
        files = project_candidate_files(catalog, run_id=run_id)
        files[f"/candidate/{run_id}/duties/duty-999.json"] = json.dumps(
            {"handle": "duty-999", "statement": "新增職責"},
            ensure_ascii=False,
        )
        return files

    first = parse_candidate_files(catalog, files_for(RUN_ID))
    same_run = parse_candidate_files(catalog, files_for(RUN_ID))
    second = parse_candidate_files(catalog, files_for(SECOND_RUN_ID))
    first_id = next(
        duty.duty_id
        for duty in first.approved_document.duties
        if duty.statement == "新增職責"
    )
    same_run_id = next(
        duty.duty_id
        for duty in same_run.approved_document.duties
        if duty.statement == "新增職責"
    )
    second_id = next(
        duty.duty_id
        for duty in second.approved_document.duties
        if duty.statement == "新增職責"
    )

    assert first_id == same_run_id
    assert first_id != second_id


def test_parse_rejects_non_uuid_candidate_run_namespace() -> None:
    catalog = WorkspaceCatalog.from_snapshot(_document(), pending=())
    files = project_candidate_files(catalog, run_id=RUN_ID)
    invalid_files = {
        path.replace(f"/candidate/{RUN_ID}/", "/candidate/not-a-uuid/"): value
        for path, value in files.items()
    }

    with pytest.raises(WorkspaceResourceError, match="must be a UUID"):
        parse_candidate_files(catalog, invalid_files)


def test_parse_rejects_mixed_candidate_run_namespaces() -> None:
    catalog = WorkspaceCatalog.from_snapshot(_document(), pending=())
    files = project_candidate_files(catalog, run_id=RUN_ID)
    files[f"/candidate/{SECOND_RUN_ID}/header.json"] = files[
        f"/candidate/{RUN_ID}/header.json"
    ]

    with pytest.raises(WorkspaceResourceError, match="another run"):
        parse_candidate_files(catalog, files)


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
        WorkspaceCatalog.from_snapshot(document, pending=())


def test_catalog_deduplicates_exact_repeated_source_facts_before_mapping() -> None:
    source = EmployeeSource.pending(
        source_id=SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="員工原話",
    )

    catalog = WorkspaceCatalog.from_snapshot(
        _document(),
        pending=(),
        sources=(source, source),
    )

    assert catalog.source_ids == (SOURCE_ID,)


def test_provider_evidence_reference_rejects_invalid_handle() -> None:
    with pytest.raises(ValidationError):
        OutputEvidenceReference(
            source_handle="not-a-local-handle",
            quote="核對訂單",
            skill_ids=("task-boundary",),
        )
