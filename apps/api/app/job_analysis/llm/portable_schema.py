"""Portable strict-output JSON Schema 的投影與 lint(ADR 0040 決定 24)。

OpenRouter-first 前提下 provider 端的 schema 保證不可攜:支援度 per endpoint、
enforcement 因 provider 而異、strict mode 會限制可用特性(決定 23)。因此送出去的
schema 只用可攜子集——object／array／基本型別、required、nullable union、enum、
`additionalProperties: false`、基本巢狀——其餘一律由 deterministic verifier 負責
(決定 25)。

投影會**丟掉**本地約束(`minLength`、`pattern`、`default`…)。那不是損失:Pydantic
仍是這些約束的權威,parse 時照樣執行;provider schema 只負責語法邊界。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_ANNOTATION_KEYWORDS = frozenset({"$schema", "description", "title"})
_STRUCTURAL_KEYWORDS = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "anyOf",
        "enum",
        "items",
        "properties",
        "required",
        "type",
    }
)
_UNSUPPORTED_CONSTRAINTS = frozenset(
    {
        "default",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "maxItems",
        "maxLength",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "multipleOf",
        "pattern",
        "prefixItems",
        "uniqueItems",
    }
)
_JSON_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)


class ProviderSchemaPortabilityError(ValueError):
    """A provider-facing schema is outside the approved portable subset."""


def _project(value: Any) -> Any:
    if isinstance(value, list):
        return [_project(item) for item in value]
    if not isinstance(value, dict):
        return value

    projected: dict[str, Any] = {}
    for key, item in value.items():
        if key in _UNSUPPORTED_CONSTRAINTS:
            continue
        if key == "const":
            # 單值 const 在部分 provider 的 strict mode 不被支援;單元素 enum 一樣嚴格。
            projected["enum"] = [_project(item)]
            continue
        projected[key] = _project(item)

    if projected.get("type") == "object":
        # strict mode 要求每個 property 都在 required 裡;可選欄位靠 nullable union
        # 表達,不靠「可以不出現」。
        projected["additionalProperties"] = False
        projected["required"] = list(projected.get("properties", {}))
    return projected


def portable_strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """把本地 schema 投影成可攜子集,並在回傳前自我 lint。"""

    projected = _project(deepcopy(schema))
    assert_portable_strict_output_schema(projected)
    return projected


def _without_titles(value: Any) -> Any:
    if isinstance(value, list):
        return [_without_titles(item) for item in value]
    if not isinstance(value, dict):
        return value

    stripped: dict[str, Any] = {}
    for key, item in value.items():
        if key == "title":
            continue
        if key in {"$defs", "properties"} and isinstance(item, dict):
            # 這一層的 key 是 property／definition 名稱,不是 schema 關鍵字:
            # 名為 `title` 的欄位不能被當成標註吃掉。
            stripped[key] = {
                name: _without_titles(child) for name, child in item.items()
            }
            continue
        stripped[key] = _without_titles(item)
    return stripped


def compact_strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """可攜投影:拿掉自動生成的 `title`,並把 `$ref` 全部內聯。

    `title` 是 Pydantic 依欄位名生成的 Title Case 版本(`target_task_ordinals` 旁邊配一個
    `"Target Task Ordinals"`),對模型零資訊量卻佔 schema 的 17%。`description` 保留,
    但在 wire 契約裡那是刻意寫給模型的中性值約定,不是開發者註解的出口——
    `tests/test_job_analysis_wire_schema.py` 守住總量與內容。

    `$ref` 內聯是**可攜性要求**,不是最佳化:Pydantic 把 enum 欄位輸出成
    `{"$ref": …, "description": …}`,OpenAI strict 直接拒收帶兄弟 keyword 的 `$ref`
    (2026-07-31 `openai/gpt-5.6-luna-pro`:`$ref cannot have keywords {'description'}`)。
    而那些 `description` 就是給模型的規則本體,不能為了保住 `$ref` 拿掉。
    這份契約每個 `$def` 都只被引用一次,展開沒有重用損失——schema 反而變小,
    離 Anthropic 的 grammar 上限更遠。展開時 property 端的 keyword 蓋過 `$def` 自己的。
    """

    projected = _project(_without_titles(deepcopy(schema)))
    assert_portable_strict_output_schema(projected)
    return expand_refs(projected)


def expand_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """把 `$ref` 全部內聯。編譯後的 grammar 沒有共用,計數必須照展開後的形狀算。"""

    defs = schema.get("$defs") or schema.get("definitions") or {}

    def walk(node: Any, depth: int = 0) -> Any:
        if depth > 200:
            raise RecursionError("schema appears recursive; unsupported by strict mode")
        if isinstance(node, list):
            return [walk(item, depth + 1) for item in node]
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if isinstance(ref, str):
            merged = deepcopy(defs[ref.rsplit("/", 1)[-1]])
            merged.update({key: item for key, item in node.items() if key != "$ref"})
            return walk(merged, depth + 1)
        return {
            key: walk(item, depth + 1) for key, item in node.items() if key != "$defs"
        }

    return walk(schema)


def schema_complexity(schema: dict[str, Any]) -> dict[str, int]:
    """strict grammar 編譯器關心的維度,一律以 `$ref` 展開後的形狀計數。

    這不是官方限制的副本,是我們自己的預算尺。官方明載個別限制全部滿足仍可能被拒
    (另有未公開的 compiled grammar size 上限),所以送出去的 schema 要留餘裕,
    不是壓到剛好合規。
    """

    flat = expand_refs(schema)
    totals = {
        "union_parameters": 0,
        "optional_parameters": 0,
        "properties": 0,
        "enum_sites": 0,
        "enum_values": 0,
        "nesting_levels": 0,
    }

    def walk(node: Any, level: int) -> None:
        totals["nesting_levels"] = max(totals["nesting_levels"], level)
        if isinstance(node, list):
            for item in node:
                walk(item, level)
            return
        if not isinstance(node, dict):
            return

        branches = node.get("anyOf")
        if isinstance(branches, list):
            totals["union_parameters"] += 1
            if any(
                isinstance(branch, dict) and branch.get("type") == "null"
                for branch in branches
            ):
                # strict 要求全欄位 required;optional 就是以 null union 表達的那些。
                totals["optional_parameters"] += 1
            for branch in branches:
                walk(branch, level)

        enum_values = node.get("enum")
        if isinstance(enum_values, list):
            totals["enum_sites"] += 1
            totals["enum_values"] += len(enum_values)

        properties = node.get("properties")
        if isinstance(properties, dict):
            totals["properties"] += len(properties)
            for sub in properties.values():
                walk(sub, level + 1)

        if "items" in node:
            walk(node["items"], level + 1)

    walk(flat, 0)
    return totals


def assert_portable_strict_output_schema(schema: dict[str, Any]) -> None:
    """在 schema 送到任何 provider 之前擋下不可攜的語意。"""

    def visit(value: Any, path: str) -> None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")
            return
        if not isinstance(value, dict):
            return

        unknown = set(value) - _ANNOTATION_KEYWORDS - _STRUCTURAL_KEYWORDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ProviderSchemaPortabilityError(
                f"unsupported JSON Schema keyword(s) at {path}: {names}"
            )

        schema_type = value.get("type")
        if schema_type is not None and schema_type not in _JSON_TYPES:
            raise ProviderSchemaPortabilityError(
                f"unsupported JSON type at {path}: {schema_type!r}"
            )

        if schema_type == "object":
            properties = value.get("properties")
            required = value.get("required")
            if not isinstance(properties, dict) or not isinstance(required, list):
                raise ProviderSchemaPortabilityError(
                    f"object at {path} requires properties and required"
                )
            if required != list(properties):
                raise ProviderSchemaPortabilityError(
                    f"every property must be required in schema order at {path}"
                )
            if value.get("additionalProperties") is not False:
                raise ProviderSchemaPortabilityError(
                    f"additionalProperties must be false at {path}"
                )

        if "enum" in value:
            enum = value["enum"]
            if (
                not isinstance(enum, list)
                or not enum
                or len(enum) != len({repr(item) for item in enum})
            ):
                raise ProviderSchemaPortabilityError(
                    f"enum must be finite, non-empty, and unique at {path}"
                )

        if "anyOf" in value:
            options = value["anyOf"]
            if not isinstance(options, list) or len(options) != 2:
                raise ProviderSchemaPortabilityError(
                    f"only two-branch nullable anyOf is allowed at {path}"
                )
            nulls = sum(
                isinstance(option, dict) and option.get("type") == "null"
                for option in options
            )
            if nulls != 1:
                raise ProviderSchemaPortabilityError(
                    f"anyOf must contain exactly one null branch at {path}"
                )

        for key, item in value.items():
            if key in {"$defs", "properties"} and isinstance(item, dict):
                for name, child in item.items():
                    visit(child, f"{path}.{key}.{name}")
            elif key not in {"enum", "required"}:
                visit(item, f"{path}.{key}")

    visit(schema, "$")
