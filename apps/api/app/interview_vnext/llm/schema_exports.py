"""Published JSON Schemas for provider-neutral LLM contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .operation import OperationSpec
from .port import ModelCallRequest
from .result import ModelCallResult


SchemaFactory = Callable[[], dict[str, Any]]


SCHEMA_EXPORTS: dict[str, tuple[str, str, SchemaFactory]] = {
    "llm-operation-spec.v1.schema.json": (
        "https://caliburn.local/schemas/llm-operation-spec.v1.schema.json",
        "Caliburn interview vNext LLM operation specification v1",
        OperationSpec.model_json_schema,
    ),
    "model-call-request.v1.schema.json": (
        "https://caliburn.local/schemas/model-call-request.v1.schema.json",
        "Caliburn interview vNext provider-neutral model request v1",
        ModelCallRequest.model_json_schema,
    ),
    "model-call-result.v1.schema.json": (
        "https://caliburn.local/schemas/model-call-result.v1.schema.json",
        "Caliburn interview vNext provider-neutral model result v1",
        ModelCallResult.model_json_schema,
    ),
}


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
