"""The six pre-registered R1 arms and their case-arm observation plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ArmSpec:
    arm_id: str
    model_role: str
    schema_weight: str
    stage_count: int
    harness: str


ARMS = (
    ArmSpec("A1", "strongest", "light", 1, "minimal"),
    ArmSpec("A2", "strongest", "light", 2, "full"),
    ArmSpec("A3", "strongest", "heavy", 2, "full"),
    ArmSpec("A4", "economical", "light", 2, "full"),
    ArmSpec("A5", "economical", "heavy", 2, "full"),
    ArmSpec("A6", "strongest", "light", 1, "full"),
)


@dataclass(frozen=True)
class ObservationPlan:
    case_id: str
    case_revision: int
    arm: ArmSpec
    round: int = 1
    attempt: int = 1

    @property
    def observation_id(self) -> str:
        return f"{self.case_id}-{self.arm.arm_id}-r{self.round}-a{self.attempt}"


def arm_by_id(arm_id: str) -> ArmSpec:
    for arm in ARMS:
        if arm.arm_id == arm_id:
            return arm
    raise KeyError(f"unknown R1 arm: {arm_id}")


def build_observation_plans(cases: Iterable[dict[str, Any]]) -> list[ObservationPlan]:
    return [
        ObservationPlan(
            case_id=case["case_id"],
            case_revision=case["case_revision"],
            arm=arm,
        )
        for case in cases
        for arm in ARMS
    ]


def max_generator_calls(plans: Iterable[ObservationPlan]) -> int:
    return sum(plan.arm.stage_count for plan in plans)
