"""R1a budget-limited architecture screening.

只包含 owner 核准的 A1／A6／A2 子集；不是完整六 arm R1，也不是 production runtime。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .blind_grader import (
    build_blind_packets,
    build_grader_stage,
    merge_grader_passes,
)
from .capture import TrialCapture
from .contracts import canonical_hash, load_case_dir, suite_hash
from .live_preflight import (
    MODEL_PROFILES,
    HarnessFailure,
    LiveModelPort,
    LiveSession,
    _load_env_value,
    fetch_catalog_binding,
    parse_grader_payload,
)
from .matrix import ObservationPlan, build_observation_plans
from .paths import CASES_DIR
from .runner import OUTCOME_COMPLETED, OUTCOME_HARNESS_INVALID, ObservationResult
from .runner import run_observation
from .transport import build_client
from .validate_r1_cases import FROZEN_SUITE_HASH

R1A_ARM_IDS = ("A1", "A6", "A2")
R1A_MAX_COST = Decimal("2.50")
R1A_SEED = 20260727

CALIBRATION_CASE: dict[str, Any] = {
    "case_id": "R1-GRADER-CALIBRATION",
    "case_revision": 1,
    "case_family_id": "R1-GRADER-CALIBRATION",
    "source_type": "constructed_edge",
    "sources": [
        {
            "source_id": "cal-source-01",
            "source_kind": "employee_turn",
            "text": "我每週負責整理客服回報，交付問題趨勢摘要。",
        },
        {
            "source_id": "cal-source-02",
            "source_kind": "employee_turn",
            "text": "我會使用 Python。",
        },
        {
            "source_id": "cal-source-03",
            "source_kind": "employee_turn",
            "text": "我有時會幫忙處理報表。",
        },
    ],
}

CALIBRATION_FORWARD = {
    "case_id": CALIBRATION_CASE["case_id"],
    "sources": CALIBRATION_CASE["sources"],
    "candidates": [
        {
            "label": "candidate-01",
            "view": {
                "analysis_decision": "propose_current_tasks",
                "proposed_tasks": [
                    {
                        "task_statement": "整理客服回報並產出問題趨勢摘要",
                        "intended_outcome": "提供產品團隊可用的問題趨勢",
                        "source_anchors": [
                            {
                                "source_id": "cal-source-01",
                                "quote": "每週負責整理客服回報，交付問題趨勢摘要",
                            }
                        ],
                    }
                ],
                "next_question": None,
                "limitations": [],
            },
        },
        {
            "label": "candidate-02",
            "view": {
                "analysis_decision": "propose_current_tasks",
                "proposed_tasks": [
                    {
                        "task_statement": "使用 Python",
                        "intended_outcome": "完成工作",
                        "source_anchors": [
                            {
                                "source_id": "cal-source-02",
                                "quote": "使用 Python",
                            }
                        ],
                    }
                ],
                "next_question": None,
                "limitations": [],
            },
        },
        {
            "label": "candidate-03",
            "view": {
                "analysis_decision": "clarify",
                "proposed_tasks": [],
                "next_question": {
                    "text": "處理報表是固定責任，還是偶爾代班？",
                    "purpose": "確認責任與穩定性",
                },
                "limitations": ["目前無法判定是否為穩定本人責任"],
            },
        },
    ],
}
CALIBRATION_REVERSE = {
    **CALIBRATION_FORWARD,
    "candidates": list(reversed(CALIBRATION_FORWARD["candidates"])),
}
CALIBRATION_GOLD = {
    "candidate-01": {
        "meaningful_outcome": "pass",
        "source_grounding": "pass",
    },
    "candidate-02": {
        "meaningful_outcome": "fail",
        "source_grounding": "pass",
    },
    "candidate-03": {
        "meaningful_outcome": "unknown",
        "source_grounding": "unknown",
    },
}


def select_r1a_plans(cases: list[dict[str, Any]]) -> list[ObservationPlan]:
    allowed = set(R1A_ARM_IDS)
    return [
        plan
        for plan in build_observation_plans(cases)
        if plan.arm.arm_id in allowed
    ]


def map_grades_to_arms(
    label_to_arm: dict[str, str],
    grades_by_label: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    if set(label_to_arm) != set(grades_by_label):
        raise ValueError("grader labels did not match the blind label map")
    return dict(
        sorted(
            (
                (label_to_arm[label], dict(sorted(grades.items())))
                for label, grades in grades_by_label.items()
            ),
            key=lambda item: item[0],
        )
    )


def calibration_matches_gold(
    gold: dict[str, dict[str, str]],
    observed: dict[str, dict[str, str]],
) -> bool:
    return observed == gold


async def run_grader_pair(
    *,
    session: Any,
    case: dict[str, Any],
    suite_hash: str,
    forward: dict[str, Any],
    reverse: dict[str, Any],
    label_to_arm: dict[str, str],
    dimensions: tuple[str, ...],
) -> dict[str, dict[str, str]]:
    passes: list[dict[str, dict[str, str]]] = []
    safe_case_name = case["case_id"].lower().replace("-", "_")
    for order_name, packet in (("forward", forward), ("reverse", reverse)):
        stage = build_grader_stage(packet, dimensions=dimensions)
        payload = await session.send_structured(
            role="grader",
            arm=f"GRADER-{order_name}",
            system_instruction=stage.system_instruction,
            user_content=stage.user_content,
            output_schema=stage.output_schema,
            schema_name=f"r1_{safe_case_name}_{order_name}",
            prompt_version=stage.prompt_version,
            context_version="r1-task-discovery-grader-context.1",
            context_packet=packet,
            max_output_tokens=2048,
            case=case,
            suite_hash=suite_hash,
        )
        passes.append(
            parse_grader_payload(
                payload,
                expected_labels=set(label_to_arm),
                expected_dimensions=set(dimensions),
            )
        )
    return map_grades_to_arms(
        label_to_arm,
        merge_grader_passes(passes[0], passes[1]),
    )


def build_screening_report(
    *,
    cases: list[dict[str, Any]],
    plans: list[ObservationPlan],
    results: list[ObservationResult],
    grades_by_case: dict[str, dict[str, dict[str, str]]],
    total_cost: str,
) -> dict[str, Any]:
    if len(plans) != len(results):
        raise ValueError("every R1a plan must have exactly one result")

    expected_observations = len(cases) * len(R1A_ARM_IDS)
    attempted_without_harness_failure = (
        len(results) == expected_observations
        and all(result.outcome != OUTCOME_HARNESS_INVALID for result in results)
    )

    paired = list(zip(plans, results, strict=True))
    grades_complete = True
    for case in cases:
        case_id = case["case_id"]
        expected_dimensions = set(
            case["expected"]["common_applicable_rubric_dimensions"]
        )
        case_grades = grades_by_case.get(case_id, {})
        expected_graded_arms = {
            plan.arm.arm_id
            for plan, result in paired
            if plan.case_id == case_id and result.outcome == OUTCOME_COMPLETED
        }
        if set(case_grades) != expected_graded_arms:
            grades_complete = False
            continue
        if any(set(grades) != expected_dimensions for grades in case_grades.values()):
            grades_complete = False

    review_items: set[tuple[str, str, str]] = set()
    for case_id in ("TI-R1-02", "TI-R1-07"):
        for arm_id in R1A_ARM_IDS:
            review_items.add((case_id, arm_id, "locked_anchor"))
    for plan, result in paired:
        if result.outcome != OUTCOME_COMPLETED:
            review_items.add(
                (plan.case_id, plan.arm.arm_id, "deterministic_invalid")
            )
    for case_id, arm_grades in grades_by_case.items():
        for arm_id, dimensions in arm_grades.items():
            if any(verdict in ("fail", "unknown") for verdict in dimensions.values()):
                review_items.add((case_id, arm_id, "grader_fail_or_unknown"))

    return {
        "batch_name": "R1a architecture screening",
        "executed_arms": list(R1A_ARM_IDS),
        "observation_count": len(results),
        "generator_call_count": sum(result.call_count for result in results),
        "outcomes": dict(
            sorted(Counter(result.outcome for result in results).items())
        ),
        "grader_case_count": len(grades_by_case),
        "batch_complete": attempted_without_harness_failure and grades_complete,
        "provisional_screening_eligible": (
            attempted_without_harness_failure and grades_complete
        ),
        # 設計要求 anchor／fail／unknown 仍需 owner review；程式不能替 owner 通過。
        "quality_conclusion_eligible": False,
        "owner_review_queue": [
            {"case_id": case_id, "arm_id": arm_id, "reason": reason}
            for case_id, arm_id, reason in sorted(review_items)
        ],
        "total_cost": total_cost,
        "limitations": [
            "R1a only: A3/A4/A5 were not executed",
            "owner review is required before any screening conclusion",
        ],
    }


def _result_record(result: ObservationResult) -> dict[str, Any]:
    return {
        "observation_id": result.observation_id,
        "outcome": result.outcome,
        "call_count": result.call_count,
        "canonical_view": result.canonical_view,
        "state_change_view": result.state_change_view,
        "findings": [
            {
                "check": finding.check,
                "message": finding.message,
                "severity": finding.severity,
                "locator": finding.locator,
            }
            for finding in result.findings
        ],
    }


async def _run_calibration(session: LiveSession) -> dict[str, dict[str, str]]:
    observed = await run_grader_pair(
        session=session,
        case=CALIBRATION_CASE,
        suite_hash="r1-grader-calibration-no-suite",
        forward=CALIBRATION_FORWARD,
        reverse=CALIBRATION_REVERSE,
        label_to_arm={label: label for label in CALIBRATION_GOLD},
        dimensions=("meaningful_outcome", "source_grounding"),
    )
    if not calibration_matches_gold(CALIBRATION_GOLD, observed):
        raise HarnessFailure(
            f"grader calibration did not match frozen gold: {observed!r}"
        )
    return observed


def _owner_review_artifacts(
    report: dict[str, Any],
    cases_by_id: dict[str, dict[str, Any]],
    results_by_case: dict[str, dict[str, ObservationResult]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    packets: list[dict[str, Any]] = []
    mapping: dict[str, str] = {}
    for index, item in enumerate(report["owner_review_queue"], start=1):
        case_id = item["case_id"]
        arm_id = item["arm_id"]
        result = results_by_case[case_id][arm_id]
        review_id = f"review-{index:03d}"
        packets.append(
            {
                "review_id": review_id,
                "case_id": case_id,
                "sources": cases_by_id[case_id]["sources"],
                "view": result.canonical_view,
                "deterministic_outcome": result.outcome,
                "reason": item["reason"],
            }
        )
        mapping[review_id] = arm_id
    return packets, mapping


async def run_live_r1a(
    *,
    env_file: Path,
    output_dir: Path,
    max_cost: Decimal = R1A_MAX_COST,
) -> dict[str, Any]:
    api_key = _load_env_value(env_file, "OPENROUTER_API_KEY")
    cases = load_case_dir(CASES_DIR)
    frozen_hash = suite_hash(cases)
    if frozen_hash != FROZEN_SUITE_HASH:
        raise HarnessFailure("formal R1 suite hash did not match the frozen hash")
    plans = select_r1a_plans(cases)
    output_dir.mkdir(parents=True, exist_ok=False)

    async with build_client(120.0) as client:
        bindings = {
            role: await fetch_catalog_binding(
                client,
                api_key=api_key,
                requested_model=MODEL_PROFILES[role][0],
                endpoint_tag=MODEL_PROFILES[role][1],
            )
            for role in ("strongest", "grader")
        }
        session = LiveSession(
            client=client,
            api_key=api_key,
            output_dir=output_dir,
            bindings=bindings,
            max_cost=max_cost,
        )
        calibration = await _run_calibration(session)

        cases_by_id = {case["case_id"]: case for case in cases}
        results: list[ObservationResult] = []
        results_by_case: dict[str, dict[str, ObservationResult]] = {
            case["case_id"]: {} for case in cases
        }
        for plan in plans:
            case = cases_by_id[plan.case_id]
            result = await run_observation(
                case,
                plan,
                LiveModelPort(session, case=case, suite_hash=frozen_hash),
            )
            results.append(result)
            results_by_case[plan.case_id][plan.arm.arm_id] = result
            if result.outcome == OUTCOME_HARNESS_INVALID:
                raise HarnessFailure(
                    f"{plan.observation_id} was harness_invalid: "
                    f"{[str(finding) for finding in result.findings]}"
                )

        grades_by_case: dict[str, dict[str, dict[str, str]]] = {}
        blind_packets: dict[str, dict[str, Any]] = {}
        for case in cases:
            case_id = case["case_id"]
            valid_results = {
                arm_id: result
                for arm_id, result in results_by_case[case_id].items()
                if result.outcome == OUTCOME_COMPLETED
            }
            if not valid_results:
                grades_by_case[case_id] = {}
                continue
            forward, reverse, label_to_arm = build_blind_packets(
                case,
                valid_results,
                seed=R1A_SEED,
            )
            blind_packets[case_id] = {
                "forward": forward,
                "reverse": reverse,
                "label_to_arm": label_to_arm,
            }
            dimensions = tuple(
                case["expected"]["common_applicable_rubric_dimensions"]
            )
            grades_by_case[case_id] = await run_grader_pair(
                session=session,
                case=case,
                suite_hash=frozen_hash,
                forward=forward,
                reverse=reverse,
                label_to_arm=label_to_arm,
                dimensions=dimensions,
            )

    report = build_screening_report(
        cases=cases,
        plans=plans,
        results=results,
        grades_by_case=grades_by_case,
        total_cost=str(session.total_cost),
    )
    report.update(
        {
            "run_id": output_dir.name,
            "status": "passed" if report["batch_complete"] else "incomplete",
            "suite_hash": frozen_hash,
            "grader_calibration": {
                "gold_hash": canonical_hash(CALIBRATION_GOLD),
                "observed": calibration,
                "matched": True,
            },
            "bindings": {
                role: {
                    "requested_model": binding.requested_model,
                    "canonical_model": binding.canonical_model,
                    "endpoint_tag": binding.endpoint_tag,
                    "provider_name": binding.provider_name,
                    "snapshot_hash": binding.snapshot_hash,
                }
                for role, binding in bindings.items()
            },
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    owner_packets, owner_map = _owner_review_artifacts(
        report,
        cases_by_id,
        results_by_case,
    )
    root = TrialCapture(output_dir)
    root.write("observations.json", [_result_record(result) for result in results])
    root.write("grades.json", grades_by_case)
    root.write("blind-packets.json", blind_packets)
    root.write("owner-review-packets.json", owner_packets)
    root.write("owner-review-map.json", owner_map)
    root.write("report.json", report)
    return report


def _default_output_dir() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path("output") / "professional-consultant-r1" / f"r1a-{stamp}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="R1a A1/A6/A2 budget-limited live architecture screening"
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--max-cost", type=Decimal, default=None)
    args = parser.parse_args(argv)
    output_dir = args.output_dir or _default_output_dir()
    try:
        report = asyncio.run(
            run_live_r1a(
                env_file=args.env_file,
                output_dir=output_dir,
                max_cost=args.max_cost or R1A_MAX_COST,
            )
        )
    except Exception as exc:
        if output_dir.exists():
            if not (output_dir / "failure.json").exists():
                failure = TrialCapture(output_dir)
                failure.write(
                    "failure.json",
                    {
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
        print(
            json.dumps(
                {
                    "status": "failed",
                    "output_dir": str(output_dir),
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
