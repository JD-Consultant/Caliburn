"""Strict contracts for the V3-5 turn eval harness.

Case/gold/batch/trial/grader/review/report document models per
docs/plans/2026-07-18-interview-vnext-v3-5-turn-eval-harness-plan.md §6/§9/§13
/§14/§15. Runtime inputs and gold are separate documents on purpose: the
runner-facing ``TurnEvalCaseInputs`` type lives in ``loader.py`` and never
carries gold/reference/adjudication fields (§8.2). Production code must not
import this module; evals import ``app`` contracts, never the reverse.
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import AfterValidator, Field, field_validator, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.evidence import (
    EvidenceKind,
    EvidenceSubject,
    FrequencyUnit,
    Importance,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.identifiers import (
    Locale,
    NonEmptyText,
    SemVer,
    Sha256,
    StableName,
    UtcDatetime,
)
from app.interview_vnext.domain.transcript import TranscriptRole
from app.interview_vnext.llm.result import (
    FailureKind,
    FinishReason,
    ModelOutcome,
    TokenUsage,
)
from app.interview_vnext.llm.turn_interpret import (
    EpisodeSignal,
    EvidenceQualifiersProposal,
    InsufficiencyReason,
    TurnInterpretOutput,
    UserSignal,
)


# ── Shared scalars ───────────────────────────────────────────────────────────

CaseId = Annotated[
    str, Field(pattern=r"^TI-[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)
]
# turn/episode/evidence logical keys inside one case (§6.2/§6.3)
CaseKey = Annotated[
    str, Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", max_length=64)
]
GoldId = Annotated[
    str, Field(pattern=r"^[gf]-[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)
]
GitSha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]


def _canonical_object(value: str) -> str:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("payload must encode a JSON object")
    if value != canonical_json(parsed):
        raise ValueError("payload must use canonical JSON")
    return value


CanonicalJsonObject = Annotated[str, AfterValidator(_canonical_object)]


# ── Enums ────────────────────────────────────────────────────────────────────


class CaseSplit(StrEnum):
    DEVELOPMENT = "development"
    CHALLENGE = "challenge"


class DifficultyTag(StrEnum):
    TYPICAL = "typical"
    EDGE = "edge"
    ADVERSARIAL = "adversarial"


class CaseSourceType(StrEnum):
    CONSTRUCTED_EDGE = "constructed_edge"
    REAL_INCIDENT = "real_incident"
    REAL_SUCCESS = "real_success"


class AnnotationStatus(StrEnum):
    DRAFT = "draft"
    SELF_CHECKED = "self_checked"
    ADJUDICATED_BY_MAINTAINER = "adjudicated_by_maintainer"
    DOMAIN_REVIEWED = "domain_reviewed"
    DISPUTED = "disputed"


class GoldRequirement(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class GoldLabelStatus(StrEnum):
    """§6.5:unknown/disputed/needs_sme 必須可表示;非 adjudicated 不進 gate 分母。"""

    ADJUDICATED = "adjudicated"
    UNKNOWN = "unknown"
    DISPUTED = "disputed"
    NEEDS_SME = "needs_sme"


class FailureSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    DIAGNOSTIC = "diagnostic"


class ExpectedCommit(StrEnum):
    EVIDENCE = "evidence"
    NO_OP = "no_op"


class ExecutionMode(StrEnum):
    """Provider path of a batch: scripted reference, mocked transport, or live."""

    REFERENCE = "reference"
    MOCKED = "mocked"
    LIVE = "live"


class TrialDisposition(StrEnum):
    QUALITY_SCORED = "quality_scored"
    INFRASTRUCTURE_INVALID = "infrastructure_invalid"
    HARNESS_INVALID = "harness_invalid"
    CANCELLED = "cancelled"


class GraderStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"
    NOT_APPLICABLE = "not_applicable"
    INVALID = "invalid"


class ReviewDecisionLabel(StrEnum):
    EQUIVALENT = "equivalent"
    NARROWER_BUT_VALID = "narrower_but_valid"
    BROADER_UNSUPPORTED = "broader_unsupported"
    DIFFERENT = "different"
    UNKNOWN = "unknown"
    NEEDS_SME = "needs_sme"


class FailureAttribution(StrEnum):
    CONTEXT = "context"
    PROMPT = "prompt"
    SCHEMA = "schema"
    MODEL = "model"
    PROVIDER = "provider"
    VERIFIER = "verifier"
    REDUCER = "reducer"
    GOLD = "gold"
    RUNNER = "runner"
    INFRASTRUCTURE = "infrastructure"
    REVIEW = "review"


class BatchDecision(StrEnum):
    HARNESS_INVALID = "HARNESS_INVALID"
    BATCH_INCOMPLETE = "BATCH_INCOMPLETE"
    REVIEW_INCOMPLETE = "REVIEW_INCOMPLETE"
    TURN_GATE_FAIL = "TURN_GATE_FAIL"
    TURN_GATE_PASS_ENGINEERING = "TURN_GATE_PASS_ENGINEERING"
    TURN_GATE_PASS_DOMAIN_REVIEWED = "TURN_GATE_PASS_DOMAIN_REVIEWED"


class CaseDecision(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW_INCOMPLETE = "review_incomplete"


# ── turn_eval_case.v1(§6.1)─────────────────────────────────────────────────


class TurnEvalCaseFiles(DomainModel):
    """Fixed per-case artifact filenames; no symlink/abs-path/extra file (§6)."""

    transcript: Literal["transcript.jsonl"] = "transcript.jsonl"
    initial_state: Literal["initial_state.json"] = "initial_state.json"
    reference_snapshot: Literal["reference_snapshot.json"] = "reference_snapshot.json"
    gold: Literal["gold.json"] = "gold.json"
    reference_output: Literal["reference_output.json"] = "reference_output.json"
    adjudication: Literal["adjudication.md"] = "adjudication.md"


class TurnEvalCase(DomainModel):
    schema_version: Literal["turn_eval_case.v1"]
    case_id: CaseId
    split: CaseSplit
    locale: Locale
    task_type: Literal["turn_interpret"]
    failure_purpose: Annotated[
        str, Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$", max_length=64)
    ]
    difficulty_tags: tuple[DifficultyTag, ...] = Field(min_length=1)
    target_turn_key: CaseKey
    source_type: CaseSourceType
    annotation_status: AnnotationStatus
    pilot_only: bool
    files: TurnEvalCaseFiles
    applicable_graders: tuple[StableName, ...] = Field(min_length=1)

    @field_validator("difficulty_tags")
    @classmethod
    def tags_are_canonical(
        cls, value: tuple[DifficultyTag, ...]
    ) -> tuple[DifficultyTag, ...]:
        if len(value) != len(set(value)):
            raise ValueError("difficulty_tags must be unique")
        if tuple(sorted(value, key=lambda tag: tag.value)) != value:
            raise ValueError("difficulty_tags must use canonical sort order")
        return value

    @field_validator("applicable_graders")
    @classmethod
    def graders_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("applicable_graders must be unique")
        return value

    @model_validator(mode="after")
    def synthetic_cases_are_pilot_only(self) -> "TurnEvalCase":
        if self.source_type == CaseSourceType.CONSTRUCTED_EDGE and not self.pilot_only:
            raise ValueError("constructed_edge cases must declare pilot_only=true")
        return self


# ── turn_eval_transcript_turn.v1(§6.2)──────────────────────────────────────


class TurnEvalTranscriptTurn(DomainModel):
    """One transcript line; raw text preserved, no trim/NFKC/whitespace merge."""

    schema_version: Literal["turn_eval_transcript_turn.v1"]
    turn_key: CaseKey
    sequence: int = Field(ge=1)
    role: TranscriptRole
    locale: Locale
    text: NonEmptyText
    occurred_offset_seconds: int = Field(ge=0)


# ── turn_eval_initial_fixture.v1(§6.3)──────────────────────────────────────


class TurnEvalOpenEpisodeFixture(DomainModel):
    episode_key: CaseKey
    target: NonEmptyText
    opened_turn_key: CaseKey


class TurnEvalPriorEvidenceFixture(DomainModel):
    """Declarative prior evidence rebuilt through ApplyEvidenceCommand (§6.3)."""

    evidence_key: CaseKey
    source_turn_key: CaseKey
    episode_key: CaseKey | None = None
    subject: EvidenceSubject
    kind: EvidenceKind
    claim: NonEmptyText
    quote: NonEmptyText
    quote_occurrence: int = Field(ge=1)
    qualifiers: EvidenceQualifiersProposal


class TurnEvalInitialFixture(DomainModel):
    schema_version: Literal["turn_eval_initial_fixture.v1"]
    session_status_before_replay: Literal["draft"]
    activate_before_transcript: bool
    open_episode: TurnEvalOpenEpisodeFixture | None = None
    prior_evidence: tuple[TurnEvalPriorEvidenceFixture, ...] = ()

    @model_validator(mode="after")
    def fixture_is_replayable(self) -> "TurnEvalInitialFixture":
        # v1 fixture 一律從 draft 啟用;不啟用就 replay transcript 是壞 fixture。
        if not self.activate_before_transcript:
            raise ValueError("v1 fixture must activate the session before replay")
        keys = tuple(item.evidence_key for item in self.prior_evidence)
        if len(keys) != len(set(keys)):
            raise ValueError("prior evidence keys must be unique")
        for item in self.prior_evidence:
            if item.episode_key is not None:
                if self.open_episode is None:
                    raise ValueError(
                        "prior evidence references an episode but none is opened"
                    )
                if item.episode_key != self.open_episode.episode_key:
                    raise ValueError(
                        "prior evidence episode_key must match the opened episode"
                    )
        return self


# ── turn_eval_gold.v1(§6.5)─────────────────────────────────────────────────


class QualifierExact(DomainModel):
    mode: Literal["exact"]
    value: NonEmptyText


class QualifierOneOf(DomainModel):
    mode: Literal["one_of"]
    values: tuple[NonEmptyText, ...] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def values_are_sorted_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("one_of values must be unique and sorted")
        return value


class QualifierNotApplicable(DomainModel):
    mode: Literal["not_applicable"]


QualifierExpectation = Annotated[
    Union[QualifierExact, QualifierOneOf, QualifierNotApplicable],
    Field(discriminator="mode"),
]

_QUALIFIER_VALUE_DOMAINS: dict[str, frozenset[str]] = {
    "time_scope": frozenset(item.value for item in TimeScope),
    "typicality": frozenset(item.value for item in Typicality),
    "polarity": frozenset(item.value for item in Polarity),
    "frequency_unit": frozenset(item.value for item in FrequencyUnit),
    "importance": frozenset(item.value for item in Importance),
    "ownership": frozenset(item.value for item in Ownership),
}


def _expected_values(expectation: object) -> tuple[str, ...]:
    if isinstance(expectation, QualifierExact):
        return (expectation.value,)
    if isinstance(expectation, QualifierOneOf):
        return expectation.values
    return ()


class GoldQualifierExpectations(DomainModel):
    """Per-field discriminated expectation;三種 shape 互斥,不用 null 猜語意。"""

    time_scope: QualifierExpectation
    typicality: QualifierExpectation
    polarity: QualifierExpectation
    frequency_unit: QualifierExpectation
    frequency_value: QualifierExpectation
    importance: QualifierExpectation
    ownership: QualifierExpectation

    @model_validator(mode="after")
    def values_belong_to_field_domains(self) -> "GoldQualifierExpectations":
        for field_name, domain in _QUALIFIER_VALUE_DOMAINS.items():
            invalid = [
                value
                for value in _expected_values(getattr(self, field_name))
                if value not in domain
            ]
            if invalid:
                raise ValueError(
                    f"{field_name} expectation has values outside its enum: {invalid}"
                )
        for value in _expected_values(self.frequency_value):
            try:
                parsed = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError(
                    "frequency_value expectation must be a decimal string"
                ) from exc
            if not parsed.is_finite() or parsed < 0:
                raise ValueError(
                    "frequency_value expectation must be a finite non-negative decimal"
                )
        return self


class GoldSourceAnchor(DomainModel):
    turn_key: CaseKey
    quote: NonEmptyText
    occurrence: int = Field(ge=1)


class TurnEvalGoldObservation(DomainModel):
    gold_id: GoldId
    requirement: GoldRequirement
    label_status: GoldLabelStatus = GoldLabelStatus.ADJUDICATED
    semantic_target: NonEmptyText
    allowed_subjects: tuple[EvidenceSubject, ...] = Field(min_length=1)
    allowed_kinds: tuple[EvidenceKind, ...] = Field(min_length=1)
    source_anchors: tuple[GoldSourceAnchor, ...] = Field(min_length=1)
    qualifiers: GoldQualifierExpectations
    correction_target_evidence_keys: tuple[CaseKey, ...] = ()
    severity_if_missed: FailureSeverity
    rationale: NonEmptyText

    @field_validator("allowed_subjects", "allowed_kinds")
    @classmethod
    def enum_lists_are_unique(cls, value: tuple) -> tuple:
        if len(value) != len(set(value)):
            raise ValueError("allowed subject/kind lists must be unique")
        return value

    @model_validator(mode="after")
    def observation_is_coherent(self) -> "TurnEvalGoldObservation":
        if not self.gold_id.startswith("g-"):
            raise ValueError("gold observation IDs must use the 'g-' prefix")
        if self.severity_if_missed == FailureSeverity.DIAGNOSTIC:
            raise ValueError("severity_if_missed cannot be diagnostic")
        anchors = tuple(
            (anchor.turn_key, anchor.quote, anchor.occurrence)
            for anchor in self.source_anchors
        )
        if len(anchors) != len(set(anchors)):
            raise ValueError("source anchors must be unique")
        targets = self.correction_target_evidence_keys
        if len(targets) != len(set(targets)):
            raise ValueError("correction target keys must be unique")
        if targets and EvidenceKind.CORRECTION not in self.allowed_kinds:
            raise ValueError(
                "correction targets require correction in allowed_kinds"
            )
        return self


class TurnEvalGoldForbiddenClaim(DomainModel):
    gold_id: GoldId
    description: NonEmptyText
    severity: FailureSeverity

    @model_validator(mode="after")
    def claim_is_coherent(self) -> "TurnEvalGoldForbiddenClaim":
        if not self.gold_id.startswith("f-"):
            raise ValueError("forbidden claim IDs must use the 'f-' prefix")
        if self.severity not in {FailureSeverity.CRITICAL, FailureSeverity.MAJOR}:
            raise ValueError("forbidden claim severity must be critical or major")
        return self


class GoldStateExpectation(DomainModel):
    state_hash_changed: bool
    prior_evidence_superseded_keys: tuple[CaseKey, ...] = ()
    forbidden_superseded_keys: tuple[CaseKey, ...] = ()

    @model_validator(mode="after")
    def key_sets_are_coherent(self) -> "GoldStateExpectation":
        superseded = self.prior_evidence_superseded_keys
        forbidden = self.forbidden_superseded_keys
        if len(superseded) != len(set(superseded)):
            raise ValueError("superseded keys must be unique")
        if len(forbidden) != len(set(forbidden)):
            raise ValueError("forbidden superseded keys must be unique")
        if set(superseded) & set(forbidden):
            raise ValueError("a key cannot be both expected and forbidden to supersede")
        return self


class TurnEvalGold(DomainModel):
    schema_version: Literal["turn_eval_gold.v1"]
    case_id: CaseId
    allowed_user_signals: tuple[UserSignal, ...] = Field(min_length=1)
    allowed_episode_signals: tuple[EpisodeSignal, ...] = Field(min_length=1)
    expected_commit: ExpectedCommit
    observations: tuple[TurnEvalGoldObservation, ...] = ()
    forbidden_claims: tuple[TurnEvalGoldForbiddenClaim, ...] = ()
    required_insufficiencies: tuple[InsufficiencyReason, ...] = ()
    allowed_insufficiencies: tuple[InsufficiencyReason, ...] = ()
    state_expectation: GoldStateExpectation

    @field_validator("allowed_user_signals", "allowed_episode_signals")
    @classmethod
    def signal_lists_are_unique(cls, value: tuple) -> tuple:
        if len(value) != len(set(value)):
            raise ValueError("allowed signal lists must be unique")
        return value

    @model_validator(mode="after")
    def gold_is_coherent(self) -> "TurnEvalGold":
        gold_ids = tuple(item.gold_id for item in self.observations) + tuple(
            item.gold_id for item in self.forbidden_claims
        )
        if len(gold_ids) != len(set(gold_ids)):
            raise ValueError("gold IDs must be unique across observations and claims")
        if len(self.required_insufficiencies) != len(set(self.required_insufficiencies)):
            raise ValueError("required insufficiencies must be unique")
        if len(self.allowed_insufficiencies) != len(set(self.allowed_insufficiencies)):
            raise ValueError("allowed insufficiencies must be unique")
        if set(self.required_insufficiencies) & set(self.allowed_insufficiencies):
            raise ValueError("an insufficiency cannot be both required and allowed")
        required = tuple(
            item
            for item in self.observations
            if item.requirement == GoldRequirement.REQUIRED
        )
        if self.expected_commit == ExpectedCommit.NO_OP:
            if required:
                raise ValueError("no-op gold cannot carry required observations")
            if self.state_expectation.state_hash_changed:
                raise ValueError("no-op gold requires an unchanged state hash")
            if self.state_expectation.prior_evidence_superseded_keys:
                raise ValueError("no-op gold cannot expect superseded evidence")
        else:
            if not required:
                raise ValueError("evidence gold requires at least one required claim")
            if not self.state_expectation.state_hash_changed:
                raise ValueError("evidence gold requires a changed state hash")
        return self


# ── turn_eval_reference_output.v1(§6.6)─────────────────────────────────────


class TurnEvalReferenceOutput(DomainModel):
    """Known-good output with logical correction targets, portable across trials."""

    schema_version: Literal["turn_eval_reference_output.v1"]
    case_id: CaseId
    output: TurnInterpretOutput
    correction_target_bindings: dict[str, tuple[CaseKey, ...]] = {}

    @model_validator(mode="after")
    def bindings_are_the_single_target_source(self) -> "TurnEvalReferenceOutput":
        proposals = {item.proposal_key: item for item in self.output.observations}
        for proposal in self.output.observations:
            if proposal.correction_target_evidence_ids:
                raise ValueError(
                    "reference output must not persist trial-scoped correction UUIDs"
                )
        for proposal_key, targets in self.correction_target_bindings.items():
            proposal = proposals.get(proposal_key)
            if proposal is None:
                raise ValueError(
                    f"binding references unknown proposal key {proposal_key!r}"
                )
            if not targets:
                raise ValueError("correction target binding cannot be empty")
            if len(targets) != len(set(targets)):
                raise ValueError("correction target binding keys must be unique")
            if proposal.kind != EvidenceKind.CORRECTION:
                raise ValueError("only correction proposals may bind targets")
            if proposal.correction_target_unknown:
                raise ValueError(
                    "unknown-target corrections cannot carry a target binding"
                )
        for proposal in self.output.observations:
            if (
                proposal.kind == EvidenceKind.CORRECTION
                and not proposal.correction_target_unknown
                and proposal.proposal_key not in self.correction_target_bindings
            ):
                raise ValueError(
                    "known-target corrections require a logical target binding"
                )
        return self


# ── Suite manifest(§8.1;loader-owned,不進 published schema 清單)─────────


class SuiteManifestEntry(DomainModel):
    case_id: CaseId
    split: CaseSplit
    runtime_input_hash: Sha256
    evaluation_contract_hash: Sha256
    case_content_hash: Sha256


class TurnEvalSuiteManifestDefinition(DomainModel):
    schema_version: Literal["turn_eval_suite_manifest.v1"] = (
        "turn_eval_suite_manifest.v1"
    )
    suite_version: StableName
    cases: tuple[SuiteManifestEntry, ...] = Field(min_length=1)

    @field_validator("cases")
    @classmethod
    def cases_are_ordered_and_unique(
        cls, value: tuple[SuiteManifestEntry, ...]
    ) -> tuple[SuiteManifestEntry, ...]:
        ids = tuple(entry.case_id for entry in value)
        if len(ids) != len(set(ids)):
            raise ValueError("suite manifest case IDs must be unique")
        ordered = tuple(
            sorted(value, key=lambda entry: (entry.split.value, entry.case_id))
        )
        if ordered != value:
            raise ValueError("suite manifest cases must be sorted by (split, case_id)")
        return value


class TurnEvalSuiteManifest(TurnEvalSuiteManifestDefinition):
    suite_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "TurnEvalSuiteManifest":
        definition = TurnEvalSuiteManifestDefinition.model_validate(
            self.model_dump(exclude={"suite_hash"})
        )
        if canonical_hash(definition) != self.suite_hash:
            raise ValueError("suite manifest hash mismatch")
        return self


def define_turn_eval_suite_manifest(**values) -> TurnEvalSuiteManifest:
    definition = TurnEvalSuiteManifestDefinition(**values)
    return TurnEvalSuiteManifest(
        **definition.model_dump(), suite_hash=canonical_hash(definition)
    )


# ── turn_eval_batch_plan.v1(§9.1/§10)───────────────────────────────────────


class BatchPlanCase(DomainModel):
    case_id: CaseId
    split: CaseSplit
    runtime_input_hash: Sha256
    evaluation_contract_hash: Sha256
    case_content_hash: Sha256


class TurnEvalBatchPlanDefinition(DomainModel):
    schema_version: Literal["turn_eval_batch_plan.v1"] = "turn_eval_batch_plan.v1"
    batch_id: UUID
    execution_mode: ExecutionMode
    suite_version: StableName
    suite_hash: Sha256
    cases: tuple[BatchPlanCase, ...] = Field(min_length=1)
    quality_slots_per_case: int = Field(ge=1, le=3)
    max_trial_attempts_per_slot: int = Field(ge=1, le=3)
    max_concurrency: int = Field(ge=1, le=3)
    ordering_seed: NonEmptyText
    git_sha: GitSha
    dirty_worktree: bool
    operation_name: StableName
    operation_definition_hash: Sha256
    prompt_hash: Sha256
    output_schema_hash: Sha256
    context_policy_hash: Sha256
    verifier_policy_hash: Sha256
    provider: StableName
    provider_config_hash: Sha256
    requested_model: NonEmptyText
    catalog_canonical_model: NonEmptyText | None = None
    upstream_endpoint_slug: NonEmptyText | None = None
    expected_upstream_provider_name: NonEmptyText | None = None
    model_catalog_hash: Sha256 | None = None
    endpoint_catalog_hash: Sha256 | None = None
    reasoning_effort: StableName | None = None
    reasoning_exclude: bool = True
    data_collection: Literal["deny", "allow"] | None = None
    zdr_required: bool | None = None
    account_checklist_confirmed_at: UtcDatetime | None = None
    account_checklist_confirmed_by: NonEmptyText | None = None
    max_inference_calls: int = Field(ge=1)
    max_observed_cost_usd: Decimal = Field(gt=0)
    max_wall_clock_minutes: int = Field(ge=1)
    created_at: UtcDatetime

    @field_validator("cases")
    @classmethod
    def cases_are_ordered_and_unique(
        cls, value: tuple[BatchPlanCase, ...]
    ) -> tuple[BatchPlanCase, ...]:
        ids = tuple(entry.case_id for entry in value)
        if len(ids) != len(set(ids)):
            raise ValueError("batch plan case IDs must be unique")
        ordered = tuple(
            sorted(value, key=lambda entry: (entry.split.value, entry.case_id))
        )
        if ordered != value:
            raise ValueError("batch plan cases must be sorted by (split, case_id)")
        return value

    @model_validator(mode="after")
    def live_batches_bind_route_and_checklist(self) -> "TurnEvalBatchPlanDefinition":
        if self.execution_mode == ExecutionMode.LIVE:
            missing = [
                name
                for name in (
                    "catalog_canonical_model",
                    "upstream_endpoint_slug",
                    "expected_upstream_provider_name",
                    "model_catalog_hash",
                    "endpoint_catalog_hash",
                    "data_collection",
                    "zdr_required",
                    "account_checklist_confirmed_at",
                    "account_checklist_confirmed_by",
                )
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    f"live batch plan requires route/checklist fields: {missing}"
                )
        return self


class TurnEvalBatchPlan(TurnEvalBatchPlanDefinition):
    plan_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "TurnEvalBatchPlan":
        definition = TurnEvalBatchPlanDefinition.model_validate(
            self.model_dump(exclude={"plan_hash"})
        )
        if canonical_hash(definition) != self.plan_hash:
            raise ValueError("batch plan hash mismatch")
        return self


def define_turn_eval_batch_plan(**values) -> TurnEvalBatchPlan:
    definition = TurnEvalBatchPlanDefinition(**values)
    return TurnEvalBatchPlan(
        **definition.model_dump(), plan_hash=canonical_hash(definition)
    )


# ── turn_eval_trial.v1(§9.3/§9.4)───────────────────────────────────────────


class TrialRouteEvidence(DomainModel):
    """Normalized routing summary; the authoritative artifact stays in Capture."""

    metadata_present: bool
    strategy: str | None = None
    selected_provider_name: str | None = None
    selected_model: str | None = None
    single_upstream_attempt: bool | None = None
    pipeline_clean: bool | None = None
    failures: tuple[NonEmptyText, ...] = ()


class TrialAttemptRecord(DomainModel):
    attempt: int = Field(ge=1)
    outcome: ModelOutcome
    finish_reason: FinishReason
    failure_kind: FailureKind | None = None
    reason_code: str | None = None
    retryable: bool | None = None
    resolved_model: NonEmptyText | None = None
    provider_request_id: str | None = None
    generation_id: str | None = None
    usage: TokenUsage
    observed_cost_usd: Decimal | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    had_schema_repair: bool = False
    route: TrialRouteEvidence | None = None


class TurnEvalTrial(DomainModel):
    schema_version: Literal["turn_eval_trial.v1"]
    trial_id: UUID
    case_id: CaseId
    slot_index: int = Field(ge=1, le=3)
    trial_attempt: int = Field(ge=1, le=3)
    runtime_input_hash: Sha256
    evaluation_contract_hash: Sha256
    tenant_id: UUID
    user_id: UUID
    profile_id: UUID
    session_id: UUID
    run_id: UUID
    operation_id: UUID
    started_at: UtcDatetime
    completed_at: UtcDatetime
    disposition: TrialDisposition
    included_in_quality_denominator: bool
    had_infrastructure_retry: bool = False
    terminal_run_status: Literal["open", "completed", "failed"] | None = None
    terminal_checkpoint_status: StableName | None = None
    terminal_outcome: Literal["committed", "failed", "pending"] | None = None
    terminal_reason_code: str | None = None
    attempts: tuple[TrialAttemptRecord, ...] = ()
    requested_model: NonEmptyText
    context_hash: Sha256 | None = None
    prompt_hash: Sha256 | None = None
    output_schema_hash: Sha256 | None = None
    operation_definition_hash: Sha256 | None = None
    provider_config_hash: Sha256 | None = None
    model_catalog_hash: Sha256 | None = None
    endpoint_catalog_hash: Sha256 | None = None
    state_before_hash: Sha256 | None = None
    state_after_hash: Sha256 | None = None
    accepted_evidence_ids: tuple[UUID, ...] = ()
    verifier_accepted_count: int | None = Field(default=None, ge=0)
    verifier_dropped_count: int | None = Field(default=None, ge=0)
    verifier_reason_codes: tuple[StableName, ...] = ()
    usage_input_tokens: int | None = Field(default=None, ge=0)
    usage_output_tokens: int | None = Field(default=None, ge=0)
    usage_cache_read_tokens: int | None = Field(default=None, ge=0)
    usage_cache_write_tokens: int | None = Field(default=None, ge=0)
    usage_reasoning_tokens: int | None = Field(default=None, ge=0)
    observed_cost_total_usd: Decimal | None = Field(default=None, ge=0)
    latency_total_ms: int | None = Field(default=None, ge=0)
    capture_manifest_artifact_id: UUID | None = None
    capture_event_count: int | None = Field(default=None, ge=1)
    capture_last_event_hash: Sha256 | None = None
    limitations: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def trial_is_coherent(self) -> "TurnEvalTrial":
        if self.completed_at < self.started_at:
            raise ValueError("trial completed_at cannot precede started_at")
        expected_denominator = self.disposition == TrialDisposition.QUALITY_SCORED
        if self.included_in_quality_denominator != expected_denominator:
            raise ValueError(
                "included_in_quality_denominator must match the disposition"
            )
        numbers = tuple(item.attempt for item in self.attempts)
        if numbers != tuple(range(1, len(numbers) + 1)):
            raise ValueError("attempt records must be sequential from 1")
        if self.disposition == TrialDisposition.QUALITY_SCORED and not self.attempts:
            raise ValueError("quality-scored trial requires at least one attempt")
        if self.terminal_outcome == "committed":
            if self.state_before_hash is None or self.state_after_hash is None:
                raise ValueError("committed trial requires state hashes")
        ids = (
            self.tenant_id,
            self.user_id,
            self.profile_id,
            self.session_id,
            self.run_id,
            self.operation_id,
        )
        if len(set(ids)) != len(ids):
            raise ValueError("trial identity UUIDs must be distinct")
        return self


# ── turn_eval_grader_result.v1(§13)─────────────────────────────────────────


class TurnEvalGraderResult(DomainModel):
    schema_version: Literal["turn_eval_grader_result.v1"]
    grader_name: StableName
    grader_version: SemVer
    grader_definition_hash: Sha256
    case_id: CaseId
    trial_id: UUID
    status: GraderStatus
    severity: FailureSeverity | None = None
    reason_code: StableName
    subject_ids: tuple[NonEmptyText, ...] = ()
    details_json: CanonicalJsonObject = "{}"

    @model_validator(mode="after")
    def severity_matches_status(self) -> "TurnEvalGraderResult":
        if self.status == GraderStatus.FAIL and self.severity is None:
            raise ValueError("failed grader result requires a severity")
        if (
            self.status in {GraderStatus.PASS, GraderStatus.NOT_APPLICABLE}
            and self.severity is not None
        ):
            raise ValueError("pass/not_applicable grader result cannot carry severity")
        return self


# ── turn_eval_review_decision.v1(§14.3)─────────────────────────────────────


class TurnEvalReviewDecision(DomainModel):
    schema_version: Literal["turn_eval_review_decision.v1"]
    review_item_id: UUID
    review_item_hash: Sha256
    decision: ReviewDecisionLabel
    violated_forbidden_gold_ids: tuple[GoldId, ...] = ()
    reason: NonEmptyText
    reviewer: NonEmptyText
    reviewed_at: UtcDatetime
    revision: int = Field(ge=1, default=1)
    supersedes_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def decision_is_coherent(self) -> "TurnEvalReviewDecision":
        for gold_id in self.violated_forbidden_gold_ids:
            if not gold_id.startswith("f-"):
                raise ValueError("violated gold IDs must reference forbidden claims")
        if len(self.violated_forbidden_gold_ids) != len(
            set(self.violated_forbidden_gold_ids)
        ):
            raise ValueError("violated forbidden gold IDs must be unique")
        if self.supersedes_revision is not None:
            if self.supersedes_revision >= self.revision:
                raise ValueError("a revision can only supersede an earlier revision")
        elif self.revision != 1:
            raise ValueError("revision > 1 requires supersedes_revision")
        return self


# ── Metrics(§13.3;分子/分母保留,空分母 = not applicable)────────────────


METRIC_QUANTUM = Decimal("0.000001")


class MetricResult(DomainModel):
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: Decimal | None = None

    @model_validator(mode="after")
    def value_matches_ratio(self) -> "MetricResult":
        if self.denominator == 0:
            if self.value is not None:
                raise ValueError("empty denominator metric must have no value")
            return self
        if self.numerator > self.denominator:
            raise ValueError("metric numerator cannot exceed denominator")
        expected = (Decimal(self.numerator) / Decimal(self.denominator)).quantize(
            METRIC_QUANTUM, rounding=ROUND_HALF_EVEN
        )
        if self.value != expected:
            raise ValueError("metric value does not match numerator/denominator")
        return self

    @classmethod
    def compute(cls, numerator: int, denominator: int) -> "MetricResult":
        value = None
        if denominator > 0:
            value = (Decimal(numerator) / Decimal(denominator)).quantize(
                METRIC_QUANTUM, rounding=ROUND_HALF_EVEN
            )
        return cls(numerator=numerator, denominator=denominator, value=value)

    @property
    def applicable(self) -> bool:
        return self.denominator > 0


class MetricSummary(DomainModel):
    """Per-slot raw values plus median/worst;不可把 not-applicable 填成 0/1。"""

    values: tuple[Decimal | None, ...] = Field(min_length=1)
    median: Decimal | None = None
    worst: Decimal | None = None

    @model_validator(mode="after")
    def summary_matches_values(self) -> "MetricSummary":
        present = sorted(value for value in self.values if value is not None)
        if not present:
            if self.median is not None or self.worst is not None:
                raise ValueError("summary of all-N/A values must be N/A")
            return self
        middle = len(present) // 2
        if len(present) % 2:
            expected_median = present[middle]
        else:
            expected_median = (
                (present[middle - 1] + present[middle]) / 2
            ).quantize(METRIC_QUANTUM, rounding=ROUND_HALF_EVEN)
        if self.median != expected_median or self.worst != present[0]:
            raise ValueError("metric summary does not match its values")
        return self

    @classmethod
    def compute(cls, values: tuple[Decimal | None, ...]) -> "MetricSummary":
        present = sorted(value for value in values if value is not None)
        if not present:
            return cls(values=values)
        middle = len(present) // 2
        if len(present) % 2:
            median = present[middle]
        else:
            median = ((present[middle - 1] + present[middle]) / 2).quantize(
                METRIC_QUANTUM, rounding=ROUND_HALF_EVEN
            )
        return cls(values=values, median=median, worst=present[0])


# ── turn_eval_case_report.v1(§15.2)─────────────────────────────────────────


class CaseSlotReport(DomainModel):
    slot_index: int = Field(ge=1, le=3)
    trial_id: UUID
    disposition: TrialDisposition
    hard_gate_passed: bool | None = None
    raw_precision: MetricResult | None = None
    committed_precision: MetricResult | None = None
    recall: MetricResult | None = None
    qualifier_exactness: MetricResult | None = None
    expected_no_evidence_passed: bool | None = None
    critical_count: int = Field(ge=0)
    major_count: int = Field(ge=0)
    minor_count: int = Field(ge=0)
    review_complete: bool

    @model_validator(mode="after")
    def scored_slots_carry_gates(self) -> "CaseSlotReport":
        if self.disposition == TrialDisposition.QUALITY_SCORED:
            if self.hard_gate_passed is None:
                raise ValueError("quality-scored slot requires a hard gate result")
        elif self.hard_gate_passed is not None:
            raise ValueError("non-scored slot cannot carry a hard gate result")
        return self


class TurnEvalCaseReport(DomainModel):
    schema_version: Literal["turn_eval_case_report.v1"]
    case_id: CaseId
    split: CaseSplit
    slots: tuple[CaseSlotReport, ...] = Field(min_length=1)
    pass_pow_3: bool
    raw_precision_summary: MetricSummary
    committed_precision_summary: MetricSummary
    recall_summary: MetricSummary
    qualifier_exactness_summary: MetricSummary
    trials_with_critical: int = Field(ge=0)
    trials_with_major: int = Field(ge=0)
    trials_with_minor: int = Field(ge=0)
    case_specific_gate_passed: bool | None = None
    case_decision: CaseDecision

    @model_validator(mode="after")
    def report_is_coherent(self) -> "TurnEvalCaseReport":
        indexes = tuple(slot.slot_index for slot in self.slots)
        if indexes != tuple(range(1, len(indexes) + 1)):
            raise ValueError("case report slots must be sequential from 1")
        scored = [
            slot
            for slot in self.slots
            if slot.disposition == TrialDisposition.QUALITY_SCORED
        ]
        expected_pass3 = len(scored) == 3 and all(
            slot.hard_gate_passed for slot in scored
        )
        if self.pass_pow_3 != expected_pass3:
            raise ValueError("pass_pow_3 must reflect three passing quality slots")
        if self.trials_with_critical > 0 and self.case_decision == CaseDecision.PASS:
            raise ValueError("a case with a critical failure cannot pass")
        if self.case_decision == CaseDecision.PASS and not self.pass_pow_3:
            raise ValueError("a passing case requires pass^3")
        return self


# ── turn_eval_batch_report.v1(§15.3~§15.6)──────────────────────────────────


class HardGateResult(DomainModel):
    gate_name: StableName
    passed: bool
    details_json: CanonicalJsonObject = "{}"


class SplitMetrics(DomainModel):
    precision: MetricResult
    recall: MetricResult
    qualifier_exactness: MetricResult


class CasePassEntry(DomainModel):
    case_id: CaseId
    split: CaseSplit
    pass_pow_3: bool
    case_decision: CaseDecision


class FailureRecord(DomainModel):
    trial_id: UUID | None = None
    case_id: CaseId | None = None
    attribution: FailureAttribution
    severity: FailureSeverity
    reason_code: StableName
    description: NonEmptyText
    prevented_by_verifier: bool = False


class ReviewCompleteness(DomainModel):
    required_review_items: int = Field(ge=0)
    completed_review_items: int = Field(ge=0)
    needs_sme_count: int = Field(ge=0)
    failure_traces_read: int = Field(ge=0)
    passing_trace_sample_required: int = Field(ge=0)
    passing_trace_sample_read: int = Field(ge=0)

    @property
    def complete(self) -> bool:
        return (
            self.completed_review_items >= self.required_review_items
            and self.passing_trace_sample_read >= self.passing_trace_sample_required
        )


class BatchTotals(DomainModel):
    total_trials: int = Field(ge=0)
    quality_trials: int = Field(ge=0)
    infrastructure_invalid_trials: int = Field(ge=0)
    harness_invalid_trials: int = Field(ge=0)
    cancelled_trials: int = Field(ge=0)
    inference_calls: int = Field(ge=0)
    usage_input_tokens: int | None = Field(default=None, ge=0)
    usage_output_tokens: int | None = Field(default=None, ge=0)
    usage_cache_read_tokens: int | None = Field(default=None, ge=0)
    usage_cache_write_tokens: int | None = Field(default=None, ge=0)
    usage_reasoning_tokens: int | None = Field(default=None, ge=0)
    observed_cost_total_usd: Decimal | None = Field(default=None, ge=0)
    wall_clock_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def totals_are_coherent(self) -> "BatchTotals":
        classified = (
            self.quality_trials
            + self.infrastructure_invalid_trials
            + self.harness_invalid_trials
            + self.cancelled_trials
        )
        if classified != self.total_trials:
            raise ValueError("trial disposition totals must sum to total_trials")
        return self


class TurnEvalBatchReport(DomainModel):
    schema_version: Literal["turn_eval_batch_report.v1"]
    batch_id: UUID
    plan_hash: Sha256
    suite_version: StableName
    suite_hash: Sha256
    execution_mode: ExecutionMode
    git_sha: GitSha
    dirty_worktree: bool
    promotion_eligible: bool
    decision: BatchDecision
    hard_gates: tuple[HardGateResult, ...] = Field(min_length=1)
    raw_precision_micro: MetricResult
    committed_precision_micro: MetricResult
    recall_micro: MetricResult
    qualifier_exactness_micro: MetricResult
    development_metrics: SplitMetrics | None = None
    challenge_metrics: SplitMetrics | None = None
    split_gap_within_limit: bool | None = None
    case_matrix: tuple[CasePassEntry, ...] = Field(min_length=1)
    totals: BatchTotals
    review: ReviewCompleteness
    failures: tuple[FailureRecord, ...] = ()
    limitations: tuple[NonEmptyText, ...] = ()
    created_at: UtcDatetime

    @model_validator(mode="after")
    def report_is_coherent(self) -> "TurnEvalBatchReport":
        ids = tuple(entry.case_id for entry in self.case_matrix)
        if len(ids) != len(set(ids)):
            raise ValueError("case matrix IDs must be unique")
        gate_names = tuple(gate.gate_name for gate in self.hard_gates)
        if len(gate_names) != len(set(gate_names)):
            raise ValueError("hard gate names must be unique")
        if self.dirty_worktree and self.promotion_eligible:
            raise ValueError("a dirty-worktree batch is never promotion eligible")
        passing = {
            BatchDecision.TURN_GATE_PASS_ENGINEERING,
            BatchDecision.TURN_GATE_PASS_DOMAIN_REVIEWED,
        }
        if self.decision in passing:
            if not self.promotion_eligible:
                raise ValueError("a passing decision requires promotion eligibility")
            if not all(gate.passed for gate in self.hard_gates):
                raise ValueError("a passing decision requires all hard gates green")
            if not all(entry.pass_pow_3 for entry in self.case_matrix):
                raise ValueError("a passing decision requires pass^3 on every case")
        return self


# ── Grader identity helper(§13)──────────────────────────────────────────────


class GraderDefinition(DomainModel):
    """Versioned identity for one deterministic grader implementation."""

    grader_name: StableName
    grader_version: SemVer
    policy: CanonicalJsonObject = "{}"

    @property
    def definition_hash(self) -> str:
        return canonical_hash(self)
