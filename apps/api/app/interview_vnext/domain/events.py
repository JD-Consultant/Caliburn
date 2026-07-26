"""Typed, deterministic domain events emitted by pure reducers."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import Field, model_validator

from .base import DomainModel
from .episode import EpisodeStatus, GapStatus
from .evidence import InferenceStatus
from .identifiers import NonEmptyText, Sha256, UtcDatetime
from .interpretation import DialogueAct, EpisodeSignal, TurnInsufficiencyCode
from .job_model import CandidateStatus
from .question_frame import QuestionFrameStaleReason
from .review import ReviewAction
from .session import SessionStatus


class EventBase(DomainModel):
    event_id: UUID
    session_id: UUID
    command_id: UUID
    ordinal: int = Field(ge=0)
    state_version: int = Field(ge=1)
    occurred_at: UtcDatetime


class SessionTransitionedEvent(EventBase):
    schema_version: Literal["session_transitioned_event.v1"] = "session_transitioned_event.v1"
    event_type: Literal["session.transitioned"] = "session.transitioned"
    previous_status: SessionStatus
    target_status: SessionStatus
    stop_reason: str | None = None


class TranscriptTurnAppendedEvent(EventBase):
    schema_version: Literal["transcript_turn_appended_event.v1"] = (
        "transcript_turn_appended_event.v1"
    )
    event_type: Literal["transcript.turn_appended"] = "transcript.turn_appended"
    turn_id: UUID
    turn_sequence: int = Field(ge=1)


class EvidenceObservedEvent(EventBase):
    schema_version: Literal["evidence_observed_event.v1"] = "evidence_observed_event.v1"
    event_type: Literal["evidence.observed"] = "evidence.observed"
    evidence_id: UUID
    turn_id: UUID


class EvidenceSupersededEvent(EventBase):
    schema_version: Literal["evidence_superseded_event.v1"] = (
        "evidence_superseded_event.v1"
    )
    event_type: Literal["evidence.superseded"] = "evidence.superseded"
    previous_evidence_id: UUID
    replacement_evidence_id: UUID


class EvidenceWithdrawnEvent(EventBase):
    schema_version: Literal["evidence_withdrawn_event.v1"] = "evidence_withdrawn_event.v1"
    event_type: Literal["evidence.withdrawn"] = "evidence.withdrawn"
    evidence_id: UUID
    source_turn_id: UUID
    reason: NonEmptyText


class EpisodeOpenedEvent(EventBase):
    schema_version: Literal["episode_opened_event.v1"] = "episode_opened_event.v1"
    event_type: Literal["episode.opened"] = "episode.opened"
    episode_id: UUID
    opened_turn_id: UUID


class EpisodeTransitionedEvent(EventBase):
    schema_version: Literal["episode_transitioned_event.v1"] = (
        "episode_transitioned_event.v1"
    )
    event_type: Literal["episode.transitioned"] = "episode.transitioned"
    episode_id: UUID
    previous_status: EpisodeStatus
    target_status: EpisodeStatus
    closed_turn_id: UUID | None = None

    @model_validator(mode="after")
    def close_turn_matches_target(self) -> "EpisodeTransitionedEvent":
        if self.target_status == EpisodeStatus.CLOSED and self.closed_turn_id is None:
            raise ValueError("closed episode event requires closed_turn_id")
        if self.target_status != EpisodeStatus.CLOSED and self.closed_turn_id is not None:
            raise ValueError("only closed episode event may set closed_turn_id")
        return self


class GapProposedEvent(EventBase):
    schema_version: Literal["gap_proposed_event.v1"] = "gap_proposed_event.v1"
    event_type: Literal["gap.proposed"] = "gap.proposed"
    gap_id: UUID
    episode_id: UUID


class GapTransitionedEvent(EventBase):
    schema_version: Literal["gap_transitioned_event.v1"] = "gap_transitioned_event.v1"
    event_type: Literal["gap.transitioned"] = "gap.transitioned"
    gap_id: UUID
    previous_status: GapStatus
    target_status: GapStatus
    source_turn_id: UUID | None = None
    cause: Literal["command", "evidence_withdrawn"] = "command"


class InferenceAppliedEvent(EventBase):
    schema_version: Literal["inference_applied_event.v1"] = "inference_applied_event.v1"
    event_type: Literal["inference.applied"] = "inference.applied"
    inference_id: UUID
    previous_status: InferenceStatus | None = None
    target_status: InferenceStatus


class InferenceTransitionedEvent(EventBase):
    schema_version: Literal["inference_transitioned_event.v1"] = (
        "inference_transitioned_event.v1"
    )
    event_type: Literal["inference.transitioned"] = "inference.transitioned"
    inference_id: UUID
    previous_status: InferenceStatus
    target_status: InferenceStatus
    cause: Literal["employee_decision", "evidence_withdrawn"]
    decision_evidence_id: UUID | None = None

    @model_validator(mode="after")
    def decision_source_matches_cause(self) -> "InferenceTransitionedEvent":
        if self.cause == "employee_decision" and self.decision_evidence_id is None:
            raise ValueError("employee decision event requires decision_evidence_id")
        if self.cause != "employee_decision" and self.decision_evidence_id is not None:
            raise ValueError("only employee decision event may set decision_evidence_id")
        return self


class InferenceSupersededEvent(EventBase):
    schema_version: Literal["inference_superseded_event.v1"] = (
        "inference_superseded_event.v1"
    )
    event_type: Literal["inference.superseded"] = "inference.superseded"
    previous_inference_id: UUID
    replacement_inference_id: UUID


class CandidateAppliedEvent(EventBase):
    schema_version: Literal["candidate_applied_event.v1"] = "candidate_applied_event.v1"
    event_type: Literal["candidate.applied"] = "candidate.applied"
    candidate_id: UUID
    previous_status: CandidateStatus | None = None
    target_status: CandidateStatus


class CandidateTransitionedEvent(EventBase):
    schema_version: Literal["candidate_transitioned_event.v1"] = (
        "candidate_transitioned_event.v1"
    )
    event_type: Literal["candidate.transitioned"] = "candidate.transitioned"
    candidate_id: UUID
    previous_status: CandidateStatus
    target_status: CandidateStatus
    cause: Literal[
        "verifier",
        "evidence_withdrawn",
        "inference_rejected",
        "inference_superseded",
    ]


class QuestionFrameOpenedEvent(EventBase):
    schema_version: Literal["question_frame_opened_event.v1"] = (
        "question_frame_opened_event.v1"
    )
    event_type: Literal["question_frame.opened"] = "question_frame.opened"
    question_frame_id: UUID
    consultant_turn_id: UUID
    definition_hash: Sha256


class QuestionFrameAnswerBoundEvent(EventBase):
    schema_version: Literal["question_frame_answer_bound_event.v1"] = (
        "question_frame_answer_bound_event.v1"
    )
    event_type: Literal["question_frame.answer_bound"] = "question_frame.answer_bound"
    question_frame_id: UUID
    employee_turn_id: UUID


class QuestionFrameConsumedEvent(EventBase):
    schema_version: Literal["question_frame_consumed_event.v1"] = (
        "question_frame_consumed_event.v1"
    )
    event_type: Literal["question_frame.consumed"] = "question_frame.consumed"
    question_frame_id: UUID
    employee_turn_id: UUID
    operation_id: UUID


class QuestionFrameSupersededEvent(EventBase):
    schema_version: Literal["question_frame_superseded_event.v1"] = (
        "question_frame_superseded_event.v1"
    )
    event_type: Literal["question_frame.superseded"] = "question_frame.superseded"
    previous_question_frame_id: UUID
    replacement_question_frame_id: UUID


class QuestionFrameStaledEvent(EventBase):
    schema_version: Literal["question_frame_staled_event.v1"] = (
        "question_frame_staled_event.v1"
    )
    event_type: Literal["question_frame.staled"] = "question_frame.staled"
    question_frame_id: UUID
    answer_turn_id: UUID | None = None
    reason: QuestionFrameStaleReason


class TurnInterpretationAppliedEvent(EventBase):
    schema_version: Literal["turn_interpretation_applied_event.v1"] = (
        "turn_interpretation_applied_event.v1"
    )
    event_type: Literal["turn.interpretation_applied"] = "turn.interpretation_applied"
    interpretation_id: UUID
    employee_turn_id: UUID
    operation_id: UUID
    question_frame_id: UUID | None = None
    accepted_evidence_ids: tuple[UUID, ...] = ()
    dialogue_act: DialogueAct
    episode_signal: EpisodeSignal
    insufficiency_codes: tuple[TurnInsufficiencyCode, ...] = ()


class ReviewDecisionAppliedEvent(EventBase):
    schema_version: Literal["review_decision_applied_event.v1"] = (
        "review_decision_applied_event.v1"
    )
    event_type: Literal["review.applied"] = "review.applied"
    review_id: UUID
    candidate_id: UUID
    action: ReviewAction


DomainEvent: TypeAlias = Annotated[
    SessionTransitionedEvent
    | TranscriptTurnAppendedEvent
    | EvidenceObservedEvent
    | EvidenceSupersededEvent
    | EvidenceWithdrawnEvent
    | EpisodeOpenedEvent
    | EpisodeTransitionedEvent
    | GapProposedEvent
    | GapTransitionedEvent
    | InferenceAppliedEvent
    | InferenceTransitionedEvent
    | InferenceSupersededEvent
    | CandidateAppliedEvent
    | CandidateTransitionedEvent
    | QuestionFrameOpenedEvent
    | QuestionFrameAnswerBoundEvent
    | QuestionFrameConsumedEvent
    | QuestionFrameSupersededEvent
    | QuestionFrameStaledEvent
    | TurnInterpretationAppliedEvent
    | ReviewDecisionAppliedEvent,
    Field(discriminator="event_type"),
]
