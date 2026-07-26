"""Quote primitives and the discriminated Evidence support union.

This module owns ``QuoteSpan``/``QuoteMatch``. ``evidence.py`` imports them from
here, so the dependency runs evidence -> support only: ``Evidence.v3`` (R5-B) can
add a ``support`` field without an import cycle.

That union carries provenance instead of a single top-level quote/span. Two
support kinds exist:

- ``literal_employee_span``: the claim is directly supported by an exact quote of
  the current employee turn (the v2 quote/span semantics);
- ``contextual_answer``: the proposition/value comes from a validated
  QuestionFrame target, and the employee's authority is a short answer span
  (是 / 每週 / 主管) bound to that target.

These are pure value objects enforcing intra-support coherence. Binding a support
to an actual active frame, and materializing it from a verified answer, are
reducer/verifier concerns (amendment plan §7, §10) not validated here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .base import DomainModel
from .identifiers import NonEmptyText, Sha256


class QuoteSpan(DomainModel):
    unit: Literal["unicode_code_point"] = "unicode_code_point"
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def end_is_after_start(self) -> "QuoteSpan":
        if self.end <= self.start:
            raise ValueError("quote span end must be greater than start")
        return self


class QuoteMatch(StrEnum):
    EXACT = "exact"
    NORMALIZED = "normalized"


class ContextualBindingKind(StrEnum):
    AFFIRMATION = "affirmation"
    DENIAL = "denial"
    SLOT_VALUE = "slot_value"
    CHOICE_SELECTION = "choice_selection"


class ContextualResolution(StrEnum):
    AFFIRMED = "affirmed"
    DENIED = "denied"
    SUPPLIED = "supplied"
    SELECTED = "selected"


_BINDING_RESOLUTION: dict[ContextualBindingKind, ContextualResolution] = {
    ContextualBindingKind.AFFIRMATION: ContextualResolution.AFFIRMED,
    ContextualBindingKind.DENIAL: ContextualResolution.DENIED,
    ContextualBindingKind.SLOT_VALUE: ContextualResolution.SUPPLIED,
    ContextualBindingKind.CHOICE_SELECTION: ContextualResolution.SELECTED,
}


class LiteralEmployeeSpanSupport(DomainModel):
    support_kind: Literal["literal_employee_span"] = "literal_employee_span"
    employee_turn_id: UUID
    quote: NonEmptyText
    span: QuoteSpan
    quote_match: QuoteMatch = QuoteMatch.EXACT
    normalization_version: Literal["quote_nfkc_ws.v1"] | None = None

    @model_validator(mode="after")
    def normalization_is_coherent(self) -> "LiteralEmployeeSpanSupport":
        if self.quote_match is QuoteMatch.NORMALIZED and self.normalization_version is None:
            raise ValueError("normalized quotes require normalization_version")
        if self.quote_match is QuoteMatch.EXACT and self.normalization_version is not None:
            raise ValueError("exact quotes cannot set normalization_version")
        return self


class ContextualAnswerSupport(DomainModel):
    support_kind: Literal["contextual_answer"] = "contextual_answer"
    employee_turn_id: UUID
    answer_quote: NonEmptyText
    answer_span: QuoteSpan
    question_frame_id: UUID
    question_frame_definition_hash: Sha256
    target_ordinal: Annotated[int, Field(ge=1)]
    target_hash: Sha256
    binding_kind: ContextualBindingKind
    resolution: ContextualResolution
    value_text: NonEmptyText | None = None
    choice_option_ordinal: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def binding_is_coherent(self) -> "ContextualAnswerSupport":
        if self.resolution is not _BINDING_RESOLUTION[self.binding_kind]:
            raise ValueError("resolution must match binding_kind")
        if self.binding_kind in {
            ContextualBindingKind.AFFIRMATION,
            ContextualBindingKind.DENIAL,
        }:
            if self.value_text is not None or self.choice_option_ordinal is not None:
                raise ValueError("affirmation/denial support carries no value or option")
        elif self.binding_kind is ContextualBindingKind.SLOT_VALUE:
            if self.value_text is None:
                raise ValueError("slot_value support requires value_text")
            if self.choice_option_ordinal is not None:
                raise ValueError("slot_value support carries no choice option")
            if self.value_text not in self.answer_quote:
                raise ValueError("slot value_text must be an exact substring of answer_quote")
        elif self.binding_kind is ContextualBindingKind.CHOICE_SELECTION:
            if self.choice_option_ordinal is None:
                raise ValueError("choice_selection support requires choice_option_ordinal")
            if self.value_text is not None:
                raise ValueError("choice_selection support carries no value_text")
        return self


EvidenceSupport = Annotated[
    LiteralEmployeeSpanSupport | ContextualAnswerSupport,
    Field(discriminator="support_kind"),
]
