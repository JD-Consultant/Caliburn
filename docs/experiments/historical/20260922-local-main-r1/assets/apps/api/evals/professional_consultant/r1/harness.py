"""Offline execution of the exact ADR 0040 R1 fast-screen matrix."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, model_validator

from app.professional_consultant.contracts import (
    Identifier,
    ShortText,
    TaskDiscoveryOutput,
)
from app.professional_consultant.prompts import PromptProfile
from app.professional_consultant.runner import (
    OperationFailure,
    OperationRunError,
    run_task_discovery_once,
    run_task_discovery_two_stage,
)

from .ablation import (
    AblationArm,
    HarnessProfile,
    ModelTier,
    RunnerKind,
    build_fast_screen_plan,
)
from .capture import (
    ContextOperationInputCapture,
    SourceStateSnapshot,
    TrialCaptureBundle,
    TrialEvidence,
    TrialStatus,
    read_trial_capture,
    write_trial_capture,
)
from .contracts import R1EvalModel, R1RuntimeCase
from .minimal_harness import (
    MinimalTaskDiscoveryOutput,
    run_minimal_task_discovery_once,
)
from .observed_provider import (
    ObservedScriptedProvider,
    ScriptedObservedStep,
)


class ModelTierBindings(R1EvalModel):
    """Logical tiers are bound by the caller; T3 chooses no live model slug."""

    strongest: ShortText
    cheap: ShortText

    def requested_model_for(self, tier: ModelTier) -> str:
        if tier is ModelTier.STRONGEST:
            return self.strongest
        return self.cheap


class TrialScriptFactory(Protocol):
    def __call__(
        self, case: R1RuntimeCase, arm: AblationArm
    ) -> tuple[ScriptedObservedStep, ...]: ...


class FastScreenRunSummary(R1EvalModel):
    schema_version: Literal["r1_fast_screen_run_summary.v1"]
    planned_observations: Literal[48]
    expected_generator_calls: Literal[80]
    terminal_trials: int = Field(ge=0, le=48)
    actual_generator_attempts: int = Field(ge=0, le=80)
    evaluable_observations: int = Field(ge=0, le=48)
    failure_count: int = Field(ge=0, le=48)
    execution_complete: bool
    trial_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def actual_counts_are_consistent(self) -> "FastScreenRunSummary":
        if self.evaluable_observations + self.failure_count != self.terminal_trials:
            raise ValueError("terminal trial counts are inconsistent")
        expected_complete = (
            self.terminal_trials == 48
            and self.actual_generator_attempts == 80
            and self.evaluable_observations == 48
            and self.failure_count == 0
        )
        if self.execution_complete is not expected_complete:
            raise ValueError("execution_complete does not match actual evidence")
        return self


async def run_fast_screen_offline(
    cases: tuple[R1RuntimeCase, ...],
    *,
    bindings: ModelTierBindings,
    script_factory: TrialScriptFactory,
    capture_root: Path,
) -> FastScreenRunSummary:
    """Execute 48 offline slots and derive actual counts from written evidence."""

    plan = build_fast_screen_plan(cases)
    cases_by_id = {case.metadata.case_id: case for case in cases}
    published_trial_ids: list[str] = []

    for trial in plan.trials:
        case = cases_by_id[trial.case_id]
        arm = trial.arm
        provider = ObservedScriptedProvider(
            requested_model=bindings.requested_model_for(arm.model_tier),
            steps=script_factory(case, arm),
        )
        result: TaskDiscoveryOutput | MinimalTaskDiscoveryOutput | None = None
        failure: OperationFailure | None = None
        try:
            if arm.harness_profile is HarnessProfile.MINIMAL:
                result = await run_minimal_task_discovery_once(
                    case.runtime_input, provider=provider
                )
            elif arm.runner_kind is RunnerKind.ONCE:
                result = await run_task_discovery_once(
                    case.runtime_input,
                    provider=provider,
                    prompt_profile=PromptProfile.FULL,
                    schema_profile=arm.schema_profile,
                )
            else:
                result = await run_task_discovery_two_stage(
                    case.runtime_input,
                    provider=provider,
                    schema_profile=arm.schema_profile,
                )
        except OperationRunError as exc:
            failure = exc.failure

        status = (
            TrialStatus.SUCCEEDED if failure is None else TrialStatus.FAILED
        )
        source_state = SourceStateSnapshot(
            schema_version="r1_source_state_snapshot.v1",
            trial_id=trial.trial_id,
            case_id=trial.case_id,
            arm_id=arm.arm_id,
            runtime_case=case,
        )
        context = ContextOperationInputCapture(
            schema_version="r1_context_operation_input.v1",
            trial_id=trial.trial_id,
            case_id=trial.case_id,
            arm_id=arm.arm_id,
            calls=tuple(provider.operation_inputs),
        )
        evidence = TrialEvidence(
            schema_version="r1_trial_evidence.v1",
            trial_id=trial.trial_id,
            case_id=trial.case_id,
            arm_id=arm.arm_id,
            status=status,
            attempts=tuple(provider.attempts),
            result=result,
            failure=failure,
        )
        write_trial_capture(
            capture_root,
            TrialCaptureBundle(
                arm=arm,
                source_state=source_state,
                context_operation_input=context,
                trial_evidence=evidence,
            ),
        )
        published_trial_ids.append(trial.trial_id)

    captures = tuple(
        read_trial_capture(capture_root, trial_id)
        for trial_id in published_trial_ids
    )
    terminal_trials = len(captures)
    actual_attempts = sum(
        len(capture.trial_evidence.attempts) for capture in captures
    )
    evaluable = sum(
        capture.trial_evidence.status is TrialStatus.SUCCEEDED
        for capture in captures
    )
    failures = terminal_trials - evaluable
    complete = (
        terminal_trials == plan.planned_observations
        and actual_attempts == plan.expected_generator_calls
        and evaluable == plan.planned_observations
    )
    return FastScreenRunSummary(
        schema_version="r1_fast_screen_run_summary.v1",
        planned_observations=48,
        expected_generator_calls=80,
        terminal_trials=terminal_trials,
        actual_generator_attempts=actual_attempts,
        evaluable_observations=evaluable,
        failure_count=failures,
        execution_complete=complete,
        trial_ids=tuple(published_trial_ids),
    )
