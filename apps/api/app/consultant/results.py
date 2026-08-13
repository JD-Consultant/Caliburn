"""Typed semantic output from one professional-consultant run.

These models are deliberately upstream of document authority.  A model may
describe reviewable document changes, but it cannot return or replace an
``ApprovedJobDocument``.  Application code verifies this result and later
turns accepted changes into durable authority commands.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator
from typing_extensions import Annotated

from app.consultant.state import QuoteAnchor


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SkillId = Literal[
    "work-discovery",
    "story-interview",
    "task-boundary",
    "duty-grouping",
    "output",
    "performance-indicator",
    "knowledge",
    "skill",
    "completion-red-team",
]


class ResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnalysisBasis(ResultModel):
    """Employee evidence and professional method used for one semantic claim."""

    source_ids: tuple[UUID, ...] = Field(min_length=1)
    quote_anchors: tuple[QuoteAnchor, ...] = ()
    skill_ids: tuple[SkillId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def dependencies_are_unique_and_anchored(self) -> AnalysisBasis:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("duplicate source dependency")
        if len(self.skill_ids) != len(set(self.skill_ids)):
            raise ValueError("duplicate Skill dependency")
        anchor_sources = {anchor.source_id for anchor in self.quote_anchors}
        if not anchor_sources <= set(self.source_ids):
            raise ValueError("quote anchor source must be a declared source dependency")
        return self


class UnderstandingOperation(StrEnum):
    ADD = "add"
    REVISE = "revise"
    RETIRE = "retire"


class UnderstandingChange(ResultModel):
    operation: UnderstandingOperation
    understanding_id: UUID | None = None
    kind: NonEmptyText
    text: NonEmptyText
    basis: AnalysisBasis


class AttentionOperation(StrEnum):
    ADD = "add"
    REVISE = "revise"
    PARK = "park"
    RETIRE = "retire"


class AttentionChange(ResultModel):
    operation: AttentionOperation
    attention_id: UUID | None = None
    kind: NonEmptyText
    subject_id: UUID | None = None
    reason: NonEmptyText
    basis: AnalysisBasis


class GapReason(StrEnum):
    WORK_COVERAGE_MISSING = "work_coverage_missing"
    TASK_BOUNDARY_UNCLEAR = "task_boundary_unclear"
    CURRENT_RESPONSIBILITY_UNCLEAR = "current_responsibility_unclear"
    COMPLETION_STANDARD_MISSING = "completion_standard_missing"
    DUTY_GROUPING_UNCERTAIN = "duty_grouping_uncertain"
    PERFORMANCE_EVIDENCE_MISSING = "performance_evidence_missing"
    KNOWLEDGE_EVIDENCE_MISSING = "knowledge_evidence_missing"
    SKILL_EVIDENCE_MISSING = "skill_evidence_missing"
    SOURCE_CONTRADICTION = "source_contradiction"
    EMPLOYEE_DECISION_PENDING = "employee_decision_pending"
    ROUTINE_WORK_MAY_BE_MISSING = "routine_work_may_be_missing"


class VisibleGap(ResultModel):
    reason: GapReason
    description: NonEmptyText
    subject_kind: NonEmptyText
    subject_id: UUID | None = None
    blocks_dependent_analysis: bool = False
    basis: AnalysisBasis


class DocumentChangeOperation(StrEnum):
    ADD = "add"
    REVISE = "revise"
    WITHDRAW = "withdraw"
    MERGE = "merge"
    SPLIT = "split"
    REASSIGN = "reassign"
    REORDER = "reorder"


class OpksKind(StrEnum):
    OUTPUT = "output"
    PERFORMANCE_INDICATOR = "indicator"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"


class ReviewableDocumentChange(ResultModel):
    """A semantic draft for employee review, never an authority mutation."""

    operation: DocumentChangeOperation
    path: NonEmptyText
    after: JsonValue | None = None
    opks_kind: OpksKind | None = None
    task_ids: tuple[UUID, ...] = ()
    indicator_ids: tuple[UUID, ...] = ()
    basis: AnalysisBasis

    @model_validator(mode="after")
    def references_are_unique(self) -> ReviewableDocumentChange:
        if len(self.task_ids) != len(set(self.task_ids)):
            raise ValueError("duplicate task_ids")
        if len(self.indicator_ids) != len(set(self.indicator_ids)):
            raise ValueError("duplicate indicator_ids")
        if self.operation is not DocumentChangeOperation.WITHDRAW and self.after is None:
            raise ValueError("non-withdraw document change requires an after value")
        return self


class NextQuestion(ResultModel):
    """Exactly one employee-facing main answer target, when another is needed."""

    text: NonEmptyText
    answer_target: NonEmptyText
    reason: NonEmptyText
    basis: AnalysisBasis


class SufficiencyRecommendation(ResultModel):
    """Advisory evidence sufficiency; it is not a pause or finish lifecycle."""

    currently_enough: bool
    reason: NonEmptyText
    remaining_gap_reasons: tuple[GapReason, ...] = ()
    basis: AnalysisBasis

    @model_validator(mode="after")
    def gaps_match_recommendation(self) -> SufficiencyRecommendation:
        if self.currently_enough and self.remaining_gap_reasons:
            raise ValueError("currently sufficient result cannot list unresolved gaps")
        if not self.currently_enough and not self.remaining_gap_reasons:
            raise ValueError("insufficient result requires at least one concrete gap")
        return self


class ConsultantResult(ResultModel):
    """One coherent result owned by the single professional consultant."""

    visible_reply: NonEmptyText
    reply_basis: AnalysisBasis
    used_skill_ids: tuple[SkillId, ...] = Field(min_length=1)
    understanding_changes: tuple[UnderstandingChange, ...] = ()
    attention_changes: tuple[AttentionChange, ...] = ()
    gaps: tuple[VisibleGap, ...] = ()
    reviewable_document_changes: tuple[ReviewableDocumentChange, ...] = ()
    next_question: NextQuestion | None = None
    sufficiency: SufficiencyRecommendation

    @model_validator(mode="after")
    def every_claim_uses_a_declared_skill(self) -> ConsultantResult:
        if len(self.used_skill_ids) != len(set(self.used_skill_ids)):
            raise ValueError("duplicate used_skill_ids")
        used = set(self.used_skill_ids)
        for basis in self.analysis_bases():
            if not set(basis.skill_ids) <= used:
                raise ValueError("semantic claim depends on an undeclared used Skill")
        return self

    def analysis_bases(self) -> tuple[AnalysisBasis, ...]:
        values: list[AnalysisBasis] = [
            self.reply_basis,
            *(item.basis for item in self.understanding_changes),
            *(item.basis for item in self.attention_changes),
            *(item.basis for item in self.gaps),
            *(item.basis for item in self.reviewable_document_changes),
            self.sufficiency.basis,
        ]
        if self.next_question is not None:
            values.append(self.next_question.basis)
        return tuple(values)

    def factual_texts(self) -> tuple[tuple[str, AnalysisBasis], ...]:
        values: list[tuple[str, AnalysisBasis]] = [
            (self.visible_reply, self.reply_basis),
            *(
                (item.text, item.basis)
                for item in self.understanding_changes
            ),
            *((item.reason, item.basis) for item in self.attention_changes),
            *((item.description, item.basis) for item in self.gaps),
            *((item.reason, item.basis) for item in (self.sufficiency,)),
        ]
        for change in self.reviewable_document_changes:
            if change.after is not None and not (
                change.operation
                in {
                    DocumentChangeOperation.REASSIGN,
                    DocumentChangeOperation.REORDER,
                }
                or change.path.endswith(
                    ("/duty_id", "/display_order", "/task_ids", "/indicator_ids")
                )
            ):
                values.append((_json_text(change.after), change.basis))
        if self.next_question is not None:
            values.extend(
                (
                    (self.next_question.text, self.next_question.basis),
                    (self.next_question.reason, self.next_question.basis),
                )
            )
        return tuple(values)


def _json_text(value: JsonValue) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(f"{key} {_json_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_json_text(item) for item in value)
    return str(value)
