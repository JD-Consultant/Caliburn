"""Deterministic projections for understanding, progress and sufficiency.

LangGraph owns the lifecycle and persistence.  This module supplies only the
job-analysis-specific policies a generic workflow framework cannot infer:
which semantic shifts merit employee calibration, which gaps are structural,
and how to explain currently known coverage without a fake denominator.
"""

from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256
from typing import Any, Literal, Sequence
from uuid import UUID, uuid5

from pydantic import Field

from app.consultant.results import (
    GapReason,
    SufficiencyRecommendation,
    UnderstandingChange,
)
from app.consultant.state import (
    ApprovedJobDocument,
    ApprovedOpksKind,
    ApprovedTask,
    CalibrationDecision,
    CalibrationKind,
    CalibrationStatus,
    CalibrationTrigger,
    ConsultantThreadState,
    DocumentChangeStatus,
    DocumentPatchAction,
    DurableModel,
    EmployeeSourceKind,
    GapItem,
    GapStatus,
    InterviewWorkItem,
    InterviewWorkStatus,
    SourceReference,
    UnderstandingCalibration,
    UnderstandingImpact,
    UnderstandingItem,
    UnderstandingStatus,
)
from app.consultant.workspace_review import WorkspaceReviewProjection


class OpeningNavigationProjection(DurableModel):
    visible: bool
    steps: tuple[str, ...]


class CurrentInterviewProjection(DurableModel):
    work_id: UUID
    title: str
    why_now: str
    missing_before_enough: str | None = None
    recommended_next_step: str | None = None


class UnderstandingItemProjection(DurableModel):
    understanding_id: UUID
    kind: str
    text: str
    status: UnderstandingStatus
    source_ids: tuple[UUID, ...]


CalibrationAction = Literal["confirm", "direct_correction", "later"]


class CalibrationProjection(DurableModel):
    calibration_id: UUID
    kind: CalibrationKind
    trigger: CalibrationTrigger
    status: CalibrationStatus
    affected_work_ids: tuple[UUID, ...]
    changed_understanding_ids: tuple[UUID, ...]
    allowed_actions: tuple[CalibrationAction, ...] = (
        "confirm",
        "direct_correction",
        "later",
    )


class UnderstandingProjection(DurableModel):
    label: Literal["AI 目前理解"] = "AI 目前理解"
    collapsible: Literal[True] = True
    items: tuple[UnderstandingItemProjection, ...]
    parked_clues: tuple[CurrentInterviewProjection, ...]
    calibration: CalibrationProjection | None = None


CoverageStatus = InterviewWorkStatus | Literal[
    "awaiting_employee_decision",
    "employee_deferred",
]


class CoverageItemProjection(DurableModel):
    work_id: UUID
    title: str
    status: CoverageStatus
    reason: str


class DepthStatus(StrEnum):
    EVIDENCE_PRESENT = "evidence_present"
    GAP = "gap"
    INTERVIEWING = "interviewing"
    NOT_YET_DEEPENED = "not_yet_deepened"
    SUFFICIENT_FOR_NOW = "sufficient_for_now"
    HELD_WITH_REASON = "held_with_reason"


class WorkDepthProjection(DurableModel):
    work_id: UUID
    task_boundary: DepthStatus
    duty_grouping: DepthStatus
    output: DepthStatus
    performance_indicator: DepthStatus
    knowledge: DepthStatus
    skill: DepthStatus


class EmployeeDecisionProjection(DurableModel):
    pending: int = Field(ge=0)
    deferred: int = Field(ge=0)


class GapProjection(DurableModel):
    gap_id: UUID
    reason_code: str
    description: str
    subject_kind: str
    subject_id: UUID | None = None
    blocks_dependent_analysis: bool
    status: GapStatus


class SemanticProgressProjection(DurableModel):
    currently_known_work_count: int = Field(ge=0)
    coverage: tuple[CoverageItemProjection, ...]
    depth: tuple[WorkDepthProjection, ...]
    employee_decisions: EmployeeDecisionProjection
    gaps: tuple[GapProjection, ...]


class SufficiencyEvidence(DurableModel):
    known_work_count: int = Field(ge=0)
    sufficient_work_count: int = Field(ge=0)
    active_or_unvisited_work_count: int = Field(ge=0)
    blocking_gap_count: int = Field(ge=0)
    structural_decision_count: int = Field(ge=0)


class SufficiencyProjection(DurableModel):
    currently_enough: bool
    why_enough: str
    remaining_gap_reasons: tuple[str, ...] = ()
    likely_benefit_of_continuing: str
    deterministic_evidence: SufficiencyEvidence
    assessed_revision: int = Field(ge=0)
    needs_recalculation: bool = False


_BLOCKING_IMPACTS = {
    UnderstandingImpact.STRUCTURAL_PREMISE: CalibrationTrigger.STRUCTURAL_PREMISE,
    UnderstandingImpact.HIGH_RISK_RESPONSIBILITY: (
        CalibrationTrigger.HIGH_RISK_RESPONSIBILITY
    ),
    UnderstandingImpact.CONTRADICTION: CalibrationTrigger.CONTRADICTION,
}
_SOFT_IMPACTS = {
    UnderstandingImpact.MEANINGFUL_SHIFT: CalibrationTrigger.MEANINGFUL_SHIFT,
    UnderstandingImpact.EMPLOYEE_REQUEST: CalibrationTrigger.EMPLOYEE_REQUEST,
}
_BLOCKING_GAP_REASONS = {
    GapReason.SOURCE_CONTRADICTION.value,
    GapReason.CURRENT_RESPONSIBILITY_UNCLEAR.value,
}


def _work_items(state: ConsultantThreadState) -> dict[str, InterviewWorkItem]:
    return {
        key: InterviewWorkItem.model_validate(value)
        for key, value in state.get("interview_work", {}).items()
    }


def _understanding_items(
    state: ConsultantThreadState,
) -> dict[str, UnderstandingItem]:
    return {
        key: UnderstandingItem.model_validate(value)
        for key, value in state.get("understanding", {}).items()
    }


def current_understanding_items(
    state: ConsultantThreadState,
) -> tuple[UnderstandingItem, ...]:
    items = (
        item
        for item in _understanding_items(state).values()
        if item.superseded_by_version_id is None
        and item.status
        not in {UnderstandingStatus.SUPERSEDED, UnderstandingStatus.RETIRED}
    )
    return tuple(sorted(items, key=lambda item: (item.created_revision, str(item.version_id))))


def opening_navigation_from_state(
    state: ConsultantThreadState,
) -> OpeningNavigationProjection:
    return OpeningNavigationProjection(
        visible=not bool(state.get("messages")),
        steps=(
            "先用你的完整描述整理目前已知的工作範圍。",
            "每次只選一個最值得深入的重點，並說明為什麼現在問。",
            "訪談中發現的新 Task、Duty 或 O／P／K／S 會保留並持續修正。",
            "AI 建議的文件內容都要由你接受、修改後接受或拒絕才會正式寫入。",
        ),
    )


def current_interview_from_state(
    state: ConsultantThreadState,
) -> CurrentInterviewProjection | None:
    current_id = state.get("current_work_id")
    if current_id is None:
        return None
    item = _work_items(state).get(current_id)
    if item is None or item.status is not InterviewWorkStatus.ACTIVE:
        return None
    return CurrentInterviewProjection(
        work_id=item.work_id,
        title=item.title,
        why_now=item.priority_reason,
        missing_before_enough=item.missing_before_enough,
        recommended_next_step=item.recommended_next_step,
    )


def understanding_projection_from_state(
    state: ConsultantThreadState,
) -> UnderstandingProjection:
    items = tuple(
        UnderstandingItemProjection(
            understanding_id=item.understanding_id,
            kind=item.kind,
            text=item.text,
            status=item.status,
            source_ids=item.source_ids,
        )
        for item in current_understanding_items(state)
    )
    parked = tuple(
        CurrentInterviewProjection(
            work_id=item.work_id,
            title=item.title,
            why_now=item.priority_reason,
            missing_before_enough=item.missing_before_enough,
            recommended_next_step=item.recommended_next_step,
        )
        for item in _work_items(state).values()
        if item.status is InterviewWorkStatus.PARKED
    )
    calibration = _current_calibration_projection(state)
    return UnderstandingProjection(
        items=items,
        parked_clues=parked,
        calibration=calibration,
    )


def _current_calibration_projection(
    state: ConsultantThreadState,
) -> CalibrationProjection | None:
    calibration_id = state.get("latest_calibration_id")
    if calibration_id is None:
        return None
    raw = state.get("understanding_calibrations", {}).get(calibration_id)
    if raw is None:
        return None
    calibration = UnderstandingCalibration.model_validate(raw)
    if calibration.status not in {CalibrationStatus.PENDING, CalibrationStatus.LATER}:
        return None
    return CalibrationProjection(
        calibration_id=calibration.calibration_id,
        kind=calibration.kind,
        trigger=calibration.trigger,
        status=calibration.status,
        affected_work_ids=calibration.affected_work_ids,
        changed_understanding_ids=calibration.understanding_ids,
    )


def _axis_for_kind(kind: str) -> str | None:
    normalized = kind.lower().replace("-", "_")
    if "duty" in normalized:
        return "duty_grouping"
    if "performance" in normalized or "indicator" in normalized:
        return "performance_indicator"
    if "knowledge" in normalized:
        return "knowledge"
    if "skill" in normalized:
        return "skill"
    if "output" in normalized:
        return "output"
    if "task" in normalized or "responsibility" in normalized:
        return "task_boundary"
    return None


def _axis_for_gap(reason: str) -> str | None:
    return {
        GapReason.TASK_BOUNDARY_UNCLEAR.value: "task_boundary",
        GapReason.CURRENT_RESPONSIBILITY_UNCLEAR.value: "task_boundary",
        GapReason.COMPLETION_STANDARD_MISSING.value: "task_boundary",
        GapReason.DUTY_GROUPING_UNCERTAIN.value: "duty_grouping",
        GapReason.PERFORMANCE_EVIDENCE_MISSING.value: "performance_indicator",
        GapReason.KNOWLEDGE_EVIDENCE_MISSING.value: "knowledge",
        GapReason.SKILL_EVIDENCE_MISSING.value: "skill",
    }.get(reason)


def _axis_for_work_kind(kind: str) -> str | None:
    normalized = kind.lower().replace("-", "_")
    if "duty" in normalized:
        return "duty_grouping"
    if "performance" in normalized or "indicator" in normalized:
        return "performance_indicator"
    if "knowledge" in normalized:
        return "knowledge"
    if "skill" in normalized:
        return "skill"
    if "output" in normalized:
        return "output"
    if "task" in normalized or "responsibility" in normalized:
        return "task_boundary"
    return None


def semantic_progress_from_state(
    state: ConsultantThreadState,
) -> SemanticProgressProjection:
    work = tuple(
        item
        for item in _work_items(state).values()
        if item.status is not InterviewWorkStatus.RETIRED
    )
    understanding = current_understanding_items(state)
    gaps = tuple(
        GapItem.model_validate(value)
        for value in state.get("gaps", {}).values()
        if value.get("status") != GapStatus.RESOLVED.value
    )
    coverage = tuple(
        CoverageItemProjection(
            work_id=item.work_id,
            title=item.title,
            status=item.status,
            reason=item.priority_reason,
        )
        for item in sorted(work, key=lambda item: str(item.work_id))
    )
    depth: list[WorkDepthProjection] = []
    axes = (
        "task_boundary",
        "duty_grouping",
        "output",
        "performance_indicator",
        "knowledge",
        "skill",
    )
    for item in work:
        values = {axis: DepthStatus.NOT_YET_DEEPENED for axis in axes}
        for claim in understanding:
            if not claim.work_ids or item.work_id not in claim.work_ids:
                continue
            axis = _axis_for_kind(claim.kind)
            if axis is not None:
                values[axis] = DepthStatus.EVIDENCE_PRESENT
        for gap in gaps:
            if gap.subject_id != item.work_id:
                continue
            axis = _axis_for_gap(gap.reason)
            if axis is not None:
                values[axis] = DepthStatus.GAP
        work_axis = _axis_for_work_kind(item.kind)
        if item.status is InterviewWorkStatus.ACTIVE:
            if (
                work_axis is not None
                and values[work_axis] is DepthStatus.NOT_YET_DEEPENED
            ):
                values[work_axis] = DepthStatus.INTERVIEWING
        elif item.status is InterviewWorkStatus.SUFFICIENT_FOR_NOW:
            if (
                work_axis is not None
                and values[work_axis] is DepthStatus.NOT_YET_DEEPENED
            ):
                values[work_axis] = DepthStatus.SUFFICIENT_FOR_NOW
        elif item.status in {
            InterviewWorkStatus.PARKED,
            InterviewWorkStatus.UNKNOWN,
            InterviewWorkStatus.NOT_APPLICABLE,
        }:
            if (
                work_axis is not None
                and values[work_axis] is DepthStatus.NOT_YET_DEEPENED
            ):
                values[work_axis] = DepthStatus.HELD_WITH_REASON
        depth.append(WorkDepthProjection(work_id=item.work_id, **values))

    return SemanticProgressProjection(
        currently_known_work_count=len(work),
        coverage=coverage,
        depth=tuple(depth),
        employee_decisions=EmployeeDecisionProjection(
            pending=0,
            deferred=0,
        ),
        gaps=tuple(
            GapProjection(
                gap_id=item.gap_id,
                reason_code=item.reason,
                description=item.description,
                subject_kind=item.subject_kind,
                subject_id=item.subject_id,
                blocks_dependent_analysis=item.blocks_dependent_analysis,
                status=item.status,
            )
            for item in gaps
        ),
    )


def _review_task_ids(action: DocumentPatchAction) -> tuple[UUID, ...]:
    parts = action.path.strip("/").split("/")
    if not parts or parts[0] != "tasks":
        return ()
    identities: list[UUID] = []
    if len(parts) >= 2:
        try:
            identities.append(UUID(parts[1]))
        except ValueError:
            pass
    for value in (action.before, action.after):
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, dict) or item.get("task_id") is None:
                continue
            try:
                identities.append(UUID(str(item["task_id"])))
            except ValueError:
                continue
    return tuple(dict.fromkeys(identities))


def _task_review_statuses(
    workspace_review: WorkspaceReviewProjection,
) -> dict[UUID, DocumentChangeStatus]:
    statuses: dict[UUID, DocumentChangeStatus] = {}
    for changeset in workspace_review.changesets:
        for action in changeset.actions:
            if action.status not in {
                DocumentChangeStatus.PENDING,
                DocumentChangeStatus.DEFERRED,
            }:
                continue
            for task_id in _review_task_ids(action):
                if (
                    statuses.get(task_id) is DocumentChangeStatus.PENDING
                    or action.status is DocumentChangeStatus.PENDING
                ):
                    statuses[task_id] = DocumentChangeStatus.PENDING
                else:
                    statuses[task_id] = DocumentChangeStatus.DEFERRED
    return statuses


def _document_task_depth(
    task: ApprovedTask,
    document: ApprovedJobDocument,
) -> WorkDepthProjection:
    kinds = {
        item.kind
        for item in document.opks
        if task.task_id in item.task_ids
    }
    return WorkDepthProjection(
        work_id=task.task_id,
        task_boundary=DepthStatus.EVIDENCE_PRESENT,
        duty_grouping=(
            DepthStatus.EVIDENCE_PRESENT
            if task.duty_id is not None
            else DepthStatus.GAP
        ),
        output=(
            DepthStatus.EVIDENCE_PRESENT
            if ApprovedOpksKind.OUTPUT in kinds
            else DepthStatus.NOT_YET_DEEPENED
        ),
        performance_indicator=(
            DepthStatus.EVIDENCE_PRESENT
            if ApprovedOpksKind.PERFORMANCE_INDICATOR in kinds
            else DepthStatus.NOT_YET_DEEPENED
        ),
        knowledge=(
            DepthStatus.EVIDENCE_PRESENT
            if ApprovedOpksKind.KNOWLEDGE in kinds
            else DepthStatus.NOT_YET_DEEPENED
        ),
        skill=(
            DepthStatus.EVIDENCE_PRESENT
            if ApprovedOpksKind.SKILL in kinds
            else DepthStatus.NOT_YET_DEEPENED
        ),
    )


def _merge_document_depth(
    base: WorkDepthProjection | None,
    document_depth: WorkDepthProjection,
    *,
    work_id: UUID,
) -> WorkDepthProjection:
    if base is None:
        return document_depth.model_copy(update={"work_id": work_id})
    updates: dict[str, Any] = {"work_id": work_id}
    for axis in (
        "task_boundary",
        "duty_grouping",
        "output",
        "performance_indicator",
        "knowledge",
        "skill",
    ):
        existing = getattr(base, axis)
        candidate = getattr(document_depth, axis)
        updates[axis] = (
            candidate
            if existing is DepthStatus.NOT_YET_DEEPENED
            and candidate is not DepthStatus.NOT_YET_DEEPENED
            else existing
        )
    return WorkDepthProjection(**updates)


def semantic_progress_from_workspace(
    state: ConsultantThreadState,
    *,
    working_document: ApprovedJobDocument,
    workspace_review: WorkspaceReviewProjection,
) -> SemanticProgressProjection:
    """Project valid Store workspace facts without persisting another work model."""

    approved = ApprovedJobDocument.model_validate(state["approved_document"])
    if approved.document_id != working_document.document_id:
        raise ValueError("workspace progress document scope does not match")
    base = semantic_progress_from_state(state)
    base_coverage = {item.work_id: item for item in base.coverage}
    base_depth = {item.work_id: item for item in base.depth}
    work_items = tuple(
        item
        for item in _work_items(state).values()
        if item.status is not InterviewWorkStatus.RETIRED
    )
    work_by_subject = {
        item.subject_id: item
        for item in sorted(work_items, key=lambda value: str(value.work_id))
        if item.subject_id is not None
    }
    work_by_id = {item.work_id: item for item in work_items}
    review_statuses = _task_review_statuses(workspace_review)
    approved_tasks = {item.task_id: item for item in approved.tasks}
    working_tasks = {item.task_id: item for item in working_document.tasks}
    coverage: dict[UUID, CoverageItemProjection] = dict(base_coverage)
    depth: dict[UUID, WorkDepthProjection] = dict(base_depth)

    for task_id in sorted(approved_tasks.keys() | working_tasks.keys(), key=str):
        task = working_tasks.get(task_id) or approved_tasks[task_id]
        linked_work = work_by_subject.get(task_id) or work_by_id.get(task_id)
        work_id = linked_work.work_id if linked_work is not None else task_id
        existing = base_coverage.get(work_id)
        review_status = review_statuses.get(task_id)
        if existing is not None:
            item_status: CoverageStatus = existing.status
            title = existing.title
            reason = existing.reason
        elif review_status is DocumentChangeStatus.PENDING:
            item_status = "awaiting_employee_decision"
            title = task.statement
            reason = "AI 已整理成工作草稿，等待你確認後才會進入正式 JD。"
        elif review_status is DocumentChangeStatus.DEFERRED:
            item_status = "employee_deferred"
            title = task.statement
            reason = "你已選擇稍後處理；內容仍保留在工作草稿。"
        else:
            item_status = InterviewWorkStatus.AVAILABLE
            title = task.statement
            reason = "已辨識為工作，可按需要繼續深入訪談。"
        coverage[work_id] = CoverageItemProjection(
            work_id=work_id,
            title=title,
            status=item_status,
            reason=reason,
        )
        document_depth = _document_task_depth(task, working_document)
        depth[work_id] = _merge_document_depth(
            base_depth.get(work_id),
            document_depth,
            work_id=work_id,
        )

    pending = 0
    deferred = 0
    for changeset in workspace_review.changesets:
        for action in changeset.actions:
            if action.status is DocumentChangeStatus.PENDING:
                pending += 1
            elif action.status is DocumentChangeStatus.DEFERRED:
                deferred += 1
    return base.model_copy(
        update={
            "currently_known_work_count": len(coverage),
            "coverage": tuple(coverage[key] for key in sorted(coverage, key=str)),
            "depth": tuple(depth[key] for key in sorted(depth, key=str)),
            "employee_decisions": EmployeeDecisionProjection(
                pending=pending,
                deferred=deferred,
            ),
        }
    )


def _structural_decision_count(state: ConsultantThreadState) -> int:
    del state
    return 0


def sufficiency_evidence_from_state(
    state: ConsultantThreadState,
) -> SufficiencyEvidence:
    work = [
        item
        for item in _work_items(state).values()
        if item.status is not InterviewWorkStatus.RETIRED
    ]
    gaps = [
        GapItem.model_validate(value)
        for value in state.get("gaps", {}).values()
        if value.get("status") == GapStatus.ACTIVE.value
    ]
    return SufficiencyEvidence(
        known_work_count=len(work),
        sufficient_work_count=sum(
            item.status is InterviewWorkStatus.SUFFICIENT_FOR_NOW for item in work
        ),
        active_or_unvisited_work_count=sum(
            item.status
            in {
                InterviewWorkStatus.ACTIVE,
                InterviewWorkStatus.AVAILABLE,
                InterviewWorkStatus.BLOCKED,
            }
            for item in work
        ),
        blocking_gap_count=sum(
            item.blocks_dependent_analysis or item.reason in _BLOCKING_GAP_REASONS
            for item in gaps
        ),
        structural_decision_count=_structural_decision_count(state),
    )


def assess_sufficiency(
    state: ConsultantThreadState,
    recommendation: SufficiencyRecommendation,
    *,
    revision: int,
) -> SufficiencyProjection:
    evidence = sufficiency_evidence_from_state(state)
    deterministic_ready = (
        evidence.known_work_count > 0
        and evidence.active_or_unvisited_work_count == 0
        and evidence.blocking_gap_count == 0
        and evidence.structural_decision_count == 0
    )
    currently_enough = recommendation.currently_enough and deterministic_ready
    if recommendation.currently_enough and not deterministic_ready:
        why = "模型認為資料接近足夠，但仍有可檢查的重大工作、缺口或結構決策未處理。"
    else:
        why = recommendation.reason
    return SufficiencyProjection(
        currently_enough=currently_enough,
        why_enough=why,
        remaining_gap_reasons=tuple(
            reason.value for reason in recommendation.remaining_gap_reasons
        ),
        likely_benefit_of_continuing=recommendation.continuing_benefit,
        deterministic_evidence=evidence,
        assessed_revision=revision,
    )


def sufficiency_projection_from_state(
    state: ConsultantThreadState,
) -> SufficiencyProjection:
    raw = state.get("sufficiency")
    if raw is not None:
        return SufficiencyProjection.model_validate(raw)
    evidence = sufficiency_evidence_from_state(state)
    return SufficiencyProjection(
        currently_enough=False,
        why_enough="尚未形成可檢查的足夠性建議。",
        likely_benefit_of_continuing="開始描述工作後，顧問會依實際缺口說明下一步價值。",
        deterministic_evidence=evidence,
        assessed_revision=state.get("revision", 0),
        needs_recalculation=False,
    )


def invalidate_sufficiency(
    state: ConsultantThreadState,
    *,
    revision: int,
) -> dict[str, Any] | None:
    if state.get("sufficiency") is None:
        return None
    prior = SufficiencyProjection.model_validate(state["sufficiency"])
    return prior.model_copy(
        update={
            "currently_enough": False,
            "why_enough": "收到新的員工資訊，足夠性會在本次分析後重新計算。",
            "assessed_revision": revision,
            "needs_recalculation": True,
        }
    ).model_dump(mode="json")


def create_calibration(
    *,
    document_id: UUID,
    run_id: UUID,
    revision: int,
    state: ConsultantThreadState,
    changes: Sequence[UnderstandingChange],
    changed_items: Sequence[UnderstandingItem],
    focus_changed: bool,
    returning_after_long_gap: bool,
) -> tuple[
    dict[str, dict[str, Any]],
    str | None,
    dict[str, dict[str, Any]],
]:
    blocking = next(
        (
            _BLOCKING_IMPACTS[change.impact]
            for change in changes
            if change.impact in _BLOCKING_IMPACTS
        ),
        None,
    )
    soft = next(
        (
            _SOFT_IMPACTS[change.impact]
            for change in changes
            if change.impact in _SOFT_IMPACTS
        ),
        None,
    )
    trigger = blocking or soft
    if trigger is None and returning_after_long_gap:
        trigger = CalibrationTrigger.LONG_RETURN
    if trigger is None and focus_changed:
        trigger = CalibrationTrigger.FOCUS_TRANSITION
    calibrations = dict(state.get("understanding_calibrations", {}))
    work = dict(state.get("interview_work", {}))
    if trigger is None:
        return calibrations, state.get("latest_calibration_id"), work

    selected = tuple(changed_items) or current_understanding_items(state)
    if not selected:
        return calibrations, state.get("latest_calibration_id"), work
    digest_payload = [
        {
            "understanding_id": str(item.understanding_id),
            "text": item.text,
            "status": item.status.value,
        }
        for item in sorted(selected, key=lambda item: str(item.understanding_id))
    ]
    content_digest = sha256(
        json.dumps(digest_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if trigger is not CalibrationTrigger.EMPLOYEE_REQUEST and any(
        value.get("content_digest") == content_digest for value in calibrations.values()
    ):
        return calibrations, state.get("latest_calibration_id"), work

    affected_work_ids = tuple(
        sorted(
            {
                work_id
                for item in selected
                for work_id in item.work_ids
            }
            or (
                {UUID(state["current_work_id"])}
                if state.get("current_work_id") is not None
                else set()
            ),
            key=str,
        )
    )
    source_ids = tuple(
        sorted({source_id for item in selected for source_id in item.source_ids}, key=str)
    )
    kind = (
        CalibrationKind.BRANCH_BLOCKING
        if blocking is not None
        else CalibrationKind.SOFT
    )
    calibration_id = uuid5(document_id, f"calibration:{run_id}:{content_digest}")
    calibration = UnderstandingCalibration(
        calibration_id=calibration_id,
        kind=kind,
        trigger=trigger,
        understanding_ids=tuple(item.understanding_id for item in selected),
        affected_work_ids=affected_work_ids,
        source_ids=source_ids,
        content_digest=content_digest,
        created_revision=revision,
    )
    for key, value in tuple(calibrations.items()):
        existing = UnderstandingCalibration.model_validate(value)
        if existing.status in {CalibrationStatus.PENDING, CalibrationStatus.LATER}:
            calibrations[key] = existing.model_copy(
                update={"status": CalibrationStatus.SUPERSEDED}
            ).model_dump(mode="json")
            for work_id in existing.affected_work_ids:
                raw = work.get(str(work_id))
                if raw is None:
                    continue
                item = InterviewWorkItem.model_validate(raw)
                blockers = tuple(
                    blocker
                    for blocker in item.blocked_by_decision_ids
                    if blocker != existing.calibration_id
                )
                update: dict[str, Any] = {
                    "blocked_by_decision_ids": blockers,
                }
                if (
                    item.status is InterviewWorkStatus.BLOCKED
                    and not blockers
                    and item.resume_status is not None
                ):
                    update.update(
                        {
                            "status": item.resume_status,
                            "resume_status": None,
                        }
                    )
                work[str(work_id)] = item.model_copy(update=update).model_dump(
                    mode="json"
                )
    calibrations[str(calibration_id)] = calibration.model_dump(mode="json")
    if kind is CalibrationKind.BRANCH_BLOCKING:
        for work_id in affected_work_ids:
            raw = work.get(str(work_id))
            if raw is None:
                continue
            item = InterviewWorkItem.model_validate(raw)
            if item.status not in {
                InterviewWorkStatus.RETIRED,
                InterviewWorkStatus.NOT_APPLICABLE,
            }:
                resume_status = item.resume_status
                if resume_status is None:
                    resume_status = (
                        item.status
                        if item.status is not InterviewWorkStatus.BLOCKED
                        else InterviewWorkStatus.AVAILABLE
                    )
                work[str(work_id)] = item.model_copy(
                    update={
                        "status": InterviewWorkStatus.BLOCKED,
                        "blocked_by_decision_ids": tuple(
                            dict.fromkeys(
                                (*item.blocked_by_decision_ids, calibration_id)
                            )
                        ),
                        "resume_status": resume_status,
                        "last_changed_revision": revision,
                    }
                ).model_dump(mode="json")
    return calibrations, str(calibration_id), work


def decide_calibration(
    *,
    state: ConsultantThreadState,
    calibration_id: UUID,
    decision: CalibrationDecision,
    source_reference: SourceReference | None,
    revision: int,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    str | None,
]:
    calibrations = dict(state.get("understanding_calibrations", {}))
    raw = calibrations.get(str(calibration_id))
    if raw is None:
        raise KeyError(f"understanding calibration {calibration_id} was not found")
    calibration = UnderstandingCalibration.model_validate(raw)
    if calibration.status not in {CalibrationStatus.PENDING, CalibrationStatus.LATER}:
        raise ValueError("understanding calibration was already decided")
    understanding = dict(state.get("understanding", {}))
    work = dict(state.get("interview_work", {}))
    if decision is CalibrationDecision.CONFIRM:
        if source_reference is None:
            raise ValueError("confirming understanding requires employee evidence")
        if source_reference.kind is not EmployeeSourceKind.EMPLOYEE_TURN:
            raise ValueError("understanding confirmation must be an employee turn")
        calibration = calibration.model_copy(
            update={
                "status": CalibrationStatus.CONFIRMED,
                "decision_source_id": source_reference.source_id,
            }
        )
        for key, value in tuple(understanding.items()):
            item = UnderstandingItem.model_validate(value)
            if (
                item.understanding_id in calibration.understanding_ids
                and item.superseded_by_version_id is None
                and item.status is not UnderstandingStatus.RETIRED
            ):
                understanding[key] = item.model_copy(
                    update={
                        "status": UnderstandingStatus.EMPLOYEE_CONFIRMED,
                        "source_ids": tuple(
                            dict.fromkeys(
                                (*item.source_ids, source_reference.source_id)
                            )
                        ),
                    }
                ).model_dump(mode="json")
        for work_id in calibration.affected_work_ids:
            value = work.get(str(work_id))
            if value is None:
                continue
            item = InterviewWorkItem.model_validate(value)
            if calibration.calibration_id in item.blocked_by_decision_ids:
                blockers = tuple(
                    blocker
                    for blocker in item.blocked_by_decision_ids
                    if blocker != calibration.calibration_id
                )
                update: dict[str, Any] = {
                    "blocked_by_decision_ids": blockers,
                    "last_changed_revision": revision,
                }
                if not blockers:
                    update.update(
                        {
                            "status": item.resume_status
                            or InterviewWorkStatus.AVAILABLE,
                            "resume_status": None,
                        }
                    )
                work[str(work_id)] = item.model_copy(
                    update=update
                ).model_dump(mode="json")
    else:
        if source_reference is not None:
            raise ValueError("deferring understanding must not create evidence")
        calibration = calibration.model_copy(update={"status": CalibrationStatus.LATER})
    calibrations[str(calibration_id)] = calibration.model_dump(mode="json")
    latest = str(calibration_id) if decision is CalibrationDecision.LATER else None
    return calibrations, understanding, work, latest
