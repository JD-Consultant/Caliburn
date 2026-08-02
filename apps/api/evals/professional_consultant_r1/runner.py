"""No-network R1 observation runner with an injected model port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .assembler import (
    STAGE_FINAL,
    STAGE_UNDERSTAND,
    AssembledStage,
    assemble_stage,
    verify_portable_output,
    verify_stage1_result,
)
from .contracts import Finding, project_canonical_view
from .matrix import ObservationPlan
from .verify_output import ARM_CLASS_FULL, ARM_CLASS_MINIMAL, verify_output

OUTCOME_COMPLETED = "completed"
OUTCOME_STAGE1_INVALID = "stage1_invalid"
OUTCOME_FINAL_INVALID = "final_invalid"
OUTCOME_HARNESS_INVALID = "harness_invalid"


class HarnessFailure(RuntimeError):
    """Transport／route／provider protocol 失敗；不得記成模型語意品質。"""


class ModelOutputFailure(RuntimeError):
    """模型沒有產生可進 local verifier 的 structured payload。"""


class ModelPort(Protocol):
    async def complete(self, stage: AssembledStage) -> Any: ...


@dataclass(frozen=True)
class ObservationResult:
    observation_id: str
    outcome: str
    call_count: int
    canonical_view: dict[str, Any] | None
    state_change_view: dict[str, Any] | None
    findings: tuple[Finding, ...]
    stage_outputs: tuple[Any, ...]


async def run_observation(
    case: dict[str, Any],
    plan: ObservationPlan,
    port: ModelPort,
) -> ObservationResult:
    outputs: list[Any] = []
    stage1_result: Any = None
    attempted_calls = 0

    if plan.arm.stage_count == 2:
        first = assemble_stage(case, plan.arm, STAGE_UNDERSTAND)
        attempted_calls += 1
        try:
            stage1_result = await port.complete(first)
        except ModelOutputFailure as exc:
            return ObservationResult(
                observation_id=plan.observation_id,
                outcome=OUTCOME_STAGE1_INVALID,
                call_count=attempted_calls,
                canonical_view=None,
                state_change_view=None,
                findings=(Finding(check="output_parse", message=str(exc)),),
                stage_outputs=tuple(outputs),
            )
        except HarnessFailure as exc:
            return ObservationResult(
                observation_id=plan.observation_id,
                outcome=OUTCOME_HARNESS_INVALID,
                call_count=attempted_calls,
                canonical_view=None,
                state_change_view=None,
                findings=(Finding(check="harness_invalid", message=str(exc)),),
                stage_outputs=tuple(outputs),
            )
        outputs.append(stage1_result)
        stage1_verification = verify_stage1_result(case, plan.arm, stage1_result)
        if not stage1_verification.ok:
            return ObservationResult(
                observation_id=plan.observation_id,
                outcome=OUTCOME_STAGE1_INVALID,
                call_count=1,
                canonical_view=None,
                state_change_view=None,
                findings=tuple(stage1_verification.findings),
                stage_outputs=tuple(outputs),
            )

    final = assemble_stage(
        case,
        plan.arm,
        STAGE_FINAL,
        stage1_result=stage1_result,
    )
    attempted_calls += 1
    try:
        raw_final = await port.complete(final)
    except ModelOutputFailure as exc:
        return ObservationResult(
            observation_id=plan.observation_id,
            outcome=OUTCOME_FINAL_INVALID,
            call_count=attempted_calls,
            canonical_view=None,
            state_change_view=None,
            findings=(Finding(check="output_parse", message=str(exc)),),
            stage_outputs=tuple(outputs),
        )
    except HarnessFailure as exc:
        return ObservationResult(
            observation_id=plan.observation_id,
            outcome=OUTCOME_HARNESS_INVALID,
            call_count=attempted_calls,
            canonical_view=None,
            state_change_view=None,
            findings=(Finding(check="harness_invalid", message=str(exc)),),
            stage_outputs=tuple(outputs),
        )
    outputs.append(raw_final)
    canonical = project_canonical_view(raw_final)
    state_change = raw_final.get("state_change") if isinstance(raw_final, dict) else None
    schema_verification = verify_portable_output(raw_final, final.output_schema)
    if not schema_verification.ok:
        return ObservationResult(
            observation_id=plan.observation_id,
            outcome=OUTCOME_FINAL_INVALID,
            call_count=len(outputs),
            canonical_view=canonical,
            state_change_view=state_change,
            findings=tuple(schema_verification.findings),
            stage_outputs=tuple(outputs),
        )
    arm_class = ARM_CLASS_MINIMAL if plan.arm.harness == "minimal" else ARM_CLASS_FULL
    verification = verify_output(case, canonical, arm_class, state_change)
    if not verification.ok:
        return ObservationResult(
            observation_id=plan.observation_id,
            outcome=OUTCOME_FINAL_INVALID,
            call_count=len(outputs),
            canonical_view=canonical,
            state_change_view=state_change,
            findings=tuple(verification.findings),
            stage_outputs=tuple(outputs),
        )
    return ObservationResult(
        observation_id=plan.observation_id,
        outcome=OUTCOME_COMPLETED,
        call_count=len(outputs),
        canonical_view=canonical,
        state_change_view=state_change,
        findings=(),
        stage_outputs=tuple(outputs),
    )
