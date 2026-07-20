"""Append-only transcript turn contract."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import DomainModel
from .identifiers import Locale, ShortText, UtcDatetime


class TranscriptRole(StrEnum):
    CONSULTANT = "consultant"
    EMPLOYEE = "employee"


class TranscriptTurn(DomainModel):
    schema_version: Literal["transcript_turn.v1"] = "transcript_turn.v1"
    turn_id: UUID
    session_id: UUID
    client_turn_id: ShortText
    sequence: int = Field(ge=1)
    role: TranscriptRole
    text: str = Field(min_length=1)
    previous_turn_id: UUID | None = None
    locale: Locale = "zh-TW"
    occurred_at: UtcDatetime
    received_at: UtcDatetime

    @field_validator("text")
    @classmethod
    def text_is_not_blank_but_remains_verbatim(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text cannot be blank")
        return value

    @model_validator(mode="after")
    def receipt_cannot_precede_occurrence(self) -> "TranscriptTurn":
        if self.received_at < self.occurred_at:
            raise ValueError("received_at must be >= occurred_at")
        return self
