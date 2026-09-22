"""Portable provider-schema projections derived from R1 output contracts."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from .contracts import (
    ConsultantContract,
    Identifier,
    TaskDiscoveryOutput,
    TurnUnderstandOutput,
    WorkReconcileDecideOutput,
)
from .prompts import OperationName


class SchemaProfile(StrEnum):
    LIGHT = "light"
    HEAVY = "heavy"


SchemaText = Annotated[str, Field(min_length=1, max_length=200_000)]


class ProviderSchemaArtifact(ConsultantContract):
    schema_id: Identifier
    operation: OperationName
    profile: SchemaProfile
    schema_text: SchemaText


_OUTPUT_MODELS: dict[OperationName, type[BaseModel]] = {
    OperationName.TASK_DISCOVERY: TaskDiscoveryOutput,
    OperationName.TURN_UNDERSTAND: TurnUnderstandOutput,
    OperationName.WORK_RECONCILE_DECIDE: WorkReconcileDecideOutput,
}

_SCHEMA_NAMES = {
    OperationName.TASK_DISCOVERY: "task-discover-output",
    OperationName.TURN_UNDERSTAND: "turn-understand-output",
    OperationName.WORK_RECONCILE_DECIDE: "work-reconcile-decide-output",
}

_PROPERTY_DESCRIPTIONS = {
    "schema_version": "固定的 operation output schema 版本。",
    "claims": "本回合從員工來源辨識出的 Source Claims；資訊不足時可以是空陣列。",
    "unmapped_signals": "重要但尚不能安全映射為工作結構的來源訊號。",
    "stories": "由來源 claims 組成的工作故事材料；故事本身不是 Task。",
    "work_units": "跨 claims 或 stories 整併後、仍可進一步調整邊界的工作單元。",
    "decisions": "對既有與新 Task Candidate 的 add/edit/merge/split/no-op/clarify 裁決。",
    "task_candidates": "符合 Task 定義的候選；沒有足夠支持時必須是空陣列。",
    "next_question": "唯一一個自然、單一、不重複且不引導的下一問。",
    "anchors": "精確引用允許來源文字的 Unicode code-point 半開區間。",
    "ownership": "該 claim 描述的工作責任歸屬，不得把他人責任改成本人責任。",
    "time_scope": "該 claim 是目前、過去、未來假設或未知。",
    "typicality": "例行、週期、正式低頻、一次性、例外或未知。",
    "correction_target_claim_id": "更正 claim 指向的舊 claim ID；非更正時為 null。",
    "support_claim_ids": "對該工作單元或 Task 提供正向支持的 claim IDs。",
    "counter_claim_ids": "削弱、限制或反駁該工作單元或 Task 的 claim IDs。",
    "boundary": "Task 六項邊界判準的逐項狀態，不得以欄位必填逼出 Task。",
    "work_unit_ids": "形成該 Task 或 decision 的 Work Unit IDs。",
    "action": "下一問只可 broaden、deepen_story 或 clarify_boundary。",
    "target_gap": "此下一問要降低的單一最高價值資訊缺口。",
}


def _project_node(
    node: dict[str, object],
    *,
    definitions: dict[str, object],
    profile: SchemaProfile,
    property_name: str | None = None,
) -> dict[str, object]:
    reference = node.get("$ref")
    if isinstance(reference, str):
        prefix = "#/$defs/"
        if not reference.startswith(prefix):
            raise ValueError(f"non-local schema reference is not portable: {reference}")
        name = reference.removeprefix(prefix)
        target = definitions.get(name)
        if not isinstance(target, dict):
            raise ValueError(f"unknown local schema reference: {reference}")
        return _project_node(
            target,
            definitions=definitions,
            profile=profile,
            property_name=property_name,
        )

    projected: dict[str, object] = {}
    if "const" in node:
        projected["enum"] = [node["const"]]
    elif isinstance(node.get("enum"), list):
        projected["enum"] = node["enum"]

    schema_type = node.get("type")
    if isinstance(schema_type, str):
        projected["type"] = schema_type

    properties = node.get("properties")
    if isinstance(properties, dict):
        projected["properties"] = {
            name: _project_node(
                child,
                definitions=definitions,
                profile=profile,
                property_name=name,
            )
            for name, child in properties.items()
            if isinstance(child, dict)
        }
    required = node.get("required")
    if isinstance(required, list):
        projected["required"] = required
    if "additionalProperties" in node:
        if node["additionalProperties"] is not False:
            raise ValueError("portable object schemas must be closed")
        projected["additionalProperties"] = False

    items = node.get("items")
    if isinstance(items, dict):
        projected["items"] = _project_node(
            items, definitions=definitions, profile=profile
        )
    variants = node.get("anyOf")
    if isinstance(variants, list):
        projected["anyOf"] = [
            _project_node(child, definitions=definitions, profile=profile)
            for child in variants
            if isinstance(child, dict)
        ]

    if profile is SchemaProfile.HEAVY:
        description = _PROPERTY_DESCRIPTIONS.get(property_name or "")
        if description is None and isinstance(node.get("description"), str):
            description = node["description"]
        if description is not None:
            projected["description"] = description
    return projected


def provider_schema_for(
    operation: OperationName, profile: SchemaProfile
) -> ProviderSchemaArtifact:
    """Project a canonical portable schema without changing its value shape."""

    raw = _OUTPUT_MODELS[operation].model_json_schema()
    definitions = raw.get("$defs", {})
    if not isinstance(definitions, dict):
        raise ValueError("Pydantic schema definitions must be an object")
    projected = _project_node(
        raw, definitions=definitions, profile=profile
    )
    schema_json = json.dumps(
        projected,
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    schema_id = f"{_SCHEMA_NAMES[operation]}.{profile.value}.v1"
    return ProviderSchemaArtifact(
        schema_id=schema_id,
        operation=operation,
        profile=profile,
        schema_text=schema_json,
    )
