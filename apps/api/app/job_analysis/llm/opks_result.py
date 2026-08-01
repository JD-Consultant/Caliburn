"""OPKS model result 的 application-side 形狀。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.job_analysis.domain import DomainModel, NonEmptyText


class OpksGenerationEntityKind(StrEnum):
    OUTPUT = "output"
    INDICATOR = "indicator"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"


class OpksDecision(StrEnum):
    ADD_NEW = "add_new"
    REUSE_EXISTING = "reuse_existing"
    REVISE_EXISTING = "revise_existing"
    REMOVE_EXISTING = "remove_existing"
    UNCERTAIN = "uncertain"


class OpksResultItem(DomainModel):
    entity_kind: OpksGenerationEntityKind
    decision: OpksDecision
    target_ordinal: int | None = Field(default=None, ge=1)
    text: NonEmptyText | None = None


class OpksResult(DomainModel):
    items: tuple[OpksResultItem, ...] = ()

