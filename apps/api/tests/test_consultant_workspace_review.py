from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

from app.consultant.document_authority import apply_document_actions
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    DocumentChangeStatus,
    DocumentPatchOperation,
    EmployeeSource,
    EmployeeSourceKind,
    SourceProcessingStatus,
    SourceValidity,
)
from app.consultant.workspace_resources import (
    WorkspaceCatalog,
    project_workspace_files,
    workspace_entity_id,
)
from app.consultant.workspace_review import (
    WorkspaceReviewDecision,
    WorkspaceReviewDecisionKind,
    derive_workspace_review,
    workspace_review_files,
)
from app.consultant.workspace_state import (
    WorkspaceDiagnostic,
    WorkspaceManifest,
    WorkspaceValidationStatus,
    approved_document_digest,
    workspace_resource_digest,
)
from app.consultant.workspace_validation import (
    WorkspacePayloadValidation,
    evidence_basis_digest,
    validate_workspace_payload,
)


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000801")
DUTY_ID = UUID("00000000-0000-0000-0000-000000000811")
TASK_ID = UUID("00000000-0000-0000-0000-000000000812")
OUTPUT_ID = UUID("00000000-0000-0000-0000-000000000813")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000814")
CORRECTED_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000815")
SKILLS = ("knowledge", "task-boundary")


def _source() -> EmployeeSource:
    return EmployeeSource.pending(
        source_id=SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="員工說明核對訂單、完成正確訂單與工作邊界。",
    ).model_copy(update={"processing_status": SourceProcessingStatus.COMMITTED})


def _document() -> ApprovedJobDocument:
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
                statement="核對訂單",
                action="核對",
                object="訂單",
                purpose_result="避免錯誤出貨",
                display_order=0,
            ),
        ),
        opks=(
            ApprovedOpksItem(
                item_id=OUTPUT_ID,
                kind=ApprovedOpksKind.KNOWLEDGE,
                text="訂單核對規則",
                display_order=0,
                task_ids=(TASK_ID,),
                evidence_source_ids=(SOURCE_ID,),
            ),
        ),
    )


def _catalog() -> WorkspaceCatalog:
    return WorkspaceCatalog.from_snapshot(_document(), sources=(_source(),))


def _workspace() -> tuple[dict[str, str], dict[str, UUID]]:
    projection = project_workspace_files(_document(), handle_registry={})
    return dict(projection.files), dict(projection.handle_registry)


def _edit(files: dict[str, str], path: str, **updates: object) -> None:
    payload = json.loads(files[path])
    payload.update(updates)
    files[path] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _validated(files: dict[str, str]) -> WorkspacePayloadValidation:
    return validate_workspace_payload(
        files,
        catalog=_catalog(),
        selected_skill_ids=SKILLS,
        loaded_skill_ids=SKILLS,
    )


def _manifest(
    files: dict[str, str],
    registry: dict[str, UUID],
    *,
    generation: int = 3,
    status: WorkspaceValidationStatus = WorkspaceValidationStatus.VALID,
) -> WorkspaceManifest:
    return WorkspaceManifest(
        generation=generation,
        resource_digest=workspace_resource_digest(files),
        approved_baseline_revision=7,
        approved_baseline_digest=approved_document_digest(_document()),
        evidence_basis_digest=evidence_basis_digest((_source(),)),
        validation_status=status,
        entity_ids_by_handle=registry,
    )


def _derive(
    files: dict[str, str],
    registry: dict[str, UUID],
    *,
    decisions: tuple[WorkspaceReviewDecision, ...] = (),
    generation: int = 3,
):
    return derive_workspace_review(
        _document(),
        _validated(files),
        _manifest(files, registry, generation=generation),
        decisions,
    )


def test_formatting_and_json_key_order_do_not_create_a_semantic_review() -> None:
    files, registry = _workspace()
    for path, raw in tuple(files.items()):
        files[path] = json.dumps(
            json.loads(raw), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    review = _derive(files, registry)

    assert review.groups == ()
    assert review.changesets == ()
    assert review.diagnostics == ()


def test_semantic_review_ids_are_stable_and_bind_the_workspace_version() -> None:
    files, registry = _workspace()
    _edit(files, "/workspace/tasks/task-001.json", statement="複核採購訂單")

    first = _derive(files, registry)
    replay = _derive(dict(reversed(tuple(files.items()))), registry)
    next_generation = _derive(files, registry, generation=4)

    assert len(first.groups) == 1
    assert first.groups[0].changeset == replay.groups[0].changeset
    assert first.groups[0].group_digest == replay.groups[0].group_digest
    assert (
        first.groups[0].changeset.changeset_id
        != next_generation.groups[0].changeset.changeset_id
    )
    assert (
        first.groups[0].changeset.actions[0].action_id
        != next_generation.groups[0].changeset.actions[0].action_id
    )


def test_resource_level_header_diagnostic_blocks_only_header_review_group() -> None:
    files, registry = _workspace()
    _edit(files, "/workspace/header.json", job_title="資深採購專員")
    _edit(files, "/workspace/tasks/task-001.json", statement="複核採購訂單")
    valid = _validated(files)
    diagnostic = WorkspaceDiagnostic(
        code="evidence-source-stale",
        path="/workspace/header.json",
        message="Header Evidence source is no longer current.",
    )
    validation = replace(valid, diagnostics=(diagnostic,))
    manifest = _manifest(
        files,
        registry,
        status=WorkspaceValidationStatus.CONFLICTED,
    ).model_copy(update={"diagnostics": (diagnostic,)})

    review = derive_workspace_review(_document(), validation, manifest, ())
    header_group = next(
        group
        for group in review.groups
        if any(action.path == "/job_title" for action in group.actions)
    )
    task_group = next(
        group
        for group in review.groups
        if any(str(TASK_ID) in action.path for action in group.actions)
    )

    assert header_group.diagnostics == (diagnostic,)
    assert task_group.diagnostics == ()
    assert review.blocking_diagnostics == ()


def test_source_corrected_opks_diagnostic_blocks_only_its_review_group() -> None:
    document = _document().model_copy(
        update={
            "opks": (
                _document().opks[0].model_copy(
                    update={"kind": ApprovedOpksKind.OUTPUT}
                ),
            )
        }
    )
    projected = project_workspace_files(document, handle_registry={})
    files = dict(projected.files)
    registry = dict(projected.handle_registry)
    _edit(files, "/workspace/opks/o/o-001.json", text="更新後的核對結果")
    _edit(files, "/workspace/tasks/task-001.json", statement="複核採購訂單")
    original = _source().model_copy(
        update={
            "validity": SourceValidity.SUPERSEDED,
            "superseded_by_source_id": CORRECTED_SOURCE_ID,
        }
    )
    correction = EmployeeSource.pending(
        source_id=CORRECTED_SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="更正：只需使用新版訂單核對規則。",
        supersedes_source_id=SOURCE_ID,
    ).model_copy(update={"processing_status": SourceProcessingStatus.COMMITTED})
    catalog = WorkspaceCatalog.from_snapshot(
        document,
        sources=(original, correction),
    )
    validation = validate_workspace_payload(
        files,
        catalog=catalog,
        selected_skill_ids=SKILLS,
        loaded_skill_ids=SKILLS,
    )
    manifest = WorkspaceManifest(
        generation=3,
        resource_digest=workspace_resource_digest(files),
        approved_baseline_revision=7,
        approved_baseline_digest=approved_document_digest(document),
        evidence_basis_digest=evidence_basis_digest((correction,)),
        validation_status=WorkspaceValidationStatus.CONFLICTED,
        diagnostics=validation.diagnostics,
        entity_ids_by_handle=registry,
    )

    review = derive_workspace_review(document, validation, manifest, ())
    opks_group = next(
        group
        for group in review.groups
        if any(str(OUTPUT_ID) in action.path for action in group.actions)
    )
    task_group = next(
        group
        for group in review.groups
        if any(str(TASK_ID) in action.path for action in group.actions)
    )

    assert any(
        diagnostic.code == "evidence-source-stale"
        for diagnostic in opks_group.diagnostics
    )
    assert task_group.diagnostics == ()
    assert review.blocking_diagnostics == ()


def test_add_withdraw_reassign_and_reorder_are_derived_without_split_or_merge() -> None:
    files, registry = _workspace()
    new_duty_id = workspace_entity_id(
        DOCUMENT_ID, "duty-002", "duty", handle_registry=registry
    )
    registry["duty-002"] = new_duty_id
    files["/workspace/duties/duty-002.json"] = json.dumps(
        {"handle": "duty-002", "statement": "管理供應商"},
        ensure_ascii=False,
    )
    _edit(
        files,
        "/workspace/tasks/task-001.json",
        duty_handle="duty-002",
    )
    del files["/workspace/opks/k/k-001.json"]

    review = _derive(files, registry)
    actions = tuple(action for group in review.groups for action in group.changeset.actions)

    assert {action.operation for action in actions} == {
        DocumentPatchOperation.ADD,
        DocumentPatchOperation.WITHDRAW,
        DocumentPatchOperation.REASSIGN,
    }
    assert all(action.operation in set(DocumentPatchOperation) for action in actions)


def test_review_files_translate_only_structural_id_fields_to_handles() -> None:
    files, registry = _workspace()
    new_duty_id = workspace_entity_id(
        DOCUMENT_ID, "duty-002", "duty", handle_registry=registry
    )
    registry["duty-002"] = new_duty_id
    files["/workspace/duties/duty-002.json"] = json.dumps(
        {"handle": "duty-002", "statement": "管理供應商"},
        ensure_ascii=False,
    )
    _edit(
        files,
        "/workspace/header.json",
        notes=str(TASK_ID),
    )
    _edit(
        files,
        "/workspace/tasks/task-001.json",
        duty_handle="duty-002",
        statement=str(DUTY_ID),
        object=str(OUTPUT_ID),
    )

    serialized = workspace_review_files(_derive(files, registry))
    actions = tuple(
        action
        for path, raw in serialized.items()
        if path.startswith("/groups/")
        for action in json.loads(raw)["actions"]
    )
    by_path = {action["path"]: action for action in actions}

    assert by_path["/tasks/task-001/duty_id"]["after"] == "duty-002"
    assert by_path["/tasks/task-001/statement"]["after"] == str(DUTY_ID)
    assert by_path["/tasks/task-001/object"]["after"] == str(OUTPUT_ID)
    assert by_path["/notes"]["after"] == str(TASK_ID)


def test_existing_entity_display_order_is_a_reorder_not_a_revise() -> None:
    files, registry = _workspace()
    _edit(files, "/workspace/tasks/task-001.json", display_order=4)

    review = _derive(files, registry)

    assert len(review.groups) == 1
    action = review.groups[0].changeset.actions[0]
    assert action.operation is DocumentPatchOperation.REORDER
    assert action.path == f"/tasks/{TASK_ID}/display_order"
    assert action.after == 4


def test_ten_independent_task_and_opks_changes_remain_individually_reviewable() -> None:
    tasks = tuple(
        ApprovedTask(
            task_id=UUID(f"00000000-0000-0000-0000-{820 + index:012d}"),
            duty_id=DUTY_ID,
            statement=f"工作 {index}",
            action="處理",
            object=f"資料 {index}",
            display_order=index,
        )
        for index in range(10)
    )
    approved = _document().model_copy(update={"tasks": (), "opks": ()})
    after = approved.model_copy(
        update={
            "tasks": tasks,
            "opks": tuple(
                ApprovedOpksItem(
                    item_id=UUID(f"00000000-0000-0000-0000-{840 + index:012d}"),
                    kind=ApprovedOpksKind.OUTPUT,
                    text=f"規則 {index}",
                    display_order=index,
                    task_ids=(task.task_id,),
                    evidence_source_ids=(SOURCE_ID,),
                )
                for index, task in enumerate(tasks)
            ),
        }
    )
    basis = _validated(_workspace()[0]).default_basis
    assert basis is not None
    validation = WorkspacePayloadValidation(
        document=SimpleNamespace(approved_document=after),
        diagnostics=(),
        current_sources=(_source(),),
        evidence_by_handle={},
        default_basis=basis,
    )
    manifest = _manifest(_workspace()[0], {}, generation=9).model_copy(
        update={"approved_baseline_digest": approved_document_digest(approved)}
    )

    review = derive_workspace_review(approved, validation, manifest, ())

    assert len(review.groups) == 10
    assert all(len(group.changeset.actions) == 2 for group in review.groups)
    assert all(
        {action.operation for action in group.changeset.actions}
        == {DocumentPatchOperation.ADD}
        for group in review.groups
    )
    assert all(
        all(action.atomic_subgroup_id is None for action in group.changeset.actions)
        for group in review.groups
    )

    rejected = derive_workspace_review(
        approved,
        validation,
        manifest,
        (
            WorkspaceReviewDecision.from_group(
                WorkspaceReviewDecisionKind.REJECT,
                review.groups[0],
                workspace_digest=review.workspace_digest,
            ),
        ),
    )
    assert len(rejected.groups) == 9
    assert rejected.diagnostics[0].code == "rejected-semantic-change"
    assert rejected.blocking_diagnostics == ()

    first_group = review.groups[0]
    rejected_output = next(
        action for action in first_group.actions if action.path.startswith("/opks")
    )
    partially_rejected = derive_workspace_review(
        approved,
        validation,
        manifest,
        (
            WorkspaceReviewDecision.from_group(
                WorkspaceReviewDecisionKind.REJECT,
                first_group,
                workspace_digest=review.workspace_digest,
                selected_action_ids=(rejected_output.action_id,),
            ),
        ),
    )
    remaining_first_group = next(
        group
        for group in partially_rejected.groups
        if any(action.target_key == first_group.actions[0].target_key for action in group.actions)
    )
    assert len(remaining_first_group.actions) == 1
    assert remaining_first_group.actions[0].path.startswith("/tasks")
    assert any(
        item.code == "rejected-semantic-change"
        for item in partially_rejected.diagnostics
    )


def test_task_replacement_forms_one_atomic_dependency_group() -> None:
    files, registry = _workspace()
    del files["/workspace/tasks/task-001.json"]
    for index in (2, 3):
        handle = f"task-{index:03d}"
        registry[handle] = workspace_entity_id(
            DOCUMENT_ID, handle, "task", handle_registry=registry
        )
        files[f"/workspace/tasks/{handle}.json"] = json.dumps(
            {
                "handle": handle,
                "duty_handle": "duty-001",
                "statement": f"替代工作 {index}",
                "action": "處理",
                "object": "訂單",
                "purpose_result": "完成採購",
                "context": None,
                "frequency_text": None,
                "responsibility_role": "primary",
                "enablers": [],
            },
            ensure_ascii=False,
        )
    _edit(
        files,
        "/workspace/opks/k/k-001.json",
        task_handles=["task-002", "task-003"],
        evidence=[
            {
                "source_handle": "source-001",
                "quote": "核對訂單",
                "skill_ids": ["knowledge"],
            }
        ],
    )

    review = _derive(files, registry)
    group = review.group_containing_path("/tasks/task-001")

    assert group is not None
    assert {action.operation for action in group.changeset.actions} == {
        DocumentPatchOperation.ADD,
        DocumentPatchOperation.WITHDRAW,
        DocumentPatchOperation.REVISE,
    }
    subgroup_ids = {action.atomic_subgroup_id for action in group.changeset.actions}
    assert len(subgroup_ids) == 1
    assert None not in subgroup_ids


def test_invalid_or_unvalidated_workspace_only_exposes_diagnostics() -> None:
    files, registry = _workspace()
    validation = WorkspacePayloadValidation(
        document=None,
        diagnostics=_validated({**files, "/workspace/tasks/task-001.json": "{"}).diagnostics,
        current_sources=(_source(),),
        evidence_by_handle={},
        default_basis=None,
    )
    manifest = _manifest(
        files,
        registry,
        status=WorkspaceValidationStatus.UNVALIDATED,
    )

    review = derive_workspace_review(_document(), validation, manifest, ())

    assert review.changesets == ()
    assert review.groups == ()
    assert review.diagnostics


def test_valid_manifest_with_a_different_approved_baseline_is_not_reviewable() -> None:
    files, registry = _workspace()
    _edit(files, "/workspace/tasks/task-001.json", statement="複核採購訂單")
    manifest = _manifest(files, registry).model_copy(
        update={"approved_baseline_digest": "f" * 64}
    )

    review = derive_workspace_review(_document(), _validated(files), manifest, ())

    assert review.groups == ()
    assert any(item.code == "approved-baseline-stale" for item in review.diagnostics)


def test_valid_workspace_with_a_stale_evidence_basis_is_not_reviewable() -> None:
    files, registry = _workspace()
    _edit(files, "/workspace/tasks/task-001.json", statement="複核採購訂單")
    manifest = _manifest(files, registry).model_copy(
        update={"evidence_basis_digest": "e" * 64}
    )

    review = derive_workspace_review(_document(), _validated(files), manifest, ())

    assert review.groups == ()
    assert [item.code for item in review.diagnostics] == ["evidence-basis-stale"]


def test_accepted_after_state_naturally_disappears_from_review_projection() -> None:
    files, registry = _workspace()
    _edit(files, "/workspace/tasks/task-001.json", statement="複核採購訂單")
    pending = _derive(files, registry)
    accepted = apply_document_actions(
        _document(),
        tuple(
            action for group in pending.groups for action in group.changeset.actions
        ),
    )
    manifest = _manifest(files, registry).model_copy(
        update={
            "approved_baseline_revision": 8,
            "approved_baseline_digest": approved_document_digest(accepted),
        }
    )

    review = derive_workspace_review(accepted, _validated(files), manifest, ())

    assert review.groups == ()
    assert review.diagnostics == ()


def test_defer_and_reject_are_projected_only_for_matching_fingerprints() -> None:
    files, registry = _workspace()
    _edit(files, "/workspace/tasks/task-001.json", statement="複核採購訂單")
    pending = _derive(files, registry)
    group = pending.groups[0]
    defer = WorkspaceReviewDecision.from_group(
        WorkspaceReviewDecisionKind.DEFER,
        group,
        workspace_digest=pending.workspace_digest,
    )

    deferred = _derive(files, registry, decisions=(defer,))
    changed_files = dict(files)
    _edit(
        changed_files,
        "/workspace/tasks/task-001.json",
        statement="再次複核採購訂單",
    )
    changed_workspace = _derive(changed_files, registry, decisions=(defer,))

    assert {
        action.status for action in deferred.groups[0].changeset.actions
    } == {DocumentChangeStatus.DEFERRED}
    assert {
        action.status for action in changed_workspace.groups[0].changeset.actions
    } == {DocumentChangeStatus.PENDING}

    reject = WorkspaceReviewDecision.from_group(
        WorkspaceReviewDecisionKind.REJECT,
        group,
        workspace_digest=pending.workspace_digest,
    )
    rejected = _derive(files, registry, decisions=(reject,))

    assert rejected.groups == ()
    assert any(item.code == "rejected-semantic-change" for item in rejected.diagnostics)

    for field in ("evidence_digest", "boundary_digest"):
        changed_basis = replace(reject, **{field: "a" * 64})
        revived = _derive(files, registry, decisions=(changed_basis,))
        assert len(revived.groups) == 1

    unrelated_request = replace(reject, employee_request_digest="a" * 64)
    still_rejected = _derive(files, registry, decisions=(unrelated_request,))
    assert still_rejected.groups == ()
    assert [item.code for item in still_rejected.diagnostics] == [
        "rejected-semantic-change"
    ]


def test_raw_workspace_digest_change_preserves_defer_and_reject() -> None:
    files, registry = _workspace()
    _edit(files, "/workspace/tasks/task-001.json", statement="複核採購訂單")
    pending = _derive(files, registry)
    group = pending.groups[0]
    defer = WorkspaceReviewDecision.from_group(
        WorkspaceReviewDecisionKind.DEFER,
        group,
        workspace_digest=pending.workspace_digest,
    )
    reject = WorkspaceReviewDecision.from_group(
        WorkspaceReviewDecisionKind.REJECT,
        group,
        workspace_digest=pending.workspace_digest,
    )
    raw_changed_files = dict(files)
    task_path = "/workspace/tasks/task-001.json"
    raw_changed_files[task_path] = json.dumps(
        json.loads(raw_changed_files[task_path]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    deferred_replay = _derive(raw_changed_files, registry, decisions=(defer,))
    rejected_replay = _derive(raw_changed_files, registry, decisions=(reject,))

    assert deferred_replay.workspace_digest != pending.workspace_digest
    assert {
        action.status for action in deferred_replay.groups[0].changeset.actions
    } == {DocumentChangeStatus.DEFERRED}
    assert rejected_replay.groups == ()
    assert [item.code for item in rejected_replay.diagnostics] == [
        "rejected-semantic-change"
    ]


def test_unrelated_workspace_change_preserves_deferred_group() -> None:
    files, registry = _workspace()
    _edit(files, "/workspace/tasks/task-001.json", statement="複核採購訂單")
    pending = _derive(files, registry)
    task_group = next(
        group
        for group in pending.groups
        if any(str(TASK_ID) in action.path for action in group.actions)
    )
    defer = WorkspaceReviewDecision.from_group(
        WorkspaceReviewDecisionKind.DEFER,
        task_group,
        workspace_digest=pending.workspace_digest,
    )

    changed_files = dict(files)
    _edit(changed_files, "/workspace/header.json", job_title="資深採購專員")
    replay = _derive(changed_files, registry, decisions=(defer,), generation=4)
    replay_task_group = next(
        group
        for group in replay.groups
        if any(str(TASK_ID) in action.path for action in group.actions)
    )
    header_group = next(
        group
        for group in replay.groups
        if any(action.path == "/job_title" for action in group.actions)
    )

    assert replay.workspace_digest != pending.workspace_digest
    assert {action.status for action in replay_task_group.actions} == {
        DocumentChangeStatus.DEFERRED
    }
    assert {action.status for action in header_group.actions} == {
        DocumentChangeStatus.PENDING
    }
