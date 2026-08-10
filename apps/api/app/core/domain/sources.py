"""Provenance contracts:SourceRef、SourceAnchor、SupportLink(§9.1)。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from .base import DomainModel, Identifier, NonEmptyText


class SourceKind(StrEnum):
    EMPLOYEE_TURN = "employee_turn"
    DIRECT_EDIT = "direct_edit"
    PROPOSAL_DECISION = "proposal_decision"


class SourceRef(DomainModel):
    kind: SourceKind
    id: Identifier


class SourceAnchor(DomainModel):
    """一筆來源指涉,可帶逐字引用與提問回合。

    `quote` 是否為該回合原文的逐字子字串、`question_turn_id` 是否指向已存在且較早的
    顧問回合,都需要 transcript 才能判斷,歸 deterministic verifier(§9.5);此處只鎖
    「employee_turn 一定要有 quote」這條與 transcript 無關的形狀規則。
    """

    source_ref: SourceRef
    quote: NonEmptyText | None = None
    question_turn_id: Identifier | None = None

    @model_validator(mode="after")
    def employee_turn_requires_quote(self):
        if self.source_ref.kind is SourceKind.EMPLOYEE_TURN and self.quote is None:
            raise ValueError("employee_turn source requires a quote")
        return self


class SupportLink(SourceAnchor):
    """Task 的依據;`superseded_by` 非空即失效(§9.1、§9.5)。"""

    superseded_by: SourceRef | None = None

    @property
    def is_effective(self) -> bool:
        return self.superseded_by is None
