"""Exact ADR 0040 ablation registry and fast-screen plan."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import model_validator

from app.professional_consultant.contracts import Identifier
from app.professional_consultant.schema_projection import SchemaProfile

from .contracts import R1EvalModel, R1RuntimeCase, SourceType


class ArmId(StrEnum):
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    A6 = "A6"


class ModelTier(StrEnum):
    STRONGEST = "strongest"
    CHEAP = "cheap"


class RunnerKind(StrEnum):
    ONCE = "once"
    TWO_STAGE = "two_stage"


class HarnessProfile(StrEnum):
    """The whole harness bundle, not merely the prompt profile."""

    MINIMAL = "minimal"
    FULL = "full"


class AblationArm(R1EvalModel):
    arm_id: ArmId
    model_tier: ModelTier
    schema_profile: SchemaProfile
    runner_kind: RunnerKind
    harness_profile: HarnessProfile
    expected_generator_calls: Literal[1, 2]

    @model_validator(mode="after")
    def call_count_matches_runner(self) -> "AblationArm":
        expected = 1 if self.runner_kind is RunnerKind.ONCE else 2
        if self.expected_generator_calls != expected:
            raise ValueError("expected generator calls must match runner kind")
        return self


# Literal registry: do not replace with a Cartesian-product generator.
ABLATION_ARMS: tuple[AblationArm, ...] = (
    AblationArm(
        arm_id=ArmId.A1,
        model_tier=ModelTier.STRONGEST,
        schema_profile=SchemaProfile.LIGHT,
        runner_kind=RunnerKind.ONCE,
        harness_profile=HarnessProfile.MINIMAL,
        expected_generator_calls=1,
    ),
    AblationArm(
        arm_id=ArmId.A2,
        model_tier=ModelTier.STRONGEST,
        schema_profile=SchemaProfile.LIGHT,
        runner_kind=RunnerKind.TWO_STAGE,
        harness_profile=HarnessProfile.FULL,
        expected_generator_calls=2,
    ),
    AblationArm(
        arm_id=ArmId.A3,
        model_tier=ModelTier.STRONGEST,
        schema_profile=SchemaProfile.HEAVY,
        runner_kind=RunnerKind.TWO_STAGE,
        harness_profile=HarnessProfile.FULL,
        expected_generator_calls=2,
    ),
    AblationArm(
        arm_id=ArmId.A4,
        model_tier=ModelTier.CHEAP,
        schema_profile=SchemaProfile.LIGHT,
        runner_kind=RunnerKind.TWO_STAGE,
        harness_profile=HarnessProfile.FULL,
        expected_generator_calls=2,
    ),
    AblationArm(
        arm_id=ArmId.A5,
        model_tier=ModelTier.CHEAP,
        schema_profile=SchemaProfile.HEAVY,
        runner_kind=RunnerKind.TWO_STAGE,
        harness_profile=HarnessProfile.FULL,
        expected_generator_calls=2,
    ),
    AblationArm(
        arm_id=ArmId.A6,
        model_tier=ModelTier.STRONGEST,
        schema_profile=SchemaProfile.LIGHT,
        runner_kind=RunnerKind.ONCE,
        harness_profile=HarnessProfile.FULL,
        expected_generator_calls=1,
    ),
)


class FastScreenTrial(R1EvalModel):
    trial_id: Identifier
    case_id: Identifier
    case_family_id: Identifier
    source_type: SourceType
    arm: AblationArm


class FastScreenPlan(R1EvalModel):
    schema_version: Literal["r1_fast_screen_plan.v1"]
    case_count: Literal[8]
    arm_count: Literal[6]
    planned_observations: Literal[48]
    expected_generator_calls: Literal[80]
    grader_calls_included: Literal[False]
    trials: tuple[FastScreenTrial, ...]


def build_fast_screen_plan(
    cases: tuple[R1RuntimeCase, ...],
) -> FastScreenPlan:
    """Freeze the 8-case x 6-arm quick-screen slots before execution."""

    if len(cases) != 8:
        raise ValueError("R1 fast screen requires exactly eight cases")
    case_ids = tuple(case.metadata.case_id for case in cases)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("R1 fast-screen case IDs must be unique")

    trials = tuple(
        FastScreenTrial(
            trial_id=f"fast-{case.metadata.case_id}-{arm.arm_id.value}",
            case_id=case.metadata.case_id,
            case_family_id=case.metadata.case_family_id,
            source_type=case.metadata.source_type,
            arm=arm,
        )
        for case in cases
        for arm in ABLATION_ARMS
    )
    expected_calls = sum(
        trial.arm.expected_generator_calls for trial in trials
    )
    if len(trials) != 48 or expected_calls != 80:
        raise AssertionError("ADR 0040 fast-screen constants drifted")
    return FastScreenPlan(
        schema_version="r1_fast_screen_plan.v1",
        case_count=8,
        arm_count=6,
        planned_observations=48,
        expected_generator_calls=80,
        grader_calls_included=False,
        trials=trials,
    )
