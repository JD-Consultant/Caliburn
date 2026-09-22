"""Typed R1 fixture metadata kept outside the production runtime."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.professional_consultant.contracts import (
    Identifier,
    QuestionContext,
    ShortText,
    SourceClaim,
    Story,
    TaskCandidate,
    TaskDiscoveryInput,
    WorkUnit,
)


class R1EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SourceType(StrEnum):
    CONSTRUCTED_EDGE = "constructed_edge"
    HUMAN_MANUAL_TEST = "human_manual_test"
    REAL_EMPLOYEE_INTERVIEW = "real_employee_interview"


class CaseFiles(R1EvalModel):
    transcript: Literal["transcript.jsonl"]
    expectations: Literal["expectations.json"]
    adjudication: Literal["adjudication.md"]


class R1CaseDocument(R1EvalModel):
    schema_version: Literal["r1_task_discovery_case.v1"]
    case_id: Identifier
    case_family_id: Identifier
    source_type: SourceType
    source_session_ref: Identifier | None
    title: ShortText
    capability: ShortText
    target_message_id: Identifier
    question_context: QuestionContext | None
    prior_claims: tuple[SourceClaim, ...]
    prior_stories: tuple[Story, ...]
    prior_work_units: tuple[WorkUnit, ...]
    existing_task_candidates: tuple[TaskCandidate, ...]
    omitted_relevant_context: bool
    files: CaseFiles


class R1CaseMetadata(R1EvalModel):
    case_id: Identifier
    case_family_id: Identifier
    source_type: SourceType
    source_session_ref: Identifier | None
    title: ShortText
    capability: ShortText


class R1RuntimeCase(R1EvalModel):
    metadata: R1CaseMetadata
    runtime_input: TaskDiscoveryInput


class ForbiddenPromotion(R1EvalModel):
    category: Literal["tool", "step", "past", "other_person", "one_off"]
    statement: ShortText


class R1CaseExpectations(R1EvalModel):
    schema_version: Literal["r1_task_discovery_expectations.v1"]
    case_id: Identifier
    minimum_task_candidates: int = Field(ge=0, le=8)
    maximum_task_candidates: int = Field(ge=0, le=8)
    permitted_decisions: tuple[
        Literal["add", "edit", "merge", "split", "no_op", "clarify"], ...
    ]
    expected_next_action: Literal["broaden", "deepen_story", "clarify_boundary"]
    forbidden_promotions: tuple[ForbiddenPromotion, ...]
    acceptable_task_examples: tuple[ShortText, ...]
    required_qualifier_notes: tuple[ShortText, ...]
    question_intent: ShortText
    critical_notes: Annotated[tuple[ShortText, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def task_count_range_is_ordered(self) -> "R1CaseExpectations":
        if self.minimum_task_candidates > self.maximum_task_candidates:
            raise ValueError("minimum task count cannot exceed maximum")
        return self


class R1EvaluationCase(R1EvalModel):
    metadata: R1CaseMetadata
    expectations: R1CaseExpectations
    adjudication_markdown: str


class RubricDimension(R1EvalModel):
    code: Identifier
    title: ShortText
    description: ShortText
    score_zero: ShortText
    score_one: ShortText
    score_two: ShortText


class RubricRule(R1EvalModel):
    code: Identifier
    title: ShortText
    description: ShortText


class MaterialImprovementPolicy(R1EvalModel):
    fast_screen_case_count: Literal[8]
    normalized_mean_delta: float = Field(ge=0, le=1)
    family_net_win_rate: float = Field(ge=0, le=1)
    critical_regressions_allowed: Literal[0]
    critical_trial_count: Literal[3]


class JobAnalysisQualityRubric(R1EvalModel):
    schema_version: Literal["job_analysis_quality_rubric.v1"]
    task_definition: ShortText
    task_boundary_dimensions: Annotated[
        tuple[RubricDimension, ...], Field(min_length=1)
    ]
    critical_rules: Annotated[tuple[RubricRule, ...], Field(min_length=1)]
    question_rules: Annotated[tuple[RubricRule, ...], Field(min_length=1)]
    material_improvement: MaterialImprovementPolicy
