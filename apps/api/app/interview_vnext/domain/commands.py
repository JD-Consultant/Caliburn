"""Pure reducer commands with optimistic concurrency and idempotency keys."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from .base import DomainModel
from .evidence import Evidence
from .identifiers import UtcDatetime
from .session import SessionStatus
from .transcript import TranscriptTurn


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


class AppendTranscriptTurnCommand(CommandBase):
    schema_version: Literal["append_transcript_turn_command.v1"] = (
        "append_transcript_turn_command.v1"
    )
    turn: TranscriptTurn


class ApplyEvidenceCommand(CommandBase):
    schema_version: Literal["apply_evidence_command.v1"] = "apply_evidence_command.v1"
    turn_id: UUID
    observations: Annotated[tuple[Evidence, ...], Field(min_length=1)]
