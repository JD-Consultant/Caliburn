"""Human review decisions are an authority boundary, not model feedback text."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from .base import DomainModel
from .identifiers import UtcDatetime


class ReviewAction(StrEnum):
    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"


class ReviewDecision(DomainModel):
    schema_version: Literal["review_decision.v1"] = "review_decision.v1"
    review_id: UUID
    session_id: UUID
    candidate_id: UUID
    reviewer_id: UUID
    action: ReviewAction
    edited_statement: str | None = None
    reason: str | None = None
    decided_at: UtcDatetime

    @model_validator(mode="after")
    def edited_content_matches_action(self) -> "ReviewDecision":
        if self.action == ReviewAction.EDIT:
            if self.edited_statement is None or not self.edited_statement.strip():
                raise ValueError("edit decision requires edited_statement")
        elif self.edited_statement is not None:
            raise ValueError("only edit decision may set edited_statement")
        if self.reason is not None and not self.reason.strip():
            raise ValueError("review reason cannot be blank")
        return self
