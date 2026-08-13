"""Typed LangGraph interrupt for ambiguities only an employee can resolve."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID, uuid5

from langgraph.types import interrupt
from pydantic import model_validator

from app.consultant.results import RequiredClarificationDraft
from app.consultant.state import (
    ConsultantThreadState,
    DurableModel,
    EmployeeSourceKind,
    InterviewWorkItem,
    InterviewWorkStatus,
    RequiredClarification,
    SourceReference,
)


class ClarificationAnswer(DurableModel):
    choice: str
    text: str
    source_reference: SourceReference

    @model_validator(mode="after")
    def answer_is_employee_evidence(self) -> ClarificationAnswer:
        if not self.choice.strip() or not self.text.strip():
            raise ValueError("clarification answer must not be blank")
        if self.source_reference.kind is not EmployeeSourceKind.EMPLOYEE_TURN:
            raise ValueError("clarification answer must be an employee-turn source")
        return self


def create_required_clarification(
    *,
    document_id: UUID,
    run_id: UUID,
    draft: RequiredClarificationDraft,
    interview_work: Mapping[str, dict[str, Any]],
    revision: int,
) -> tuple[RequiredClarification, dict[str, dict[str, Any]], str | None]:
    clarification_id = uuid5(
        document_id,
        f"consultant:{run_id}:required-clarification",
    )
    missing = set(draft.affected_work_ids) - {
        InterviewWorkItem.model_validate(raw).work_id
        for raw in interview_work.values()
    }
    if missing:
        raise ValueError(
            "required clarification references unknown interview work: "
            + ", ".join(sorted(map(str, missing)))
        )
    request = RequiredClarification(
        clarification_id=clarification_id,
        question=draft.question,
        reason=draft.reason,
        current_understanding=draft.current_understanding,
        choices=draft.choices,
        affected_work_ids=draft.affected_work_ids,
        affected_branch=draft.affected_branch,
        source_ids=draft.basis.source_ids,
    )
    updated = dict(interview_work)
    for key, raw in interview_work.items():
        item = InterviewWorkItem.model_validate(raw)
        if item.work_id not in set(draft.affected_work_ids):
            continue
        blockers = tuple(
            dict.fromkeys((*item.blocked_by_decision_ids, clarification_id))
        )
        resume_status = item.resume_status
        if resume_status is None:
            resume_status = (
                item.status
                if item.status is not InterviewWorkStatus.BLOCKED
                else InterviewWorkStatus.AVAILABLE
            )
        updated[key] = item.model_copy(
            update={
                "status": InterviewWorkStatus.BLOCKED,
                "blocked_by_decision_ids": blockers,
                "resume_status": resume_status,
                "priority_reason": "這個分支有重大歧義，需先由員工確認。",
                "last_changed_revision": revision,
            }
        ).model_dump(mode="json")
    current = next(
        (
            str(InterviewWorkItem.model_validate(raw).work_id)
            for raw in updated.values()
            if InterviewWorkItem.model_validate(raw).status
            is InterviewWorkStatus.ACTIVE
        ),
        None,
    )
    return request, updated, current


def _interrupt_payload(request: RequiredClarification) -> dict[str, Any]:
    return {
        "kind": "required_clarification",
        "request_id": str(request.clarification_id),
        "reason": request.reason,
        "question": request.question,
        "current_understanding": request.current_understanding,
        "choices": list(request.choices),
        "affected_work_ids": [str(item) for item in request.affected_work_ids],
        "affected_branch": request.affected_branch,
    }


def resolve_required_clarification(
    state: ConsultantThreadState,
    request: RequiredClarification,
    answer: ClarificationAnswer,
) -> ConsultantThreadState:
    if answer.choice not in request.choices:
        raise ValueError("clarification answer choice is not offered by the request")
    source_id = answer.source_reference.source_id
    if str(source_id) == state.get("latest_source_id"):
        raise ValueError("clarification answer source was already applied")
    revision = state.get("revision", 0) + 1
    work = dict(state.get("interview_work", {}))
    for key, raw in tuple(work.items()):
        item = InterviewWorkItem.model_validate(raw)
        if request.clarification_id not in item.blocked_by_decision_ids:
            continue
        blockers = tuple(
            blocker
            for blocker in item.blocked_by_decision_ids
            if blocker != request.clarification_id
        )
        update: dict[str, Any] = {
            "blocked_by_decision_ids": blockers,
            "last_changed_revision": revision,
        }
        if not blockers:
            update.update(
                {
                    "status": item.resume_status or InterviewWorkStatus.AVAILABLE,
                    "resume_status": None,
                    "priority_reason": "員工已回答必要澄清，這個分支可重新分析。",
                }
            )
        work[key] = item.model_copy(update=update).model_dump(mode="json")
    supersessions = dict(state.get("source_supersessions", {}))
    if answer.source_reference.supersedes_source_id is not None:
        supersessions[str(answer.source_reference.supersedes_source_id)] = str(source_id)
    return {
        "revision": revision,
        "source_count": state.get("source_count", 0) + 1,
        "latest_source_id": str(source_id),
        "source_supersessions": supersessions,
        "interview_work": work,
        "current_work_id": next(
            (
                key
                for key, raw in work.items()
                if InterviewWorkItem.model_validate(raw).status
                is InterviewWorkStatus.ACTIVE
            ),
            None,
        ),
        "required_clarification": None,
        "sufficiency": None,
    }


def interrupt_for_required_clarification(
    state: ConsultantThreadState,
) -> ConsultantThreadState:
    raw = state.get("required_clarification")
    if raw is None:
        return {}
    request = RequiredClarification.model_validate(raw)
    answer = ClarificationAnswer.model_validate(interrupt(_interrupt_payload(request)))
    return resolve_required_clarification(state, request, answer)
