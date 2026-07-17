"""Published JSON Schemas for interview vNext application workflow contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .noop_result import OperationNoopResult


SchemaFactory = Callable[[], dict[str, Any]]


SCHEMA_EXPORTS: dict[str, tuple[str, str, SchemaFactory]] = {
    "operation-noop-result.v1.schema.json": (
        "https://caliburn.local/schemas/operation-noop-result.v1.schema.json",
        "Caliburn interview vNext verified no-op operation result v1",
        OperationNoopResult.model_json_schema,
    ),
}


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
