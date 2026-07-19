"""Published JSON Schemas for Capture vNext contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .artifacts import ArtifactRecord
from .checkpoint import OperationCheckpoint
from .events import ExecutionEvent, ExecutionTaxonomy, RunManifest
from .outbox import OutboxRecord


SchemaFactory = Callable[[], dict[str, Any]]


SCHEMA_EXPORTS: dict[str, tuple[str, str, SchemaFactory]] = {
    "execution-artifact.v1.schema.json": (
        "https://caliburn.local/schemas/execution-artifact.v1.schema.json",
        "Caliburn interview vNext immutable execution artifact v1",
        ArtifactRecord.model_json_schema,
    ),
    "execution-taxonomy.v1.schema.json": (
        "https://caliburn.local/schemas/execution-taxonomy.v1.schema.json",
        "Caliburn interview vNext execution taxonomy v1",
        ExecutionTaxonomy.model_json_schema,
    ),
    "execution-event.v1.schema.json": (
        "https://caliburn.local/schemas/execution-event.v1.schema.json",
        "Caliburn interview vNext execution event v1",
        ExecutionEvent.model_json_schema,
    ),
    "capture-run-manifest.v1.schema.json": (
        "https://caliburn.local/schemas/capture-run-manifest.v1.schema.json",
        "Caliburn interview vNext Capture run manifest v1",
        RunManifest.model_json_schema,
    ),
    "capture-outbox-record.v1.schema.json": (
        "https://caliburn.local/schemas/capture-outbox-record.v1.schema.json",
        "Caliburn interview vNext Capture outbox record v1",
        OutboxRecord.model_json_schema,
    ),
    "operation-checkpoint.v2.schema.json": (
        "https://caliburn.local/schemas/operation-checkpoint.v2.schema.json",
        "Caliburn interview vNext operation checkpoint v2",
        OperationCheckpoint.model_json_schema,
    ),
}

# The v1 checkpoint schema is superseded by v2 but never rewritten or deleted
# (ADR 0036 §11). It stays on disk as a frozen historical artifact.
HISTORICAL_SCHEMAS: frozenset[str] = frozenset(
    {"operation-checkpoint.v1.schema.json"}
)


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
