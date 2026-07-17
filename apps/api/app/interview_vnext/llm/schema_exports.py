"""Published JSON Schemas for provider-neutral LLM contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .context import (
    CONTEXT_PACKET_ADAPTER,
    ContextBudgetReport,
    ContextSelectionManifest,
    ReferenceSnapshot,
)
from .operation import OperationSpec
from .port import ModelCallRequest
from .result import ModelCallResult


SchemaFactory = Callable[[], dict[str, Any]]


SCHEMA_EXPORTS: dict[str, tuple[str, str, SchemaFactory]] = {
    "context-packet.v1.schema.json": (
        "https://caliburn.local/schemas/context-packet.v1.schema.json",
        "Caliburn interview vNext operation-specific context packet v1",
        CONTEXT_PACKET_ADAPTER.json_schema,
    ),
    "context-selection-manifest.v1.schema.json": (
        "https://caliburn.local/schemas/context-selection-manifest.v1.schema.json",
        "Caliburn interview vNext context selection manifest v1",
        ContextSelectionManifest.model_json_schema,
    ),
    "context-budget-report.v1.schema.json": (
        "https://caliburn.local/schemas/context-budget-report.v1.schema.json",
        "Caliburn interview vNext context budget report v1",
        ContextBudgetReport.model_json_schema,
    ),
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
    "reference-snapshot.v1.schema.json": (
        "https://caliburn.local/schemas/reference-snapshot.v1.schema.json",
        "Caliburn interview vNext immutable reference snapshot v1",
        ReferenceSnapshot.model_json_schema,
    ),
}


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
