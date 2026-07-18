"""V3-5 E6:mocked batch scheduler、Capture export、bundle、report(§18.5)。

需要 real PostgreSQL(run_trial 走 production durable stack)。涵蓋:36 成功
trial 填滿 slot、每 adapter call 一次 POST、infrastructure replacement 保留原
trial、budget 停線、Capture 匯出與 secret scan、atomic bundle 與 integrity
manifest、case/batch report 與 pass^3、markdown 去 provider identity。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
import pytest_asyncio

from app.interview_vnext.application.operation_executor import (
    TurnInterpretProviderProfile,
)
from app.interview_vnext.llm.result import (
    FailureKind,
    FinishReason,
    ModelCallResult,
    ModelFailure,
    ModelOutcome,
    TokenUsage,
    build_structured_payload,
)
from app.interview_vnext.llm.port import LlmPort, ModelCallEnvelope
from app.interview_vnext.llm.testing import ScriptedLlmPort, ScriptedStep
from app.interview_vnext.observability.artifacts import build_inline_artifact
from evals.interview_vnext.capture_export import (
    SecretLeakError,
    export_run_bundle,
)
from evals.interview_vnext.contracts import (
    BatchDecision,
    CaseDecision,
    CaseSplit,
    ReviewCompleteness,
    ReviewDecisionLabel,
    TrialDisposition,
)
from evals.interview_vnext.fixture_builder import materialize_reference_output
from evals.interview_vnext.identities import trial_scoped_ids, turn_uuid
from evals.interview_vnext.loader import load_suite
from evals.interview_vnext.review import (
    build_review_items,
    edge_decision_map,
    import_review_decisions,
)
from evals.interview_vnext.contracts import TurnEvalReviewDecision
from evals.interview_vnext.scheduler import (
    Budget,
    BudgetExceeded,
    accepted_proposal_keys,
    build_trial_record,
    classify_disposition,
    committed_kind,
    evidence_status_map,
    schedule_slot,
    trial_output,
    verifier_reason_codes,
    write_trial_bundle,
)
from evals.interview_vnext.turn_eval_runner import cleanup_trial_rows, run_trial
from evals.interview_vnext.turn_graders import (
    GradingContext,
    build_candidate_edges,
    compute_trial_metrics,
    run_deterministic_graders,
)
from evals.interview_vnext.turn_report import (
    TrialScore,
    build_batch_report,
    build_case_report,
    render_markdown,
)

CASES_ROOT = Path(__file__).resolve().parents[1] / "evals/interview_vnext/cases"
TRIAL_STARTED_AT = datetime(2026, 7, 18, 9, 0, tzinfo=UTC)
OUTPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-output.v1.schema.json"
)
PROFILE = TurnInterpretProviderProfile(
    provider="scripted", requested_model="scripted-reference"
)


@pytest.fixture(scope="module")
def suite():
    return load_suite(CASES_ROOT, suite_version="turn-interpret-pilot.v1")


@pytest_asyncio.fixture
async def tracked_cleanup(postgres_session_factory):
    created = []
    yield created
    await cleanup_trial_rows(postgres_session_factory, created)


def usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=800, output_tokens=120, cache_read_tokens=0,
        cache_write_tokens=0, reasoning_tokens=0,
    )


def reference_llm_factory(suite):
    index_by_id = {c.case.case_id: i for i, c in enumerate(suite.runtime_inputs)}

    def factory(inputs, trial_id) -> LlmPort:
        idx = index_by_id[inputs.case.case_id]
        evaluation = suite.evaluation_contracts[idx]
        output = materialize_reference_output(
            inputs, evaluation.reference_output, trial_id=trial_id
        )
        ids = trial_scoped_ids(trial_id)
        attempt_id = uuid5(ids.operation_id, "attempt/1")
        visible = build_inline_artifact(
            artifact_id=uuid5(attempt_id, "visible-response"),
            kind="model.visible_response",
            media_type="application/json",
            payload=output.model_dump(mode="json"),
            run_id=ids.run_id,
            session_id=ids.session_id,
            turn_id=turn_uuid(trial_id, inputs.case.target_turn_key),
            operation_id=ids.operation_id,
            attempt_id=attempt_id,
            created_at=TRIAL_STARTED_AT,
            contains_test_data=True,
        )
        return ScriptedLlmPort(
            {
                "turn.interpret": [
                    ScriptedStep(
                        expected_attempt=1,
                        outcome=ModelOutcome.SUCCEEDED,
                        finish_reason=FinishReason.COMPLETED,
                        parsed_output=build_structured_payload(
                            schema_id=OUTPUT_SCHEMA_ID, value=output
                        ),
                        visible_response_artifact=visible.ref,
                        supporting_artifacts=(visible,),
                        usage=usage(),
                    )
                ]
            }
        )

    return factory


class TimeoutLlm(LlmPort):
    """Always returns a retryable transport timeout (infrastructure-invalid)."""

    async def generate_structured(self, request) -> ModelCallEnvelope:
        completed = request.created_at + timedelta(milliseconds=1)
        result = ModelCallResult(
            run_id=request.run_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
            attempt=request.attempt,
            operation_name=request.operation_name,
            operation_definition_hash=request.operation_definition_hash,
            provider=request.provider,
            requested_model=request.requested_model,
            resolved_model=request.requested_model,
            outcome=ModelOutcome.FAILED,
            finish_reason=FinishReason.PROVIDER_ERROR,
            failure=ModelFailure(
                kind=FailureKind.TRANSPORT_TIMEOUT,
                reason_code="provider.timeout",
                retryable=True,
                safe_message="scripted timeout",
            ),
            usage=TokenUsage(limitations=("no usage after timeout",)),
            latency_ms=1,
            started_at=request.created_at,
            completed_at=completed,
            prompt_hash=request.prompt_hash,
            output_schema_id=request.output_schema_id,
            output_schema_hash=request.output_schema_hash,
            context_hash=request.context_hash,
        )
        return ModelCallEnvelope(result=result, supporting_artifacts=())


def elapsed_zero() -> float:
    return 0.0


def make_budget() -> Budget:
    return Budget(
        max_inference_calls=120,
        max_observed_cost_usd=Decimal("10.00"),
        max_wall_clock_seconds=180 * 60,
    )


# ── slot scheduling ──────────────────────────────────────────────────────────


async def test_quality_slot_fills_on_first_success(
    postgres_session_factory, suite, tracked_cleanup
):
    inputs = suite.runtime_inputs[0]
    batch_id = uuid5(NAMESPACE_URL, "batch:slot-success")
    result = await schedule_slot(
        inputs,
        batch_id=batch_id,
        case_id=inputs.case.case_id,
        slot_index=1,
        session_factory=postgres_session_factory,
        llm_factory=reference_llm_factory(suite),
        profile=PROFILE,
        trial_started_at_factory=lambda: TRIAL_STARTED_AT,
        max_trial_attempts=3,
        budget=make_budget(),
        elapsed_seconds_factory=elapsed_zero,
    )
    for _, execution, _, _ in result.executions:
        if execution is not None:
            tracked_cleanup.append(execution.ids)
    assert len(result.executions) == 1
    assert result.quality_execution is not None
    assert result.executions[0][2] == TrialDisposition.QUALITY_SCORED


async def test_infrastructure_replacement_keeps_original(
    postgres_session_factory, suite, tracked_cleanup
):
    inputs = suite.runtime_inputs[0]
    batch_id = uuid5(NAMESPACE_URL, "batch:slot-infra")
    result = await schedule_slot(
        inputs,
        batch_id=batch_id,
        case_id=inputs.case.case_id,
        slot_index=1,
        session_factory=postgres_session_factory,
        llm_factory=lambda inputs, trial_id: TimeoutLlm(),
        profile=PROFILE,
        trial_started_at_factory=lambda: TRIAL_STARTED_AT,
        max_trial_attempts=3,
        budget=make_budget(),
        elapsed_seconds_factory=elapsed_zero,
    )
    for _, execution, _, _ in result.executions:
        if execution is not None:
            tracked_cleanup.append(execution.ids)
    # 三次都 infrastructure_invalid → slot incomplete,原 trials 全保留
    assert len(result.executions) == 3
    assert all(
        d == TrialDisposition.INFRASTRUCTURE_INVALID
        for _, _, d, _ in result.executions
    )
    assert result.incomplete is True
    assert result.quality_execution is None


async def test_budget_stops_new_trials(
    postgres_session_factory, suite, tracked_cleanup
):
    inputs = suite.runtime_inputs[0]
    batch_id = uuid5(NAMESPACE_URL, "batch:budget")
    budget = Budget(
        max_inference_calls=1,
        max_observed_cost_usd=Decimal("10.00"),
        max_wall_clock_seconds=180 * 60,
    )
    with pytest.raises(BudgetExceeded):
        result = await schedule_slot(
            inputs,
            batch_id=batch_id,
            case_id=inputs.case.case_id,
            slot_index=1,
            session_factory=postgres_session_factory,
            llm_factory=lambda inputs, trial_id: TimeoutLlm(),
            profile=PROFILE,
            trial_started_at_factory=lambda: TRIAL_STARTED_AT,
            max_trial_attempts=3,
            budget=budget,
            elapsed_seconds_factory=elapsed_zero,
        )
    # 清掉已建立的第一個 trial
    tracked_cleanup.append(trial_scoped_ids(
        __import__("evals.interview_vnext.identities", fromlist=["trial_uuid"]).trial_uuid(
            __import__("evals.interview_vnext.identities", fromlist=["slot_uuid"]).slot_uuid(
                batch_id, inputs.case.case_id, 1
            ),
            1,
        )
    ))


# ── Capture export + secret scan ─────────────────────────────────────────────


async def run_one(postgres_session_factory, suite, case_id, salt):
    idx = [c.case.case_id for c in suite.runtime_inputs].index(case_id)
    inputs = suite.runtime_inputs[idx]
    trial_id = uuid5(NAMESPACE_URL, f"e6:{salt}:{case_id}")
    llm = reference_llm_factory(suite)(inputs, trial_id)
    execution = await run_trial(
        inputs,
        session_factory=postgres_session_factory,
        llm=llm,
        profile=PROFILE,
        trial_id=trial_id,
        trial_started_at=TRIAL_STARTED_AT,
    )
    return inputs, suite.evaluation_contracts[idx], execution


async def test_capture_export_validates_and_scans(
    postgres_session_factory, suite, tracked_cleanup
):
    inputs, evaluation, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", "export"
    )
    tracked_cleanup.append(execution.ids)
    bundle = await export_run_bundle(
        postgres_session_factory,
        tenant_id=execution.ids.tenant_id,
        run_id=execution.ids.run_id,
    )
    assert bundle.event_count == execution.run.event_count
    assert bundle.manifest.last_event_hash == bundle.last_event_hash
    kinds = {a.ref.kind for a in bundle.artifacts}
    assert "model.request" in kinds
    assert "capture.run_manifest" in kinds


async def test_capture_export_flags_secret(
    postgres_session_factory, suite, tracked_cleanup, monkeypatch
):
    inputs, evaluation, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", "secret"
    )
    tracked_cleanup.append(execution.ids)
    import evals.interview_vnext.capture_export as ce

    real = ce.ser.load_artifact

    def leaky(row):
        record = real(row)
        if record.ref.kind == "model.request":
            return record.model_copy(
                update={"inline_content": (record.inline_content or "") + " sk-or-ABCDEF"}
            )
        return record

    monkeypatch.setattr(ce.ser, "load_artifact", leaky)
    with pytest.raises(SecretLeakError):
        await export_run_bundle(
            postgres_session_factory,
            tenant_id=execution.ids.tenant_id,
            run_id=execution.ids.run_id,
        )


async def test_trial_bundle_is_atomic_with_integrity_manifest(
    postgres_session_factory, suite, tracked_cleanup, tmp_path
):
    inputs, evaluation, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", "bundle"
    )
    tracked_cleanup.append(execution.ids)
    bundle = await export_run_bundle(
        postgres_session_factory,
        tenant_id=execution.ids.tenant_id,
        run_id=execution.ids.run_id,
    )
    trial = build_trial_record(
        execution,
        case_id=inputs.case.case_id,
        slot_index=1,
        trial_attempt=1,
        runtime_input_hash=inputs.runtime_input_hash,
        evaluation_contract_hash=evaluation.evaluation_contract_hash,
        disposition=TrialDisposition.QUALITY_SCORED,
        reason_code=None,
        requested_model="scripted-reference",
        capture=bundle,
    )
    trial_dir = write_trial_bundle(
        tmp_path,
        trial=trial,
        capture=bundle,
        grader_results_json=[],
        review_items_json=[],
        final_state_json=execution.state_after.model_dump(mode="json"),
        candidate_output_json=None,
        verification_report_json=None,
    )
    assert (trial_dir / "trial.json").is_file()
    assert (trial_dir / "capture" / "events.jsonl").is_file()
    assert (trial_dir / "integrity-manifest.json").is_file()
    import json

    manifest = json.loads((trial_dir / "integrity-manifest.json").read_text("utf-8"))
    names = {e["path"] for e in manifest["files"]}
    assert "trial.json" in names
    assert "integrity-manifest.json" not in names  # 不含自己
    # 不覆寫既有目錄
    with pytest.raises(FileExistsError):
        write_trial_bundle(
            tmp_path,
            trial=trial,
            capture=bundle,
            grader_results_json=[],
            review_items_json=[],
            final_state_json=execution.state_after.model_dump(mode="json"),
            candidate_output_json=None,
            verification_report_json=None,
        )


# ── report aggregation ───────────────────────────────────────────────────────


def grade_execution(inputs, evaluation, execution, *, slot_index, split):
    output = trial_output(execution)
    ctx = GradingContext(
        inputs=inputs,
        gold=evaluation.gold,
        trial_id=execution.ids.trial_id,
        case_id=inputs.case.case_id,
        output=output,
        report=execution.outcome.verification_report,
        committed_kind=committed_kind(execution),
        state_before_hash=execution.state_before_hash,
        state_after_hash=execution.state_after_hash,
        evidence_status=evidence_status_map(execution),
    )
    grader_results = run_deterministic_graders(ctx)
    edges = build_candidate_edges(
        inputs, evaluation.gold, output, trial_id=execution.ids.trial_id
    )
    decisions = {edge.edge_key: ReviewDecisionLabel.EQUIVALENT for edge in edges}
    # unmatched proposals also need a decision
    matched = {e.proposal_key for e in edges}
    for p in output.observations:
        if p.proposal_key not in matched:
            decisions[("__unmatched__", p.proposal_key)] = (
                ReviewDecisionLabel.DIFFERENT
            )
    metrics = compute_trial_metrics(
        gold=evaluation.gold,
        output=output,
        edges=edges,
        decisions=decisions,
        accepted_proposal_keys=accepted_proposal_keys(execution),
    )
    return TrialScore(
        trial_id=execution.ids.trial_id,
        case_id=inputs.case.case_id,
        split=split,
        slot_index=slot_index,
        disposition=TrialDisposition.QUALITY_SCORED,
        grader_results=grader_results,
        metrics=metrics,
        review_complete=True,
        inference_calls=1,
    )


async def test_reference_batch_reaches_engineering_pass(
    postgres_session_factory, suite, tracked_cleanup
):
    scores = []
    gold_by_case = {}
    split_by_case = {}
    for inputs, evaluation in zip(
        suite.runtime_inputs, suite.evaluation_contracts, strict=True
    ):
        gold_by_case[inputs.case.case_id] = evaluation.gold
        split_by_case[inputs.case.case_id] = inputs.case.split
        for slot in (1, 2, 3):
            trial_id = uuid5(NAMESPACE_URL, f"batch-pass:{inputs.case.case_id}:{slot}")
            llm = reference_llm_factory(suite)(inputs, trial_id)
            execution = await run_trial(
                inputs,
                session_factory=postgres_session_factory,
                llm=llm,
                profile=PROFILE,
                trial_id=trial_id,
                trial_started_at=TRIAL_STARTED_AT,
            )
            tracked_cleanup.append(execution.ids)
            scores.append(
                grade_execution(
                    inputs, evaluation, execution,
                    slot_index=slot, split=inputs.case.split,
                )
            )

    review = ReviewCompleteness(
        required_review_items=len(scores),
        completed_review_items=len(scores),
        needs_sme_count=0,
        failure_traces_read=0,
        passing_trace_sample_required=8,
        passing_trace_sample_read=8,
    )
    report = build_batch_report(
        batch_id=uuid4(),
        plan_hash="sha256:" + "0" * 64,
        suite_version="turn-interpret-pilot.v1",
        suite_hash=suite.manifest.suite_hash,
        execution_mode="mocked",
        git_sha="1" * 40,
        dirty_worktree=False,
        gold_by_case=gold_by_case,
        split_by_case=split_by_case,
        scores=scores,
        review=review,
        route_clean=True,
        capture_verified=True,
        created_at=TRIAL_STARTED_AT,
    )
    assert report.decision == BatchDecision.TURN_GATE_PASS_ENGINEERING
    # §8.3:mocked batch 永不 promotion-eligible(只有 live 可)
    assert report.promotion_eligible is False
    assert all(entry.pass_pow_3 for entry in report.case_matrix)
    assert report.recall_micro.value == Decimal("1.000000")

    md = render_markdown(report)
    for forbidden in ("openrouter", "anthropic", "claude", "sk-or"):
        assert forbidden not in md.lower()
    assert "pass^3" in md.lower() or "pass^3" in md


def test_case_report_pass_pow_3_requires_three_scored(suite):
    inputs = suite.runtime_inputs[0]
    evaluation = suite.evaluation_contracts[0]
    # 只有 2 scored slots → 不可 pass^3
    from evals.interview_vnext.turn_graders import TrialMetrics
    from evals.interview_vnext.contracts import MetricResult

    def perfect_metrics():
        return TrialMetrics(
            raw_precision=MetricResult.compute(1, 1),
            committed_precision=MetricResult.compute(1, 1),
            recall=MetricResult.compute(1, 1),
            qualifier_exactness=MetricResult.compute(1, 1),
            expected_no_evidence_passed=None,
            signals_pass=True,
            insufficiency_pass=True,
            matched_pairs=(),
            false_positive_keys=(),
            missed_required_gold_ids=(),
            prevented_by_verifier_keys=(),
            review_incomplete=False,
        )

    scores = [
        TrialScore(
            trial_id=uuid4(),
            case_id=inputs.case.case_id,
            split=CaseSplit.DEVELOPMENT,
            slot_index=i,
            disposition=(
                TrialDisposition.QUALITY_SCORED
                if i < 3
                else TrialDisposition.INFRASTRUCTURE_INVALID
            ),
            grader_results=(),
            metrics=perfect_metrics(),
            review_complete=True,
        )
        for i in (1, 2, 3)
    ]
    report = build_case_report(
        inputs.case.case_id, CaseSplit.DEVELOPMENT, evaluation.gold, scores
    )
    assert report.pass_pow_3 is False
    assert report.case_decision == CaseDecision.FAIL
