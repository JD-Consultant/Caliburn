"""Public R1 prompt and portable provider-schema behavior."""

from __future__ import annotations

import json

from app.professional_consultant.prompts import (
    OperationName,
    PromptProfile,
    prompt_for,
)
from app.professional_consultant.schema_projection import (
    SchemaProfile,
    provider_schema_for,
)


def _schema_keywords(node: object) -> set[str]:
    if not isinstance(node, dict):
        return set()
    found = set(node)
    properties = node.get("properties")
    if isinstance(properties, dict):
        for child in properties.values():
            found.update(_schema_keywords(child))
    items = node.get("items")
    if items is not None:
        found.update(_schema_keywords(items))
    variants = node.get("anyOf")
    if isinstance(variants, list):
        for child in variants:
            found.update(_schema_keywords(child))
    return found


def _without_descriptions(node: object) -> object:
    if isinstance(node, dict):
        return {
            key: _without_descriptions(value)
            for key, value in node.items()
            if key != "description"
        }
    if isinstance(node, list):
        return [_without_descriptions(value) for value in node]
    return node


def _object_nodes(node: object) -> list[dict[str, object]]:
    if not isinstance(node, dict):
        return []
    current = [node] if node.get("type") == "object" else []
    for value in node.values():
        if isinstance(value, dict):
            current.extend(_object_nodes(value))
        elif isinstance(value, list):
            for item in value:
                current.extend(_object_nodes(item))
    return current


def test_task_discovery_prompts_are_versioned_and_change_only_the_harness() -> None:
    minimal = prompt_for(OperationName.TASK_DISCOVERY, PromptProfile.MINIMAL)
    full = prompt_for(OperationName.TASK_DISCOVERY, PromptProfile.FULL)

    assert minimal.prompt_id == "task-discover.minimal.v1"
    assert full.prompt_id == "task-discover.full.v1"
    assert minimal.operation is full.operation is OperationName.TASK_DISCOVERY
    assert minimal.content != full.content
    assert "具有明確工作結果" in minimal.content
    assert "Source Claim" not in minimal.content
    assert "Source Claim" in full.content
    assert "Unmapped Signal" in full.content
    assert "chain-of-thought" not in minimal.content.casefold()
    assert "chain-of-thought" not in full.content.casefold()


def test_two_stage_prompts_keep_understanding_and_decision_responsibilities_apart() -> None:
    understand = prompt_for(
        OperationName.TURN_UNDERSTAND, PromptProfile.FULL
    )
    decide = prompt_for(
        OperationName.WORK_RECONCILE_DECIDE, PromptProfile.FULL
    )

    assert understand.prompt_id == "turn-understand.full.v1"
    assert decide.prompt_id == "work-reconcile-decide.full.v1"
    assert "Source Claim" in understand.content
    assert "Task Candidate" not in understand.content
    assert "Task Candidate" in decide.content
    assert "下一問" in decide.content
    assert "重新解讀員工原話" not in decide.content


def test_light_and_heavy_schemas_keep_one_portable_value_shape() -> None:
    allowed = {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "anyOf",
        "description",
    }

    for operation in OperationName:
        light = provider_schema_for(operation, SchemaProfile.LIGHT)
        heavy = provider_schema_for(operation, SchemaProfile.HEAVY)
        light_schema = json.loads(light.schema_text)
        heavy_schema = json.loads(heavy.schema_text)

        assert light.schema_id.endswith(".light.v1")
        assert heavy.schema_id.endswith(".heavy.v1")
        assert _without_descriptions(light_schema) == _without_descriptions(
            heavy_schema
        )
        assert "description" not in _schema_keywords(light_schema)
        assert "description" in _schema_keywords(heavy_schema)
        assert _schema_keywords(light_schema) <= allowed
        assert _schema_keywords(heavy_schema) <= allowed
        assert json.dumps(
            light_schema,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) == light.schema_text
        for object_node in _object_nodes(light_schema):
            assert object_node["additionalProperties"] is False
            assert set(object_node["required"]) == set(
                object_node["properties"]
            )
