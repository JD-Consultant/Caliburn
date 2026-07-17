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
from .portable_schema import portable_strict_output_schema
from .result import ModelCallResult
from .turn_interpret import (
    TurnInterpretInput,
    TurnInterpretOutput,
    TurnInterpretVerificationReport,
)


SchemaFactory = Callable[[], dict[str, Any]]


def _turn_interpret_output_schema() -> dict[str, Any]:
    return portable_strict_output_schema(TurnInterpretOutput.model_json_schema())


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
    "turn-interpret-input.v1.schema.json": (
        "https://caliburn.local/schemas/turn-interpret-input.v1.schema.json",
        "Caliburn interview vNext turn interpretation input v1",
        TurnInterpretInput.model_json_schema,
    ),
    "turn-interpret-output.v1.schema.json": (
        "https://caliburn.local/schemas/turn-interpret-output.v1.schema.json",
        "Caliburn interview vNext portable turn interpretation output v1",
        _turn_interpret_output_schema,
    ),
    "turn-interpret-verification-report.v1.schema.json": (
        "https://caliburn.local/schemas/turn-interpret-verification-report.v1.schema.json",
        "Caliburn interview vNext turn interpretation verification report v1",
        TurnInterpretVerificationReport.model_json_schema,
    ),
}


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
