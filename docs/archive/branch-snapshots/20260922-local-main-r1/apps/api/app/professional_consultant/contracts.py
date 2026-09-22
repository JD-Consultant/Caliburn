"""Immutable R1 Task Discovery domain and operation values.

JSON is validated with ``model_validate_json``. Internal Python callers must
provide exact types; coercion is intentionally disabled.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


class ConsultantContract(BaseModel):
    """Closed, recursively immutable-by-convention R1 value object."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value cannot be blank")
    return value


Identifier = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]
SourceText = Annotated[
    str, Field(min_length=1, max_length=20_000), AfterValidator(_not_blank)
]
QuoteText = Annotated[
    str, Field(min_length=1, max_length=4_000), AfterValidator(_not_blank)
]


class EmployeeMessage(ConsultantContract):
    message_id: Identifier
    text: SourceText


class SourceSpan(ConsultantContract):
    """Unicode code-point half-open source range ``[start, end)``."""

    message_id: Identifier
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: QuoteText

    @model_validator(mode="after")
    def end_follows_start(self) -> "SourceSpan":
        if self.end <= self.start:
            raise ValueError("source span end must be greater than start")
        return self


ShortText = Annotated[
    str, Field(min_length=1, max_length=512), AfterValidator(_not_blank)
]
StatementText = Annotated[
    str, Field(min_length=1, max_length=1_024), AfterValidator(_not_blank)
]
QuestionText = Annotated[
    str, Field(min_length=1, max_length=1_024), AfterValidator(_not_blank)
]
Anchors = Annotated[tuple[SourceSpan, ...], Field(min_length=1)]
Identifiers = tuple[Identifier, ...]


class TranscriptRole(StrEnum):
    CONSULTANT = "consultant"
    EMPLOYEE = "employee"


class OwnershipScope(StrEnum):
    EMPLOYEE_RESPONSIBLE = "employee_responsible"
    SHARED_RESPONSIBILITY = "shared_responsibility"
    FORMAL_SUPPORT = "formal_support"
    OTHER_RESPONSIBLE = "other_responsible"
    UNKNOWN = "unknown"


class TimeScope(StrEnum):
    CURRENT = "current"
    PAST = "past"
    FUTURE_HYPOTHETICAL = "future_hypothetical"
    UNKNOWN = "unknown"


class Typicality(StrEnum):
    ROUTINE = "routine"
    PERIODIC = "periodic"
    FORMAL_LOW_FREQUENCY = "formal_low_frequency"
    ONE_OFF = "one_off"
    EXCEPTIONAL = "exceptional"
    UNKNOWN = "unknown"


class Polarity(StrEnum):
    AFFIRMED = "affirmed"
    DENIED = "denied"


class ClaimCertainty(StrEnum):
    EXPLICIT = "explicit"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ClaimKind(StrEnum):
    WORK_ACTIVITY = "work_activity"
    OUTCOME = "outcome"
    TOOL_OR_METHOD = "tool_or_method"
    STEP = "step"
    CONDITION = "condition"
    FREQUENCY = "frequency"
    OWNERSHIP = "ownership"
    CORRECTION = "correction"
    OTHER = "other"


class BoundaryStatus(StrEnum):
    MET = "met"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"


class ReconciliationKind(StrEnum):
    ADD = "add"
    EDIT = "edit"
    MERGE = "merge"
    SPLIT = "split"
    NO_OP = "no_op"
    CLARIFY = "clarify"


class ConsultantAction(StrEnum):
    BROADEN = "broaden"
    DEEPEN_STORY = "deepen_story"
    CLARIFY_BOUNDARY = "clarify_boundary"


class TranscriptTurn(ConsultantContract):
    turn_id: Identifier
    role: TranscriptRole
    text: SourceText


class QuestionContext(ConsultantContract):
    question_id: Identifier
    question_text: QuestionText
    target_claim_ids: Identifiers
    target_candidate_ids: Identifiers


class SourceClaim(ConsultantContract):
    claim_id: Identifier
    kind: ClaimKind
    statement: StatementText
    ownership: OwnershipScope
    time_scope: TimeScope
    typicality: Typicality
    polarity: Polarity
    certainty: ClaimCertainty
    action: ShortText | None
    object: ShortText | None
    recipient: ShortText | None
    outcome: ShortText | None
    tool_or_method: ShortText | None
    condition: ShortText | None
    correction_target_claim_id: Identifier | None
    anchors: Anchors

    @model_validator(mode="after")
    def correction_shape_is_explicit(self) -> "SourceClaim":
        if self.kind is ClaimKind.CORRECTION:
            if self.correction_target_claim_id is None:
                raise ValueError("correction claim requires a target claim")
        elif self.correction_target_claim_id is not None:
            raise ValueError("only correction claims may carry a correction target")
        if len(set(self.anchors)) != len(self.anchors):
            raise ValueError("claim anchors must be unique")
        return self


class UnmappedSignal(ConsultantContract):
    signal_id: Identifier
    summary: StatementText
    significance: ShortText
    missing_information: ShortText
    anchors: Anchors


class Story(ConsultantContract):
    story_id: Identifier
    summary: StatementText
    claim_ids: Annotated[Identifiers, Field(min_length=1)]
    outcome: ShortText | None
    gaps: tuple[ShortText, ...]


class WorkUnit(ConsultantContract):
    work_unit_id: Identifier
    statement: StatementText
    claim_ids: Annotated[Identifiers, Field(min_length=1)]
    story_ids: Identifiers
    outcome: ShortText | None
    support_claim_ids: Annotated[Identifiers, Field(min_length=1)]
    counter_claim_ids: Identifiers
    unresolved_boundary: tuple[ShortText, ...]


class TaskBoundaryAssessment(ConsultantContract):
    meaningful_outcome: BoundaryStatus
    role_responsibility: BoundaryStatus
    assignability: BoundaryStatus
    checkability: BoundaryStatus
    stability: BoundaryStatus
    boundary_coherence: BoundaryStatus


class TaskCandidate(ConsultantContract):
    candidate_id: Identifier
    statement: StatementText
    work_unit_ids: Annotated[Identifiers, Field(min_length=1)]
    support_claim_ids: Annotated[Identifiers, Field(min_length=1)]
    counter_claim_ids: Identifiers
    boundary: TaskBoundaryAssessment
    limitations: tuple[ShortText, ...]


class ReconciliationDecision(ConsultantContract):
    decision_id: Identifier
    kind: ReconciliationKind
    candidate_id: Identifier | None
    existing_candidate_ids: Identifiers
    work_unit_ids: Identifiers
    rationale: ShortText
    missing_information: ShortText | None

    @model_validator(mode="after")
    def fields_match_decision_kind(self) -> "ReconciliationDecision":
        if self.kind is ReconciliationKind.ADD:
            if self.candidate_id is None or self.existing_candidate_ids:
                raise ValueError("add requires a new candidate and no existing candidate")
        elif self.kind is ReconciliationKind.EDIT:
            if self.candidate_id is None or len(self.existing_candidate_ids) != 1:
                raise ValueError("edit requires one existing and one resulting candidate")
        elif self.kind is ReconciliationKind.MERGE:
            if self.candidate_id is None or len(self.existing_candidate_ids) < 2:
                raise ValueError("merge requires at least two existing candidates")
        elif self.kind is ReconciliationKind.SPLIT:
            if self.candidate_id is None or len(self.existing_candidate_ids) != 1:
                raise ValueError("split requires one existing and a resulting candidate")
        elif self.kind is ReconciliationKind.NO_OP and self.candidate_id is not None:
            raise ValueError("no-op cannot point at a resulting candidate")
        if self.kind is ReconciliationKind.CLARIFY:
            if self.missing_information is None:
                raise ValueError("clarify requires missing information")
        elif self.missing_information is not None:
            raise ValueError("only clarify may carry missing information")
        return self


class NextQuestion(ConsultantContract):
    action: ConsultantAction
    text: QuestionText
    target_gap: ShortText
    claim_ids: Identifiers


class TurnUnderstandInput(ConsultantContract):
    schema_version: Literal["turn_understand_input.v1"]
    employee_message: EmployeeMessage
    question_context: QuestionContext | None
    recent_transcript: tuple[TranscriptTurn, ...]
    prior_claims: tuple[SourceClaim, ...]
    omitted_relevant_context: bool


class TurnUnderstandOutput(ConsultantContract):
    schema_version: Literal["turn_understand_output.v1"]
    claims: tuple[SourceClaim, ...]
    unmapped_signals: tuple[UnmappedSignal, ...]


class WorkReconcileDecideInput(ConsultantContract):
    schema_version: Literal["work_reconcile_decide_input.v1"]
    employee_message: EmployeeMessage
    understanding: TurnUnderstandOutput
    prior_claims: tuple[SourceClaim, ...]
    prior_stories: tuple[Story, ...]
    prior_work_units: tuple[WorkUnit, ...]
    existing_task_candidates: tuple[TaskCandidate, ...]
    recent_questions: tuple[QuestionText, ...]
    omitted_relevant_context: bool


class WorkReconcileDecideOutput(ConsultantContract):
    schema_version: Literal["work_reconcile_decide_output.v1"]
    stories: tuple[Story, ...]
    work_units: tuple[WorkUnit, ...]
    decisions: tuple[ReconciliationDecision, ...]
    task_candidates: tuple[TaskCandidate, ...]
    next_question: NextQuestion


class TaskDiscoveryInput(ConsultantContract):
    schema_version: Literal["task_discovery_input.v1"]
    employee_message: EmployeeMessage
    question_context: QuestionContext | None
    recent_transcript: tuple[TranscriptTurn, ...]
    prior_claims: tuple[SourceClaim, ...]
    prior_stories: tuple[Story, ...]
    prior_work_units: tuple[WorkUnit, ...]
    existing_task_candidates: tuple[TaskCandidate, ...]
    recent_questions: tuple[QuestionText, ...]
    omitted_relevant_context: bool


class TaskDiscoveryOutput(ConsultantContract):
    schema_version: Literal["task_discovery_output.v1"]
    claims: tuple[SourceClaim, ...]
    unmapped_signals: tuple[UnmappedSignal, ...]
    stories: tuple[Story, ...]
    work_units: tuple[WorkUnit, ...]
    decisions: tuple[ReconciliationDecision, ...]
    task_candidates: tuple[TaskCandidate, ...]
    next_question: NextQuestion
