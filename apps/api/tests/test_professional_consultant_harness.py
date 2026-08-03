"""End-to-end offline execution tests for the 48-slot R1 fast screen."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.professional_consultant.contracts import (
    ConsultantAction,
    NextQuestion,
    TaskDiscoveryOutput,
    TurnUnderstandOutput,
    WorkReconcileDecideOutput,
)
from app.professional_consultant.runner import (
    OperationFailureCode,
    StructuredOperationResponse,
)
from evals.professional_consultant.r1.ablation import (
    AblationArm,
    ArmId,
    HarnessProfile,
)
from evals.professional_consultant.r1.capture import (
    ResolvedResponseFacts,
    TrialStatus,
    read_trial_capture,
)
from evals.professional_consultant.r1.contracts import R1RuntimeCase
from evals.professional_consultant.r1.harness import (
    ModelTierBindings,
    run_fast_screen_offline,
)
from evals.professional_consultant.r1.loader import load_runtime_suite
from evals.professional_consultant.r1.minimal_harness import (
    MinimalTaskDiscoveryOutput,
)
from evals.professional_consultant.r1.observed_provider import (
    ScriptedObservedFailure,
    ScriptedObservedStep,
    ScriptedObservedSuccess,
)


CASES_ROOT = (
    Path(__file__).parents[1]
    / "evals"
    / "professional_consultant"
    / "r1"
    / "cases"
)


def _question(case: R1RuntimeCase, arm: AblationArm) -> NextQuestion:
    return NextQuestion(
        action=ConsultantAction.BROADEN,
        text=(
            f"請再描述一項目前由你固定負責且有明確結果的工作"
            f"（{case.metadata.case_id}-{arm.arm_id.value}）？"
        ),
        target_gap="其他穩定且可檢核的本人工作責任",
        claim_ids=(),
    )


def _success(
    output_text: str,
    *,
    case: R1RuntimeCase,
    arm: AblationArm,
    index: int,
) -> ScriptedObservedSuccess:
    return ScriptedObservedSuccess(
        response=StructuredOperationResponse(output_text=output_text),
        resolved=ResolvedResponseFacts(
            evidence_source="response",
            generation_id=(
                f"gen-{case.metadata.case_id}-{arm.arm_id.value}-{index}"
            ),
            resolved_model=f"resolved/{arm.model_tier.value}-model",
            resolved_provider=f"Provider {arm.model_tier.value}",
            resolved_endpoint=f"endpoint/{arm.model_tier.value}-1",
        ),
    )


def _successful_script(
    case: R1RuntimeCase,
    arm: AblationArm,
) -> tuple[ScriptedObservedStep, ...]:
    question = _question(case, arm)
    if arm.arm_id is ArmId.A1:
        output = MinimalTaskDiscoveryOutput(
            schema_version="minimal_task_discovery_output.v1",
            task_candidates=(),
            next_question=question,
        )
        return (_success(output.model_dump_json(), case=case, arm=arm, index=1),)
    if arm.runner_kind.value == "once":
        output = TaskDiscoveryOutput(
            schema_version="task_discovery_output.v1",
            claims=(),
            unmapped_signals=(),
            stories=(),
            work_units=(),
            decisions=(),
            task_candidates=(),
            next_question=question,
        )
        return (_success(output.model_dump_json(), case=case, arm=arm, index=1),)
    understanding = TurnUnderstandOutput(
        schema_version="turn_understand_output.v1",
        claims=(),
        unmapped_signals=(),
    )
    reconcile = WorkReconcileDecideOutput(
        schema_version="work_reconcile_decide_output.v1",
        stories=(),
        work_units=(),
        decisions=(),
        task_candidates=(),
        next_question=question,
    )
    return (
        _success(
            understanding.model_dump_json(), case=case, arm=arm, index=1
        ),
        _success(reconcile.model_dump_json(), case=case, arm=arm, index=2),
    )


@pytest.mark.asyncio
async def test_offline_fast_screen_executes_48_trials_and_80_attempts(
    tmp_path: Path,
) -> None:
    cases = load_runtime_suite(CASES_ROOT)

    summary = await run_fast_screen_offline(
        cases,
        bindings=ModelTierBindings(
            strongest="requested/strongest-alias",
            cheap="requested/cheap-alias",
        ),
        script_factory=_successful_script,
        capture_root=tmp_path,
    )

    assert summary.planned_observations == 48
    assert summary.expected_generator_calls == 80
    assert summary.terminal_trials == 48
    assert summary.actual_generator_attempts == 80
    assert summary.evaluable_observations == 48
    assert summary.failure_count == 0
    assert summary.execution_complete is True
    assert len(summary.trial_ids) == 48
    assert len(list(tmp_path.glob("*/manifest.json"))) == 48

    a1_id = f"fast-{cases[0].metadata.case_id}-A1"
    a6_id = f"fast-{cases[0].metadata.case_id}-A6"
    a1 = read_trial_capture(tmp_path, a1_id)
    a6 = read_trial_capture(tmp_path, a6_id)
    assert a1.manifest.arm.harness_profile is HarnessProfile.MINIMAL
    assert a6.manifest.arm.harness_profile is HarnessProfile.FULL
    assert a1.context_operation_input.calls[0].request.output_schema.schema_id == (
        "minimal-task-discover-output.light.v1"
    )
    assert a6.context_operation_input.calls[0].request.output_schema.schema_id == (
        "task-discover-output.light.v1"
    )
    assert a1.context_operation_input.calls[0].requested_model == (
        "requested/strongest-alias"
    )
    assert a1.trial_evidence.attempts[0].resolved is not None
    assert a1.trial_evidence.attempts[0].resolved.resolved_model == (
        "resolved/strongest-model"
    )


@pytest.mark.asyncio
async def test_stage_one_failure_is_terminal_without_inventing_call_80(
    tmp_path: Path,
) -> None:
    cases = load_runtime_suite(CASES_ROOT)
    failed_case_id = cases[0].metadata.case_id

    def script_with_one_stage_failure(
        case: R1RuntimeCase,
        arm: AblationArm,
    ) -> tuple[ScriptedObservedStep, ...]:
        if case.metadata.case_id == failed_case_id and arm.arm_id is ArmId.A2:
            return (ScriptedObservedFailure(safe_reason="provider unavailable"),)
        return _successful_script(case, arm)

    summary = await run_fast_screen_offline(
        cases,
        bindings=ModelTierBindings(
            strongest="requested/strongest-alias",
            cheap="requested/cheap-alias",
        ),
        script_factory=script_with_one_stage_failure,
        capture_root=tmp_path,
    )

    assert summary.terminal_trials == 48
    assert summary.actual_generator_attempts == 79
    assert summary.evaluable_observations == 47
    assert summary.failure_count == 1
    assert summary.execution_complete is False
    failed = read_trial_capture(tmp_path, f"fast-{failed_case_id}-A2")
    assert failed.manifest.expected_generator_calls == 2
    assert len(failed.context_operation_input.calls) == 1
    assert len(failed.trial_evidence.attempts) == 1
    assert failed.trial_evidence.status is TrialStatus.FAILED
    assert failed.trial_evidence.failure is not None
    assert failed.trial_evidence.failure.code is OperationFailureCode.PROVIDER_FAILED
