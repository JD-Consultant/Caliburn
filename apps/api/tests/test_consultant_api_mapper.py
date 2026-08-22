from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.api.consultant_mapper import to_consultant_snapshot_view
from app.consultant.state import (
    ApprovedJobDocument,
    ApprovedTask,
    GapItem,
    InterviewPriority,
    InterviewWorkItem,
    InterviewWorkStatus,
    RunExecutionEvidence,
    RunReceipt,
    RunStatus,
    initial_thread_state,
)
from app.consultant.views import DocumentReviewProjection, snapshot_from_state
from app.consultant.workspace_state import WorkspaceDiagnostic


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
        execution_evidence=RunExecutionEvidence(
            resolved_execution={"profile_id": "primary-consultant"},
            context_selection_receipts=({"loaded_sources": []},),
            attempt_receipts=({"actual_provider": "Anthropic"},),
        ),
    ).model_dump(mode="json")

    view = to_consultant_snapshot_view(snapshot_from_state(state))

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


def test_initial_snapshot_is_naturally_resumable_without_a_pause_state() -> None:
    document_id = uuid4()
    view = to_consultant_snapshot_view(
        snapshot_from_state(initial_thread_state(document_id))
    )

    assert view.document_id == document_id
    assert view.run is None
    assert view.opening_navigation.visible is True
    assert view.messages == []
    assert view.readiness.force_export_allowed is True


def test_snapshot_mapper_projects_store_review_status_generation_and_employee_diagnostics() -> None:
    document_id = uuid4()
    snapshot = snapshot_from_state(initial_thread_state(document_id))
    diagnostics = (
        WorkspaceDiagnostic(
            code="workspace-rebase-conflict",
            path="/workspace/tasks/task-001.json/statement",
            message="Technical store conflict details must not reach employees.",
        ),
    )

    for status, review_diagnostics in (
        ("clean", ()),
        ("pending", ()),
        ("invalid", diagnostics),
        ("conflicted", diagnostics),
    ):
        view = to_consultant_snapshot_view(
            snapshot.model_copy(
                update={
                    "document_review": DocumentReviewProjection(
                        workspace_generation=11,
                        workspace_status=status,
                        diagnostics=review_diagnostics,
                        bundles=(),
                        unresolved_action_count=0,
                        blocked_branches=(),
                        safe_interview_work_available=True,
                        decision_required_before_more_interview=False,
                    )
                }
            )
        )

        assert view.document_review.workspace_generation == 11
        assert view.document_review.workspace_status.value == status
        if review_diagnostics:
            assert view.document_review.diagnostics[0].code == "workspace-rebase-conflict"
            assert view.document_review.diagnostics[0].path == "工作內容"
            assert "Technical" not in view.document_review.diagnostics[0].message
