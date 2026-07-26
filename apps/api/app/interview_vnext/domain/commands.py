"""Pure reducer commands with optimistic concurrency and idempotency keys."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import DomainModel
from .episode import EpisodeStatus, Gap, GapStatus
from .evidence import Evidence, Inference, InferenceStatus
from .identifiers import NonEmptyText, UtcDatetime
from .interpretation import TurnInterpretationRecord
from .job_model import CandidateJobItem, CandidateStatus
from .question_frame import QuestionFrameDefinition, QuestionFrameStaleReason
from .review import ReviewDecision
from .session import SessionStatus
from .transcript import TranscriptRole, TranscriptTurn


class CommandBase(DomainModel):
    command_id: UUID
    expected_state_version: int = Field(ge=0)
    occurred_at: UtcDatetime


class TransitionSessionCommand(CommandBase):
    schema_version: Literal["transition_session_command.v1"] = "transition_session_command.v1"
    target_status: SessionStatus
    stop_reason: str | None = None

    @field_validator("stop_reason")
    @classmethod
    def stop_reason_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("stop_reason cannot be blank")
        return value


class AppendConsultantQuestionCommand(CommandBase):
    """A consultant question always persists the frame it opens (ADR 0037 §3)."""

    schema_version: Literal["append_consultant_question_command.v1"] = (
        "append_consultant_question_command.v1"
    )
    turn: TranscriptTurn
    frame_definition: QuestionFrameDefinition

    @model_validator(mode="after")
    def turn_is_consultant(self) -> "AppendConsultantQuestionCommand":
        if self.turn.role != TranscriptRole.CONSULTANT:
            raise ValueError("consultant question command requires a consultant turn")
        return self


class AppendEmployeeTurnCommand(CommandBase):
    """Frame binding is the reducer's job: the caller cannot name a frame."""

    schema_version: Literal["append_employee_turn_command.v1"] = (
        "append_employee_turn_command.v1"
    )
    turn: TranscriptTurn

    @model_validator(mode="after")
    def turn_is_employee(self) -> "AppendEmployeeTurnCommand":
        if self.turn.role != TranscriptRole.EMPLOYEE:
            raise ValueError("employee turn command requires an employee turn")
        return self


class InvalidateQuestionFrameCommand(CommandBase):
    schema_version: Literal["invalidate_question_frame_command.v1"] = (
        "invalidate_question_frame_command.v1"
    )
    question_frame_id: UUID
    reason: QuestionFrameStaleReason


class ApplyTurnInterpretationCommand(CommandBase):
    """Receipt plus the evidence it accepted; zero observations is valid."""

    schema_version: Literal["apply_turn_interpretation_command.v1"] = (
        "apply_turn_interpretation_command.v1"
    )
    record: TurnInterpretationRecord
    observations: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def accepted_ids_match_observations(self) -> "ApplyTurnInterpretationCommand":
        observed_ids = tuple(item.evidence_id for item in self.observations)
        if self.record.accepted_evidence_ids != observed_ids:
            raise ValueError("record.accepted_evidence_ids must equal observation IDs, in order")
        for item in self.observations:
            if item.extractor_operation_id != self.record.operation_id:
                raise ValueError("observations must come from the record's operation")
            if item.session_id != self.record.session_id:
                raise ValueError("observations must belong to the record's session")
        return self


class WithdrawEvidenceCommand(CommandBase):
    schema_version: Literal["withdraw_evidence_command.v1"] = "withdraw_evidence_command.v1"
    evidence_id: UUID
    source_turn_id: UUID
    reason: NonEmptyText


class OpenEpisodeCommand(CommandBase):
    schema_version: Literal["open_episode_command.v1"] = "open_episode_command.v1"
    episode_id: UUID
    target: NonEmptyText
    opened_turn_id: UUID


class TransitionEpisodeCommand(CommandBase):
    schema_version: Literal["transition_episode_command.v1"] = (
        "transition_episode_command.v1"
    )
    episode_id: UUID
    target_status: EpisodeStatus
    closed_turn_id: UUID | None = None

    @model_validator(mode="after")
    def closure_fields_match_target(self) -> "TransitionEpisodeCommand":
        if self.target_status == EpisodeStatus.OPEN:
            raise ValueError("transition command cannot target open")
        if self.target_status == EpisodeStatus.CLOSED and self.closed_turn_id is None:
            raise ValueError("closed transition requires closed_turn_id")
        if self.target_status != EpisodeStatus.CLOSED and self.closed_turn_id is not None:
            raise ValueError("only closed transition may set closed_turn_id")
        return self


class ApplyGapProposalsCommand(CommandBase):
    schema_version: Literal["apply_gap_proposals_command.v1"] = (
        "apply_gap_proposals_command.v1"
    )
    episode_id: UUID
    gaps: Annotated[tuple[Gap, ...], Field(min_length=1)]


class TransitionGapCommand(CommandBase):
    schema_version: Literal["transition_gap_command.v1"] = "transition_gap_command.v1"
    gap_id: UUID
    target_status: GapStatus
    source_turn_id: UUID | None = None
    resolution_evidence_ids: tuple[UUID, ...] = ()
    unresolved_reason: str | None = None

    @model_validator(mode="after")
    def transition_fields_match_target(self) -> "TransitionGapCommand":
        if self.unresolved_reason is not None and not self.unresolved_reason.strip():
            raise ValueError("unresolved_reason cannot be blank")
        if self.target_status == GapStatus.OPEN:
            raise ValueError("transition command cannot target open")
        if self.target_status in {GapStatus.ASKED, GapStatus.ANSWERED}:
            if self.source_turn_id is None:
                raise ValueError("asked/answered transition requires source_turn_id")
            if self.unresolved_reason is not None:
                raise ValueError("asked/answered transition cannot set unresolved_reason")
            if self.target_status == GapStatus.ANSWERED and not self.resolution_evidence_ids:
                raise ValueError("answered transition requires resolution_evidence_ids")
        elif self.target_status in {GapStatus.DECLINED, GapStatus.NOT_APPLICABLE}:
            if self.source_turn_id is None or self.unresolved_reason is None:
                raise ValueError("declined/not_applicable requires source turn and reason")
            if (
                self.target_status == GapStatus.NOT_APPLICABLE
                and not self.resolution_evidence_ids
            ):
                raise ValueError("not_applicable requires resolution_evidence_ids")
        elif self.target_status == GapStatus.DEFERRED and self.unresolved_reason is None:
            raise ValueError("deferred transition requires unresolved_reason")
        if self.target_status not in {GapStatus.ANSWERED, GapStatus.NOT_APPLICABLE}:
            if self.resolution_evidence_ids:
                raise ValueError("only answered/not_applicable may set resolution evidence")
        if len(self.resolution_evidence_ids) != len(set(self.resolution_evidence_ids)):
            raise ValueError("resolution_evidence_ids must be unique")
        return self


class ApplyInferenceProposalsCommand(CommandBase):
    schema_version: Literal["apply_inference_proposals_command.v1"] = (
        "apply_inference_proposals_command.v1"
    )
    inferences: Annotated[tuple[Inference, ...], Field(min_length=1)]


class DecideInferenceCommand(CommandBase):
    schema_version: Literal["decide_inference_command.v1"] = "decide_inference_command.v1"
    inference_id: UUID
    target_status: InferenceStatus
    decision_evidence_id: UUID

    @model_validator(mode="after")
    def target_is_employee_decision(self) -> "DecideInferenceCommand":
        if self.target_status not in {
            InferenceStatus.CONFIRMED_BY_EMPLOYEE,
            InferenceStatus.REJECTED,
        }:
            raise ValueError("inference decision must confirm or reject")
        return self


class SupersedeInferenceCommand(CommandBase):
    schema_version: Literal["supersede_inference_command.v1"] = (
        "supersede_inference_command.v1"
    )
    inference_id: UUID
    replacement: Inference


class ApplyCandidateProposalsCommand(CommandBase):
    schema_version: Literal["apply_candidate_proposals_command.v1"] = (
        "apply_candidate_proposals_command.v1"
    )
    candidates: Annotated[tuple[CandidateJobItem, ...], Field(min_length=1)]


class TransitionCandidateCommand(CommandBase):
    schema_version: Literal["transition_candidate_command.v1"] = (
        "transition_candidate_command.v1"
    )
    candidate_id: UUID
    target_status: CandidateStatus


class ApplyReviewDecisionCommand(CommandBase):
    schema_version: Literal["apply_review_decision_command.v1"] = (
        "apply_review_decision_command.v1"
    )
    decision: ReviewDecision
