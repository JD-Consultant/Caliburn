"""V3-5 E1:turn eval contracts 的 strict validation 與 schema drift tests(§18.1)。"""

from __future__ import annotations

import json
import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.interview_vnext.domain.evidence import EvidenceKind, EvidenceSubject
from app.interview_vnext.domain.interpretation import DialogueAct
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.transcript import TranscriptRole
from app.interview_vnext.llm.result import (
    FinishReason,
    ModelOutcome,
    TokenUsage,
)
from app.interview_vnext.llm.turn_interpret import (
    EpisodeSignal,
    CorrectionProposal,
    EvidenceQualifiersProposal,
    FrequencyQualifierProposal,
    ObservationProposal,
    TurnInterpretOutput,
)
from app.interview_vnext.domain.evidence import (
    FrequencyUnit,
    Importance,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from evals.interview_vnext.contracts import (
    BatchDecision,
    BatchPlanCase,
    BatchTotals,
    CaseDecision,
    CasePassEntry,
    CaseSlotReport,
    CaseSplit,
    ExecutionMode,
    ExpectedCommit,
    FailureSeverity,
    GoldStateExpectation,
    GraderStatus,
    HardGateResult,
    MetricResult,
    MetricSummary,
    ReviewCompleteness,
    TrialAttemptRecord,
    TrialDisposition,
    TurnEvalBatchPlan,
    TurnEvalBatchReport,
    TurnEvalCase,
    TurnEvalCaseReport,
    TurnEvalGold,
    TurnEvalGoldForbiddenClaim,
    TurnEvalGoldObservation,
    TurnEvalGraderResult,
    TurnEvalInitialFixture,
    TurnEvalReferenceOutput,
    TurnEvalReviewDecision,
    TurnEvalTranscriptTurn,
    TurnEvalTrial,
    define_turn_eval_batch_plan,
    define_turn_eval_suite_manifest,
)
from evals.interview_vnext.write_schemas import (
    HISTORICAL_SCHEMAS,
    SCHEMA_DIR,
    SCHEMA_EXPORTS,
    published_schema,
    write_schemas,
)


NOW = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
SHA = "sha256:" + "0" * 64
GIT_SHA = "1" * 40

HISTORICAL_SCHEMA_HASHES = {
    "turn-eval-batch-plan.v1.schema.json": "sha256:c6db755690bcae447cf58da427220e51260773be96998989266662b1d466aaa1",
    "turn-eval-batch-report.v1.schema.json": "sha256:12b9243b4100daeac7637093dcefebd5403a02754a9cea6fca05acaa2f933728",
    "turn-eval-case.v1.schema.json": "sha256:6222ad7955eb862003fa4eceaab8942c09de908628e30a412c32c6dbbd4a89c6",
    "turn-eval-case-report.v1.schema.json": "sha256:812c502586735d6d1b37f5f07137f2cdf3bccaa2a3890adbdda79158c34e6ecf",
    "turn-eval-gold.v1.schema.json": "sha256:1d8b8886e1d777f4f3491bf9cbf34a37178f45ce946cea22a8999a55ef0b8184",
    "turn-eval-grader-result.v1.schema.json": "sha256:385adb08f90639dc539e32203d6fe29a6a5527d810b11f464b284ae8f6d4a312",
    "turn-eval-initial-fixture.v1.schema.json": "sha256:174a88f05893be650b68f50382df7c1cdf5b1e3fe4968ca77744879c710e7277",
    "turn-eval-reference-output.v1.schema.json": "sha256:f7abbcf5b423dd73e9732edf23c3ab15062f0b63a5d6f749a5a25dd494d2c176",
    "turn-eval-review-decision.v1.schema.json": "sha256:416b7cd6f2e615026d7b705a70e1397590ba6e3dbb83b414f857967276385e32",
    "turn-eval-transcript.v1.schema.json": "sha256:b49140e7a8275ccd6ac9325c33632307098873024942f4ea9a6a50f5ce42b136",
    "turn-eval-trial.v1.schema.json": "sha256:bf475714581279661c88f2ccd93b4b6a5ce53189c649f54a67e7e3593b35289e",
}


def valid_case(**overrides) -> TurnEvalCase:
    payload = {
        "schema_version": "turn_eval_case.v2",
        "case_id": "TI-01-single-action",
        "split": "development",
        "locale": "zh-TW",
        "task_type": "turn_interpret",
        "failure_purpose": "single_explicit_action",
        "difficulty_tags": ["typical"],
        "target_turn_key": "employee-target",
        "source_type": "constructed_edge",
        "annotation_status": "adjudicated_by_maintainer",
        "pilot_only": True,
        "files": {},
        "applicable_graders": ["schema_validity", "quote_validity"],
    }
    payload.update(overrides)
    return TurnEvalCase.model_validate(payload)


def qualifier_expectations(**overrides) -> dict:
    payload = {
        "time_scope": {"mode": "exact", "value": "current"},
        "typicality": {"mode": "exact", "value": "typical"},
        "polarity": {"mode": "exact", "value": "affirmed"},
        "frequency_unit": {"mode": "exact", "value": "per_day"},
        "frequency_value": {"mode": "not_applicable"},
        "importance": {"mode": "one_of", "values": ["not_stated"]},
        "ownership": {"mode": "exact", "value": "owner"},
    }
    payload.update(overrides)
    return payload


def gold_observation(**overrides) -> TurnEvalGoldObservation:
    payload = {
        "gold_id": "g-action-check-orders",
        "requirement": "required",
        "semantic_target": "員工目前固定核對前一日的出貨訂單",
        "allowed_subjects": ["employee"],
        "allowed_kinds": ["action"],
        "source_anchors": [
            {"turn_key": "employee-target", "quote": "核對前一日的出貨訂單", "occurrence": 1}
        ],
        "qualifiers": qualifier_expectations(),
        "correction_target_evidence_keys": [],
        "severity_if_missed": "major",
        "rationale": "核心例行工作",
    }
    payload.update(overrides)
    return TurnEvalGoldObservation.model_validate(payload)


def valid_gold(**overrides) -> TurnEvalGold:
    payload = {
        "schema_version": "turn_eval_gold.v2",
        "case_id": "TI-01-single-action",
        "allowed_dialogue_acts": ["standalone_answer"],
        "allowed_episode_signals": ["continue"],
        "expected_commit": "evidence_and_receipt",
        "observations": [gold_observation().model_dump()],
        "forbidden_claims": [
            {"gold_id": "f-invented-kpi", "description": "不得新增原文沒有的數字", "severity": "critical"}
        ],
        "required_insufficiencies": [],
        "allowed_insufficiencies": [],
        "state_expectation": {
            "state_hash_changed": True,
            "prior_evidence_superseded_keys": [],
            "forbidden_superseded_keys": [],
        },
    }
    payload.update(overrides)
    return TurnEvalGold.model_validate(payload)


def proposal_qualifiers() -> EvidenceQualifiersProposal:
    return EvidenceQualifiersProposal(
        time_scope=TimeScope.CURRENT,
        typicality=Typicality.TYPICAL,
        polarity=Polarity.AFFIRMED,
        frequency=FrequencyQualifierProposal(value=None, unit=FrequencyUnit.PER_DAY, verbatim=None),
        importance=Importance.NOT_STATED,
        ownership=Ownership.OWNER,
    )


def correction_proposal(*, key: str = "obs-correction", unknown: bool = False) -> ObservationProposal:
    return ObservationProposal(
        subject=EvidenceSubject.EMPLOYEE,
        kind=EvidenceKind.CORRECTION,
        claim="每月寄一次庫存報表",
        quote="是每月寄一次庫存報表",
        quote_occurrence=1,
        qualifiers=proposal_qualifiers(),
        correction=CorrectionProposal(target_unknown=unknown),
    )


def reference_output(*, observations=(), bindings=None) -> TurnEvalReferenceOutput:
    return TurnEvalReferenceOutput.model_validate(
        {
            "schema_version": "turn_eval_reference_output.v2",
            "case_id": "TI-09-known-correction",
            "output": TurnInterpretOutput(
                schema_version="turn_interpret_output.v2",
                literal_observations=tuple(observations),
                answer_bindings=(),
                dialogue_act=DialogueAct.CORRECTION,
                episode_signal=EpisodeSignal.CONTINUE,
                emergent_topics=(),
                turn_insufficiency_codes=(),
            ).model_dump(),
            "correction_target_bindings": bindings or {},
        }
    )


def plan_case(case_id: str = "TI-01-single-action", split: str = "development") -> dict:
    return {
        "case_id": case_id,
        "split": split,
        "runtime_input_hash": SHA,
        "evaluation_contract_hash": SHA,
        "case_content_hash": SHA,
    }


def valid_plan_definition(**overrides) -> dict:
    payload = {
        "batch_id": uuid4(),
        "execution_mode": "mocked",
        "suite_version": "turn-interpret-c1-v2-pilot.v1",
        "suite_hash": SHA,
        "cases": [plan_case()],
        "quality_slots_per_case": 3,
        "max_trial_attempts_per_slot": 3,
        "max_concurrency": 1,
        "ordering_seed": "seed-1",
        "git_sha": GIT_SHA,
        "dirty_worktree": False,
        "operation_name": "turn.interpret",
        "operation_definition_hash": SHA,
        "prompt_hash": SHA,
        "output_schema_hash": SHA,
        "context_policy_hash": SHA,
        "verifier_policy_hash": SHA,
        "provider": "openrouter",
        "provider_config_hash": SHA,
        "requested_model": "anthropic/claude-sonnet-5",
        "max_inference_calls": 120,
        "max_observed_cost_usd": Decimal("10.00"),
        "max_wall_clock_minutes": 180,
        "created_at": NOW,
    }
    payload.update(overrides)
    return payload


def valid_trial(**overrides) -> TurnEvalTrial:
    payload = {
        "schema_version": "turn_eval_trial.v2",
        "trial_id": uuid4(),
        "case_id": "TI-01-single-action",
        "slot_index": 1,
        "trial_attempt": 1,
        "runtime_input_hash": SHA,
        "evaluation_contract_hash": SHA,
        "tenant_id": uuid4(),
        "user_id": uuid4(),
        "profile_id": uuid4(),
        "session_id": uuid4(),
        "run_id": uuid4(),
        "operation_id": uuid4(),
        "started_at": NOW,
        "completed_at": NOW + timedelta(seconds=30),
        "disposition": "quality_scored",
        "included_in_quality_denominator": True,
        "terminal_run_status": "completed",
        "terminal_checkpoint_status": "committed",
        "terminal_outcome": "committed",
        "attempts": [
            TrialAttemptRecord(
                attempt=1,
                outcome=ModelOutcome.SUCCEEDED,
                finish_reason=FinishReason.COMPLETED,
                usage=TokenUsage(
                    input_tokens=100,
                    output_tokens=50,
                    cache_read_tokens=0,
                    cache_write_tokens=0,
                    reasoning_tokens=0,
                ),
                observed_cost_usd=Decimal("0.01"),
                latency_ms=1500,
            ).model_dump()
        ],
        "requested_model": "anthropic/claude-sonnet-5",
        "state_before_hash": SHA,
        "state_after_hash": SHA,
    }
    payload.update(overrides)
    return TurnEvalTrial.model_validate(payload)


# ── strict extra fields ──────────────────────────────────────────────────────


def test_top_level_documents_reject_extra_fields():
    documents = (
        (TurnEvalCase, valid_case().model_dump()),
        (TurnEvalGold, valid_gold().model_dump()),
        (TurnEvalTrial, valid_trial().model_dump()),
    )
    for model, payload in documents:
        payload["unexpected"] = "x"
        with pytest.raises(ValidationError):
            model.model_validate(payload)


def test_transcript_turn_contract():
    turn = TurnEvalTranscriptTurn.model_validate(
        {
            "schema_version": "turn_eval_transcript_turn.v2",
            "turn_key": "employee-target",
            "sequence": 2,
            "role": "employee",
            "locale": "zh-TW",
            "text": "我每天早上核對前一日的出貨訂單。",
            "occurred_offset_seconds": 2,
        }
    )
    assert turn.role is TranscriptRole.EMPLOYEE
    with pytest.raises(ValidationError):
        TurnEvalTranscriptTurn.model_validate(
            {**turn.model_dump(), "sequence": 0}
        )
    with pytest.raises(ValidationError):
        TurnEvalTranscriptTurn.model_validate(
            {**turn.model_dump(), "turn_key": "Employee-Target"}
        )


# ── case rules ───────────────────────────────────────────────────────────────


def test_case_difficulty_tags_must_be_canonical_and_unique():
    valid_case(difficulty_tags=["adversarial", "typical"])
    with pytest.raises(ValidationError):
        valid_case(difficulty_tags=["typical", "adversarial"])
    with pytest.raises(ValidationError):
        valid_case(difficulty_tags=["typical", "typical"])


def test_constructed_cases_must_be_pilot_only():
    with pytest.raises(ValidationError):
        valid_case(pilot_only=False)


def test_case_files_are_fixed_names():
    with pytest.raises(ValidationError):
        valid_case(files={"transcript": "other.jsonl"})


# ── initial fixture rules ────────────────────────────────────────────────────


def test_fixture_requires_activation_and_episode_consistency():
    fixture = {
        "schema_version": "turn_eval_initial_fixture.v2",
        "session_status_before_replay": "planned",
        "activate_before_transcript": True,
        "open_episode": {
            "episode_key": "episode-main",
            "target": "例行報表處理",
            "opened_turn_key": "consultant-01",
        },
        "prior_evidence": [],
    }
    TurnEvalInitialFixture.model_validate(fixture)
    with pytest.raises(ValidationError):
        TurnEvalInitialFixture.model_validate(
            {**fixture, "activate_before_transcript": False}
        )
    orphan = {
        **fixture,
        "open_episode": None,
        "prior_evidence": [
            {
                "evidence_key": "prior-a",
                "source_turn_key": "employee-prior",
                "episode_key": "episode-main",
                "subject": "employee",
                "kind": "frequency",
                "claim": "每週寄一次庫存報表",
                "quote": "我每週寄一次庫存報表。",
                "quote_occurrence": 1,
                "qualifiers": proposal_qualifiers().model_dump(),
            }
        ],
    }
    with pytest.raises(ValidationError):
        TurnEvalInitialFixture.model_validate(orphan)


# ── gold rules ───────────────────────────────────────────────────────────────


def test_gold_qualifier_modes_are_exclusive_and_typed():
    with pytest.raises(ValidationError):
        gold_observation(
            qualifiers=qualifier_expectations(
                time_scope={"mode": "exact", "value": "sometimes"}
            )
        )
    with pytest.raises(ValidationError):
        gold_observation(
            qualifiers=qualifier_expectations(
                frequency_value={"mode": "exact", "value": "two"}
            )
        )
    with pytest.raises(ValidationError):
        gold_observation(
            qualifiers=qualifier_expectations(
                importance={"mode": "one_of", "values": ["not_stated", "not_stated"]}
            )
        )
    with pytest.raises(ValidationError):
        gold_observation(
            qualifiers=qualifier_expectations(time_scope={"mode": "exact"})
        )


def test_gold_ids_and_severity_rules():
    with pytest.raises(ValidationError):
        gold_observation(gold_id="f-not-an-observation")
    with pytest.raises(ValidationError):
        gold_observation(severity_if_missed="diagnostic")
    with pytest.raises(ValidationError):
        TurnEvalGoldForbiddenClaim.model_validate(
            {"gold_id": "f-minor", "description": "x", "severity": "minor"}
        )


def test_gold_correction_targets_require_correction_kind():
    with pytest.raises(ValidationError):
        gold_observation(correction_target_evidence_keys=["prior-a"])
    gold_observation(
        allowed_kinds=["correction"],
        correction_target_evidence_keys=["prior-a"],
        qualifiers=qualifier_expectations(
            frequency_unit={"mode": "exact", "value": "per_month"}
        ),
    )


def test_gold_receipt_only_and_evidence_commit_coherence():
    with pytest.raises(ValidationError):
        valid_gold(expected_commit="receipt_only")
    valid_gold(
        expected_commit="receipt_only",
        observations=[],
        state_expectation={
            "state_hash_changed": True,
            "prior_evidence_superseded_keys": [],
            "forbidden_superseded_keys": [],
        },
    )
    with pytest.raises(ValidationError):
        valid_gold(
            state_expectation={
                "state_hash_changed": False,
                "prior_evidence_superseded_keys": [],
                "forbidden_superseded_keys": [],
            }
        )


def test_gold_duplicate_ids_rejected():
    with pytest.raises(ValidationError):
        valid_gold(
            forbidden_claims=[
                {"gold_id": "f-x", "description": "a", "severity": "critical"},
                {"gold_id": "f-x", "description": "b", "severity": "critical"},
            ]
        )


def test_state_expectation_key_sets_disjoint():
    with pytest.raises(ValidationError):
        GoldStateExpectation.model_validate(
            {
                "state_hash_changed": True,
                "prior_evidence_superseded_keys": ["prior-a"],
                "forbidden_superseded_keys": ["prior-a"],
            }
        )


# ── reference output rules ───────────────────────────────────────────────────


def test_reference_output_bindings_are_single_source_of_truth():
    reference_output(
        observations=(correction_proposal(),),
        bindings={"1": ("prior-inventory-report-frequency",)},
    )
    with pytest.raises(ValidationError):
        reference_output(observations=(correction_proposal(),))  # 缺 binding
    with pytest.raises(ValidationError):
        reference_output(
            observations=(correction_proposal(unknown=True),),
            bindings={"1": ("prior-a",)},
        )
    with pytest.raises(ValidationError):
        reference_output(bindings={"missing-key": ("prior-a",)})


def test_reference_output_rejects_trial_scoped_correction_ordinals():
    proposal = correction_proposal().model_copy(
        update={"correction": CorrectionProposal(target_candidate_ordinals=(1,))}
    )
    with pytest.raises(ValidationError):
        reference_output(
            observations=(proposal,), bindings={"1": ("prior-a",)}
        )


# ── suite manifest / batch plan hash ─────────────────────────────────────────


def test_suite_manifest_orders_cases_and_verifies_hash():
    manifest = define_turn_eval_suite_manifest(
        suite_version="turn-interpret-c1-v2-pilot.v1",
        cases=[
            plan_case("TI-09-known-correction", "challenge"),
            plan_case("TI-01-single-action", "development"),
        ],
    )
    # (split, case_id) 字典序:challenge < development
    assert [entry.split for entry in manifest.cases] == [
        CaseSplit.CHALLENGE,
        CaseSplit.DEVELOPMENT,
    ]
    assert manifest.cases[0].case_id == "TI-09-known-correction"
    with pytest.raises(ValidationError):
        manifest.model_validate({**manifest.model_dump(), "suite_hash": SHA})


def test_suite_manifest_input_must_be_presorted():
    with pytest.raises(ValidationError):
        define_turn_eval_suite_manifest(
            suite_version="turn-interpret-c1-v2-pilot.v1",
            cases=[
                plan_case("TI-02-action-output", "development"),
                plan_case("TI-01-single-action", "development"),
            ],
        )


def test_batch_plan_hash_binds_definition():
    plan = define_turn_eval_batch_plan(**valid_plan_definition())
    reparsed = TurnEvalBatchPlan.model_validate(plan.model_dump())
    assert reparsed.plan_hash == plan.plan_hash
    tampered = plan.model_dump()
    tampered["max_inference_calls"] = 121
    with pytest.raises(ValidationError):
        TurnEvalBatchPlan.model_validate(tampered)


def test_live_batch_plan_requires_route_and_checklist():
    with pytest.raises(ValidationError):
        define_turn_eval_batch_plan(
            **valid_plan_definition(execution_mode="live")
        )
    define_turn_eval_batch_plan(
        **valid_plan_definition(
            execution_mode="live",
            catalog_canonical_model="anthropic/claude-sonnet-5",
            upstream_endpoint_slug="anthropic",
            expected_upstream_provider_name="Anthropic",
            model_catalog_hash=SHA,
            endpoint_catalog_hash=SHA,
            data_collection="deny",
            zdr_required=False,
            account_checklist_confirmed_at=NOW,
            account_checklist_confirmed_by="owner",
        )
    )


# ── trial rules ──────────────────────────────────────────────────────────────


def test_trial_quality_denominator_matches_disposition():
    with pytest.raises(ValidationError):
        valid_trial(included_in_quality_denominator=False)
    infra = valid_trial(
        disposition="infrastructure_invalid",
        included_in_quality_denominator=False,
        terminal_outcome="failed",
        terminal_run_status="failed",
    )
    assert infra.disposition is TrialDisposition.INFRASTRUCTURE_INVALID


def test_trial_attempts_must_be_sequential_and_present_for_quality():
    with pytest.raises(ValidationError):
        valid_trial(attempts=[])
    attempt = valid_trial().attempts[0]
    with pytest.raises(ValidationError):
        valid_trial(
            attempts=[
                attempt.model_dump(),
                {**attempt.model_dump(), "attempt": 3},
            ]
        )


def test_trial_committed_requires_state_hashes_and_distinct_ids():
    with pytest.raises(ValidationError):
        valid_trial(state_after_hash=None)
    shared = uuid4()
    with pytest.raises(ValidationError):
        valid_trial(tenant_id=shared, user_id=shared)


# ── grader result / review decision ──────────────────────────────────────────


def test_grader_result_severity_and_details_rules():
    base = {
        "schema_version": "turn_eval_grader_result.v2",
        "grader_name": "quote_span",
        "grader_version": "1.0.0",
        "grader_definition_hash": SHA,
        "case_id": "TI-01-single-action",
        "trial_id": uuid4(),
        "status": "pass",
        "reason_code": "ok",
    }
    TurnEvalGraderResult.model_validate(base)
    with pytest.raises(ValidationError):
        TurnEvalGraderResult.model_validate({**base, "status": "fail"})
    with pytest.raises(ValidationError):
        TurnEvalGraderResult.model_validate(
            {**base, "severity": "major"}
        )
    with pytest.raises(ValidationError):
        TurnEvalGraderResult.model_validate(
            {**base, "details_json": '{"b":1,"a":2}'}
        )
    canonical = canonical_json({"b": 1, "a": 2})
    TurnEvalGraderResult.model_validate({**base, "details_json": canonical})


def test_review_decision_revision_chain():
    base = {
        "schema_version": "turn_eval_review_decision.v2",
        "review_item_id": uuid4(),
        "review_item_hash": SHA,
        "decision": "equivalent",
        "reason": "語意等價",
        "reviewer": "maintainer",
        "reviewed_at": NOW,
    }
    TurnEvalReviewDecision.model_validate(base)
    with pytest.raises(ValidationError):
        TurnEvalReviewDecision.model_validate({**base, "revision": 2})
    TurnEvalReviewDecision.model_validate(
        {**base, "revision": 2, "supersedes_revision": 1}
    )
    with pytest.raises(ValidationError):
        TurnEvalReviewDecision.model_validate(
            {**base, "revision": 2, "supersedes_revision": 2}
        )
    with pytest.raises(ValidationError):
        TurnEvalReviewDecision.model_validate(
            {**base, "violated_forbidden_gold_ids": ["g-not-forbidden"]}
        )


# ── metrics ──────────────────────────────────────────────────────────────────


def test_metric_result_empty_denominator_is_not_applicable():
    metric = MetricResult.compute(0, 0)
    assert metric.value is None and not metric.applicable
    with pytest.raises(ValidationError):
        MetricResult.model_validate({"numerator": 0, "denominator": 0, "value": "1"})
    with pytest.raises(ValidationError):
        MetricResult.model_validate({"numerator": 3, "denominator": 2, "value": "1.5"})
    exact = MetricResult.compute(2, 3)
    assert str(exact.value) == "0.666667"
    with pytest.raises(ValidationError):
        MetricResult.model_validate(
            {"numerator": 2, "denominator": 3, "value": "0.666666"}
        )


def test_metric_summary_median_and_worst():
    summary = MetricSummary.compute((Decimal("1"), None, Decimal("0.5")))
    assert summary.worst == Decimal("0.5")
    assert summary.median == Decimal("0.75")
    empty = MetricSummary.compute((None, None, None))
    assert empty.median is None and empty.worst is None
    with pytest.raises(ValidationError):
        MetricSummary.model_validate(
            {"values": ["1", "0.5"], "median": "1", "worst": "0.5"}
        )


# ── case / batch report coherence ────────────────────────────────────────────


def slot(index: int, *, passed: bool = True, disposition: str = "quality_scored") -> dict:
    return CaseSlotReport.model_validate(
        {
            "slot_index": index,
            "trial_id": uuid4(),
            "disposition": disposition,
            "hard_gate_passed": passed if disposition == "quality_scored" else None,
            "raw_precision": MetricResult.compute(1, 1).model_dump(),
            "committed_precision": MetricResult.compute(1, 1).model_dump(),
            "recall": MetricResult.compute(1, 1).model_dump(),
            "qualifier_exactness": MetricResult.compute(6, 6).model_dump(),
            "critical_count": 0,
            "major_count": 0 if passed else 1,
            "minor_count": 0,
            "review_complete": True,
        }
    ).model_dump()


def case_report(**overrides) -> TurnEvalCaseReport:
    ones = MetricSummary.compute((Decimal("1"), Decimal("1"), Decimal("1"))).model_dump()
    payload = {
        "schema_version": "turn_eval_case_report.v2",
        "case_id": "TI-01-single-action",
        "split": "development",
        "slots": [slot(1), slot(2), slot(3)],
        "pass_pow_3": True,
        "raw_precision_summary": ones,
        "committed_precision_summary": ones,
        "recall_summary": ones,
        "qualifier_exactness_summary": ones,
        "trials_with_critical": 0,
        "trials_with_major": 0,
        "trials_with_minor": 0,
        "case_decision": "pass",
    }
    payload.update(overrides)
    return TurnEvalCaseReport.model_validate(payload)


def test_case_report_pass_pow_3_requires_three_green_slots():
    case_report()
    with pytest.raises(ValidationError):
        case_report(slots=[slot(1), slot(2), slot(3, passed=False)])
    with pytest.raises(ValidationError):
        case_report(
            slots=[slot(1), slot(2)],
            pass_pow_3=True,
        )
    two_of_three = case_report(
        slots=[slot(1), slot(2), slot(3, passed=False)],
        pass_pow_3=False,
        trials_with_major=1,
        case_decision="fail",
    )
    assert two_of_three.pass_pow_3 is False


def test_case_report_critical_cannot_pass():
    with pytest.raises(ValidationError):
        case_report(trials_with_critical=1)


def batch_report(**overrides) -> TurnEvalBatchReport:
    metric = MetricResult.compute(1, 1).model_dump()
    payload = {
        "schema_version": "turn_eval_batch_report.v2",
        "batch_id": uuid4(),
        "plan_hash": SHA,
        "suite_version": "turn-interpret-c1-v2-pilot.v1",
        "suite_hash": SHA,
        "execution_mode": "live",
        "git_sha": GIT_SHA,
        "dirty_worktree": False,
        "promotion_eligible": True,
        "decision": "TURN_GATE_PASS_ENGINEERING",
        "hard_gates": [{"gate_name": "route_integrity", "passed": True}],
        "raw_precision_micro": metric,
        "committed_precision_micro": metric,
        "recall_micro": metric,
        "qualifier_exactness_micro": metric,
        "case_matrix": [
            {
                "case_id": "TI-01-single-action",
                "split": "development",
                "pass_pow_3": True,
                "case_decision": "pass",
            }
        ],
        "totals": BatchTotals(
            total_trials=3,
            quality_trials=3,
            infrastructure_invalid_trials=0,
            harness_invalid_trials=0,
            cancelled_trials=0,
            inference_calls=3,
        ).model_dump(),
        "review": ReviewCompleteness(
            required_review_items=3,
            completed_review_items=3,
            needs_sme_count=0,
            failure_traces_read=0,
            passing_trace_sample_required=1,
            passing_trace_sample_read=1,
        ).model_dump(),
        "created_at": NOW,
    }
    payload.update(overrides)
    return TurnEvalBatchReport.model_validate(payload)


def test_batch_report_passing_decision_requires_green_gates():
    batch_report()
    with pytest.raises(ValidationError):
        batch_report(
            hard_gates=[{"gate_name": "route_integrity", "passed": False}]
        )
    with pytest.raises(ValidationError):
        batch_report(dirty_worktree=True)
    failed = batch_report(
        decision="TURN_GATE_FAIL",
        promotion_eligible=False,
        hard_gates=[{"gate_name": "route_integrity", "passed": False}],
        case_matrix=[
            {
                "case_id": "TI-01-single-action",
                "split": "development",
                "pass_pow_3": False,
                "case_decision": "fail",
            }
        ],
    )
    assert failed.decision is BatchDecision.TURN_GATE_FAIL


def test_batch_totals_must_sum():
    with pytest.raises(ValidationError):
        BatchTotals(
            total_trials=3,
            quality_trials=1,
            infrastructure_invalid_trials=0,
            harness_invalid_trials=0,
            cancelled_trials=0,
            inference_calls=3,
        )


# ── schema export drift(§18.1)──────────────────────────────────────────────


def test_schema_export_is_deterministic(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_schemas(first)
    write_schemas(second)
    for filename in SCHEMA_EXPORTS:
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_committed_turn_eval_schemas_match_models():
    assert {path.name for path in SCHEMA_DIR.glob("*.json")} == (
        set(SCHEMA_EXPORTS) | set(HISTORICAL_SCHEMAS)
    )
    for filename in SCHEMA_EXPORTS:
        committed = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        assert committed == published_schema(filename), filename


def test_historical_turn_eval_schemas_are_frozen():
    assert set(HISTORICAL_SCHEMA_HASHES) == set(HISTORICAL_SCHEMAS)
    for filename, expected in HISTORICAL_SCHEMA_HASHES.items():
        actual = "sha256:" + hashlib.sha256(
            (SCHEMA_DIR / filename).read_bytes()
        ).hexdigest()
        assert actual == expected, filename


def test_published_schemas_have_stable_ids_and_forbid_unknown_fields():
    for filename in SCHEMA_EXPORTS:
        schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        assert schema["$id"] == f"https://caliburn.local/schemas/{filename}"
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
