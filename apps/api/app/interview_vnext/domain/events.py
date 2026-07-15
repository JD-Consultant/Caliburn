"""Typed, deterministic domain events emitted by pure reducers."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import Field

from .base import DomainModel
from .identifiers import UtcDatetime
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


DomainEvent: TypeAlias = Annotated[
    SessionTransitionedEvent
    | TranscriptTurnAppendedEvent
    | EvidenceObservedEvent
    | EvidenceSupersededEvent,
    Field(discriminator="event_type"),
]
