"""Published JSON Schemas for interview vNext application workflow contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .noop_result import OperationNoopResult


SchemaFactory = Callable[[], dict[str, Any]]


def _turn_interpret_execution_outcome_schema() -> dict[str, Any]:
    # Imported lazily: operation_executor pulls in the provider port, and the
    # schema writer must not drag that graph in at module import time.
    from .operation_executor import TurnInterpretExecutionOutcome

    return TurnInterpretExecutionOutcome.model_json_schema()


SCHEMA_EXPORTS: dict[str, tuple[str, str, SchemaFactory]] = {
    "operation-noop-result.v1.schema.json": (
        "https://caliburn.local/schemas/operation-noop-result.v1.schema.json",
        "Caliburn interview vNext verified no-op operation result v1",
        OperationNoopResult.model_json_schema,
    ),
    "turn-interpret-execution-outcome.v2.schema.json": (
        "https://caliburn.local/schemas/turn-interpret-execution-outcome.v2.schema.json",
        "Caliburn interview vNext turn interpretation execution outcome v2",
        _turn_interpret_execution_outcome_schema,
    ),
}


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
