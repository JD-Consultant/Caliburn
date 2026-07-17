"""Portable strict-output JSON Schema projection and lint.

Provider constrained decoding is intentionally treated as a syntax boundary.
Pydantic remains the authority for constraints that are removed here.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_ANNOTATION_KEYWORDS = frozenset({"$id", "$schema", "description", "title"})
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
        "uniqueItems",
    }
)
_JSON_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)


class ProviderSchemaPortabilityError(ValueError):
    """A provider-facing schema is outside the approved portable subset."""


def portable_strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove local-only constraints and assert the strict provider intersection."""

    projected = _project(deepcopy(schema))
    assert_portable_strict_output_schema(projected)
    return projected


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
            projected["enum"] = [_project(item)]
            continue
        projected[key] = _project(item)

    if projected.get("type") == "object":
        properties = projected.get("properties", {})
        projected["additionalProperties"] = False
        projected["required"] = list(properties)
    return projected


def assert_portable_strict_output_schema(
    schema: dict[str, Any], *, max_nullable_unions: int = 16
) -> None:
    """Reject unsupported semantics before a schema reaches either provider."""

    nullable_unions = 0

    def visit(value: Any, path: str) -> None:
        nonlocal nullable_unions
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
            if not isinstance(enum, list) or not enum or len(enum) != len(
                {repr(item) for item in enum}
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
            nullable_unions += 1

        for key, item in value.items():
            if key in {"$defs", "properties"} and isinstance(item, dict):
                for name, child in item.items():
                    visit(child, f"{path}.{key}.{name}")
            elif key not in {"enum", "required"}:
                visit(item, f"{path}.{key}")

    visit(schema, "$")
    if nullable_unions > max_nullable_unions:
        raise ProviderSchemaPortabilityError(
            f"nullable union count {nullable_unions} exceeds {max_nullable_unions}"
        )
