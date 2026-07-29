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
