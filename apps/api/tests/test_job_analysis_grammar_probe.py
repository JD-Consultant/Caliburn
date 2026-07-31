"""Probe U 的離線計數與轉換測試。**沒有任何網路呼叫。**

這些測試守的是「單一變因」這件事本身:轉換只能折疊 `anyOf: [X, null]`,
其他一切——property 數量與名稱、`required`、enum、巢狀深度、陣列結構——都必須逐項不動。
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.job_analysis.llm import task_analysis_result_provider_schema
from scripts.job_analysis_grammar_probe import (
    PROBE_MAX_OUTPUT_TOKENS,
    build_probe_body,
    build_report,
    count_schema,
    drop_nullable_unions,
    expand_refs,
    schema_hash,
)


OFFICIAL_UNION_LIMIT = 16
OFFICIAL_OPTIONAL_LIMIT = 24


def failed_body() -> dict[str, Any]:
    """2026-07-31 那次失敗請求的形狀(schema 取自 production,其餘欄位為當時的固定值)。"""
    return {
        "model": "anthropic/claude-opus-5",
        "messages": [
            {"role": "system", "content": "instructions"},
            {"role": "user", "content": "packet"},
        ],
        "max_tokens": 4096,
        "reasoning": {"effort": "high", "exclude": True},
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "task_analysis_result.v1",
                "strict": True,
                "schema": task_analysis_result_provider_schema(),
            },
        },
        "provider": {
            "order": ["anthropic"],
            "only": ["anthropic"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
    }


# ── 轉換本身 ───────────────────────────────────────────────────────────────


def test_nullable_union_collapses_to_its_single_branch():
    assert drop_nullable_unions({"anyOf": [{"type": "string"}, {"type": "null"}]}) == {
        "type": "string"
    }


def test_ref_bearing_nullable_union_keeps_the_ref():
    node = {"anyOf": [{"$ref": "#/$defs/TaskFields"}, {"type": "null"}]}

    assert drop_nullable_unions(node) == {"$ref": "#/$defs/TaskFields"}


def test_outer_decoration_survives_the_collapse():
    node = {
        "anyOf": [{"type": "integer"}, {"type": "null"}],
        "title": "Ordinal",
        "description": "keep me",
    }

    assert drop_nullable_unions(node) == {
        "type": "integer",
        "title": "Ordinal",
        "description": "keep me",
    }


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(
            {"anyOf": [{"type": "string"}, {"type": "integer"}]}, id="union-without-null"
        ),
        pytest.param(
            {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}]},
            id="three-branch-union",
        ),
    ],
)
def test_unions_that_are_not_two_branch_nullable_are_left_alone(node):
    assert drop_nullable_unions(copy.deepcopy(node)) == node


def test_transform_does_not_mutate_its_input():
    schema = task_analysis_result_provider_schema()
    before = copy.deepcopy(schema)

    drop_nullable_unions(schema)

    assert schema == before


# ── 產品 schema 的實際計數 ─────────────────────────────────────────────────


def test_production_schema_exceeds_the_official_union_limit():
    counts = count_schema(task_analysis_result_provider_schema())

    assert counts["union_parameters"] == 17
    assert counts["union_parameters"] > OFFICIAL_UNION_LIMIT
    assert counts["optional_parameters"] == 17
    assert counts["optional_parameters"] <= OFFICIAL_OPTIONAL_LIMIT


def test_probe_schema_carries_no_unions_at_all():
    probe = drop_nullable_unions(task_analysis_result_provider_schema())
    counts = count_schema(probe)

    assert counts["union_parameters"] == 0
    assert counts["nullable_unions"] == 0
    assert counts["optional_parameters"] == 0


@pytest.mark.parametrize("dimension", ["properties", "enum_sites", "enum_values", "nesting_levels"])
def test_every_other_counted_dimension_is_untouched(dimension: str):
    """union 以外的維度一動,這個 probe 就不再是單一變因。"""
    original = task_analysis_result_provider_schema()
    probe = drop_nullable_unions(original)

    assert count_schema(probe)[dimension] == count_schema(original)[dimension]


def test_property_names_are_identical_after_the_transform():
    def names(schema: dict[str, Any]) -> set[str]:
        found: set[str] = set()

        def walk(node: Any, path: str) -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item, path)
            elif isinstance(node, dict):
                for key, sub in (node.get("properties") or {}).items():
                    found.add(f"{path}.{key}")
                    walk(sub, f"{path}.{key}")
                for branch in node.get("anyOf") or []:
                    walk(branch, path)
                if "items" in node:
                    walk(node["items"], f"{path}[]")

        walk(expand_refs(schema), "root")
        return found

    original = task_analysis_result_provider_schema()

    assert names(drop_nullable_unions(original)) == names(original)


def test_required_lists_are_identical_after_the_transform():
    def required(schema: dict[str, Any]) -> list[list[str]]:
        found: list[list[str]] = []

        def walk(node: Any) -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item)
            elif isinstance(node, dict):
                if isinstance(node.get("required"), list):
                    found.append(sorted(node["required"]))
                for value in node.values():
                    walk(value)

        walk(expand_refs(schema))
        return sorted(found)

    original = task_analysis_result_provider_schema()

    assert required(drop_nullable_unions(original)) == required(original)


def test_transformed_schema_stays_strict_shaped():
    """strict 要求每個 object 都 `additionalProperties: false`;折疊不得破壞它。"""
    flat = expand_refs(drop_nullable_unions(task_analysis_result_provider_schema()))
    objects: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("type") == "object":
                objects.append(node)
            for value in node.values():
                walk(value)

    walk(flat)

    assert objects
    assert all(obj.get("additionalProperties") is False for obj in objects)


# ── 請求層:只有 schema 與 max_tokens 變 ───────────────────────────────────


def test_probe_body_changes_only_the_schema_and_the_output_cap():
    original = failed_body()
    probe = build_probe_body(original)

    assert probe["max_tokens"] == PROBE_MAX_OUTPUT_TOKENS
    for field in ("model", "messages", "provider", "reasoning", "stream"):
        assert probe[field] == original[field]
    assert probe["response_format"]["type"] == "json_schema"
    assert probe["response_format"]["json_schema"]["name"] == "task_analysis_result.v1"
    assert probe["response_format"]["json_schema"]["strict"] is True
    assert probe["response_format"]["json_schema"]["schema"] != (
        original["response_format"]["json_schema"]["schema"]
    )


def test_build_probe_body_does_not_mutate_the_captured_request():
    original = failed_body()
    before = copy.deepcopy(original)

    build_probe_body(original)

    assert original == before


def test_report_records_both_hashes_counts_and_the_official_limits():
    original = failed_body()
    report = build_report(original, build_probe_body(original))

    assert report["official_limits"] == {"optional_parameters": 24, "union_parameters": 16}
    assert len(report["schema_sha256"]["original"]) == 64
    assert report["schema_sha256"]["original"] != report["schema_sha256"]["probe"]
    assert report["counts"]["original"]["union_parameters"] == 17
    assert report["counts"]["probe"]["union_parameters"] == 0
    assert report["max_output_tokens"] == {"original": 4096, "probe": PROBE_MAX_OUTPUT_TOKENS}
    assert all(report["unchanged_fields"].values())
    assert report["request_bytes"]["probe"] < report["request_bytes"]["original"]


def test_schema_hash_is_stable_and_order_independent():
    schema = task_analysis_result_provider_schema()

    assert schema_hash(schema) == schema_hash(copy.deepcopy(schema))
