"""Episode, sufficiency gap, and explainable priority contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .base import DomainModel
from .identifiers import NonEmptyText, UtcDatetime


class EpisodeStatus(StrEnum):
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


class EpisodeState(DomainModel):
    schema_version: Literal["episode_state.v1"] = "episode_state.v1"
    episode_id: UUID
    session_id: UUID
    target: NonEmptyText
    status: EpisodeStatus = EpisodeStatus.OPEN
    opened_turn_id: UUID
    closed_turn_id: UUID | None = None
    evidence_ids: tuple[UUID, ...] = ()
    gap_ids: tuple[UUID, ...] = ()
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def lifecycle_is_coherent(self) -> "EpisodeState":
        if self.updated_at < self.created_at:
            raise ValueError("episode updated_at must be >= created_at")
        if self.status == EpisodeStatus.CLOSED and self.closed_turn_id is None:
            raise ValueError("closed episode requires closed_turn_id")
        if self.status != EpisodeStatus.CLOSED and self.closed_turn_id is not None:
            raise ValueError("only a closed episode may set closed_turn_id")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("episode evidence IDs must be unique")
        if len(self.gap_ids) != len(set(self.gap_ids)):
            raise ValueError("episode gap IDs must be unique")
        return self


class GapDimension(StrEnum):
    TRIGGER_INPUT = "trigger_input"
    ACTION_DECISION = "action_decision"
    OUTPUT_RECIPIENT = "output_recipient"
    PURPOSE = "purpose"
    OWNERSHIP_COLLABORATION = "ownership_collaboration"
    CONDITION_TOOL = "condition_tool"
    STANDARD_RESULT = "standard_result"
    FREQUENCY_IMPORTANCE = "frequency_importance"
    EXCEPTION_REWORK = "exception_rework"
    CONTRADICTION = "contradiction"
    EMERGENT = "emergent"


class GapStatus(StrEnum):
    OPEN = "open"
    ASKED = "asked"
    ANSWERED = "answered"
    DECLINED = "declined"
    NOT_APPLICABLE = "not_applicable"
    DEFERRED = "deferred"


class ValueLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Sensitivity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PROHIBITED = "prohibited"


class GapPriorityFeatures(DomainModel):
    jd_value: ValueLevel
    contradiction: bool = False
    redundancy: bool = False
    sensitivity: Sensitivity = Sensitivity.LOW
    burden: ValueLevel = ValueLevel.LOW


class Gap(DomainModel):
    schema_version: Literal["gap.v2"] = "gap.v2"
    gap_id: UUID
    session_id: UUID
    episode_id: UUID
    dimension: GapDimension
    question_goal: NonEmptyText
    supporting_evidence_ids: tuple[UUID, ...] = ()
    status: GapStatus = GapStatus.OPEN
    priority_features: GapPriorityFeatures
    asked_turn_ids: tuple[UUID, ...] = ()
    resolution_turn_id: UUID | None = None
    resolution_evidence_ids: tuple[UUID, ...] = ()
    unresolved_reason: str | None = None

    @model_validator(mode="after")
    def links_are_unique_and_reason_is_meaningful(self) -> "Gap":
        if len(self.supporting_evidence_ids) != len(set(self.supporting_evidence_ids)):
            raise ValueError("gap supporting evidence IDs must be unique")
        if len(self.asked_turn_ids) != len(set(self.asked_turn_ids)):
            raise ValueError("gap asked turn IDs must be unique")
        if len(self.resolution_evidence_ids) != len(set(self.resolution_evidence_ids)):
            raise ValueError("gap resolution evidence IDs must be unique")
        if self.unresolved_reason is not None and not self.unresolved_reason.strip():
            raise ValueError("unresolved_reason cannot be blank")
        if self.status == GapStatus.OPEN:
            if (
                self.asked_turn_ids
                or self.resolution_turn_id
                or self.resolution_evidence_ids
                or self.unresolved_reason
            ):
                raise ValueError("open gap cannot contain question or resolution fields")
        elif self.status == GapStatus.ASKED:
            if not self.asked_turn_ids:
                raise ValueError("asked gap requires asked_turn_ids")
            if (
                self.resolution_turn_id is not None
                or self.resolution_evidence_ids
                or self.unresolved_reason is not None
            ):
                raise ValueError("asked gap cannot contain resolution fields")
        elif self.status == GapStatus.ANSWERED:
            if (
                not self.asked_turn_ids
                or self.resolution_turn_id is None
                or not self.resolution_evidence_ids
            ):
                raise ValueError("answered gap requires question, turn, and evidence")
            if self.unresolved_reason is not None:
                raise ValueError("answered gap cannot contain unresolved_reason")
        elif self.status in {GapStatus.DECLINED, GapStatus.NOT_APPLICABLE}:
            if self.resolution_turn_id is None or self.unresolved_reason is None:
                raise ValueError("declined/not_applicable gap requires source turn and reason")
            if self.status == GapStatus.DECLINED and not self.asked_turn_ids:
                raise ValueError("declined gap must have been asked")
            if self.status == GapStatus.NOT_APPLICABLE and not self.resolution_evidence_ids:
                raise ValueError("not_applicable gap requires resolution evidence")
            if self.status == GapStatus.DECLINED and self.resolution_evidence_ids:
                raise ValueError("declined gap cannot claim resolution evidence")
        elif self.status == GapStatus.DEFERRED and self.unresolved_reason is None:
            raise ValueError("deferred gap requires unresolved_reason")
        if self.status == GapStatus.DEFERRED and self.resolution_evidence_ids:
            raise ValueError("deferred gap cannot claim resolution evidence")
        return self
