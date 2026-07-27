"""Blind packet construction and deterministic forward/reverse reconciliation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from .contracts import COMMON_DIMENSIONS, canonical_hash, canonical_json, project_canonical_view
from .verify_output import verify_grader_packet

GRADE_VALUES = frozenset({"pass", "fail", "unknown"})
GRADER_PROMPT_VERSION = "r1-task-discovery-grader.1"

DIMENSION_GUIDANCE = {
    "meaningful_outcome": "Task 是否有可辨識目的或結果，而不是純工具或手段。",
    "employee_responsibility": "內容是否確實屬於員工本人責任。",
    "assignability_checkability": "Task 邊界是否可指派並可檢查完成。",
    "stability_formal_low_frequency": "是否正確區分穩定／正式低頻責任與一次性事件。",
    "merge_split_boundary": "是否避免步驟過拆、重疊 Task，且沒有錯誤合併不同結果。",
    "past_other_one_off_exclusion": "過去工作、他人責任與一次性支援是否未進現況。",
    "correction_authority": "最新明確更正是否壓過舊說法。",
    "source_grounding": "每個 Task 是否有合法來源，且沒有輸入外推測。",
    "uncertainty_honesty": "資訊不足時是否誠實保留不確定性。",
    "next_question_value": "下一問是否單一、自然，且降低最關鍵的不確定性。",
}


@dataclass(frozen=True)
class GraderStage:
    system_instruction: str
    user_content: str
    output_schema: dict[str, Any]
    prompt_version: str = GRADER_PROMPT_VERSION

    @property
    def schema_hash(self) -> str:
        return canonical_hash(self.output_schema)


def build_blind_packets(
    case: dict[str, Any],
    views_by_arm: dict[str, dict[str, Any]],
    *,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    case_id = case["case_id"]
    arm_ids = sorted(views_by_arm)
    random.Random(f"{case_id}:{seed}").shuffle(arm_ids)

    candidates: list[dict[str, Any]] = []
    label_to_arm: dict[str, str] = {}
    for index, arm_id in enumerate(arm_ids, start=1):
        label = f"candidate-{index:02d}"
        view = project_canonical_view(views_by_arm[arm_id])
        cleanliness = verify_grader_packet(view)
        if not cleanliness.ok:
            messages = "; ".join(f.message for f in cleanliness.findings)
            raise ValueError(f"grader packet was not blind: {messages}")
        candidates.append({"label": label, "view": view})
        label_to_arm[label] = arm_id

    common = {"case_id": case_id, "sources": case["sources"]}
    forward = {**common, "candidates": candidates}
    reverse = {**common, "candidates": list(reversed(candidates))}
    return forward, reverse, label_to_arm


def build_grader_stage(
    packet: dict[str, Any],
    *,
    dimensions: tuple[str, ...],
) -> GraderStage:
    unknown = set(dimensions) - set(COMMON_DIMENSIONS)
    if unknown:
        raise ValueError(f"unknown grader dimensions: {sorted(unknown)}")
    candidates = packet.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("grader packet must contain anonymous candidates")
    labels = [candidate["label"] for candidate in candidates]

    guidance = "\n".join(
        f"- {dimension}: {DIMENSION_GUIDANCE[dimension]}"
        for dimension in dimensions
    )
    system = (
        "你是獨立的職務分析盲評者。只根據匿名候選內容與下列共同判準評分；"
        "不知道就回 unknown，不得猜測候選所屬架構、模型或 schema。"
        "不得用文風、篇幅或解釋長度代替 Task 邊界品質。\n"
        f"{guidance}"
    )
    schema = {
        "type": "object",
        "properties": {
            "grades": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "enum": labels},
                        "dimensions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dimension": {
                                        "type": "string",
                                        "enum": list(dimensions),
                                    },
                                    "verdict": {
                                        "type": "string",
                                        "enum": ["pass", "fail", "unknown"],
                                    },
                                    "reason": {"type": "string"},
                                },
                                "required": ["dimension", "verdict", "reason"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["label", "dimensions"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["grades"],
        "additionalProperties": False,
    }
    return GraderStage(
        system_instruction=system,
        user_content=canonical_json(packet),
        output_schema=schema,
    )


def merge_grader_passes(
    forward: dict[str, dict[str, str]],
    reverse: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for label in sorted(set(forward) | set(reverse)):
        merged[label] = {}
        first = forward.get(label, {})
        second = reverse.get(label, {})
        for dimension in sorted(set(first) | set(second)):
            left = first.get(dimension)
            right = second.get(dimension)
            merged[label][dimension] = (
                left if left == right and left in GRADE_VALUES else "unknown"
            )
    return merged
