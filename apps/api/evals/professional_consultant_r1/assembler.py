"""R1-only prompt, Context and portable schema assembly.

These fields measure the R1 treatments. They are not production contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import Result, canonical_hash, canonical_json, source_texts
from .matrix import ArmSpec

STAGE_UNDERSTAND = "understand"
STAGE_FINAL = "final"

PROMPT_VERSION = "r1-task-discovery-prompt.1"
CONTEXT_ASSEMBLER_VERSION = "r1-task-discovery-context.1"

TASK_DEFINITION = (
    "Task 是員工目前、穩定、屬於本人責任，且具有可辨識目的或結果的工作單位。"
)

TASK_POLICIES = (
    "Story 是證據，不自動等於 Task。",
    "工具、技術、知識、技能與單一步驟不因被提及就成為 Task。",
    "Task 必須有可辨識結果、本人責任、可指派與可檢查的邊界。",
    "正式低頻責任可成立；過去工作、他人工作與一次性代班通常不成立。",
    "最新明確更正壓過舊說法；證據不足時使用 clarify 或 no_change。",
    "一次只提出一個能降低最大不確定性的下一問；不得產出 O/P/K/S/A。",
)


def _string_schema() -> dict[str, Any]:
    return {"type": "string"}


def _nullable_string_schema() -> dict[str, Any]:
    return {"type": ["string", "null"]}


def _anchor_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "source_id": _string_schema(),
            "quote": _string_schema(),
        },
        "required": ["source_id", "quote"],
        "additionalProperties": False,
    }


def _task_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "task_statement": _string_schema(),
            "intended_outcome": _string_schema(),
            "source_anchors": {"type": "array", "items": _anchor_schema()},
        },
        "required": ["task_statement", "intended_outcome", "source_anchors"],
        "additionalProperties": False,
    }


def _next_question_schema() -> dict[str, Any]:
    return {
        "type": ["object", "null"],
        "properties": {
            "text": _nullable_string_schema(),
            "purpose": _nullable_string_schema(),
        },
        "required": ["text", "purpose"],
        "additionalProperties": False,
    }


def _state_change_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "change_type": {
                "type": "string",
                "enum": ["add", "revise", "merge", "split", "withdraw", "no_change"],
            },
            "affected_existing_task_ids": {"type": "array", "items": _string_schema()},
        },
        "required": ["change_type", "affected_existing_task_ids"],
        "additionalProperties": False,
    }


def _final_schema(arm: ArmSpec) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "analysis_decision": {
            "type": "string",
            "enum": ["propose_current_tasks", "clarify", "no_change"],
        },
        "proposed_tasks": {"type": "array", "items": _task_schema()},
        "next_question": _next_question_schema(),
        "limitations": {"type": "array", "items": _string_schema()},
        # Structured Outputs 要求 properties 全部列入 required；用 null 表示不要求
        # 模型產生可見推理，避免 rationale 本身成為 arm 的隱藏 treatment。
        "decision_basis": _nullable_string_schema(),
    }
    required = list(properties)
    if arm.harness == "full":
        properties["state_change"] = _state_change_schema()
        required.append("state_change")
    if arm.schema_weight == "heavy":
        properties["task_assessments"] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_index": {"type": "integer"},
                    "meaningful_outcome": {"type": "string", "enum": ["yes", "no", "unknown"]},
                    "employee_responsibility": {
                        "type": "string",
                        "enum": ["yes", "no", "unknown"],
                    },
                    "stability": {"type": "string", "enum": ["yes", "no", "unknown"]},
                    "boundary_coherence": {
                        "type": "string",
                        "enum": ["yes", "no", "unknown"],
                    },
                },
                "required": [
                    "candidate_index",
                    "meaningful_outcome",
                    "employee_responsibility",
                    "stability",
                    "boundary_coherence",
                ],
                "additionalProperties": False,
            },
        }
        required.append("task_assessments")
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _stage1_observation_schema(heavy: bool) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "statement": _string_schema(),
        "source_anchors": {"type": "array", "items": _anchor_schema()},
    }
    if heavy:
        properties.update(
            {
                "actor": _string_schema(),
                "time_scope": _string_schema(),
                "typicality": _string_schema(),
                "responsibility": _string_schema(),
                "activity_kind": _string_schema(),
                "intended_outcome": _string_schema(),
                "unknown_reason": _nullable_string_schema(),
            }
        )
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _stage1_schema(arm: ArmSpec) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "observations": {
                "type": "array",
                "items": _stage1_observation_schema(arm.schema_weight == "heavy"),
            },
            "corrections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "new_source_id": _string_schema(),
                        "superseded_source_ids": {
                            "type": "array",
                            "items": _string_schema(),
                        },
                    },
                    "required": ["new_source_id", "superseded_source_ids"],
                    "additionalProperties": False,
                },
            },
            "limitations": {"type": "array", "items": _string_schema()},
        },
        "required": ["observations", "corrections", "limitations"],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class AssembledStage:
    operation: str
    arm_id: str
    context_packet: dict[str, Any]
    system_instruction: str
    user_content: str
    output_schema: dict[str, Any]
    schema_name: str
    prompt_version: str = PROMPT_VERSION
    context_assembler_version: str = CONTEXT_ASSEMBLER_VERSION

    @property
    def schema_hash(self) -> str:
        return canonical_hash(self.output_schema)


def assemble_stage(
    case: dict[str, Any],
    arm: ArmSpec,
    stage: str,
    *,
    stage1_result: dict[str, Any] | None = None,
) -> AssembledStage:
    if stage not in (STAGE_UNDERSTAND, STAGE_FINAL):
        raise ValueError(f"unknown R1 stage: {stage}")
    if stage == STAGE_UNDERSTAND and arm.stage_count != 2:
        raise ValueError(f"{arm.arm_id} is one-stage and has no understand stage")
    if stage == STAGE_FINAL and arm.stage_count == 2 and stage1_result is None:
        raise ValueError(f"{arm.arm_id} final stage requires a verified stage1_result")

    context: dict[str, Any] = {"sources": case["sources"]}
    if arm.harness == "minimal":
        context["task_definition"] = TASK_DEFINITION
    else:
        context["current_work_model"] = case.get("initial_work_model") or {
            "task_candidates": []
        }
        # 設計 §5.3：Stage 1 只收 Source Layer、Current Work Model 與理解型 prompt；
        # Task 六項判準與變更規則屬 Stage 2。若 Stage 1 也帶判準，two-stage 會退化成
        # 「同一份 context 打兩次」，one-stage vs two-stage 的對比就不成立。
        if stage == STAGE_FINAL:
            context["task_policies"] = list(TASK_POLICIES)
    if stage1_result is not None:
        context["stage1_result"] = stage1_result

    if stage == STAGE_UNDERSTAND:
        system = (
            "你是職務分析顧問的理解階段。只整理員工原話中的責任、來源、更正與不確定性；"
            "不要建立正式 Task，不要推測輸入外資訊。"
        )
        schema = _stage1_schema(arm)
        schema_name = f"r1_{arm.arm_id.lower()}_understand"
    else:
        rules = "\n".join(f"- {item}" for item in TASK_POLICIES)
        system = (
            "你是職務分析顧問。根據提供的完整來源，判斷目前應成立的完整 Task 語意集合，"
            "資訊不足時可以不建立 Task。\n"
            f"{rules if arm.harness == 'full' else TASK_DEFINITION}"
        )
        schema = _final_schema(arm)
        schema_name = f"r1_{arm.arm_id.lower()}_final"

    return AssembledStage(
        operation=stage,
        arm_id=arm.arm_id,
        context_packet=context,
        system_instruction=system,
        user_content=canonical_json(context),
        output_schema=schema,
        schema_name=schema_name,
    )


def verify_portable_output(payload: Any, schema: dict[str, Any]) -> Result:
    """驗本實驗實際使用的 JSON Schema 子集，不依賴 provider 保證。

    這不是通用 JSON Schema engine；只支援本檔產生的 type／enum／required／
    additionalProperties／properties／items，避免為一次性實驗引入框架。
    """

    result = Result()

    def visit(value: Any, node: dict[str, Any], locator: str) -> None:
        allowed_types = node.get("type")
        if isinstance(allowed_types, str):
            allowed_types = [allowed_types]

        actual_type = (
            "null"
            if value is None
            else "boolean"
            if isinstance(value, bool)
            else "object"
            if isinstance(value, dict)
            else "array"
            if isinstance(value, list)
            else "integer"
            if isinstance(value, int)
            else "number"
            if isinstance(value, float)
            else "string"
            if isinstance(value, str)
            else "unknown"
        )
        if isinstance(allowed_types, list) and actual_type not in allowed_types:
            result.error(
                "output_schema",
                f"型別必須是 {allowed_types}，實得 {actual_type}",
                locator,
            )
            return

        if "enum" in node and value not in node["enum"]:
            result.error("output_schema", f"值不在 enum：{value!r}", locator)

        if actual_type == "object":
            properties = node.get("properties", {})
            for key in node.get("required", []):
                if key not in value:
                    result.error("output_schema", f"缺少必要欄位 {key}", locator)
            if node.get("additionalProperties") is False:
                for key in sorted(set(value) - set(properties)):
                    result.error("output_schema", f"不得包含欄位 {key}", locator)
            for key, child in properties.items():
                if key in value:
                    visit(value[key], child, f"{locator}.{key}")
        elif actual_type == "array":
            item_schema = node.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    visit(item, item_schema, f"{locator}[{index}]")

    visit(payload, schema, "output")
    return result


def verify_stage1_result(case: dict[str, Any], arm: ArmSpec, payload: Any) -> Result:
    result = Result()
    result.extend(verify_portable_output(payload, _stage1_schema(arm)))
    if not result.ok:
        return result
    if not isinstance(payload, dict):
        result.error("stage1_shape", "Stage 1 output 必須是物件", "stage1")
        return result
    observations = payload.get("observations")
    corrections = payload.get("corrections")
    limitations = payload.get("limitations")
    if not isinstance(observations, list):
        result.error("stage1_shape", "observations 必須是陣列", "stage1.observations")
        return result
    if not isinstance(corrections, list):
        result.error("stage1_shape", "corrections 必須是陣列", "stage1.corrections")
    if not isinstance(limitations, list):
        result.error("stage1_shape", "limitations 必須是陣列", "stage1.limitations")

    texts = source_texts(case)
    for index, observation in enumerate(observations):
        locator = f"stage1.observations[{index}]"
        if not isinstance(observation, dict):
            result.error("stage1_shape", "observation 必須是物件", locator)
            continue
        if not isinstance(observation.get("statement"), str) or not observation["statement"].strip():
            result.error("stage1_shape", "statement 必須是非空字串", locator)
        anchors = observation.get("source_anchors")
        if not isinstance(anchors, list) or not anchors:
            result.error("stage1_source_anchor", "observation 至少需要一個 source anchor", locator)
            continue
        for anchor in anchors:
            if not isinstance(anchor, dict):
                result.error("stage1_source_anchor", "source anchor 必須是物件", locator)
                continue
            source_id = anchor.get("source_id")
            quote = anchor.get("quote")
            if source_id not in texts or not isinstance(quote, str) or quote not in texts.get(source_id, ""):
                result.error(
                    "stage1_source_anchor",
                    "source_id 必須存在，且 quote 必須是該來源的逐字子字串",
                    locator,
                )
    return result
