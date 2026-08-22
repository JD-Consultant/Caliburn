"""Semantic transitions for the single adaptive professional consultant."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from langchain_core.messages import AIMessage
from pydantic import model_validator

from app.consultant.clarification import create_required_clarification
from app.consultant.results import (
    AttentionOperation,
    ConsultantResult,
    GapOperation,
    UnderstandingOperation,
)
from app.consultant.state import (
    CalibrationStatus,
    ConsultantThreadState,
    DurableModel,
    GapItem,
    GapStatus,
    InterviewPriority,
    InterviewWorkItem,
    InterviewWorkStatus,
    RequiredClarification,
    RunReceipt,
    RunExecutionEvidence,
    RunStatus,
    UnderstandingCalibration,
    UnderstandingItem,
    UnderstandingStatus,
)
from app.consultant.understanding import assess_sufficiency, create_calibration


class VerifiedConsultantCommit(DurableModel):
    """Application-verified model result admitted to one semantic checkpoint."""

    run_id: UUID
    answer_source_id: UUID
    started_at: datetime
    completed_at: datetime
    returning_after_long_gap: bool = False
    execution_evidence: RunExecutionEvidence | None = None
    result: ConsultantResult

    @model_validator(mode="after")
    def timestamps_and_answer_basis_are_consistent(self) -> VerifiedConsultantCommit:
        if self.completed_at < self.started_at:
            raise ValueError("consultant commit completed_at precedes started_at")
        if self.answer_source_id not in self.result.reply_basis.source_ids:
            raise ValueError("visible consultant reply must depend on the answer source")
        return self


_PRIORITY_ORDER = {
    InterviewPriority.EMPLOYEE_REQUEST: 0,
    InterviewPriority.CORRECTION: 1,
    InterviewPriority.CONTRADICTION_OR_RESPONSIBILITY: 2,
    InterviewPriority.TASK_BOUNDARY: 3,
    InterviewPriority.HIGH_IMPACT: 4,
    InterviewPriority.DESCRIPTION: 5,
    InterviewPriority.DUTY_GROUPING: 6,
    InterviewPriority.OPKS: 7,
    InterviewPriority.COVERAGE: 8,
    InterviewPriority.OTHER: 9,
}


def _new_id(document_id: UUID, run_id: UUID, channel: str, index: int) -> UUID:
    return uuid5(document_id, f"consultant:{run_id}:{channel}:{index}")


def _dump(model: DurableModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def normalize_current_work(
    work: dict[str, dict[str, Any]],
    *,
    preferred_work_id: UUID | None,
    revision: int,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    parsed = {
        key: InterviewWorkItem.model_validate(value) for key, value in work.items()
    }
    eligible = {
        key: item
        for key, item in parsed.items()
        if item.status
        not in {
            InterviewWorkStatus.BLOCKED,
            InterviewWorkStatus.SUFFICIENT_FOR_NOW,
            InterviewWorkStatus.UNKNOWN,
            InterviewWorkStatus.NOT_APPLICABLE,
            InterviewWorkStatus.RETIRED,
        }
    }
    selected: InterviewWorkItem | None = None
    if preferred_work_id is not None:
        selected = eligible.get(str(preferred_work_id))
    if selected is None:
        active = [item for item in eligible.values() if item.status is InterviewWorkStatus.ACTIVE]
        if active:
            selected = min(
                active,
                key=lambda item: (_PRIORITY_ORDER[item.priority], str(item.work_id)),
            )
    if selected is None:
        available = [
            item
            for item in eligible.values()
            if item.status is InterviewWorkStatus.AVAILABLE
        ]
        if not available:
            available = [
                item
                for item in eligible.values()
                if item.status is InterviewWorkStatus.PARKED
            ]
        if available:
            selected = min(
                available,
                key=lambda item: (_PRIORITY_ORDER[item.priority], str(item.work_id)),
            )

    normalized = dict(work)
    for key, item in parsed.items():
        if selected is not None and item.work_id == selected.work_id:
            if item.status is not InterviewWorkStatus.ACTIVE:
                item = item.model_copy(
                    update={
                        "status": InterviewWorkStatus.ACTIVE,
                        "last_changed_revision": revision,
                    }
                )
        elif item.status is InterviewWorkStatus.ACTIVE:
            item = item.model_copy(
                update={
                    "status": InterviewWorkStatus.PARKED,
                    "last_changed_revision": revision,
                }
            )
        normalized[key] = _dump(item)
    return normalized, str(selected.work_id) if selected is not None else None


def _apply_understanding_changes(
    *,
    document_id: UUID,
    run_id: UUID,
    revision: int,
    state: ConsultantThreadState,
    result: ConsultantResult,
) -> tuple[dict[str, dict[str, Any]], tuple[UnderstandingItem, ...]]:
    understanding = dict(state.get("understanding", {}))
    changed: list[UnderstandingItem] = []
    for index, change in enumerate(result.understanding_changes):
        if change.operation is UnderstandingOperation.ADD:
            understanding_id = _new_id(document_id, run_id, "understanding", index)
            previous: UnderstandingItem | None = None
        else:
            assert change.understanding_id is not None
            understanding_id = change.understanding_id
            current = [
                item
                for item in (
                    UnderstandingItem.model_validate(value)
                    for value in understanding.values()
                )
                if item.understanding_id == understanding_id
                and item.superseded_by_version_id is None
            ]
            if len(current) != 1:
                raise KeyError(
                    f"current understanding {understanding_id} was not found uniquely"
                )
            previous = current[0]
        version_id = _new_id(document_id, run_id, "understanding-version", index)
        status = (
            UnderstandingStatus.RETIRED
            if change.operation is UnderstandingOperation.RETIRE
            else UnderstandingStatus.ACTIVE
        )
        item = UnderstandingItem(
            understanding_id=understanding_id,
            version_id=version_id,
            kind=change.kind,
            text=change.text,
            status=status,
            impact=change.impact,
            source_ids=change.basis.source_ids,
            work_ids=change.work_ids,
            created_revision=revision,
            supersedes_version_id=(previous.version_id if previous is not None else None),
        )
        if previous is not None:
            understanding[str(previous.version_id)] = _dump(
                previous.model_copy(
                    update={
                        "status": UnderstandingStatus.SUPERSEDED,
                        "superseded_by_version_id": version_id,
                    }
                )
            )
        understanding[str(version_id)] = _dump(item)
        changed.append(item)
    return understanding, tuple(changed)


def _apply_attention_changes(
    *,
    document_id: UUID,
    run_id: UUID,
    revision: int,
    state: ConsultantThreadState,
    result: ConsultantResult,
) -> tuple[dict[str, dict[str, Any]], UUID | None, bool]:
    work = dict(state.get("interview_work", {}))
    preferred: UUID | None = None
    previous_current = state.get("current_work_id")
    for index, change in enumerate(result.attention_changes):
        if change.operation is AttentionOperation.ADD:
            work_id = _new_id(document_id, run_id, "interview-work", index)
            existing: InterviewWorkItem | None = None
        else:
            assert change.attention_id is not None
            work_id = change.attention_id
            raw = work.get(str(work_id))
            if raw is None:
                raise KeyError(f"interview work {work_id} was not found")
            existing = InterviewWorkItem.model_validate(raw)

        if change.operation is AttentionOperation.PARK:
            status = InterviewWorkStatus.PARKED
        elif change.operation is AttentionOperation.RETIRE:
            status = InterviewWorkStatus.RETIRED
        elif change.make_current:
            status = InterviewWorkStatus.ACTIVE
            preferred = work_id
        elif change.disposition is not None:
            status = change.disposition
        elif existing is not None:
            status = existing.status
        else:
            status = InterviewWorkStatus.AVAILABLE

        source_ids = tuple(
            dict.fromkeys(
                (*(existing.source_ids if existing is not None else ()), *change.basis.source_ids)
            )
        )
        item = InterviewWorkItem(
            work_id=work_id,
            kind=change.kind,
            title=change.title or (existing.title if existing is not None else change.kind),
            subject_id=(
                change.subject_id
                if change.subject_id is not None
                else (existing.subject_id if existing is not None else None)
            ),
            status=status,
            priority=change.priority,
            priority_reason=change.reason,
            missing_before_enough=(
                change.missing_before_enough
                if change.missing_before_enough is not None
                else (
                    existing.missing_before_enough if existing is not None else None
                )
            ),
            recommended_next_step=(
                change.recommended_next_step
                if change.recommended_next_step is not None
                else (
                    existing.recommended_next_step if existing is not None else None
                )
            ),
            source_ids=source_ids,
            last_changed_revision=revision,
        )
        work[str(work_id)] = _dump(item)
    work, current_id = normalize_current_work(
        work,
        preferred_work_id=preferred,
        revision=revision,
    )
    return (
        work,
        (UUID(current_id) if current_id is not None else None),
        previous_current is not None and current_id != previous_current,
    )


def _apply_gap_changes(
    *,
    document_id: UUID,
    revision: int,
    state: ConsultantThreadState,
    result: ConsultantResult,
) -> dict[str, dict[str, Any]]:
    gaps = dict(state.get("gaps", {}))
    for change in result.gaps:
        if change.gap_id is not None:
            gap_id = change.gap_id
        else:
            fingerprint = (
                f"gap:{change.reason.value}:{change.subject_kind}:"
                f"{change.subject_id or 'document'}"
            )
            gap_id = uuid5(document_id, fingerprint)
        if change.operation is GapOperation.RESOLVE and str(gap_id) not in gaps:
            raise KeyError(f"gap {gap_id} was not found")
        status = {
            GapOperation.UPSERT: GapStatus.ACTIVE,
            GapOperation.HOLD: GapStatus.HELD_WITH_REASON,
            GapOperation.RESOLVE: GapStatus.RESOLVED,
        }[change.operation]
        gaps[str(gap_id)] = _dump(
            GapItem(
                gap_id=gap_id,
                reason=change.reason.value,
                description=change.description,
                subject_kind=change.subject_kind,
                subject_id=change.subject_id,
                blocks_dependent_analysis=change.blocks_dependent_analysis,
                status=status,
                source_ids=change.basis.source_ids,
                last_changed_revision=revision,
            )
        )
    return gaps


def apply_verified_consultant_commit(
    state: ConsultantThreadState,
    *,
    document_id: UUID,
    revision: int,
    commit: VerifiedConsultantCommit,
) -> ConsultantThreadState:
    if state.get("latest_source_id") != str(commit.answer_source_id):
        raise ValueError("consultant result does not belong to the latest saved input")
    understanding, changed_items = _apply_understanding_changes(
        document_id=document_id,
        run_id=commit.run_id,
        revision=revision,
        state=state,
        result=commit.result,
    )
    work, current_work_id, focus_changed = _apply_attention_changes(
        document_id=document_id,
        run_id=commit.run_id,
        revision=revision,
        state=state,
        result=commit.result,
    )
    gaps = _apply_gap_changes(
        document_id=document_id,
        revision=revision,
        state=state,
        result=commit.result,
    )
    prospective: ConsultantThreadState = {
        **state,
        "revision": revision,
        "interview_work": work,
        "current_work_id": str(current_work_id) if current_work_id else None,
        "understanding": understanding,
        "gaps": gaps,
    }
    calibrations, latest_calibration_id, work = create_calibration(
        document_id=document_id,
        run_id=commit.run_id,
        revision=revision,
        state=prospective,
        changes=commit.result.understanding_changes,
        changed_items=changed_items,
        focus_changed=focus_changed,
        returning_after_long_gap=commit.returning_after_long_gap,
    )
    required_clarification = (
        RequiredClarification.model_validate(state["required_clarification"])
        if state.get("required_clarification") is not None
        else None
    )
    if commit.result.required_clarification is not None:
        if required_clarification is not None:
            raise ValueError(
                "an unresolved required clarification cannot be replaced"
            )
        required_clarification, work, _ = create_required_clarification(
            document_id=document_id,
            run_id=commit.run_id,
            draft=commit.result.required_clarification,
            interview_work=work,
            revision=revision,
        )
    work, current_work_id_string = normalize_current_work(
        work,
        preferred_work_id=current_work_id,
        revision=revision,
    )
    prospective.update(
        {
            "interview_work": work,
            "current_work_id": current_work_id_string,
            "understanding_calibrations": calibrations,
            "latest_calibration_id": latest_calibration_id,
        }
    )
    sufficiency = assess_sufficiency(
        prospective,
        commit.result.sufficiency,
        revision=revision,
    )
    message = AIMessage(
        id=str(commit.run_id),
        content=commit.result.visible_reply,
        response_metadata={
            "caliburn": {
                "kind": "consultant_turn",
                "run_id": str(commit.run_id),
                "answer_source_id": str(commit.answer_source_id),
                "next_question": (
                    commit.result.next_question.model_dump(mode="json")
                    if commit.result.next_question is not None
                    else None
                ),
            }
        },
    )
    receipt = RunReceipt(
        run_id=commit.run_id,
        status=RunStatus.COMPLETED,
        source_id=commit.answer_source_id,
        started_at=commit.started_at,
        completed_at=commit.completed_at,
        execution_evidence=commit.execution_evidence,
    )
    return {
        "revision": revision,
        "messages": [message],
        "current_work_id": current_work_id_string,
        "interview_work": work,
        "understanding": understanding,
        "understanding_calibrations": calibrations,
        "latest_calibration_id": latest_calibration_id,
        "gaps": gaps,
        "required_clarification": (
            required_clarification.model_dump(mode="json")
            if required_clarification is not None
            else None
        ),
        "sufficiency": sufficiency.model_dump(mode="json"),
        "latest_run": receipt.model_dump(mode="json"),
    }


def apply_source_correction(
    state: ConsultantThreadState,
    *,
    document_id: UUID,
    superseded_source_id: UUID,
    correction_source_id: UUID,
    revision: int,
) -> ConsultantThreadState:
    clarification = (
        RequiredClarification.model_validate(state["required_clarification"])
        if state.get("required_clarification") is not None
        else None
    )
    retired_clarification_id = (
        clarification.clarification_id
        if clarification is not None
        and superseded_source_id in clarification.source_ids
        else None
    )
    understanding = dict(state.get("understanding", {}))
    affected_work_ids: set[UUID] = set()
    newly_challenged_understanding_ids: set[UUID] = set()
    for key, value in tuple(understanding.items()):
        item = UnderstandingItem.model_validate(value)
        if (
            item.superseded_by_version_id is not None
            or item.status in {UnderstandingStatus.RETIRED, UnderstandingStatus.SUPERSEDED}
            or superseded_source_id not in item.source_ids
        ):
            continue
        version_id = uuid5(
            document_id,
            f"correction:{correction_source_id}:understanding:{item.understanding_id}",
        )
        challenged = item.model_copy(
            update={
                "version_id": version_id,
                "status": UnderstandingStatus.CHALLENGED,
                "created_revision": revision,
                "supersedes_version_id": item.version_id,
                "superseded_by_version_id": None,
            }
        )
        understanding[key] = _dump(
            item.model_copy(
                update={
                    "status": UnderstandingStatus.SUPERSEDED,
                    "superseded_by_version_id": version_id,
                }
            )
        )
        understanding[str(version_id)] = _dump(challenged)
        affected_work_ids.update(item.work_ids)
        newly_challenged_understanding_ids.add(item.understanding_id)

    work = dict(state.get("interview_work", {}))
    for key, value in tuple(work.items()):
        item = InterviewWorkItem.model_validate(value)
        if superseded_source_id in item.source_ids:
            affected_work_ids.add(item.work_id)
        if item.work_id not in affected_work_ids:
            continue
        blockers = tuple(
            blocker
            for blocker in item.blocked_by_decision_ids
            if blocker != retired_clarification_id
        )
        if blockers:
            status = InterviewWorkStatus.BLOCKED
            resume_status = item.resume_status or InterviewWorkStatus.AVAILABLE
            priority_reason = (
                "關聯的員工原話已更正；此分支仍有其他未決前提。"
            )
        else:
            status = InterviewWorkStatus.AVAILABLE
            resume_status = None
            priority_reason = "關聯的員工原話已更正，需重查受影響理解。"
        work[key] = _dump(
            item.model_copy(
                update={
                    "status": status,
                    "priority": InterviewPriority.CORRECTION,
                    "priority_reason": priority_reason,
                    "source_ids": tuple(
                        dict.fromkeys((*item.source_ids, correction_source_id))
                    ),
                    "blocked_by_decision_ids": blockers,
                    "resume_status": resume_status,
                    "last_changed_revision": revision,
                }
            )
        )
    gaps = dict(state.get("gaps", {}))
    for key, value in tuple(gaps.items()):
        item = GapItem.model_validate(value)
        if (
            superseded_source_id in item.source_ids
            and item.status is GapStatus.RESOLVED
        ):
            gaps[key] = _dump(
                item.model_copy(
                    update={
                        "status": GapStatus.ACTIVE,
                        "last_changed_revision": revision,
                    }
                )
            )

    calibrations = dict(state.get("understanding_calibrations", {}))
    superseded_latest_calibration = False
    for key, value in tuple(calibrations.items()):
        item = UnderstandingCalibration.model_validate(value)
        if (
            item.status in {CalibrationStatus.PENDING, CalibrationStatus.LATER}
            and set(item.understanding_ids) & newly_challenged_understanding_ids
        ):
            calibrations[key] = _dump(
                item.model_copy(update={"status": CalibrationStatus.SUPERSEDED})
            )
            if key == state.get("latest_calibration_id"):
                superseded_latest_calibration = True

    preferred = (
        min(affected_work_ids, key=str) if affected_work_ids else None
    )
    work, current_work_id = normalize_current_work(
        work,
        preferred_work_id=preferred,
        revision=revision,
    )
    return {
        "interview_work": work,
        "current_work_id": current_work_id,
        "understanding": understanding,
        "understanding_calibrations": calibrations,
        "latest_calibration_id": (
            None
            if superseded_latest_calibration
            else state.get("latest_calibration_id")
        ),
        "gaps": gaps,
        **(
            {"required_clarification": None}
            if retired_clarification_id is not None
            else {}
        ),
    }
