"""V3-5 E6:mocked batch scheduler、Capture export、bundle、report(§18.5)。

需要 real PostgreSQL(run_trial 走 production durable stack)。涵蓋:36 成功
trial 填滿 slot、每 adapter call 一次 POST、infrastructure replacement 保留原
trial、budget 停線、Capture 匯出與 secret scan、atomic bundle 與 integrity
manifest、case/batch report 與 pass^3、markdown 去 provider identity。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
import pytest_asyncio

from app.interview_vnext.llm.result import (
    FailureKind,
    FinishReason,
    ModelCallResult,
    ModelFailure,
    ModelOutcome,
    TokenUsage,
    build_structured_payload,
)
from app.interview_vnext.llm.port import LlmPort, ModelCallEnvelope, ResolvedModelCall
from app.interview_vnext.llm.testing import (
    ScriptedLlmPort,
    ScriptedStep,
    scripted_provider_config,
    scripted_turn_binding,
)

from tests.interview_vnext_llm_fixtures import unknown_execution_evidence
from app.interview_vnext.observability.artifacts import build_inline_artifact
from app.interview_vnext.domain.hashing import canonical_json
from evals.interview_vnext.batch_orchestrator import grade_execution
from evals.interview_vnext.capture_export import (
    CaptureExportError,
    SecretLeakError,
    export_run_bundle,
    validate_capture_bundle,
)
from evals.interview_vnext.contracts import (
    BatchDecision,
    CaseDecision,
    CaseSplit,
    ReviewCompleteness,
    TrialDisposition,
)
from evals.interview_vnext.fixture_builder import materialize_reference_output
from evals.interview_vnext.identities import trial_scoped_ids, turn_uuid
from evals.interview_vnext.live_batch import (
    LiveBatchError,
    _score_trial,
    _verify_trial_integrity,
)
from evals.interview_vnext.live_wiring import openrouter_attempt_records
from evals.interview_vnext.loader import load_suite
from evals.interview_vnext.review import import_review_decisions
from evals.interview_vnext.scheduler import (
    Budget,
    BudgetExceeded,
    build_trial_record,
    classify_disposition,
    schedule_slot,
    write_trial_bundle,
)
from evals.interview_vnext.turn_eval_runner import cleanup_trial_rows, run_trial
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
BINDING = scripted_turn_binding()


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

    async def generate_structured(self, call: ResolvedModelCall) -> ModelCallEnvelope:
        request = call.request
        binding = call.binding
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
            binding_id=binding.binding_id,
            binding_hash=binding.binding_hash,
            gateway_provider=binding.gateway_provider,
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
        return ModelCallEnvelope(
            result=result,
            execution_evidence=unknown_execution_evidence(
                binding, usage=TokenUsage(limitations=("no usage after timeout",))
            ),
            supporting_artifacts=(),
        )


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
        binding=BINDING, provider_config=scripted_provider_config(),
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
        binding=BINDING, provider_config=scripted_provider_config(),
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
            binding=BINDING, provider_config=scripted_provider_config(),
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
        binding=BINDING, provider_config=scripted_provider_config(),
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


async def test_capture_bundle_rejects_deleted_tampered_and_unrooted_authority(
    postgres_session_factory, suite, tracked_cleanup
):
    _, _, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", "capture-corruption"
    )
    tracked_cleanup.append(execution.ids)
    bundle = await export_run_bundle(
        postgres_session_factory,
        tenant_id=execution.ids.tenant_id,
        run_id=execution.ids.run_id,
    )
    config_root = next(
        ref for ref in bundle.manifest.root_artifacts if ref.kind == "provider.config"
    )

    deleted = replace(
        bundle,
        artifacts=tuple(
            record
            for record in bundle.artifacts
            if record.ref.artifact_id != config_root.artifact_id
        ),
    )
    with pytest.raises(CaptureExportError, match="absent|missing"):
        validate_capture_bundle(deleted)

    forged_ref = config_root.model_copy(
        update={"content_hash": "sha256:" + "f" * 64}
    )
    forged_roots = tuple(
        forged_ref if ref == config_root else ref
        for ref in bundle.manifest.root_artifacts
    )
    forged_manifest = type(bundle.manifest).model_validate(
        {
            **bundle.manifest.model_dump(),
            "root_artifacts": forged_roots,
        }
    )
    forged = replace(bundle, run=forged_manifest, manifest=forged_manifest)
    with pytest.raises(CaptureExportError, match="root artifact reference mismatch"):
        validate_capture_bundle(forged)

    # The provider-config ref remains nested in model.request and the artifact
    # remains present, but removing its direct root must still fail closure.
    unrooted_manifest = type(bundle.manifest).model_validate(
        {
            **bundle.manifest.model_dump(),
            "root_artifacts": tuple(
                ref for ref in bundle.manifest.root_artifacts if ref != config_root
            ),
        }
    )
    unrooted = replace(
        bundle, run=unrooted_manifest, manifest=unrooted_manifest
    )
    with pytest.raises(CaptureExportError, match="omits a request authority root"):
        validate_capture_bundle(unrooted)


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


async def grade_one_trial(
    session_factory, inputs, evaluation, execution, *, batch_id, slot_index,
    decision_labels=None, review_complete=True,
):
    """Online canonical path(§10.1):export → build_trial_record → grade。"""

    bundle = await export_run_bundle(
        session_factory,
        tenant_id=execution.ids.tenant_id,
        run_id=execution.ids.run_id,
    )
    disposition, reason = classify_disposition(execution)
    trial = build_trial_record(
        execution,
        case_id=inputs.case.case_id,
        slot_index=slot_index,
        trial_attempt=1,
        runtime_input_hash=inputs.runtime_input_hash,
        evaluation_contract_hash=evaluation.evaluation_contract_hash,
        disposition=disposition,
        reason_code=reason,
        requested_model="scripted-reference",
        capture=bundle,
        attempt_records=openrouter_attempt_records(bundle),
    )
    graded = grade_execution(
        inputs, evaluation, execution,
        batch_id=batch_id,
        trial_record=trial,
        decision_labels=decision_labels,
        review_complete=review_complete,
    )
    return trial, bundle, graded


async def test_reexport_and_regrade_preserve_capture_hashes(
    postgres_session_factory, suite, tracked_cleanup
):
    inputs, evaluation, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", "reexport-regrade"
    )
    tracked_cleanup.append(execution.ids)
    batch_id = uuid5(NAMESPACE_URL, "capture-reexport-regrade")

    first_trial, first_bundle, first_graded = await grade_one_trial(
        postgres_session_factory,
        inputs,
        evaluation,
        execution,
        batch_id=batch_id,
        slot_index=1,
    )
    second_trial, second_bundle, second_graded = await grade_one_trial(
        postgres_session_factory,
        inputs,
        evaluation,
        execution,
        batch_id=batch_id,
        slot_index=1,
    )

    assert second_trial == first_trial
    assert second_graded == first_graded
    assert second_bundle.manifest == first_bundle.manifest
    assert tuple(event.event_hash for event in second_bundle.events) == tuple(
        event.event_hash for event in first_bundle.events
    )
    assert tuple(ref.content_hash for ref in second_bundle.manifest.root_artifacts) == tuple(
        ref.content_hash for ref in first_bundle.manifest.root_artifacts
    )


async def test_reference_batch_reaches_engineering_pass(
    postgres_session_factory, suite, tracked_cleanup
):
    scores = []
    gold_by_case = {}
    split_by_case = {}
    batch_id = uuid5(NAMESPACE_URL, "batch-pass")
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
                binding=BINDING, provider_config=scripted_provider_config(),
                trial_id=trial_id,
                trial_started_at=TRIAL_STARTED_AT,
            )
            tracked_cleanup.append(execution.ids)
            _trial, _bundle, graded = await grade_one_trial(
                postgres_session_factory, inputs, evaluation, execution,
                batch_id=batch_id, slot_index=slot,
            )
            scores.append(graded.score)

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


# ── §10.2 grading determinism:online/offline 同一 builder、byte-equal ────────


def invalid_output_llm(inputs, trial_id) -> ScriptedLlmPort:
    """兩次 schema-invalid provider success → terminal ``output_schema_invalid``。"""

    ids = trial_scoped_ids(trial_id)
    payload = {"schema_version": "turn_interpret_output.v1", "unexpected": True}
    steps = []
    for attempt in (1, 2):
        attempt_id = uuid5(ids.operation_id, f"attempt/{attempt}")
        visible = build_inline_artifact(
            artifact_id=uuid5(attempt_id, "visible-response"),
            kind="model.visible_response",
            media_type="application/json",
            payload=payload,
            run_id=ids.run_id,
            session_id=ids.session_id,
            turn_id=turn_uuid(trial_id, inputs.case.target_turn_key),
            operation_id=ids.operation_id,
            attempt_id=attempt_id,
            created_at=TRIAL_STARTED_AT,
            contains_test_data=True,
        )
        steps.append(
            ScriptedStep(
                expected_attempt=attempt,
                outcome=ModelOutcome.SUCCEEDED,
                finish_reason=FinishReason.COMPLETED,
                parsed_output=build_structured_payload(
                    schema_id=OUTPUT_SCHEMA_ID, value=payload
                ),
                visible_response_artifact=visible.ref,
                supporting_artifacts=(visible,),
                usage=usage(),
            )
        )
    return ScriptedLlmPort({"turn.interpret": steps})


async def run_golden_path(
    postgres_session_factory, suite, output_dir, tracked_cleanup,
    *, path_name, case_id, llm_kind,
):
    idx = [c.case.case_id for c in suite.runtime_inputs].index(case_id)
    inputs = suite.runtime_inputs[idx]
    evaluation = suite.evaluation_contracts[idx]
    trial_id = uuid5(NAMESPACE_URL, f"determinism:{path_name}:{case_id}")
    # 失敗也要能重跑:trial rows 一建立就登記 cleanup,不等測試主體
    tracked_cleanup.append(trial_scoped_ids(trial_id))
    if llm_kind == "reference":
        llm = reference_llm_factory(suite)(inputs, trial_id)
    else:
        llm = invalid_output_llm(inputs, trial_id)
    execution = await run_trial(
        inputs,
        session_factory=postgres_session_factory,
        llm=llm,
        binding=BINDING, provider_config=scripted_provider_config(),
        trial_id=trial_id,
        trial_started_at=TRIAL_STARTED_AT,
    )
    trial, bundle, graded = await grade_one_trial(
        postgres_session_factory, inputs, evaluation, execution,
        batch_id=uuid5(NAMESPACE_URL, f"determinism-batch:{path_name}"),
        slot_index=1,
        decision_labels={},
        review_complete=False,
    )
    trial_dir = write_trial_bundle(
        output_dir,
        trial=trial,
        capture=bundle,
        grader_results_json=[
            g.model_dump(mode="json") for g in graded.grader_results
        ],
        review_items_json=[
            r.model_dump(mode="json") for r in graded.review_items
        ],
        final_state_json=graded.final_state_json,
        candidate_output_json=graded.candidate_output_json,
        verification_report_json=graded.verification_report_json,
    )
    return inputs, evaluation, execution, trial, graded, trial_dir


def dir_file_hashes(trial_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(trial_dir).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(trial_dir.rglob("*"))
        if path.is_file()
    }


def _rewrite_json(path: Path, mutate) -> None:
    data = json.loads(path.read_text("utf-8"))
    mutate(data)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "path_name,case_id,llm_kind",
    [
        ("committed-evidence", "TI-01-single-action", "reference"),
        ("committed-noop", "TI-11-zero-evidence", "reference"),
        ("schema-invalid", "TI-01-single-action", "invalid"),
    ],
)
async def test_grading_golden_paths_are_online_offline_byte_equal(
    postgres_session_factory, suite, tracked_cleanup, tmp_path,
    path_name, case_id, llm_kind,
):
    inputs, evaluation, execution, trial, graded, trial_dir = await run_golden_path(
        postgres_session_factory, suite, tmp_path, tracked_cleanup,
        path_name=path_name, case_id=case_id, llm_kind=llm_kind,
    )

    if path_name == "schema-invalid":
        assert trial.terminal_outcome == "failed"
        assert trial.terminal_reason_code == "output_schema_invalid"
        assert len(trial.attempts) == 2  # 一次 schema repair 後 terminal
        schema_grade = next(
            g for g in graded.grader_results if g.grader_name == "output_schema"
        )
        assert schema_grade.reason_code == "output_schema_invalid"
    elif path_name == "committed-noop":
        assert trial.terminal_outcome == "committed"
        assert trial.verifier_accepted_count == 0
    else:
        assert trial.terminal_outcome == "committed"
        assert (trial.verifier_accepted_count or 0) > 0

    before = dir_file_hashes(trial_dir)
    imported = import_review_decisions((), ())
    online_json = canonical_json(
        [g.model_dump(mode="json") for g in graded.grader_results]
    )
    stored_json = canonical_json(
        json.loads((trial_dir / "grader-results.json").read_text("utf-8"))
    )
    assert stored_json == online_json

    score, _items = _score_trial(
        trial_dir, inputs=inputs, evaluation=evaluation, imported=imported
    )
    offline_json = canonical_json(
        [g.model_dump(mode="json") for g in score.grader_results]
    )
    assert offline_json == online_json
    assert score.metrics == graded.score.metrics
    assert score.disposition == graded.score.disposition
    assert score.inference_calls == graded.score.inference_calls
    assert score.observed_cost_usd == graded.score.observed_cost_usd

    # 第二、三次 regrade 不得改動任何 bundle 檔案(§10.2)
    _score_trial(trial_dir, inputs=inputs, evaluation=evaluation, imported=imported)
    _score_trial(trial_dir, inputs=inputs, evaluation=evaluation, imported=imported)
    assert dir_file_hashes(trial_dir) == before
    assert _verify_trial_integrity(trial_dir) is True


async def test_tampered_bundle_fails_integrity_or_grader_drift(
    postgres_session_factory, suite, tracked_cleanup, tmp_path,
):
    imported = import_review_decisions((), ())

    # 竄改 trial.json 的 terminal_reason_code(grader 輸入)→ drift
    inputs, evaluation, execution, _trial, _graded, trial_dir = await run_golden_path(
        postgres_session_factory, suite, tmp_path / "reason", tracked_cleanup,
        path_name="tamper-reason", case_id="TI-01-single-action",
        llm_kind="invalid",
    )
    _rewrite_json(
        trial_dir / "trial.json",
        lambda data: data.update(terminal_reason_code="tampered_reason"),
    )
    assert _verify_trial_integrity(trial_dir) is False
    with pytest.raises(LiveBatchError, match="grader drift"):
        _score_trial(
            trial_dir, inputs=inputs, evaluation=evaluation, imported=imported
        )

    # 竄改 candidate-output.json(grader 輸入)→ drift
    inputs2, evaluation2, execution2, _t2, _g2, dir2 = await run_golden_path(
        postgres_session_factory, suite, tmp_path / "candidate", tracked_cleanup,
        path_name="tamper-candidate", case_id="TI-01-single-action",
        llm_kind="reference",
    )

    def poison_claim(data):
        data["observations"][0]["claim"] = "每天 999 次竄改主張"

    _rewrite_json(dir2 / "candidate-output.json", poison_claim)
    assert _verify_trial_integrity(dir2) is False
    with pytest.raises(LiveBatchError, match="grader drift"):
        _score_trial(dir2, inputs=inputs2, evaluation=evaluation2, imported=imported)

    # verification-report / final-state 竄改:integrity manifest 必須抓到
    inputs3, evaluation3, execution3, _t3, _g3, dir3 = await run_golden_path(
        postgres_session_factory, suite, tmp_path / "state", tracked_cleanup,
        path_name="tamper-state", case_id="TI-11-zero-evidence",
        llm_kind="reference",
    )
    _rewrite_json(
        dir3 / "final-state.json",
        lambda data: data["session"].update(reference_snapshot_id="tampered"),
    )
    _rewrite_json(
        dir3 / "verification-report.json",
        lambda data: data.update(output_hash="sha256:" + "f" * 64),
    )
    assert _verify_trial_integrity(dir3) is False


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
