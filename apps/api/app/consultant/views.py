"""Read-only projections from framework-owned consultant checkpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage
from pydantic import Field

from app.consultant.state import (
    ApprovedJobDocument,
    ConsultantThreadState,
    DocumentChangeSet,
    DurableModel,
    InterviewWorkItem,
    InterviewWorkStatus,
    RequiredClarification,
)
from app.consultant.understanding import (
    CurrentInterviewProjection,
    OpeningNavigationProjection,
    SemanticProgressProjection,
    SufficiencyProjection,
    UnderstandingProjection,
    current_interview_from_state,
    opening_navigation_from_state,
    semantic_progress_from_state,
    sufficiency_projection_from_state,
    understanding_projection_from_state,
)


class ConsultantTurnProjection(DurableModel):
    run_id: UUID
    answer_source_id: UUID
    text: str
    used_skill_ids: tuple[str, ...]
    next_question: dict[str, Any] | None = None


class BlockedInterviewBranchProjection(DurableModel):
    work_id: UUID
    title: str
    decision_action_ids: tuple[UUID, ...]
    reason: str


class DocumentReviewProjection(DurableModel):
    bundles: tuple[DocumentChangeSet, ...] = ()
    unresolved_action_count: int = Field(ge=0)
    blocked_branches: tuple[BlockedInterviewBranchProjection, ...] = ()
    safe_interview_work_available: bool
    decision_required_before_more_interview: bool
    explanation: str | None = None


class ConsultantSnapshot(DurableModel):
    document_id: UUID
    revision: int = Field(ge=0)
    source_count: int = Field(ge=0)
    latest_source_id: UUID | None = None
    source_supersessions: dict[UUID, UUID] = Field(default_factory=dict)
    messages: tuple[ConsultantTurnProjection, ...] = ()
    opening_navigation: OpeningNavigationProjection
    current_interview: CurrentInterviewProjection | None = None
    interview_work: dict[str, dict] = Field(default_factory=dict)
    understanding: dict[str, dict] = Field(default_factory=dict)
    understanding_projection: UnderstandingProjection
    gaps: dict[str, dict] = Field(default_factory=dict)
    semantic_progress: SemanticProgressProjection
    document_review: DocumentReviewProjection
    approved_document: ApprovedJobDocument
    required_clarification: RequiredClarification | None = None
    sufficiency: SufficiencyProjection
    latest_run: dict | None = None


def _consultant_turns(state: ConsultantThreadState) -> tuple[ConsultantTurnProjection, ...]:
    turns: list[ConsultantTurnProjection] = []
    for message in state.get("messages", []):
        if not isinstance(message, AIMessage):
            continue
        metadata = message.response_metadata.get("caliburn", {})
        if metadata.get("kind") != "consultant_turn":
            continue
        content = message.content
        text = content if isinstance(content, str) else str(content)
        turns.append(
            ConsultantTurnProjection(
                run_id=metadata["run_id"],
                answer_source_id=metadata["answer_source_id"],
                text=text,
                used_skill_ids=[],
                next_question=metadata.get("next_question"),
            )
        )
    return tuple(turns)


def document_review_projection_from_state(
    state: ConsultantThreadState,
) -> DocumentReviewProjection:
    work = tuple(
        InterviewWorkItem.model_validate(raw)
        for raw in state.get("interview_work", {}).values()
    )
    safe_available = any(
        item.status
        in {
            InterviewWorkStatus.ACTIVE,
            InterviewWorkStatus.AVAILABLE,
            InterviewWorkStatus.PARKED,
        }
        for item in work
    )
    return DocumentReviewProjection(
        bundles=(),
        unresolved_action_count=0,
        blocked_branches=(),
        safe_interview_work_available=safe_available,
        decision_required_before_more_interview=False,
        explanation=None,
    )


def document_review_projection_from_workspace(
    state: ConsultantThreadState,
    bundles: tuple[DocumentChangeSet, ...],
    *,
    explanation: str | None = None,
) -> DocumentReviewProjection:
    """Map a fresh Store-derived review without making it checkpoint state."""

    checkpoint = document_review_projection_from_state(state)
    unresolved_actions = sum(
        action.status.value in {"pending", "deferred"}
        for bundle in bundles
        for action in bundle.actions
    )
    return DocumentReviewProjection(
        bundles=bundles,
        unresolved_action_count=unresolved_actions,
        blocked_branches=(),
        safe_interview_work_available=checkpoint.safe_interview_work_available,
        decision_required_before_more_interview=False,
        explanation=explanation,
    )


def snapshot_from_state(state: ConsultantThreadState) -> ConsultantSnapshot:
    if not state or "document_id" not in state:
        raise ValueError("consultant thread state is empty")
    return ConsultantSnapshot.model_validate(
        {
            "document_id": state["document_id"],
            "revision": state.get("revision", 0),
            "source_count": state.get("source_count", 0),
            "latest_source_id": state.get("latest_source_id"),
            "source_supersessions": state.get("source_supersessions", {}),
            "messages": _consultant_turns(state),
            "opening_navigation": opening_navigation_from_state(state),
            "current_interview": current_interview_from_state(state),
            "interview_work": state.get("interview_work", {}),
            "understanding": state.get("understanding", {}),
            "understanding_projection": understanding_projection_from_state(state),
            "gaps": state.get("gaps", {}),
            "semantic_progress": semantic_progress_from_state(state),
            "document_review": document_review_projection_from_state(state),
            "approved_document": state["approved_document"],
            "required_clarification": state.get("required_clarification"),
            "sufficiency": sufficiency_projection_from_state(state),
            "latest_run": state.get("latest_run"),
        }
    )
