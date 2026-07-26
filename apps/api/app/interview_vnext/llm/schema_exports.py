"""Published JSON Schemas for provider-neutral LLM contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .binding import ProviderBinding
from .conformance import ConformanceReport
from .context import (
    CONTEXT_PACKET_ADAPTER,
    ContextBudgetReport,
    ContextSelectionManifest,
    QuestionSelectContextPacket,
    ReferenceSnapshot,
)
from .execution import ProviderExecutionEvidence
from .operation import OperationSpec
from .port import ModelCallRequest, ResolvedModelCall
from .portable_schema import SchemaProjectionReport, portable_strict_output_schema
from .result import ModelCallResult
from .turn_interpret import (
    TurnInterpretInput,
    TurnInterpretOutput,
    TurnInterpretVerificationReport,
)
from .question_select import (
    QuestionSelectInput,
    QuestionSelectOutput,
    QuestionSelectVerificationReport,
)


SchemaFactory = Callable[[], dict[str, Any]]


def _turn_interpret_output_schema() -> dict[str, Any]:
    return portable_strict_output_schema(TurnInterpretOutput.model_json_schema())


def _question_select_output_schema() -> dict[str, Any]:
    return portable_strict_output_schema(QuestionSelectOutput.model_json_schema())


SCHEMA_EXPORTS: dict[str, tuple[str, str, SchemaFactory]] = {
    "context-packet.v2.schema.json": (
        "https://caliburn.local/schemas/context-packet.v2.schema.json",
        "Caliburn interview vNext operation-specific context packet v2",
        CONTEXT_PACKET_ADAPTER.json_schema,
    ),
    "context-selection-manifest.v2.schema.json": (
        "https://caliburn.local/schemas/context-selection-manifest.v2.schema.json",
        "Caliburn interview vNext context selection manifest v2",
        ContextSelectionManifest.model_json_schema,
    ),
    "context-budget-report.v2.schema.json": (
        "https://caliburn.local/schemas/context-budget-report.v2.schema.json",
        "Caliburn interview vNext context budget report v2",
        ContextBudgetReport.model_json_schema,
    ),
    "llm-operation-spec.v1.schema.json": (
        "https://caliburn.local/schemas/llm-operation-spec.v1.schema.json",
        "Caliburn interview vNext LLM operation specification v1",
        OperationSpec.model_json_schema,
    ),
    "model-call-request.v2.schema.json": (
        "https://caliburn.local/schemas/model-call-request.v2.schema.json",
        "Caliburn interview vNext binding-resolved model request v2",
        ModelCallRequest.model_json_schema,
    ),
    "provider-binding.v1.schema.json": (
        "https://caliburn.local/schemas/provider-binding.v1.schema.json",
        "Caliburn interview vNext runtime provider binding v1",
        ProviderBinding.model_json_schema,
    ),
    "provider-conformance-report.v1.schema.json": (
        "https://caliburn.local/schemas/provider-conformance-report.v1.schema.json",
        "Caliburn interview vNext provider conformance report v1",
        ConformanceReport.model_json_schema,
    ),
    "provider-execution-evidence.v1.schema.json": (
        "https://caliburn.local/schemas/provider-execution-evidence.v1.schema.json",
        "Caliburn interview vNext normalized provider execution evidence v1",
        ProviderExecutionEvidence.model_json_schema,
    ),
    "model-call-result.v2.schema.json": (
        "https://caliburn.local/schemas/model-call-result.v2.schema.json",
        "Caliburn interview vNext provider-neutral model result v2",
        ModelCallResult.model_json_schema,
    ),
    "resolved-model-call.v1.schema.json": (
        "https://caliburn.local/schemas/resolved-model-call.v1.schema.json",
        "Caliburn interview vNext resolved model call v1",
        ResolvedModelCall.model_json_schema,
    ),
    "reference-snapshot.v1.schema.json": (
        "https://caliburn.local/schemas/reference-snapshot.v1.schema.json",
        "Caliburn interview vNext immutable reference snapshot v1",
        ReferenceSnapshot.model_json_schema,
    ),
    "schema-projection-report.v1.schema.json": (
        "https://caliburn.local/schemas/schema-projection-report.v1.schema.json",
        "Caliburn interview vNext portable schema projection report v1",
        SchemaProjectionReport.model_json_schema,
    ),
    "turn-interpret-input.v2.schema.json": (
        "https://caliburn.local/schemas/turn-interpret-input.v2.schema.json",
        "Caliburn interview vNext turn interpretation input v2",
        TurnInterpretInput.model_json_schema,
    ),
    "turn-interpret-output.v2.schema.json": (
        "https://caliburn.local/schemas/turn-interpret-output.v2.schema.json",
        "Caliburn interview vNext portable turn interpretation output v2",
        _turn_interpret_output_schema,
    ),
    "turn-interpret-verification-report.v2.schema.json": (
        "https://caliburn.local/schemas/turn-interpret-verification-report.v2.schema.json",
        "Caliburn interview vNext turn interpretation verification report v2",
        TurnInterpretVerificationReport.model_json_schema,
    ),
    "question-select-context.v1.schema.json": (
        "https://caliburn.local/schemas/question-select-context.v1.schema.json",
        "Caliburn interview vNext question selection context v1",
        QuestionSelectContextPacket.model_json_schema,
    ),
    "question-select-input.v1.schema.json": (
        "https://caliburn.local/schemas/question-select-input.v1.schema.json",
        "Caliburn interview vNext question selection input v1",
        QuestionSelectInput.model_json_schema,
    ),
    "question-select-output.v1.schema.json": (
        "https://caliburn.local/schemas/question-select-output.v1.schema.json",
        "Caliburn interview vNext portable question selection output v1",
        _question_select_output_schema,
    ),
    "question-select-verification-report.v1.schema.json": (
        "https://caliburn.local/schemas/question-select-verification-report.v1.schema.json",
        "Caliburn interview vNext question selection verification report v1",
        QuestionSelectVerificationReport.model_json_schema,
    ),
}


# v1 request/result schemas are superseded by v2 but never rewritten or deleted
# (ADR 0036 §11; plan §4.1). They stay on disk as frozen historical artifacts and
# are not regenerated from the active Pydantic models.
HISTORICAL_SCHEMAS: frozenset[str] = frozenset(
    {
        "model-call-request.v1.schema.json",
        "model-call-result.v1.schema.json",
        # R5-BC: context and turn-interpret contracts nest production types that
        # changed shape, so the v1 files are frozen rather than regenerated.
        "context-packet.v1.schema.json",
        "context-selection-manifest.v1.schema.json",
        "context-budget-report.v1.schema.json",
        "turn-interpret-input.v1.schema.json",
        "turn-interpret-output.v1.schema.json",
        "turn-interpret-verification-report.v1.schema.json",
    }
)

_OVERLAP = HISTORICAL_SCHEMAS & SCHEMA_EXPORTS.keys()
if _OVERLAP:
    raise RuntimeError(f"schema filenames cannot be both active and historical: {sorted(_OVERLAP)}")


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
