"""Generated-contract projections for the durable consultant workspace."""

from __future__ import annotations

from job_analysis_contract import (
    ApprovedJobDocumentView,
    ConsultantMessageView,
    ConsultantSnapshotView,
    CurrentInterviewReasonView,
    DocumentChangeSetView,
    DocumentReviewView,
    DurableRunView,
    EmployeeMessageView,
    ExportReadinessIssueView,
    ExportReadinessView,
    NextQuestionView,
    OpeningNavigationView,
    RequiredClarificationView,
    SemanticProgressView,
    SufficiencyView,
    UnderstandingView,
    VisibleWorkItemView,
)

from app.consultant.state import (
    DocumentChangeSet,
    DocumentChangeStatus,
    GapStatus,
    InterviewWorkItem,
    InterviewWorkStatus,
    EmployeeSource,
    EmployeeSourceKind,
)
from app.consultant.views import ConsultantSnapshot


def _next_question(value: dict | None) -> NextQuestionView | None:
    if value is None:
        return None
    return NextQuestionView.model_validate(
        {
            key: value[key]
            for key in ("text", "answer_target", "reason")
        }
    )


def _durable_run(value: dict | None) -> DurableRunView | None:
    if value is None:
        return None
    return DurableRunView.model_validate(
        {
            key: value.get(key)
            for key in (
                "run_id",
                "status",
                "source_id",
                "started_at",
                "completed_at",
                "error_code",
            )
        }
    )


def _document_changeset_view(value: DocumentChangeSet) -> DocumentChangeSetView:
    """Project durable review state without leaking internal workflow metadata."""

    return DocumentChangeSetView.model_validate(
        {
            "changeset_id": value.changeset_id,
            "summary": value.summary,
            "actions": [
                {
                    "action_id": action.action_id,
                    "operation": action.operation.value,
                    "path": action.path,
                    "target_key": action.target_key,
                    "before": action.before,
                    "after": action.after,
                    "source_ids": action.source_ids,
                    "quote_anchors": [
                        anchor.model_dump(mode="json")
                        for anchor in action.quote_anchors
                    ],
                    "read_set": [
                        item.model_dump(mode="json") for item in action.read_set
                    ],
                    "target_ids": action.target_ids,
                    "depends_on_action_ids": action.depends_on_action_ids,
                    "atomic_subgroup_id": action.atomic_subgroup_id,
                    "affected_work_ids": action.affected_work_ids,
                    "blocks_dependent_analysis": action.blocks_dependent_analysis,
                    "status": action.status.value,
                    "employee_after": action.employee_after,
                    "rejection_reason": action.rejection_reason,
                    "stale_reason": action.stale_reason,
                }
                for action in value.actions
            ],
            "source_ids": value.source_ids,
            "created_revision": value.created_revision,
        }
    )


def _readiness(snapshot: ConsultantSnapshot) -> ExportReadinessView:
    issues: list[ExportReadinessIssueView] = []
    for task in snapshot.approved_document.tasks:
        if task.duty_id is None:
            issues.append(
                ExportReadinessIssueView(
                    code="TASK_DUTY_MISSING",
                    message=f"Task「{task.statement}」尚未歸入 Duty。",
                    subject_id=task.task_id,
                )
            )
    for raw in snapshot.gaps.values():
        status = GapStatus(raw.get("status", GapStatus.ACTIVE.value))
        if status is GapStatus.RESOLVED:
            continue
        reason = str(raw.get("reason", "analysis_gap"))
        issues.append(
            ExportReadinessIssueView(
                code=reason.upper(),
                message=str(raw.get("description", "仍有待處理的分析缺口。")),
                subject_id=raw.get("subject_id"),
            )
        )
    unresolved_review = sum(
        action.status
        in {DocumentChangeStatus.PENDING, DocumentChangeStatus.DEFERRED}
        for raw in snapshot.review_queue.values()
        for action in DocumentChangeSet.model_validate(raw).actions
    )
    if unresolved_review:
        issues.append(
            ExportReadinessIssueView(
                code="DOCUMENT_REVIEW_PENDING",
                message=f"仍有 {unresolved_review} 項 AI 文件變更等待員工決定。",
                subject_id=None,
            )
        )
    if snapshot.required_clarification is not None:
        issues.append(
            ExportReadinessIssueView(
                code="REQUIRED_CLARIFICATION_PENDING",
                message="仍有一項重大歧義需要員工回答。",
                subject_id=snapshot.required_clarification.clarification_id,
            )
        )
    if not snapshot.sufficiency.currently_enough:
        issues.append(
            ExportReadinessIssueView(
                code="INTERVIEW_NOT_YET_SUFFICIENT",
                message=snapshot.sufficiency.why_enough,
                subject_id=None,
            )
        )
    return ExportReadinessView(
        ready=not issues,
        requires_force_confirmation=bool(issues),
        force_export_allowed=True,
        issues=issues,
    )


def to_consultant_snapshot_view(
    snapshot: ConsultantSnapshot,
    *,
    employee_sources: tuple[EmployeeSource, ...] = (),
) -> ConsultantSnapshotView:
    visible_work = []
    for _, raw in sorted(snapshot.interview_work.items()):
        item = InterviewWorkItem.model_validate(raw)
        if item.status is InterviewWorkStatus.RETIRED:
            continue
        visible_work.append(
            VisibleWorkItemView(
                work_id=item.work_id,
                kind=item.kind,
                title=item.title,
                status=item.status.value,
                priority_reason=item.priority_reason,
                blocked_by_decision_ids=list(item.blocked_by_decision_ids),
            )
        )

    messages = [
        ConsultantMessageView(
            run_id=turn.run_id,
            answer_source_id=turn.answer_source_id,
            text=turn.text,
            used_skill_ids=list(turn.used_skill_ids),
            next_question=_next_question(turn.next_question),
        )
        for turn in snapshot.messages
    ]
    review = snapshot.document_review
    return ConsultantSnapshotView(
        document_id=snapshot.document_id,
        revision=snapshot.revision,
        source_count=snapshot.source_count,
        latest_source_id=snapshot.latest_source_id,
        run=_durable_run(snapshot.latest_run),
        opening_navigation=OpeningNavigationView.model_validate(
            snapshot.opening_navigation.model_dump(mode="json")
        ),
        current_interview=(
            CurrentInterviewReasonView.model_validate(
                snapshot.current_interview.model_dump(mode="json")
            )
            if snapshot.current_interview is not None
            else None
        ),
        visible_work=visible_work,
        understanding=UnderstandingView.model_validate(
            snapshot.understanding_projection.model_dump(mode="json")
        ),
        semantic_progress=SemanticProgressView.model_validate(
            snapshot.semantic_progress.model_dump(mode="json")
        ),
        employee_messages=[
            EmployeeMessageView.model_validate(
                {
                    "source_id": source.source_id,
                    "text": source.text,
                    "created_at": source.created_at,
                    "processing_status": source.processing_status.value,
                    "validity": source.validity.value,
                    "supersedes_source_id": source.supersedes_source_id,
                    "superseded_by_source_id": source.superseded_by_source_id,
                }
            )
            for source in employee_sources
            if source.kind is EmployeeSourceKind.EMPLOYEE_TURN
        ],
        messages=messages,
        document_review=DocumentReviewView.model_validate(
            {
                "bundles": [
                    _document_changeset_view(bundle).model_dump(mode="json")
                    for bundle in review.bundles
                ],
                "unresolved_action_count": review.unresolved_action_count,
                "blocked_branches": [
                    item.model_dump(mode="json") for item in review.blocked_branches
                ],
                "safe_interview_work_available": review.safe_interview_work_available,
                "decision_required_before_more_interview": (
                    review.decision_required_before_more_interview
                ),
                "explanation": review.explanation,
            }
        ),
        required_clarification=(
            RequiredClarificationView.model_validate(
                snapshot.required_clarification.model_dump(mode="json")
            )
            if snapshot.required_clarification is not None
            else None
        ),
        sufficiency=SufficiencyView.model_validate(
            snapshot.sufficiency.model_dump(mode="json")
        ),
        approved_document=ApprovedJobDocumentView.model_validate(
            snapshot.approved_document.model_dump(mode="json")
        ),
        readiness=_readiness(snapshot),
    )


__all__ = ["to_consultant_snapshot_view"]
