from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.consultant.state import (
    DocumentChangeSet,
    DocumentPatchAction,
    DocumentPatchOperation,
    DocumentPathRead,
)
from app.consultant.workspace_authority import (
    WorkspaceAuthorityError,
    WorkspaceDecisionRecord,
    WorkspaceDecisionKind,
    WorkspaceReviewCommand,
    WorkspaceAuthorityService,
    build_workspace_rebase_plan,
    select_workspace_actions,
)
from app.consultant.workspace_review import (
    WorkspaceReviewGroup,
    WorkspaceReviewProjection,
)
from app.consultant.workspace_state import WorkspaceDiagnostic, workspace_resource_digest


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000901")
CHANGESET_ID = UUID("00000000-0000-0000-0000-000000000902")
TASK_ACTION_ID = UUID("00000000-0000-0000-0000-000000000903")
OUTPUT_ACTION_ID = UUID("00000000-0000-0000-0000-000000000904")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000905")
COMMAND_ID = UUID("00000000-0000-0000-0000-000000000906")
OTHER_CHANGESET_ID = UUID("00000000-0000-0000-0000-000000000907")
OTHER_ACTION_ID = UUID("00000000-0000-0000-0000-000000000908")
DIGEST = sha256(b"workspace-authority-test").hexdigest()


def _action(
    action_id: UUID,
    *,
    path: str,
    dependencies: tuple[UUID, ...] = (),
) -> DocumentPatchAction:
    return DocumentPatchAction(
        action_id=action_id,
        operation=DocumentPatchOperation.ADD,
        path=path,
        target_key=path,
        after={"value": str(action_id)},
        source_ids=(SOURCE_ID,),
        read_set=(DocumentPathRead(path=path, value_sha256=DIGEST),),
        depends_on_action_ids=dependencies,
    )


def _projection() -> WorkspaceReviewProjection:
    task = _action(TASK_ACTION_ID, path="/tasks")
    output = _action(
        OUTPUT_ACTION_ID,
        path="/opks",
        dependencies=(TASK_ACTION_ID,),
    )
    changeset = DocumentChangeSet(
        changeset_id=CHANGESET_ID,
        summary="新增任務及其產出",
        actions=(task, output),
        source_ids=(SOURCE_ID,),
        created_revision=7,
    )
    group = WorkspaceReviewGroup(
        changeset=changeset,
        group_digest=DIGEST,
        semantic_fingerprint=DIGEST,
        evidence_digest=DIGEST,
        employee_request_digest=DIGEST,
        boundary_digest=DIGEST,
    )
    return WorkspaceReviewProjection(workspace_digest=DIGEST, groups=(group,))


def _command(
    kind: WorkspaceDecisionKind,
    action_ids: tuple[UUID, ...],
) -> WorkspaceReviewCommand:
    return WorkspaceReviewCommand(
        command_id=COMMAND_ID,
        document_id=DOCUMENT_ID,
        decision=kind,
        approved_revision=7,
        workspace_generation=3,
        workspace_digest=DIGEST,
        changeset_id=CHANGESET_ID,
        selected_action_ids=action_ids,
        reason="員工決定",
    )


def test_visual_group_is_not_atomic_and_task_can_be_accepted_without_output() -> None:
    selected = select_workspace_actions(
        _projection(),
        _command(WorkspaceDecisionKind.ACCEPT, (TASK_ACTION_ID,)),
    )

    assert tuple(action.action_id for action in selected) == (TASK_ACTION_ID,)


def test_accepting_output_without_its_new_task_is_blocked() -> None:
    with pytest.raises(WorkspaceAuthorityError, match="depends on"):
        select_workspace_actions(
            _projection(),
            _command(WorkspaceDecisionKind.ACCEPT, (OUTPUT_ACTION_ID,)),
        )


def test_rejecting_prerequisite_without_dependent_is_blocked() -> None:
    with pytest.raises(WorkspaceAuthorityError, match="dependent"):
        select_workspace_actions(
            _projection(),
            _command(WorkspaceDecisionKind.REJECT, (TASK_ACTION_ID,)),
        )


def test_rejecting_only_dependent_is_allowed() -> None:
    selected = select_workspace_actions(
        _projection(),
        _command(WorkspaceDecisionKind.REJECT, (OUTPUT_ACTION_ID,)),
    )

    assert tuple(action.action_id for action in selected) == (OUTPUT_ACTION_ID,)


def test_owner_ten_tasks_and_nine_outputs_allows_only_tenth_output_rejection() -> None:
    task_ids = tuple(UUID(f"00000000-0000-0000-0000-{910 + index:012d}") for index in range(10))
    output_ids = tuple(UUID(f"00000000-0000-0000-0000-{920 + index:012d}") for index in range(10))
    tasks = tuple(
        _action(action_id, path="/tasks")
        for action_id in task_ids
    )
    outputs = tuple(
        _action(
            action_id,
            path="/opks",
            dependencies=(task_ids[index],),
        )
        for index, action_id in enumerate(output_ids)
    )
    group = WorkspaceReviewGroup(
        changeset=DocumentChangeSet(
            changeset_id=CHANGESET_ID,
            summary="十個任務與十個產出",
            actions=(*tasks, *outputs),
            source_ids=(SOURCE_ID,),
            created_revision=7,
        ),
        group_digest=DIGEST,
        semantic_fingerprint=DIGEST,
        evidence_digest=DIGEST,
        employee_request_digest=DIGEST,
        boundary_digest=DIGEST,
    )
    projection = WorkspaceReviewProjection(workspace_digest=DIGEST, groups=(group,))

    accepted_ids = (*task_ids, *output_ids[:9])
    accepted = select_workspace_actions(
        projection,
        _command(WorkspaceDecisionKind.ACCEPT, accepted_ids),
    )
    assert tuple(action.action_id for action in accepted) == accepted_ids

    rejected = select_workspace_actions(
        projection,
        _command(WorkspaceDecisionKind.REJECT, (output_ids[9],)),
    )
    assert tuple(action.action_id for action in rejected) == (output_ids[9],)


def test_conflicted_group_only_blocks_accept_not_reject() -> None:
    base_group = _projection().groups[0]
    conflicted_group = replace(
        base_group,
        changeset=base_group.changeset.model_copy(
            update={"actions": (base_group.actions[0],)}
        ),
        diagnostics=(
            WorkspaceDiagnostic(
                code="workspace-rebase-conflict",
                path="/workspace/tasks/task-001.json/statement",
                message="AI working value is retained.",
            ),
        ),
    )
    clean_action = _action(OTHER_ACTION_ID, path="/job_title")
    clean_changeset = DocumentChangeSet(
        changeset_id=OTHER_CHANGESET_ID,
        summary="另一個未受影響變更",
        actions=(clean_action,),
        source_ids=(SOURCE_ID,),
        created_revision=7,
    )
    clean_group = WorkspaceReviewGroup(
        changeset=clean_changeset,
        group_digest=DIGEST,
        semantic_fingerprint=DIGEST,
        evidence_digest=DIGEST,
        employee_request_digest=DIGEST,
        boundary_digest=DIGEST,
    )
    projection = WorkspaceReviewProjection(
        workspace_digest=DIGEST,
        groups=(conflicted_group, clean_group),
    )

    with pytest.raises(WorkspaceAuthorityError, match="rebase conflict"):
        select_workspace_actions(
            projection,
            _command(WorkspaceDecisionKind.ACCEPT, (TASK_ACTION_ID,)),
        )
    assert select_workspace_actions(
        projection,
        _command(WorkspaceDecisionKind.REJECT, (TASK_ACTION_ID,)),
    )
    clean_command = _command(
        WorkspaceDecisionKind.ACCEPT,
        (OTHER_ACTION_ID,),
    ).model_copy(
        update={
            "changeset_id": OTHER_CHANGESET_ID,
            "selected_action_ids": (OTHER_ACTION_ID,),
        }
    )
    assert select_workspace_actions(projection, clean_command)


def test_same_command_id_with_different_payload_has_different_digest() -> None:
    first = _command(WorkspaceDecisionKind.ACCEPT, (TASK_ACTION_ID,))
    changed = _command(WorkspaceDecisionKind.REJECT, (OUTPUT_ACTION_ID,))

    assert first.payload_digest() != changed.payload_digest()


def test_decision_record_keeps_workspace_identity_without_review_payload() -> None:
    record = WorkspaceDecisionRecord(
        command_id=COMMAND_ID,
        payload_digest=DIGEST,
        decision=WorkspaceDecisionKind.REJECT,
        changeset_id=CHANGESET_ID,
        selected_action_ids=(TASK_ACTION_ID,),
        workspace_digest=DIGEST,
        group_digest=DIGEST,
        semantic_fingerprint=DIGEST,
        evidence_digest=DIGEST,
        employee_request_digest=DIGEST,
        boundary_digest=DIGEST,
    )

    assert record.workspace_digest == DIGEST
    assert "actions" not in record.model_dump(mode="json")


def test_three_way_rebase_preserves_ai_only_and_applies_employee_only_changes() -> None:
    old = {
        "/workspace/header.json": '{"job_title":"舊職稱","notes":"舊備註"}\n'
    }
    working = {
        "/workspace/header.json": '{"job_title":"AI職稱","notes":"舊備註"}\n'
    }
    new = {
        "/workspace/header.json": '{"job_title":"舊職稱","notes":"員工備註"}\n'
    }

    plan = build_workspace_rebase_plan(
        command_id=COMMAND_ID,
        old_approved_files=old,
        workspace_files=working,
        new_approved_files=new,
        approved_revision=8,
        approved_digest=DIGEST,
    )

    assert len(plan.changes) == 1
    assert plan.changes[0].path == "/workspace/header.json"
    assert '"job_title": "AI職稱"' in (plan.changes[0].after or "")
    assert '"notes": "員工備註"' in (plan.changes[0].after or "")
    assert plan.conflicted_paths == ()


def test_three_way_rebase_does_not_rewrite_semantically_unchanged_resource() -> None:
    raw = '{"job_title":"採購專員","notes":null}\n'

    plan = build_workspace_rebase_plan(
        command_id=COMMAND_ID,
        old_approved_files={"/workspace/header.json": raw},
        workspace_files={"/workspace/header.json": raw},
        new_approved_files={"/workspace/header.json": raw},
        approved_revision=8,
        approved_digest=DIGEST,
    )

    assert plan.changes == ()


def test_three_way_rebase_keeps_ai_value_and_marks_true_overlap_conflicted() -> None:
    old = {"/workspace/header.json": '{"job_title":"舊職稱"}\n'}
    working = {"/workspace/header.json": '{"job_title":"AI職稱"}\n'}
    new = {"/workspace/header.json": '{"job_title":"員工職稱"}\n'}

    plan = build_workspace_rebase_plan(
        command_id=COMMAND_ID,
        old_approved_files=old,
        workspace_files=working,
        new_approved_files=new,
        approved_revision=8,
        approved_digest=DIGEST,
    )

    assert plan.changes == ()
    assert plan.conflicted_paths == ("/workspace/header.json/job_title",)


def test_three_way_rebase_treats_employee_accepted_workspace_path_as_resolved() -> None:
    old = {"/workspace/header.json": '{"job_title":"舊職稱"}\n'}
    working = {"/workspace/header.json": '{"job_title":"AI職稱"}\n'}
    new = {"/workspace/header.json": '{"job_title":"核准投影職稱"}\n'}

    plan = build_workspace_rebase_plan(
        command_id=COMMAND_ID,
        old_approved_files=old,
        workspace_files=working,
        new_approved_files=new,
        approved_revision=8,
        approved_digest=DIGEST,
        resolved_workspace_paths=("/workspace/header.json/job_title",),
    )

    assert plan.conflicted_paths == ()
    assert plan.changes == ()


def test_recover_passes_document_scope_to_rebase_completion_without_mutable_service_scope() -> None:
    record = WorkspaceDecisionRecord(
        command_id=COMMAND_ID,
        payload_digest=DIGEST,
        decision=WorkspaceDecisionKind.ACCEPT,
        changeset_id=CHANGESET_ID,
        selected_action_ids=(TASK_ACTION_ID,),
        workspace_digest=DIGEST,
        group_digest=DIGEST,
        semantic_fingerprint=DIGEST,
        evidence_digest=DIGEST,
        employee_request_digest=DIGEST,
        boundary_digest=DIGEST,
        status="authority_committed",
    )
    receipt = {
        "command_id": str(COMMAND_ID),
        "command_kind": "workspace_review_accept",
        "payload_sha256": DIGEST,
    }

    class FakeStore:
        async def asearch(self, namespace, *, limit):
            del namespace, limit
            return (SimpleNamespace(value=record.model_dump(mode="json")),)

    class FakeRuntime:
        store = FakeStore()

        @staticmethod
        def workspace_decision_namespace(document_id):
            return ("decision", str(document_id))

        @staticmethod
        def workspace_metadata_namespace(document_id):
            return ("metadata", str(document_id))

        async def raw_state(self, document_id):
            return {"command_receipts": {str(COMMAND_ID): receipt}}

    async def exercise() -> None:
        service = WorkspaceAuthorityService(FakeRuntime())
        calls = []

        async def finish(document_id, completed_record):
            calls.append((document_id, completed_record.command_id))

        service._finish_rebase = finish
        await service.recover(DOCUMENT_ID)
        assert calls == [(DOCUMENT_ID, COMMAND_ID)]
        assert not hasattr(service, "_document_id")

    import asyncio

    asyncio.run(exercise())


def test_selected_employee_edit_overrides_true_rebase_conflict() -> None:
    old = {"/workspace/tasks/task-001.json": '{"statement":"A","notes":"old"}\n'}
    working = {
        "/workspace/tasks/task-001.json": '{"statement":"B","notes":"AI notes"}\n'
    }
    new = {
        "/workspace/tasks/task-001.json": '{"statement":"C","notes":"old"}\n'
    }

    plan = build_workspace_rebase_plan(
        command_id=COMMAND_ID,
        old_approved_files=old,
        workspace_files=working,
        new_approved_files=new,
        approved_revision=8,
        approved_digest=DIGEST,
        employee_override_paths=("/workspace/tasks/task-001.json/statement",),
    )

    assert plan.conflicted_paths == ()
    assert '"statement": "C"' in (plan.changes[0].after or "")


def test_reject_rebase_plan_restores_selected_ai_value_to_approved() -> None:
    old = {"/workspace/tasks/task-001.json": '{"statement":"A"}\n'}
    working = {"/workspace/tasks/task-001.json": '{"statement":"B"}\n'}

    plan = build_workspace_rebase_plan(
        command_id=COMMAND_ID,
        old_approved_files=old,
        workspace_files=working,
        new_approved_files=old,
        approved_revision=7,
        approved_digest=DIGEST,
        employee_override_paths=("/workspace/tasks/task-001.json/statement",),
    )

    assert plan.conflicted_paths == ()
    assert plan.expected_workspace_digest == workspace_resource_digest(working)
    assert len(plan.changes) == 1
    assert '"statement": "A"' in (plan.changes[0].after or "")


def test_unselected_overlap_keeps_ai_value_and_only_marks_that_path_conflicted() -> None:
    old = {"/workspace/tasks/task-001.json": '{"statement":"A","notes":"D"}\n'}
    working = {
        "/workspace/tasks/task-001.json": '{"statement":"B","notes":"E"}\n'
    }
    new = {
        "/workspace/tasks/task-001.json": '{"statement":"C","notes":"F"}\n'
    }

    plan = build_workspace_rebase_plan(
        command_id=COMMAND_ID,
        old_approved_files=old,
        workspace_files=working,
        new_approved_files=new,
        approved_revision=8,
        approved_digest=DIGEST,
        employee_override_paths=("/workspace/tasks/task-001.json/statement",),
    )

    assert plan.conflicted_paths == ("/workspace/tasks/task-001.json/notes",)
    result = plan.changes[0].after or ""
    assert '"statement": "C"' in result
    assert '"notes": "E"' in result
