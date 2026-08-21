"""Typed semantic output from one professional-consultant run.

These models are deliberately upstream of document authority.  A model may
describe reviewable document changes, but it cannot return or replace an
``ApprovedJobDocument``.  Application code verifies this result and later
turns accepted changes into durable authority commands.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator
from typing_extensions import Annotated

from app.consultant.state import (
    ActionHandle,
    InterviewPriority,
    InterviewWorkStatus,
    QuoteAnchor,
    UnderstandingImpact,
)


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
DocumentScalar: TypeAlias = str | int | bool
DocumentNestedObject: TypeAlias = dict[str, DocumentScalar | None]
DocumentObject: TypeAlias = dict[
    str,
    DocumentScalar
    | None
    | list[DocumentScalar]
    | list[DocumentNestedObject],
]
DocumentAfterValue: TypeAlias = (
    DocumentScalar
    | list[DocumentScalar]
    | DocumentObject
    | list[DocumentObject]
)


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
    impact: UnderstandingImpact = UnderstandingImpact.ROUTINE
    work_ids: tuple[UUID, ...] = ()
    basis: AnalysisBasis

    @model_validator(mode="after")
    def existing_identity_is_required_for_non_add(self) -> UnderstandingChange:
        if (
            self.operation is not UnderstandingOperation.ADD
            and self.understanding_id is None
        ):
            raise ValueError("revising or retiring understanding requires its ID")
        if len(self.work_ids) != len(set(self.work_ids)):
            raise ValueError("duplicate understanding work_ids")
        return self


class AttentionOperation(StrEnum):
    ADD = "add"
    REVISE = "revise"
    PARK = "park"
    RETIRE = "retire"


class AttentionChange(ResultModel):
    operation: AttentionOperation
    attention_id: UUID | None = None
    kind: NonEmptyText
    title: NonEmptyText | None = None
    subject_id: UUID | None = None
    reason: NonEmptyText
    missing_before_enough: NonEmptyText | None = None
    recommended_next_step: NonEmptyText | None = None
    priority: InterviewPriority = InterviewPriority.OTHER
    disposition: InterviewWorkStatus | None = None
    make_current: bool = False
    basis: AnalysisBasis

    @model_validator(mode="after")
    def operation_and_attention_identity_are_consistent(self) -> AttentionChange:
        if self.operation is not AttentionOperation.ADD and self.attention_id is None:
            raise ValueError("updating interview work requires its ID")
        if self.operation in {AttentionOperation.PARK, AttentionOperation.RETIRE}:
            if self.make_current:
                raise ValueError("parked or retired work cannot become current")
        if self.disposition is InterviewWorkStatus.ACTIVE and not self.make_current:
            raise ValueError("active disposition requires make_current")
        return self


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


class GapOperation(StrEnum):
    UPSERT = "upsert"
    HOLD = "hold"
    RESOLVE = "resolve"


class VisibleGap(ResultModel):
    operation: GapOperation = GapOperation.UPSERT
    gap_id: UUID | None = None
    reason: GapReason
    description: NonEmptyText
    subject_kind: NonEmptyText
    subject_id: UUID | None = None
    blocks_dependent_analysis: bool = False
    basis: AnalysisBasis

    @model_validator(mode="after")
    def existing_identity_is_required_to_resolve(self) -> VisibleGap:
        if self.operation is GapOperation.RESOLVE and self.gap_id is None:
            raise ValueError("resolving a gap requires its ID")
        return self


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
    after: DocumentAfterValue | None = None
    target_ids: tuple[UUID, ...] = ()
    opks_kind: OpksKind | None = None
    task_ids: tuple[UUID, ...] = ()
    indicator_ids: tuple[UUID, ...] = ()
    basis: AnalysisBasis
    change_ref: str = ""
    depends_on_change_refs: tuple[str, ...] = ()
    depends_on_action_ids: tuple[UUID, ...] = ()
    supersedes_action_ids: tuple[UUID, ...] = ()
    atomic_group_ref: str = ""

    @model_validator(mode="after")
    def references_are_unique(self) -> ReviewableDocumentChange:
        for label, values in (
            ("target_ids", self.target_ids),
            ("task_ids", self.task_ids),
            ("indicator_ids", self.indicator_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")
        if self.operation is not DocumentChangeOperation.WITHDRAW and self.after is None:
            raise ValueError("non-withdraw document change requires an after value")
        if self.operation in {
            DocumentChangeOperation.MERGE,
            DocumentChangeOperation.SPLIT,
        } and not self.target_ids:
            raise ValueError("merge or split requires stable target_ids")
        if self.operation not in {
            DocumentChangeOperation.MERGE,
            DocumentChangeOperation.SPLIT,
        } and self.target_ids:
            raise ValueError("target_ids are only valid for merge or split")
        return self


class NextQuestion(ResultModel):
    """Exactly one employee-facing main answer target, when another is needed."""

    text: NonEmptyText
    answer_target: NonEmptyText
    reason: NonEmptyText
    basis: AnalysisBasis


class RequiredClarificationDraft(ResultModel):
    """A rare ambiguity only the employee can resolve before safe inference."""

    reason: NonEmptyText
    question: NonEmptyText
    current_understanding: NonEmptyText
    choices: tuple[NonEmptyText, ...] = Field(min_length=2, max_length=3)
    affected_work_ids: tuple[UUID, ...] = Field(min_length=1)
    affected_branch: NonEmptyText
    basis: AnalysisBasis

    @model_validator(mode="after")
    def choices_and_work_are_unique(self) -> RequiredClarificationDraft:
        if len(self.choices) != len(set(self.choices)):
            raise ValueError("duplicate clarification choices")
        if len(self.affected_work_ids) != len(set(self.affected_work_ids)):
            raise ValueError("duplicate clarification affected_work_ids")
        return self


class SufficiencyRecommendation(ResultModel):
    """Advisory evidence sufficiency; it is not a pause or finish lifecycle."""

    currently_enough: bool
    reason: NonEmptyText
    remaining_gap_reasons: tuple[GapReason, ...] = ()
    continuing_benefit: NonEmptyText
    basis: AnalysisBasis

    @model_validator(mode="after")
    def gaps_match_recommendation(self) -> SufficiencyRecommendation:
        if not self.currently_enough and not self.remaining_gap_reasons:
            raise ValueError("insufficient result requires at least one concrete gap")
        if len(self.remaining_gap_reasons) != len(set(self.remaining_gap_reasons)):
            raise ValueError("duplicate remaining sufficiency gap reasons")
        return self


class CandidatePublication(ResultModel):
    """A final reference to one already-persisted candidate revision."""

    candidate_revision: int = Field(ge=1)
    revision_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_handles: tuple[ActionHandle, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def action_handles_are_unique(self) -> CandidatePublication:
        if len(self.action_handles) != len(set(self.action_handles)):
            raise ValueError("duplicate candidate publication action handle")
        return self


class ConsultantResult(ResultModel):
    """One coherent result owned by the single professional consultant."""

    visible_reply: NonEmptyText
    reply_basis: AnalysisBasis
    used_skill_ids: tuple[SkillId, ...] = Field(min_length=1)
    understanding_changes: tuple[UnderstandingChange, ...] = ()
    attention_changes: tuple[AttentionChange, ...] = ()
    gaps: tuple[VisibleGap, ...] = ()
    candidate_publication: CandidatePublication | None = None
    next_question: NextQuestion | None = None
    required_clarification: RequiredClarificationDraft | None = None
    sufficiency: SufficiencyRecommendation

    @model_validator(mode="after")
    def every_claim_uses_a_declared_skill(self) -> ConsultantResult:
        if len(self.used_skill_ids) != len(set(self.used_skill_ids)):
            raise ValueError("duplicate used_skill_ids")
        used = set(self.used_skill_ids)
        for basis in self.analysis_bases():
            if not set(basis.skill_ids) <= used:
                raise ValueError("semantic claim depends on an undeclared used Skill")
        if sum(item.make_current for item in self.attention_changes) > 1:
            raise ValueError("one consultant result can select only one current work item")
        if self.next_question is not None and self.required_clarification is not None:
            raise ValueError(
                "required clarification replaces the ordinary next question"
            )
        return self

    def analysis_bases(self) -> tuple[AnalysisBasis, ...]:
        values: list[AnalysisBasis] = [
            self.reply_basis,
            *(item.basis for item in self.understanding_changes),
            *(item.basis for item in self.attention_changes),
            *(item.basis for item in self.gaps),
            self.sufficiency.basis,
        ]
        if self.next_question is not None:
            values.append(self.next_question.basis)
        if self.required_clarification is not None:
            values.append(self.required_clarification.basis)
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
            ((self.sufficiency.continuing_benefit, self.sufficiency.basis)),
        ]
        if self.next_question is not None:
            values.extend(
                (
                    (self.next_question.text, self.next_question.basis),
                    (self.next_question.reason, self.next_question.basis),
                )
            )
        if self.required_clarification is not None:
            values.extend(
                (
                    (
                        self.required_clarification.reason,
                        self.required_clarification.basis,
                    ),
                    (
                        self.required_clarification.current_understanding,
                        self.required_clarification.basis,
                    ),
                    (
                        self.required_clarification.question,
                        self.required_clarification.basis,
                    ),
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
