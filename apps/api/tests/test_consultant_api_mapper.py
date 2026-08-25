from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.api.consultant_mapper import to_consultant_snapshot_view
from app.consultant.state import (
    ApprovedJobDocument,
    ApprovedTask,
    DocumentChangeSet,
    DocumentPatchAction,
    DocumentPatchOperation,
    DocumentPathRead,
    GapItem,
    InterviewPriority,
    InterviewWorkItem,
    InterviewWorkStatus,
    RunExecutionEvidence,
    RunReceipt,
    RunStatus,
    initial_thread_state,
)
from app.consultant.views import (
    document_review_projection_from_workspace,
    snapshot_from_state,
)
from app.consultant.workspace_review import WorkspaceReviewGroup, WorkspaceReviewProjection
from app.consultant.workspace_state import (
    WorkspaceDiagnostic,
    WorkspaceValidationStatus,
)


def test_snapshot_mapper_exposes_product_projections_not_raw_framework_state() -> None:
    document_id = uuid4()
    work_id = uuid4()
    task_id = uuid4()
    gap_id = uuid4()
    state = initial_thread_state(document_id)
    state["interview_work"] = {
        str(work_id): InterviewWorkItem(
            work_id=work_id,
            kind="task",
            title="整理採購需求",
            status=InterviewWorkStatus.ACTIVE,
            priority=InterviewPriority.TASK_BOUNDARY,
            priority_reason="目前正在釐清 Task 邊界。",
            last_changed_revision=1,
        ).model_dump(mode="json")
    }
    state["current_work_id"] = str(work_id)
    state["gaps"] = {
        str(gap_id): GapItem(
            gap_id=gap_id,
            reason="task_boundary_unclear",
            description="尚未說清楚完成後的結果。",
            subject_kind="task",
            subject_id=work_id,
            source_ids=(),
            last_changed_revision=1,
        ).model_dump(mode="json")
    }
    state["approved_document"] = ApprovedJobDocument(
        document_id=document_id,
        tasks=(
            ApprovedTask(
                task_id=task_id,
                statement="整理採購需求",
                action="整理",
                object="採購需求",
                display_order=0,
            ),
        ),
    ).model_dump(mode="json")
    state["latest_run"] = RunReceipt(
        run_id=uuid4(),
        status=RunStatus.COMPLETED,
        source_id=uuid4(),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        semantic_commit_sha256="a" * 64,
        execution_evidence=RunExecutionEvidence(
            resolved_execution={"profile_id": "primary-consultant"},
            context_selection_receipts=({"loaded_sources": []},),
            attempt_receipts=({"actual_provider": "Anthropic"},),
        ),
    ).model_dump(mode="json")

    snapshot = snapshot_from_state(state)
    review = document_review_projection_from_workspace(
        state,
        workspace_generation=7,
        validation_status=WorkspaceValidationStatus.VALID,
        workspace_review=WorkspaceReviewProjection(workspace_digest="a" * 64),
    )
    view = to_consultant_snapshot_view(
        snapshot.model_copy(
            update={
                "current_document": snapshot.approved_document,
                "document_review": review,
            }
        )
    )

    assert view.current_interview is not None
    assert view.current_interview.work_id == work_id
    assert view.visible_work[0].priority_reason == "目前正在釐清 Task 邊界。"
    assert view.semantic_progress.gaps[0].reason_code == "task_boundary_unclear"
    assert {issue.code for issue in view.readiness.issues} >= {
        "TASK_DUTY_MISSING",
        "TASK_BOUNDARY_UNCLEAR",
        "INTERVIEW_NOT_YET_SUFFICIENT",
    }
    assert view.readiness.requires_force_confirmation is True
    payload = view.model_dump(mode="json")
    assert "interview_work" not in payload
    review_state_field = "review_" + "queue"
    assert review_state_field not in payload
    assert "latest_run" not in payload
    assert "execution_evidence" not in payload["run"]
    assert "pause" not in payload
    assert "finish" not in payload
    assert "deferred" not in payload
    assert "blocked_branches" not in payload["document_review"]
    assert "safe_interview_work_available" not in payload["document_review"]
    assert "decision_required_before_more_interview" not in payload["document_review"]


def test_snapshot_mapper_exposes_store_current_document_and_workspace_digest() -> None:
    document_id = uuid4()
    task_id = uuid4()
    state = initial_thread_state(document_id)
    approved_document = ApprovedJobDocument(
        document_id=document_id,
        tasks=(
            ApprovedTask(
                task_id=task_id,
                statement="核准內容",
                action="整理",
                object="採購需求",
                display_order=0,
            ),
        ),
    )
    current_document = approved_document.model_copy(
        update={
            "tasks": (
                approved_document.tasks[0].model_copy(
                    update={"statement": "AI 工作中內容"}
                ),
            )
        }
    )
    state["approved_document"] = approved_document.model_dump(mode="json")
    snapshot = snapshot_from_state(state)
    workspace_digest = "b" * 64
    review = document_review_projection_from_workspace(
        state,
        workspace_generation=7,
        validation_status=WorkspaceValidationStatus.VALID,
        workspace_review=WorkspaceReviewProjection(workspace_digest=workspace_digest),
    )
    store_derived_snapshot = snapshot.model_copy(
        update={
            "current_document": current_document,
            "document_review": review,
        }
    )

    view = to_consultant_snapshot_view(store_derived_snapshot)

    assert view.approved_document.tasks[0].statement == "核准內容"
    assert view.current_document.tasks[0].statement == "AI 工作中內容"
    assert view.document_review.workspace_digest == workspace_digest


def test_initial_snapshot_is_naturally_resumable_without_a_pause_state() -> None:
    document_id = uuid4()
    snapshot = snapshot_from_state(initial_thread_state(document_id))

    assert snapshot.document_id == document_id
    assert snapshot.latest_run is None
    assert snapshot.opening_navigation.visible is True
    assert snapshot.messages == ()
    assert snapshot.document_review is None
    with pytest.raises(ValueError, match="Store-derived document review"):
        to_consultant_snapshot_view(snapshot)


def test_snapshot_mapper_projects_store_review_status_generation_and_employee_diagnostics() -> None:
    document_id = uuid4()
    action_id = uuid4()
    changeset_id = uuid4()
    source_id = uuid4()
    subgroup_id = uuid4()
    state = initial_thread_state(document_id)
    snapshot = snapshot_from_state(state)
    invalid_diagnostics = (
        WorkspaceDiagnostic(
            code="json-syntax",
            path="/workspace/tasks/task-001.json/statement",
            message="Technical validation details must not reach employees.",
        ),
    )
    conflict_diagnostics = (
        WorkspaceDiagnostic(
            code="workspace-rebase-conflict",
            path="/workspace/tasks/task-001.json/statement",
            message="Technical store conflict details must not reach employees.",
        ),
    )
    changeset = DocumentChangeSet(
        changeset_id=changeset_id,
        summary="更新工作描述",
        actions=(
            DocumentPatchAction(
                action_id=action_id,
                operation=DocumentPatchOperation.REVISE,
                path="/tasks/task-001/statement",
                target_key="task-001",
                before="整理需求",
                after="彙整採購需求",
                source_ids=(source_id,),
                read_set=(
                    DocumentPathRead(
                        path="/tasks/task-001/statement",
                        value_sha256="0" * 64,
                    ),
                ),
                atomic_subgroup_id=subgroup_id,
            ),
            DocumentPatchAction(
                action_id=uuid4(),
                operation=DocumentPatchOperation.REVISE,
                path="/tasks/task-001/action",
                target_key="task-001",
                before="整理",
                after="彙整",
                source_ids=(source_id,),
                read_set=(
                    DocumentPathRead(
                        path="/tasks/task-001/action",
                        value_sha256="1" * 64,
                    ),
                ),
                atomic_subgroup_id=subgroup_id,
            ),
        ),
        source_ids=(source_id,),
        created_revision=0,
    )
    group = WorkspaceReviewGroup(
        changeset=changeset,
        group_digest="2" * 64,
        semantic_fingerprint="3" * 64,
        evidence_digest="4" * 64,
        employee_request_digest="5" * 64,
        boundary_digest="6" * 64,
    )
    cases = (
        (
            "clean",
            WorkspaceValidationStatus.VALID,
            WorkspaceReviewProjection(workspace_digest="a" * 64),
        ),
        (
            "pending",
            WorkspaceValidationStatus.VALID,
            WorkspaceReviewProjection(workspace_digest="a" * 64, groups=(group,)),
        ),
        (
            "invalid",
            WorkspaceValidationStatus.INVALID,
            WorkspaceReviewProjection(
                workspace_digest="a" * 64,
                diagnostics=invalid_diagnostics,
            ),
        ),
        (
            "conflicted",
            WorkspaceValidationStatus.CONFLICTED,
            WorkspaceReviewProjection(
                workspace_digest="a" * 64,
                groups=(
                    WorkspaceReviewGroup(
                        changeset=changeset,
                        group_digest=group.group_digest,
                        semantic_fingerprint=group.semantic_fingerprint,
                        evidence_digest=group.evidence_digest,
                        employee_request_digest=group.employee_request_digest,
                        boundary_digest=group.boundary_digest,
                        diagnostics=conflict_diagnostics,
                    ),
                ),
            ),
        ),
    )

    for status, validation_status, workspace_review in cases:
        review = document_review_projection_from_workspace(
            state,
            workspace_generation=11,
            validation_status=validation_status,
            workspace_review=workspace_review,
        )
        view = to_consultant_snapshot_view(
            snapshot.model_copy(
                update={
                    "current_document": snapshot.approved_document,
                    "document_review": review,
                }
            )
        )

        assert view.document_review.workspace_generation == 11
        assert view.document_review.workspace_status.value == status
        if status == "pending":
            assert [action.status.value for action in view.document_review.bundles[0].actions] == [
                "pending",
                "pending",
            ]
            assert view.document_review.unresolved_action_count == 2
        if status == "conflicted":
            assert view.document_review.bundles[0].acceptance_blocked is True
            assert view.document_review.diagnostics[0].path == "工作內容"
            assert "Technical" not in view.document_review.diagnostics[0].message
