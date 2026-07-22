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
from app.interview_vnext.llm.port import (
    LlmPort,
    ModelCallEnvelope,
    ModelCallRequest,
    ResolvedModelCall,
)
from app.interview_vnext.llm.testing import (
    ScriptedLlmPort,
    ScriptedStep,
    scripted_provider_config,
    scripted_turn_binding,
)

from tests.interview_vnext_llm_fixtures import unknown_execution_evidence
from app.interview_vnext.application.durable_commands import apply_durable_command
from app.interview_vnext.application.operation_executor import TurnExecutionStatus
from app.interview_vnext.domain.commands import TransitionSessionCommand
from app.interview_vnext.domain.session import SessionStatus
from app.interview_vnext.persistence.unit_of_work import SqlAlchemyVNextUnitOfWork
from app.interview_vnext.observability.artifacts import (
    ArtifactStorage,
    build_inline_artifact,
)
from app.interview_vnext.domain.hashing import canonical_json
from app.interview_vnext.llm.context import TurnInterpretContextPacket
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
from evals.interview_vnext.fixture_builder import run_pure_reference_gate
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
    "https://caliburn.local/schemas/turn-interpret-output.v2.schema.json"
)
BINDING = scripted_turn_binding()


@pytest.fixture(scope="module")
def suite():
    return load_suite(CASES_ROOT, suite_version="turn-interpret-c1-v2-pilot.v1")


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
        output = run_pure_reference_gate(
            inputs,
            evaluation,
            trial_id=trial_id,
            base_time=TRIAL_STARTED_AT,
        ).output
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


def _rebundle_with_manifest(bundle, forged_manifest):
    """Rebuild a bundle so its ``capture.run_manifest`` artifact agrees with
    ``forged_manifest``, isolating a single manifest-root corruption dimension past
    the §6.2 self-consistency guard so a later closure step is what fails."""

    original = next(
        record for record in bundle.artifacts
        if record.ref.kind == "capture.run_manifest"
    )
    forged_record = build_inline_artifact(
        artifact_id=original.ref.artifact_id,
        kind="capture.run_manifest",
        media_type="application/json",
        payload=forged_manifest,
        run_id=original.run_id,
        session_id=original.session_id,
        created_at=original.created_at,
    )
    return replace(
        bundle,
        run=forged_manifest,
        manifest=forged_manifest,
        artifacts=tuple(
            forged_record if record.ref.kind == "capture.run_manifest" else record
            for record in bundle.artifacts
        ),
    )


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
    # Forge the run-manifest artifact to agree with the forged manifest so the §6.2
    # self-consistency guard passes and the forged root hash is caught downstream by
    # the event-chain root-vs-record check (§8.3 manifest root ref hash mismatch).
    forged = _rebundle_with_manifest(bundle, forged_manifest)
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
    unrooted = _rebundle_with_manifest(bundle, unrooted_manifest)
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
        suite_version="turn-interpret-c1-v2-pilot.v1",
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
    payload = {"schema_version": "turn_interpret_output.v2", "unexpected": True}
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
        ("committed-receipt-only", "TI-11-zero-evidence", "reference"),
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
    elif path_name == "committed-receipt-only":
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
        data["literal_observations"][0]["claim"] = "每天 999 次竄改主張"

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


# ── R5-D bounded correctness closure ─────────────────────────────────────────
#
# 這一段封住 Capture 完整性(計畫 §3.2 缺口 A/B/C + §10 byte identity + §9 stale
# golden)。A/B/C 在 R5-D code 修正前必須紅;D/E 是 characterization/golden,現在
# 就該綠(stale 語意與 re-export 決定性已由 R5-BC 建立)。


def _bundle_record_by_id(bundle, artifact_id):
    return next(
        record for record in bundle.artifacts if record.ref.artifact_id == artifact_id
    )


def _request_from_bundle(bundle, execution) -> ModelCallRequest:
    request_id = execution.outcome.checkpoint.request_artifact.artifact_id
    record = _bundle_record_by_id(bundle, request_id)
    return ModelCallRequest.model_validate_json(record.inline_content or "")


async def test_request_content_refs_are_terminal_roots(
    postgres_session_factory, suite, tracked_cleanup
):
    """缺口 A:prompt/schema/context/selection 四個 request content dependency
    必須以完整 ArtifactRef 出現在 terminal manifest roots(§5.2)。"""

    _, _, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", "r5-d-request-roots"
    )
    tracked_cleanup.append(execution.ids)
    bundle = await export_run_bundle(
        postgres_session_factory,
        tenant_id=execution.ids.tenant_id,
        run_id=execution.ids.run_id,
    )
    request = _request_from_bundle(bundle, execution)
    roots_by_id = {
        ref.artifact_id: ref for ref in bundle.manifest.root_artifacts
    }
    for content_ref in (
        request.prompt_artifact,
        request.output_schema_artifact,
        request.context_artifact,
        request.selection_manifest_artifact,
    ):
        assert roots_by_id.get(content_ref.artifact_id) == content_ref, (
            f"request content authority not a terminal root: {content_ref.kind}"
        )


async def test_bundle_revalidates_inline_prompt_record(
    postgres_session_factory, suite, tracked_cleanup
):
    """缺口 B:in-memory bundle 必須重跑 ArtifactRecord validator。對固定的
    prompt.template inline record 做 model_copy 竄改(ref 不動),避開既有 typed
    parser 會攔的 model.request/manifest,證明缺的是 revalidation 本身。"""

    _, _, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", "r5-d-revalidate"
    )
    tracked_cleanup.append(execution.ids)
    bundle = await export_run_bundle(
        postgres_session_factory,
        tenant_id=execution.ids.tenant_id,
        run_id=execution.ids.run_id,
    )
    request = _request_from_bundle(bundle, execution)
    prompt_id = request.prompt_artifact.artifact_id
    prompt_record = _bundle_record_by_id(bundle, prompt_id)
    # 尾端加一個空白:inline bytes 變了但 ref hash/byte_size 沒動 → 只有重跑
    # ArtifactRecord validator 才會發現。model_copy 刻意跳過 validator。
    tampered = prompt_record.model_copy(
        update={"inline_content": (prompt_record.inline_content or "") + " "}
    )
    poisoned = replace(
        bundle,
        artifacts=tuple(
            tampered if record.ref.artifact_id == prompt_id else record
            for record in bundle.artifacts
        ),
    )
    with pytest.raises(CaptureExportError):
        validate_capture_bundle(poisoned)


async def test_outcome_nested_ref_requires_direct_root(
    postgres_session_factory, suite, tracked_cleanup
):
    """缺口 C:outcome 的 interpretation receipt 即使還 nested 在 outcome JSON,
    少了 direct terminal root 也必須 fail closed。移 root 時同步替換 run 與
    manifest,否則會先撞 'run and manifest disagree',測不到 outcome closure。"""

    _, _, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", "r5-d-outcome-root"
    )
    tracked_cleanup.append(execution.ids)
    bundle = await export_run_bundle(
        postgres_session_factory,
        tenant_id=execution.ids.tenant_id,
        run_id=execution.ids.run_id,
    )
    target = execution.outcome.interpretation_record_ref
    assert target is not None
    assert target in bundle.manifest.root_artifacts
    remaining = tuple(
        ref for ref in bundle.manifest.root_artifacts if ref != target
    )
    stripped_manifest = type(bundle.manifest).model_validate(
        {**bundle.manifest.model_dump(), "root_artifacts": remaining}
    )
    unrooted = replace(bundle, run=stripped_manifest, manifest=stripped_manifest)
    with pytest.raises(CaptureExportError):
        validate_capture_bundle(unrooted)


def dir_file_bytes(trial_dir: Path) -> dict[str, bytes]:
    return {
        path.relative_to(trial_dir).as_posix(): path.read_bytes()
        for path in sorted(trial_dir.rglob("*"))
        if path.is_file()
    }


async def test_two_bundle_dirs_are_byte_identical(
    postgres_session_factory, suite, tracked_cleanup, tmp_path
):
    """§10:同一 durable trial 兩次 export + write 到兩個獨立目錄後,relative
    path 集合與每個 raw bytes 必須完全相等,offline regrade 不改任何 byte。"""

    inputs, evaluation, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", "r5-d-byte-identity"
    )
    tracked_cleanup.append(execution.ids)
    batch_id = uuid5(NAMESPACE_URL, "r5-d-byte-identity")

    trial_a, bundle_a, graded_a = await grade_one_trial(
        postgres_session_factory, inputs, evaluation, execution,
        batch_id=batch_id, slot_index=1, decision_labels={}, review_complete=False,
    )
    dir_a = write_trial_bundle(
        tmp_path / "export-a",
        trial=trial_a,
        capture=bundle_a,
        grader_results_json=[g.model_dump(mode="json") for g in graded_a.grader_results],
        review_items_json=[r.model_dump(mode="json") for r in graded_a.review_items],
        final_state_json=graded_a.final_state_json,
        candidate_output_json=graded_a.candidate_output_json,
        verification_report_json=graded_a.verification_report_json,
    )
    trial_b, bundle_b, graded_b = await grade_one_trial(
        postgres_session_factory, inputs, evaluation, execution,
        batch_id=batch_id, slot_index=1, decision_labels={}, review_complete=False,
    )
    dir_b = write_trial_bundle(
        tmp_path / "export-b",
        trial=trial_b,
        capture=bundle_b,
        grader_results_json=[g.model_dump(mode="json") for g in graded_b.grader_results],
        review_items_json=[r.model_dump(mode="json") for r in graded_b.review_items],
        final_state_json=graded_b.final_state_json,
        candidate_output_json=graded_b.candidate_output_json,
        verification_report_json=graded_b.verification_report_json,
    )

    before_a = dir_file_bytes(dir_a)
    before_b = dir_file_bytes(dir_b)
    assert set(before_a) == set(before_b)
    assert before_a == before_b
    assert "integrity-manifest.json" in before_a
    assert "capture/manifest.json" in before_a

    imported = import_review_decisions((), ())
    _score_trial(dir_a, inputs=inputs, evaluation=evaluation, imported=imported)
    _score_trial(dir_b, inputs=inputs, evaluation=evaluation, imported=imported)
    assert dir_file_bytes(dir_a) == before_a
    assert dir_file_bytes(dir_b) == before_b


class _PauseOncePort(LlmPort):
    """Test-only LlmPort decorator(§9.1):包住合法 provider,取得原 envelope 後
    執行一次 before_return,以 production command path 提交一筆 PAUSED transition,
    讓後續 turn interpretation 的 CAS 走 state_context_stale。不碰 production fake、
    不 SQL、不 sleep。"""

    def __init__(self, inner: LlmPort, *, session_factory, ids, trial_id) -> None:
        self._inner = inner
        self._session_factory = session_factory
        self._ids = ids
        self._trial_id = trial_id
        self.calls = 0
        self._paused = False

    async def generate_structured(self, call: ResolvedModelCall) -> ModelCallEnvelope:
        self.calls += 1
        envelope = await self._inner.generate_structured(call)
        if not self._paused:
            self._paused = True
            await self._pause(call.request)
        return envelope

    async def _pause(self, request: ModelCallRequest) -> None:
        def uow_factory() -> SqlAlchemyVNextUnitOfWork:
            return SqlAlchemyVNextUnitOfWork(self._session_factory)

        async with uow_factory() as uow:
            current = await uow.sessions.get(
                tenant_id=self._ids.tenant_id, session_id=self._ids.session_id
            )
        occurred_at = request.created_at + timedelta(milliseconds=500)
        await apply_durable_command(
            uow_factory,
            tenant_id=self._ids.tenant_id,
            session_id=self._ids.session_id,
            run_id=self._ids.run_id,
            command=TransitionSessionCommand(
                command_id=uuid5(self._trial_id, "command/r5-d-concurrent-pause"),
                expected_state_version=current.session.state_version,
                occurred_at=occurred_at,
                target_status=SessionStatus.PAUSED,
            ),
            stage="turn.receive",
            event_id=uuid5(self._trial_id, "event/r5-d-concurrent-pause"),
            command_artifact_id=uuid5(
                self._trial_id, "artifact/command/r5-d-concurrent-pause"
            ),
            reduction_artifact_id=uuid5(
                self._trial_id, "artifact/reduction/r5-d-concurrent-pause"
            ),
            committed_at=occurred_at,
            request_idempotency_key=(
                f"turn-eval:{self._trial_id}:r5-d-concurrent-pause"
            ),
        )


async def test_stale_trial_capture_golden(
    postgres_session_factory, suite, tracked_cleanup
):
    """§9:併發 pause 讓完整 run_trial finalize 成 failed,匯出的 Capture bundle
    必須 closure 通過,且 outcome 只帶 context/input/provider/report/failure,
    不得帶 receipt/domain command/reduction/turn output。"""

    idx = [c.case.case_id for c in suite.runtime_inputs].index("TI-01-single-action")
    inputs = suite.runtime_inputs[idx]
    trial_id = uuid5(NAMESPACE_URL, "r5-d:stale:TI-01")
    ids = trial_scoped_ids(trial_id)
    # 失敗也要能重跑:trial rows 一建立就登記 cleanup。
    tracked_cleanup.append(ids)
    inner = reference_llm_factory(suite)(inputs, trial_id)
    llm = _PauseOncePort(
        inner, session_factory=postgres_session_factory, ids=ids, trial_id=trial_id
    )
    execution = await run_trial(
        inputs,
        session_factory=postgres_session_factory,
        llm=llm,
        binding=BINDING, provider_config=scripted_provider_config(),
        trial_id=trial_id,
        trial_started_at=TRIAL_STARTED_AT,
    )
    outcome = execution.outcome
    assert llm.calls == 1
    assert outcome.status == TurnExecutionStatus.FAILED
    assert outcome.reason_code == "state_context_stale"
    # 只有 pause transition 落地;target turn 沒有新 Evidence/receipt。
    assert execution.state_after.session.status == SessionStatus.PAUSED
    assert execution.state_after.evidence == execution.state_before.evidence
    assert (
        execution.state_after.turn_interpretations
        == execution.state_before.turn_interpretations
    )
    # 失敗路徑的非空 refs。
    assert outcome.context_packet_ref is not None
    assert outcome.input_ref is not None
    assert outcome.provider_result_ref is not None
    assert outcome.verification_report_ref is not None
    assert outcome.failure_ref is not None
    # 禁止出現的 committed-only refs。
    assert outcome.interpretation_record_ref is None
    assert outcome.domain_command_ref is None
    assert outcome.reduction_result_ref is None
    assert outcome.turn_output_ref is None
    # Capture 匯出 + 完整性驗證(export_run_bundle 內含 validate)。
    bundle = await export_run_bundle(
        postgres_session_factory,
        tenant_id=ids.tenant_id,
        run_id=ids.run_id,
    )
    validate_capture_bundle(bundle)


# ── §8 corruption matrix ─────────────────────────────────────────────────────
#
# 所有 corruption 都從一份已通過 export_run_bundle() 的合法 bundle 複製,只改一個
# 維度,再呼叫 validate_capture_bundle()。全部 in-memory,不重跑 DB trial、不停
# trigger、不偽造整條 chain。12 個 case 的 fixture 都 seed 一筆 consultant 提問 →
# packet.question_frame 皆為 eligible,因此 frame snapshot 一定存在且 rooted,frame
# 的 unroot / tamper / semantic-hash 向量都用真 bundle 覆蓋。


async def _committed_bundle(postgres_session_factory, suite, tracked_cleanup, salt):
    _, _, execution = await run_one(
        postgres_session_factory, suite, "TI-01-single-action", salt
    )
    tracked_cleanup.append(execution.ids)
    bundle = await export_run_bundle(
        postgres_session_factory,
        tenant_id=execution.ids.tenant_id,
        run_id=execution.ids.run_id,
    )
    return execution, bundle


def _replace_record(bundle, artifact_id, new_record):
    return replace(
        bundle,
        artifacts=tuple(
            new_record if record.ref.artifact_id == artifact_id else record
            for record in bundle.artifacts
        ),
    )


def _record_of_kind(bundle, kind):
    return next(record for record in bundle.artifacts if record.ref.kind == kind)


async def test_unrooting_any_required_root_fails_closed(
    postgres_session_factory, suite, tracked_cleanup
):
    """§8.2:逐一移除 manifest 每一個 root(record 仍在、manifest artifact 同步一致),
    每一次都必須 fail closed——即使 ref 還 nested 在其他 JSON 裡。"""

    _, bundle = await _committed_bundle(
        postgres_session_factory, suite, tracked_cleanup, "r5-d-unroot-all"
    )
    assert bundle.manifest.root_artifacts  # sanity:committed run 有 roots
    for target in bundle.manifest.root_artifacts:
        stripped_manifest = type(bundle.manifest).model_validate(
            {
                **bundle.manifest.model_dump(),
                "root_artifacts": tuple(
                    ref for ref in bundle.manifest.root_artifacts if ref != target
                ),
            }
        )
        corrupt = _rebundle_with_manifest(bundle, stripped_manifest)
        with pytest.raises(CaptureExportError):
            validate_capture_bundle(corrupt)


async def test_artifact_record_tamper_dimensions_fail_closed(
    postgres_session_factory, suite, tracked_cleanup
):
    """§8.1:對代表性 inline records 逐一做單點竄改,revalidation / scope 必須攔下。"""

    _, bundle = await _committed_bundle(
        postgres_session_factory, suite, tracked_cleanup, "r5-d-tamper"
    )
    representative_kinds = (
        "prompt.template",
        "schema.output",
        "interview.context_packet.v2",
        "interview.context_selection_manifest.v2",
        "interview.context_budget_report.v2",
        "interview.turn_interpret_input.v2",
        "interview.question_frame_snapshot.v1",
        "model.request",
        "interview.turn_interpret_execution_outcome.v2",
    )
    foreign = uuid4()
    for kind in representative_kinds:
        record = _record_of_kind(bundle, kind)
        aid = record.ref.artifact_id
        tampers = {
            "inline-content": record.model_copy(
                update={"inline_content": (record.inline_content or "") + " "}
            ),
            "byte-size": record.model_copy(
                update={"ref": record.ref.model_copy(
                    update={"byte_size": record.ref.byte_size + 1}
                )}
            ),
            "content-hash": record.model_copy(
                update={"ref": record.ref.model_copy(
                    update={"content_hash": "sha256:" + "a" * 64}
                )}
            ),
            "wrong-run": record.model_copy(update={"run_id": foreign}),
            "wrong-session": record.model_copy(update={"session_id": foreign}),
            "external": record.model_copy(
                update={
                    "storage": ArtifactStorage.EXTERNAL,
                    "inline_content": None,
                    "external_uri": "s3://eval/forbidden",
                }
            ),
        }
        for dimension, mutated in tampers.items():
            corrupt = _replace_record(bundle, aid, mutated)
            with pytest.raises(CaptureExportError):
                validate_capture_bundle(corrupt)
            assert dimension  # label kept for failure locality

    # duplicate artifact ID
    duped = replace(bundle, artifacts=bundle.artifacts + (bundle.artifacts[0],))
    with pytest.raises(CaptureExportError, match="duplicate artifact"):
        validate_capture_bundle(duped)

    # missing required record (context packet) while its root stays
    packet_id = _record_of_kind(bundle, "interview.context_packet.v2").ref.artifact_id
    missing = replace(
        bundle,
        artifacts=tuple(
            record for record in bundle.artifacts
            if record.ref.artifact_id != packet_id
        ),
    )
    with pytest.raises(CaptureExportError):
        validate_capture_bundle(missing)


async def test_manifest_and_event_corruption_fail_closed(
    postgres_session_factory, suite, tracked_cleanup
):
    """§8.3:run/manifest 分歧、event body 竄改、manifest artifact 缺失/重複/內容不符。"""

    _, bundle = await _committed_bundle(
        postgres_session_factory, suite, tracked_cleanup, "r5-d-manifest"
    )

    # bundle.run != bundle.manifest
    other_run = type(bundle.manifest).model_validate(
        {**bundle.manifest.model_dump(), "event_count": bundle.manifest.event_count + 1}
    )
    with pytest.raises(CaptureExportError, match="run and manifest disagree"):
        validate_capture_bundle(replace(bundle, run=other_run))

    # manifest self-consistency:artifact 內容與 bundle.manifest 不同
    drifted = type(bundle.manifest).model_validate(
        {**bundle.manifest.model_dump(), "event_count": bundle.manifest.event_count + 1}
    )
    with pytest.raises(CaptureExportError, match="run and manifest disagree|disagrees"):
        validate_capture_bundle(replace(bundle, run=drifted, manifest=drifted))

    # manifest artifact 缺失
    manifest_id = _record_of_kind(bundle, "capture.run_manifest").ref.artifact_id
    without_manifest = replace(
        bundle,
        artifacts=tuple(
            record for record in bundle.artifacts
            if record.ref.artifact_id != manifest_id
        ),
    )
    with pytest.raises(CaptureExportError, match="exactly one run manifest"):
        validate_capture_bundle(without_manifest)

    # manifest artifact 重複
    manifest_record = _record_of_kind(bundle, "capture.run_manifest")
    duplicate_manifest = replace(
        bundle, artifacts=bundle.artifacts + (manifest_record,)
    )
    with pytest.raises(CaptureExportError, match="duplicate artifact|exactly one run manifest"):
        validate_capture_bundle(duplicate_manifest)

    # event body 竄改但保留舊 event hash
    events = list(bundle.events)
    victim = events[-1]
    events[-1] = victim.model_copy(update={"stage": victim.stage + "-tampered"})
    with pytest.raises(CaptureExportError):
        validate_capture_bundle(replace(bundle, events=tuple(events)))


async def test_foreign_operation_scope_fails_closed(
    postgres_session_factory, suite, tracked_cleanup
):
    """§8.4:context/outcome 指向 foreign operation 的 artifact 必須 fail。"""

    _, bundle = await _committed_bundle(
        postgres_session_factory, suite, tracked_cleanup, "r5-d-foreign-op"
    )
    foreign = uuid4()
    for kind in (
        "interview.context_packet.v2",
        "interview.turn_interpret_input.v2",
        "interview.question_frame_snapshot.v1",
        "prompt.template",
        "model.request",
        "interview.turn_interpret_verification_report.v2",
        "interview.turn_interpret_execution_outcome.v2",
    ):
        record = _record_of_kind(bundle, kind)
        mutated = record.model_copy(update={"operation_id": foreign})
        corrupt = _replace_record(bundle, record.ref.artifact_id, mutated)
        with pytest.raises(CaptureExportError, match="scope mismatch"):
            validate_capture_bundle(corrupt)


async def test_stale_bundle_requires_report_and_failure_roots(
    postgres_session_factory, suite, tracked_cleanup
):
    """§8.4:stale failed bundle 少了 verification report 或 failure root 都必須 fail。"""

    idx = [c.case.case_id for c in suite.runtime_inputs].index("TI-01-single-action")
    inputs = suite.runtime_inputs[idx]
    trial_id = uuid5(NAMESPACE_URL, "r5-d:stale-matrix:TI-01")
    ids = trial_scoped_ids(trial_id)
    tracked_cleanup.append(ids)
    inner = reference_llm_factory(suite)(inputs, trial_id)
    llm = _PauseOncePort(
        inner, session_factory=postgres_session_factory, ids=ids, trial_id=trial_id
    )
    execution = await run_trial(
        inputs,
        session_factory=postgres_session_factory,
        llm=llm,
        binding=BINDING, provider_config=scripted_provider_config(),
        trial_id=trial_id,
        trial_started_at=TRIAL_STARTED_AT,
    )
    bundle = await export_run_bundle(
        postgres_session_factory, tenant_id=ids.tenant_id, run_id=ids.run_id
    )
    for target in (
        execution.outcome.verification_report_ref,
        execution.outcome.failure_ref,
    ):
        assert target is not None
        stripped = type(bundle.manifest).model_validate(
            {
                **bundle.manifest.model_dump(),
                "root_artifacts": tuple(
                    ref for ref in bundle.manifest.root_artifacts if ref != target
                ),
            }
        )
        with pytest.raises(CaptureExportError):
            validate_capture_bundle(_rebundle_with_manifest(bundle, stripped))


async def test_schema_invalid_requires_every_attempt_provider_authority(
    postgres_session_factory, suite, tracked_cleanup
):
    """§8.4:schema-invalid 兩 attempt,少任一 attempt 的 provider result root 都必須 fail。"""

    idx = [c.case.case_id for c in suite.runtime_inputs].index("TI-01-single-action")
    inputs = suite.runtime_inputs[idx]
    trial_id = uuid5(NAMESPACE_URL, "r5-d:schema-invalid:TI-01")
    ids = trial_scoped_ids(trial_id)
    tracked_cleanup.append(ids)
    llm = invalid_output_llm(inputs, trial_id)
    execution = await run_trial(
        inputs,
        session_factory=postgres_session_factory,
        llm=llm,
        binding=BINDING, provider_config=scripted_provider_config(),
        trial_id=trial_id,
        trial_started_at=TRIAL_STARTED_AT,
    )
    assert execution.outcome.reason_code == "output_schema_invalid"
    bundle = await export_run_bundle(
        postgres_session_factory, tenant_id=ids.tenant_id, run_id=ids.run_id
    )
    provider_results = tuple(
        ref for ref in bundle.manifest.root_artifacts if ref.kind == "model.result"
    )
    assert len(provider_results) == 2  # 兩次 attempt 都 root
    for target in provider_results:
        stripped = type(bundle.manifest).model_validate(
            {
                **bundle.manifest.model_dump(),
                "root_artifacts": tuple(
                    ref for ref in bundle.manifest.root_artifacts if ref != target
                ),
            }
        )
        with pytest.raises(CaptureExportError):
            validate_capture_bundle(_rebundle_with_manifest(bundle, stripped))


async def test_receipt_only_zero_evidence_is_a_legal_bundle(
    postgres_session_factory, suite, tracked_cleanup
):
    """§8.4:receipt-only(accepted Evidence 為 0)是合法 committed bundle,不得判 corruption。"""

    _, _, execution = await run_one(
        postgres_session_factory, suite, "TI-11-zero-evidence", "r5-d-receipt-only"
    )
    tracked_cleanup.append(execution.ids)
    assert execution.outcome.status == TurnExecutionStatus.COMMITTED
    assert execution.outcome.accepted_evidence == ()
    assert execution.outcome.interpretation_record_ref is not None
    assert execution.outcome.domain_command_ref is not None
    assert execution.outcome.reduction_result_ref is not None
    bundle = await export_run_bundle(
        postgres_session_factory,
        tenant_id=execution.ids.tenant_id,
        run_id=execution.ids.run_id,
    )
    validate_capture_bundle(bundle)  # 不得 raise


async def test_committed_frame_snapshot_is_rooted(
    postgres_session_factory, suite, tracked_cleanup
):
    """§5.3:eligible frame 的 snapshot 必須存在且 rooted(12-case fixture 都 seed 一筆
    consultant 提問,packet.question_frame 皆為 eligible)。其餘 frame corruption(unroot、
    content-tamper、byte/hash/scope、foreign operation)由 §8 matrix 覆蓋。"""

    _, bundle = await _committed_bundle(
        postgres_session_factory, suite, tracked_cleanup, "r5-d-frame"
    )
    packet_record = _record_of_kind(bundle, "interview.context_packet.v2")
    packet = TurnInterpretContextPacket.model_validate_json(packet_record.inline_content)
    assert packet.question_frame is not None
    frame_record = _record_of_kind(bundle, "interview.question_frame_snapshot.v1")
    root_ids = {ref.artifact_id for ref in bundle.manifest.root_artifacts}
    assert frame_record.ref.artifact_id in root_ids
