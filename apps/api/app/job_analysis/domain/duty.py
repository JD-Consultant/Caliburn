"""Employee-owned Duty grouping for Current JD Tasks."""

from __future__ import annotations

from pydantic import Field

from .base import DomainModel, Identifier, NonEmptyText


DutyId = Identifier


class Duty(DomainModel):
    duty_id: DutyId
    statement: NonEmptyText
    display_order: int = Field(ge=0)
