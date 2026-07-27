"""Segment 3：只測會影響 R1 實驗結論的 no-network 行為。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from .assembler import STAGE_FINAL, STAGE_UNDERSTAND, assemble_stage
from .batch import run_batch
from .blind_grader import (
    build_blind_packets,
    build_grader_stage,
    gradable_views,
    merge_grader_passes,
)
from .contracts import load_case, load_case_dir
from .matrix import arm_by_id, build_observation_plans, max_generator_calls
from .paths import CASES_DIR
from .report import build_batch_report
from .runner import (
    HarnessFailure,
    OUTCOME_COMPLETED,
    OUTCOME_FINAL_INVALID,
    OUTCOME_HARNESS_INVALID,
    OUTCOME_STAGE1_INVALID,
    ObservationResult,
    run_observation,
)


@pytest.fixture(scope="module")
def cases() -> list[dict[str, Any]]:
    return load_case_dir(CASES_DIR)


def _final_output(*, full: bool = False) -> dict[str, Any]:
    output = {
        "analysis_decision": "clarify",
        "proposed_tasks": [],
        "next_question": {
            "text": "最近一次開發的系統要解決什麼問題？",
            "purpose": "確認可辨識的工作結果",
        },
        "limitations": ["目前只有工具名稱，無法判定 Task"],
        "decision_basis": None,
    }
    if full:
        output["state_change"] = {
            "change_type": "no_change",
            "affected_existing_task_ids": [],
        }
    return output


def _stage1_output() -> dict[str, Any]:
    return {
        "observations": [
            {
                "statement": "員工只提供使用的技術名稱。",
                "source_anchors": [
                    {"source_id": "turn-002", "quote": "Java、HTML 和 Python"}
                ],
            }
        ],
        "corrections": [],
        "limitations": ["缺少工作目的與結果"],
    }


@dataclass
class ScriptedPort:
    outputs: list[dict[str, Any]]
    calls: list[Any] = field(default_factory=list)

    async def complete(self, stage: Any) -> dict[str, Any]:
        self.calls.append(stage)
        return self.outputs[len(self.calls) - 1]


def test_matrix_is_exactly_48_observations_and_80_max_calls(cases) -> None:
    plans = build_observation_plans(cases)
    assert len(plans) == 48
    assert {plan.arm.arm_id for plan in plans} == {"A1", "A2", "A3", "A4", "A5", "A6"}
    assert max_generator_calls(plans) == 80
    assert sum(plan.arm.stage_count == 1 for plan in plans) == 16
    assert sum(plan.arm.stage_count == 2 for plan in plans) == 32


def test_context_treatments_are_isolated_and_stage2_keeps_raw_sources(cases) -> None:
    case = next(item for item in cases if item["case_id"] == "TI-R1-08")

    minimal = assemble_stage(case, arm_by_id("A1"), STAGE_FINAL)
    full_one = assemble_stage(case, arm_by_id("A6"), STAGE_FINAL)
    stage1 = _stage1_output()
    full_two = assemble_stage(
        case,
        arm_by_id("A2"),
        STAGE_FINAL,
        stage1_result=stage1,
    )

    assert "current_work_model" not in minimal.context_packet
    assert "task_policies" not in minimal.context_packet
    assert full_one.context_packet["current_work_model"] == case["initial_work_model"]
    assert full_two.context_packet["sources"] == case["sources"]
    assert full_two.context_packet["stage1_result"] == stage1


def test_assembler_never_exposes_case_expected_answers(cases) -> None:
    case = next(item for item in cases if item["case_id"] == "TI-R1-02")
    for arm_id in ("A1", "A2", "A3", "A4", "A5", "A6"):
        arm = arm_by_id(arm_id)
        stage = STAGE_UNDERSTAND if arm.stage_count == 2 else STAGE_FINAL
        assembled = assemble_stage(case, arm, stage)
        visible = json.dumps(
            {
                "context": assembled.context_packet,
                "system": assembled.system_instruction,
                "user": assembled.user_content,
                "schema": assembled.output_schema,
            },
            ensure_ascii=False,
        )
        assert "required_behaviors" not in visible
        assert "forbidden_behaviors" not in visible
        assert "locked_regression_anchor" not in visible


@pytest.mark.asyncio
async def test_one_stage_calls_once_and_returns_canonical_view(cases) -> None:
    case = cases[0]
    plan = next(
        plan
        for plan in build_observation_plans([case])
        if plan.arm.arm_id == "A1"
    )
    port = ScriptedPort([_final_output()])

    result = await run_observation(case, plan, port)

    assert result.outcome == OUTCOME_COMPLETED
    assert len(port.calls) == 1
    assert result.canonical_view is not None
    assert "decision_basis" not in result.canonical_view


@pytest.mark.asyncio
async def test_two_stage_calls_twice_and_final_sees_stage1_result(cases) -> None:
    case = cases[0]
    plan = next(
        plan
        for plan in build_observation_plans([case])
        if plan.arm.arm_id == "A2"
    )
    port = ScriptedPort([_stage1_output(), _final_output(full=True)])

    result = await run_observation(case, plan, port)

    assert result.outcome == OUTCOME_COMPLETED
    assert len(port.calls) == 2
    assert port.calls[1].context_packet["stage1_result"] == _stage1_output()
    assert port.calls[1].context_packet["sources"] == case["sources"]


@pytest.mark.asyncio
async def test_invalid_stage1_is_terminal_without_repair_or_second_call(cases) -> None:
    case = cases[0]
    plan = next(
        plan
        for plan in build_observation_plans([case])
        if plan.arm.arm_id == "A2"
    )
    port = ScriptedPort([{"observations": "not-a-list"}])

    result = await run_observation(case, plan, port)

    assert result.outcome == OUTCOME_STAGE1_INVALID
    assert len(port.calls) == 1
    assert result.canonical_view is None


@pytest.mark.asyncio
async def test_transport_failure_is_harness_invalid_not_model_quality(cases) -> None:
    class FailingPort:
        async def complete(self, stage: Any) -> dict[str, Any]:
            raise HarnessFailure("route metadata could not attest the endpoint")

    case = cases[0]
    plan = next(
        plan for plan in build_observation_plans([case]) if plan.arm.arm_id == "A1"
    )

    result = await run_observation(case, plan, FailingPort())

    assert result.outcome == OUTCOME_HARNESS_INVALID
    assert result.call_count == 1
    assert result.canonical_view is None
    assert result.findings[0].check == "harness_invalid"


def test_blind_packets_include_sources_but_hide_arms_and_reverse_order(cases) -> None:
    case = cases[0]
    results = {
        arm_id: ObservationResult(
            observation_id=f"{case['case_id']}:{arm_id}",
            outcome=OUTCOME_COMPLETED,
            call_count=1,
            canonical_view={
                "analysis_decision": "no_change",
                "proposed_tasks": [],
                "next_question": None,
                "limitations": [],
            },
            state_change_view=None,
            findings=(),
            stage_outputs=(),
        )
        for arm_id in ("A1", "A2", "A3", "A4", "A5", "A6")
    }

    forward, reverse, label_to_arm = build_blind_packets(case, results, seed=20260727)

    assert forward["sources"] == reverse["sources"] == case["sources"]
    assert [item["label"] for item in reverse["candidates"]] == list(
        reversed([item["label"] for item in forward["candidates"]])
    )
    serialized = json.dumps([forward, reverse], ensure_ascii=False)
    assert all(arm_id not in serialized for arm_id in results)
    assert set(label_to_arm.values()) == set(results)

    grader_stage = build_grader_stage(
        forward,
        dimensions=("meaningful_outcome", "source_grounding"),
    )
    grader_visible = json.dumps(
        {
            "system": grader_stage.system_instruction,
            "user": grader_stage.user_content,
            "schema": grader_stage.output_schema,
        },
        ensure_ascii=False,
    )
    assert all(arm_id not in grader_visible for arm_id in results)
    assert "decision_basis" not in grader_visible


def test_stage1_context_withholds_stage2_task_criteria(cases) -> None:
    """設計 §5.3：判準屬 Stage 2。Stage 1 也帶就變成同一份 context 打兩次。"""
    case = cases[0]
    arm = arm_by_id("A2")

    stage1 = assemble_stage(case, arm, STAGE_UNDERSTAND)
    stage2 = assemble_stage(case, arm, STAGE_FINAL, stage1_result=_stage1_output())

    assert "task_policies" not in stage1.context_packet
    assert "current_work_model" in stage1.context_packet
    assert stage2.context_packet["task_policies"]


@pytest.mark.asyncio
async def test_deterministically_invalid_observations_never_reach_the_grader(cases) -> None:
    case = cases[0]
    plans = build_observation_plans([case])
    good_plan = next(plan for plan in plans if plan.arm.arm_id == "A1")
    bad_plan = next(plan for plan in plans if plan.arm.arm_id == "A6")

    good = await run_observation(case, good_plan, ScriptedPort([_final_output()]))
    bad_output = _final_output(full=True)
    bad_output["analysis_decision"] = "propose_current_tasks"  # 宣稱有 Task 卻是空陣列
    bad = await run_observation(case, bad_plan, ScriptedPort([bad_output]))

    assert bad.outcome == OUTCOME_FINAL_INVALID
    assert bad.canonical_view is not None  # 有值，所以不能只靠 None 判斷
    assert gradable_views({"A1": good, "A6": bad}) == {"A1": good.canonical_view}
    forward, reverse, label_to_arm = build_blind_packets(
        case,
        {"A1": good, "A6": bad},
        seed=20260727,
    )
    assert len(forward["candidates"]) == len(reverse["candidates"]) == 1
    assert label_to_arm == {"candidate-01": "A1"}


def test_grader_disagreement_becomes_unknown() -> None:
    forward = {
        "candidate-01": {
            "meaningful_outcome": "pass",
            "source_grounding": "pass",
        }
    }
    reverse = {
        "candidate-01": {
            "meaningful_outcome": "fail",
            "source_grounding": "pass",
        }
    }

    assert merge_grader_passes(forward, reverse) == {
        "candidate-01": {
            "meaningful_outcome": "unknown",
            "source_grounding": "pass",
        }
    }


@dataclass
class UniversalScriptedPort:
    calls: list[Any] = field(default_factory=list)

    async def complete(self, stage: Any) -> dict[str, Any]:
        self.calls.append(stage)
        if stage.operation == STAGE_UNDERSTAND:
            employee_source = next(
                source
                for source in stage.context_packet["sources"]
                if source["source_kind"] == "employee_turn"
            )
            quote = employee_source["text"][:8]
            observation = {
                "statement": "保留員工字面提供的工作線索。",
                "source_anchors": [
                    {"source_id": employee_source["source_id"], "quote": quote}
                ],
            }
            if "actor" in stage.output_schema["properties"]["observations"]["items"]["properties"]:
                observation.update(
                    {
                        "actor": "employee",
                        "time_scope": "current",
                        "typicality": "unknown",
                        "responsibility": "unknown",
                        "activity_kind": "unknown",
                        "intended_outcome": "unknown",
                        "unknown_reason": "scripted plumbing output",
                    }
                )
            return {
                "observations": [
                    observation
                ],
                "corrections": [],
                "limitations": [],
            }
        output = {
            "analysis_decision": "clarify",
            "proposed_tasks": [],
            "next_question": {
                "text": "這項工作要達成什麼結果？",
                "purpose": "確認 outcome",
            },
            "limitations": ["scripted plumbing output，不代表模型品質"],
            "decision_basis": None,
        }
        if "current_work_model" in stage.context_packet:
            existing = stage.context_packet["current_work_model"]["task_candidates"]
            output["state_change"] = {
                "change_type": "no_change",
                "affected_existing_task_ids": (
                    [existing[0]["task_id"]] if existing else []
                ),
            }
        if "task_assessments" in stage.output_schema["properties"]:
            output["task_assessments"] = []
        return output


@pytest.mark.asyncio
async def test_scripted_batch_runs_48_observations_but_cannot_claim_quality(cases) -> None:
    port = UniversalScriptedPort()
    plans, results = await run_batch(cases, port)
    report = build_batch_report(plans, results, scripted=True)

    assert len(plans) == len(results) == 48
    assert len(port.calls) == 80
    assert report["observation_count"] == 48
    assert report["generator_call_count"] == 80
    assert report["scripted_only"] is True
    assert report["quality_conclusion_eligible"] is False
