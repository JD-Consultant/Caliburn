from __future__ import annotations

import json
from uuid import UUID

from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    EmployeeSource,
    EmployeeSourceKind,
    SourceProcessingStatus,
)
from app.consultant.workspace_resources import WorkspaceCatalog, project_workspace_files
from app.consultant.workspace_review import derive_workspace_review
from app.consultant.workspace_state import (
    WorkspaceManifest,
    WorkspaceValidationStatus,
    approved_document_digest,
    workspace_resource_digest,
)
from app.consultant.workspace_validation import evidence_basis_digest, validate_workspace_payload
from app.consultant.current_document_edit import plan_current_document_edit


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000a01")
DUTY_ID = UUID("00000000-0000-0000-0000-000000000a02")
TASK_ID = UUID("00000000-0000-0000-0000-000000000a03")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000a04")
SKILLS = ("knowledge", "task-boundary")


def _source() -> EmployeeSource:
    return EmployeeSource.pending(
        source_id=SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="員工說明核對訂單、完成正確訂單與工作邊界。",
    ).model_copy(update={"processing_status": SourceProcessingStatus.COMMITTED})


def _document(*, task_statement: str, frequency: str) -> ApprovedJobDocument:
    return ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        job_title="採購專員",
        work_description="管理採購流程。",
        duties=(
            ApprovedDuty(
                duty_id=DUTY_ID,
                statement="管理採購作業",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=TASK_ID,
                duty_id=DUTY_ID,
                statement=task_statement,
                action="核對",
                object="訂單",
                purpose_result="避免錯誤出貨",
                frequency_text=frequency,
                display_order=0,
            ),
        ),
    )


def _review(
    approved: ApprovedJobDocument,
    current_files: dict[str, str],
    registry: dict[str, UUID],
):
    catalog = WorkspaceCatalog.from_snapshot(
        approved,
        sources=(_source(),),
        handle_registry=registry,
    )
    validation = validate_workspace_payload(
        current_files,
        catalog=catalog,
        selected_skill_ids=SKILLS,
        loaded_skill_ids=SKILLS,
    )
    manifest = WorkspaceManifest(
        generation=1,
        resource_digest=workspace_resource_digest(current_files),
        approved_baseline_revision=0,
        approved_baseline_digest=approved_document_digest(approved),
        evidence_basis_digest=evidence_basis_digest(validation.current_sources),
        validation_status=WorkspaceValidationStatus.VALID,
        entity_ids_by_handle=registry,
    )
    return derive_workspace_review(approved, validation, manifest, ())


def test_employee_edit_approves_only_touched_field_and_keeps_other_ai_diff() -> None:
    approved = _document(task_statement="核准敘述", frequency="每月")
    current = _document(task_statement="AI 新敘述", frequency="每月")
    submitted = _document(task_statement="AI 新敘述", frequency="每週")
    current_projection = project_workspace_files(current, handle_registry={})
    current_files = dict(current_projection.files)
    _attach_evidence(current_files, handle="k-001")
    registry = dict(current_projection.handle_registry)
    review = _review(approved, current_files, registry)

    plan = plan_current_document_edit(
        approved=approved,
        current=current,
        submitted=submitted,
        workspace_files=current_files,
        handle_registry=registry,
        review=review,
    )

    assert plan.approved_after.tasks[0].statement == "核准敘述"
    assert plan.approved_after.tasks[0].frequency_text == "每週"
    assert "/workspace/tasks/task-001.json/frequency_text" in plan.employee_override_paths
    assert not any(path.endswith("/statement") for path in plan.employee_override_paths)
    assert plan.employee_text_paths == (f"/tasks/{TASK_ID}/frequency_text",)
    assert all("/workspace/" not in path for path in plan.employee_text_paths)


def _attach_evidence(files: dict[str, str], *, handle: str) -> None:
    for path, raw in tuple(files.items()):
        if not path.startswith("/workspace/opks/") or not path.endswith(".json"):
            continue
        payload = json.loads(raw)
        if payload.get("handle") != handle:
            continue
        payload["evidence"] = [
            {
                "source_handle": "source-001",
                "quote": "員工說明核對訂單",
                "skill_ids": ["knowledge"],
            }
        ]
        files[path] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def test_editing_ai_added_task_promotes_required_new_duty_but_not_unrelated_opks() -> None:
    approved = _document(task_statement="核准敘述", frequency="每月").model_copy(
        update={"duties": (), "tasks": (), "opks": ()}
    )
    new_duty_id = UUID("00000000-0000-0000-0000-000000000a11")
    new_task_id = UUID("00000000-0000-0000-0000-000000000a12")
    unrelated_opks_id = UUID("00000000-0000-0000-0000-000000000a13")
    new_duty = ApprovedDuty(
        duty_id=new_duty_id,
        statement="AI 新職責",
        display_order=0,
    )
    new_task = ApprovedTask(
        task_id=new_task_id,
        duty_id=new_duty_id,
        statement="AI 新任務",
        action="處理",
        object="訂單",
        purpose_result="完成採購",
        display_order=0,
    )
    unrelated_opks = ApprovedOpksItem(
        item_id=unrelated_opks_id,
        kind=ApprovedOpksKind.KNOWLEDGE,
        text="AI 無關知識",
        display_order=0,
        evidence_source_ids=(SOURCE_ID,),
    )
    current = approved.model_copy(
        update={
            "duties": (new_duty,),
            "tasks": (new_task,),
            "opks": (unrelated_opks,),
        }
    )
    submitted = current.model_copy(
        update={
            "tasks": (new_task.model_copy(update={"statement": "員工修正任務"}),),
        }
    )
    current_projection = project_workspace_files(current, handle_registry={})
    current_files = dict(current_projection.files)
    _attach_evidence(current_files, handle="k-001")
    registry = dict(current_projection.handle_registry)
    review = _review(approved, current_files, registry)

    plan = plan_current_document_edit(
        approved,
        current,
        submitted,
        current_files,
        registry,
        review,
    )

    all_actions = tuple(action for group in review.groups for action in group.actions)
    duty_action = next(action for action in all_actions if action.path == "/duties")
    task_action = next(action for action in all_actions if action.path == "/tasks")
    unrelated_action = next(action for action in all_actions if action.path == "/opks")
    assert set(plan.accepted_pending_action_ids) == {
        duty_action.action_id,
        task_action.action_id,
    }
    assert set(plan.accepted_pending_action_ids) & {unrelated_action.action_id} == set()
    assert {item.duty_id for item in plan.approved_after.duties} == {new_duty_id}
    assert {item.task_id for item in plan.approved_after.tasks} == {new_task_id}
    assert {item.item_id for item in plan.approved_after.opks} == set()
    assert plan.approved_after.tasks[0].statement == "員工修正任務"


def test_editing_one_member_of_a_split_promotes_its_atomic_subgroup() -> None:
    approved = _document(task_statement="原始任務", frequency="每月").model_copy(
        update={
            "opks": (
                ApprovedOpksItem(
                    item_id=UUID("00000000-0000-0000-0000-000000000a21"),
                    kind=ApprovedOpksKind.KNOWLEDGE,
                    text="完成採購",
                    display_order=0,
                    task_ids=(TASK_ID,),
                    evidence_source_ids=(SOURCE_ID,),
                ),
            )
        }
    )
    split_task_ids = (
        UUID("00000000-0000-0000-0000-000000000a22"),
        UUID("00000000-0000-0000-0000-000000000a23"),
    )
    split_tasks = tuple(
        ApprovedTask(
            task_id=task_id,
            duty_id=DUTY_ID,
            statement=f"拆分任務 {index}",
            action="處理",
            object="訂單",
            purpose_result="完成採購",
            display_order=index,
        )
        for index, task_id in enumerate(split_task_ids)
    )
    current = approved.model_copy(
        update={
            "notes": "AI 無關備註",
            "tasks": split_tasks,
            "opks": (
                approved.opks[0].model_copy(update={"task_ids": split_task_ids}),
            ),
        }
    )
    submitted = current.model_copy(
        update={
            "tasks": (
                split_tasks[0].model_copy(update={"statement": "員工修正拆分任務"}),
                split_tasks[1],
            )
        }
    )
    current_projection = project_workspace_files(current, handle_registry={})
    current_files = dict(current_projection.files)
    _attach_evidence(current_files, handle="k-001")
    registry = dict(current_projection.handle_registry)
    review = _review(approved, current_files, registry)

    plan = plan_current_document_edit(
        approved,
        current,
        submitted,
        current_files,
        registry,
        review,
    )

    all_actions = tuple(action for group in review.groups for action in group.actions)
    split_action_ids = {
        action.action_id
        for action in all_actions
        if action.path.startswith("/tasks")
        or action.path.startswith("/opks/")
    }
    unrelated_action_ids = {
        action.action_id
        for action in all_actions
        if action.path == "/notes"
    }
    assert split_action_ids
    assert set(plan.accepted_pending_action_ids) == split_action_ids
    assert set(plan.accepted_pending_action_ids).isdisjoint(unrelated_action_ids)
    assert {item.task_id for item in plan.approved_after.tasks} == set(split_task_ids)
    assert plan.approved_after.tasks[0].statement == "員工修正拆分任務"
    assert plan.approved_after.opks[0].task_ids == split_task_ids
    assert plan.approved_after.notes is None


def test_removing_an_ai_only_entity_cleans_current_without_changing_approved() -> None:
    ai_task_id = UUID("00000000-0000-0000-0000-000000000a31")
    approved = _document(task_statement="核准敘述", frequency="每月")
    ai_task = ApprovedTask(
        task_id=ai_task_id,
        duty_id=DUTY_ID,
        statement="AI 暫存任務",
        action="處理",
        object="訂單",
        purpose_result="完成採購",
        display_order=1,
    )
    current = approved.model_copy(update={"tasks": (*approved.tasks, ai_task)})
    submitted = approved
    current_projection = project_workspace_files(current, handle_registry={})
    current_files = dict(current_projection.files)
    registry = dict(current_projection.handle_registry)
    review = _review(approved, current_files, registry)

    plan = plan_current_document_edit(
        approved,
        current,
        submitted,
        current_files,
        registry,
        review,
    )

    add_action = next(
        action
        for group in review.groups
        for action in group.actions
        if action.path == "/tasks"
        and isinstance(action.after, dict)
        and action.after["task_id"] == str(ai_task_id)
    )
    assert plan.approved_after.model_dump(mode="json") == approved.model_dump(mode="json")
    assert plan.accepted_pending_action_ids == (add_action.action_id,)
    assert set(plan.accepted_pending_action_ids) == {
        action.action_id
        for group in review.groups
        for action in group.actions
    }
