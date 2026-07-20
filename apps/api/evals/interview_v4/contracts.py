"""Versioned, vendor-neutral contracts for C0/C1 interview evaluation.

Pydantic is the executable validator.  ``write_schemas.py`` publishes the same
contracts as portable JSON Schema so cases and artifacts are not tied to Python
or a provider dashboard.
"""
from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.interview.eval_capture import CAPTURE_SCHEMA_MODELS


NonEmpty = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _relative_file(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.endswith("/"):
        raise ValueError("file reference must be a relative file path without '..'")
    return value


class Split(str, Enum):
    development = "development"
    validation = "validation"
    held_out = "held_out"


class SourceType(str, Enum):
    real_incident = "real_incident"
    real_success = "real_success"
    constructed_edge = "constructed_edge"
    migrated_provisional = "migrated_provisional"


class PrivacyStatus(str, Enum):
    synthetic = "synthetic"
    deidentified = "deidentified"
    redaction_pending_review = "redaction_pending_review"


class AnnotationStatus(str, Enum):
    draft = "draft"
    maintainer_checked = "maintainer_checked"
    domain_reviewed = "domain_reviewed"
    adjudicated = "adjudicated"
    disputed = "disputed"


class PrivacyMetadata(StrictModel):
    status: PrivacyStatus
    version: NonEmpty
    approved_use: Literal["architecture_eval"]
    raw_source_in_repo: Literal[False] = False
    residual_scan_passed: bool = False
    manual_review_required: bool = True


class InitialFixtures(StrictModel):
    document_fixture: NonEmpty
    session_state_fixture: NonEmpty
    reference_snapshot: NonEmpty
    review_events_fixture: NonEmpty

    _files_are_relative = field_validator(
        "document_fixture",
        "session_state_fixture",
        "reference_snapshot",
        "review_events_fixture",
    )(_relative_file)


class AnnotationMetadata(StrictModel):
    status: AnnotationStatus
    annotator_roles: list[NonEmpty] = Field(default_factory=list)
    guideline_version: NonEmpty
    adjudication_notes: NonEmpty

    _notes_are_relative = field_validator("adjudication_notes")(_relative_file)


class EpisodeBoundary(StrictModel):
    opened_employee_seq: int = Field(ge=1)
    closed_employee_seq: int = Field(ge=1)
    target: NonEmpty
    reason: NonEmpty = "fixture"

    @model_validator(mode="after")
    def close_not_before_open(self) -> "EpisodeBoundary":
        if self.closed_employee_seq < self.opened_employee_seq:
            raise ValueError("closed_employee_seq must be >= opened_employee_seq")
        return self


class ReplayConfig(StrictModel):
    ready: bool = False
    episode_boundaries: list[EpisodeBoundary] = Field(default_factory=list)
    limitations: list[NonEmpty] = Field(default_factory=list)


class EvalCaseManifest(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": "https://caliburn.local/schemas/interview-eval-case.v0.1.json",
            "title": "Caliburn interview evaluation case v0.1",
        },
    )

    schema_version: Literal["interview_eval_case.v0.1"]
    case_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")]
    split: Split
    source_type: SourceType
    locale: NonEmpty = "zh-TW"
    role_family: NonEmpty
    risk_tags: list[NonEmpty] = Field(min_length=1)
    privacy: PrivacyMetadata
    initial: InitialFixtures
    transcript: NonEmpty
    gold: NonEmpty
    source_audit: str | None = None
    annotation: AnnotationMetadata
    replay: ReplayConfig = Field(default_factory=ReplayConfig)
    applicable_graders: list[NonEmpty] = Field(min_length=1)

    _files_are_relative = field_validator("transcript", "gold", "source_audit")(
        lambda value: _relative_file(value) if value is not None else value
    )


class TranscriptTurn(StrictModel):
    seq: int = Field(ge=1)
    role: Literal["consultant", "employee"]
    text: NonEmpty


class GoldSource(StrictModel):
    turn_seq: int = Field(ge=1)
    quote: NonEmpty


class GoldEvidence(StrictModel):
    label_id: NonEmpty
    kind: NonEmpty
    claim: NonEmpty
    subject: Literal["employee", "team", "other", "unclear"] = "employee"
    polarity: Literal["affirmed", "denied", "uncertain", "corrected"] = "affirmed"
    time_scope: Literal["current", "past", "future", "hypothetical", "unclear"] = "current"
    typicality: Literal[
        "usual", "recurring", "one_off", "exception", "example_only", "unclear"
    ] = "unclear"
    qualifies_label_id: str | None = None
    source: GoldSource
    requirement: Literal["required", "optional", "forbidden"]
    notes: str = ""


class GoldInference(StrictModel):
    label_id: NonEmpty
    kind: NonEmpty
    semantic_claim: NonEmpty
    supported_by: list[NonEmpty] = Field(min_length=1)
    allowed_status: list[
        Literal["candidate", "needs_confirmation", "corroborated", "confirmed"]
    ] = Field(min_length=1)
    must_not_add: list[NonEmpty] = Field(default_factory=list)
    alternatives: list[NonEmpty] = Field(default_factory=list)
    notes: str = ""


class ProjectionClaim(StrictModel):
    label_id: NonEmpty
    kind: NonEmpty
    semantic_claim: NonEmpty
    supported_by: list[NonEmpty] = Field(default_factory=list)
    target_hint: str | None = None
    notes: str = ""


class GoldStateExpectation(StrictModel):
    expectation_id: NonEmpty
    assertion: NonEmpty
    severity: Literal["critical", "major", "minor", "diagnostic"]
    notes: str = ""


class GoldContract(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": "https://caliburn.local/schemas/interview-eval-gold.v0.1.json",
            "title": "Caliburn interview evaluation gold v0.1",
        },
    )

    schema_version: Literal["interview_eval_gold.v0.1"]
    case_id: NonEmpty
    expected_no_projection: bool = False
    required_evidence: list[GoldEvidence] = Field(default_factory=list)
    optional_evidence: list[GoldEvidence] = Field(default_factory=list)
    forbidden_evidence: list[GoldEvidence] = Field(default_factory=list)
    acceptable_inferences: list[GoldInference] = Field(default_factory=list)
    inferences_requiring_confirmation: list[GoldInference] = Field(default_factory=list)
    forbidden_inferences: list[GoldInference] = Field(default_factory=list)
    required_projection_claims: list[ProjectionClaim] = Field(default_factory=list)
    acceptable_projection_variants: list[ProjectionClaim] = Field(default_factory=list)
    forbidden_projection_claims: list[ProjectionClaim] = Field(default_factory=list)
    unresolved_gaps: list[NonEmpty] = Field(default_factory=list)
    state_expectations: list[GoldStateExpectation] = Field(default_factory=list)

    @model_validator(mode="after")
    def label_ids_are_unique(self) -> "GoldContract":
        groups = (
            self.required_evidence,
            self.optional_evidence,
            self.forbidden_evidence,
            self.acceptable_inferences,
            self.inferences_requiring_confirmation,
            self.forbidden_inferences,
            self.required_projection_claims,
            self.acceptable_projection_variants,
            self.forbidden_projection_claims,
            self.state_expectations,
        )
        ids = [item.label_id if hasattr(item, "label_id") else item.expectation_id
               for group in groups for item in group]
        if len(ids) != len(set(ids)):
            raise ValueError("all gold label/expectation ids must be unique within a case")
        return self


class ModelCallArtifact(StrictModel):
    role: NonEmpty
    provider: NonEmpty
    requested_model: NonEmpty
    resolved_model: str | None = None
    temperature: float | None = None
    seed: int | None = None
    prompt_hash: NonEmpty
    tool_schema_hash: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    raw_response_artifact: NonEmpty
    parsed_output_artifact: str | None = None
    outcome: Literal["success", "timeout", "parse_failure", "provider_failure", "fallback"]

    _artifact_files_are_relative = field_validator(
        "raw_response_artifact", "parsed_output_artifact"
    )(lambda value: _relative_file(value) if value is not None else value)


class TrajectoryStep(StrictModel):
    turn_seq: int = Field(ge=1)
    state_before: NonEmpty
    candidate_output: NonEmpty
    verifier_result: NonEmpty
    state_delta: NonEmpty
    projection_delta: NonEmpty

    _artifact_files_are_relative = field_validator(
        "state_before",
        "candidate_output",
        "verifier_result",
        "state_delta",
        "projection_delta",
    )(_relative_file)


class GraderResult(StrictModel):
    grader: NonEmpty
    passed: bool | None
    applicable: bool = True
    score: float | None = None
    severity: Literal["critical", "major", "minor", "diagnostic"] | None = None
    reason: NonEmpty
    details: list[dict[str, Any]] = Field(default_factory=list)


class FinalArtifactRefs(StrictModel):
    state: NonEmpty
    document: NonEmpty
    grader_results: NonEmpty

    _artifact_files_are_relative = field_validator(
        "state", "document", "grader_results"
    )(_relative_file)


class EvalRunArtifact(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$id": "https://caliburn.local/schemas/interview-eval-run.v0.1.json",
            "title": "Caliburn interview evaluation run v0.1",
        },
    )

    schema_version: Literal["interview_eval_run.v0.1"]
    run_id: NonEmpty
    case_id: NonEmpty
    case_content_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    candidate: Literal["C0", "C0R", "C1"]
    trial_index: int = Field(ge=1)
    git_sha: NonEmpty
    dirty_worktree: bool
    started_at: NonEmpty
    runner_version: NonEmpty
    model_calls: list[ModelCallArtifact] = Field(default_factory=list)
    trajectory: list[TrajectoryStep] = Field(default_factory=list)
    final: FinalArtifactRefs
    limitations: list[NonEmpty] = Field(default_factory=list)


SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "case.schema.json": EvalCaseManifest,
    "gold.schema.json": GoldContract,
    "run.schema.json": EvalRunArtifact,
    **CAPTURE_SCHEMA_MODELS,
}
