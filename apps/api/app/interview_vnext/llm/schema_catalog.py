"""Closed, content-addressed catalog of active production output schemas.

The outbound provider schema must be byte-identical (canonical JSON) to the
published portable schema the request's `output_schema_artifact` hash describes.
Resolution never reads the filesystem or network beyond the committed factory,
and any mismatch fails locally before HTTP.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from app.interview_vnext.domain.hashing import canonical_hash
from .operation import OperationSpec
from .operation_documents import question_select_operation, turn_interpret_operation
from .port import ModelCallRequest
from .portable_schema import (
    ProviderSchemaPortabilityError,
    assert_portable_strict_output_schema,
)
from .schema_exports import published_schema


TURN_INTERPRET_OUTPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-output.v2.schema.json"
)
QUESTION_SELECT_OUTPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/question-select-output.v1.schema.json"
)


class SchemaCatalogError(ValueError):
    """Local schema/operation binding failure; raised before any network I/O."""


@dataclass(frozen=True)
class CatalogEntry:
    filename: str
    format_name: str
    operation: OperationSpec


@dataclass(frozen=True)
class SchemaBinding:
    schema_id: str
    format_name: str
    schema_hash: str
    schema: dict[str, Any]


_PUBLISHED_ENTRIES: dict[str, CatalogEntry] = {
    TURN_INTERPRET_OUTPUT_SCHEMA_ID: CatalogEntry(
        filename="turn-interpret-output.v2.schema.json",
        format_name="turn_interpret_output_v2",
        operation=turn_interpret_operation(),
    ),
    QUESTION_SELECT_OUTPUT_SCHEMA_ID: CatalogEntry(
        filename="question-select-output.v1.schema.json",
        format_name="question_select_output_v1",
        operation=question_select_operation(),
    ),
}


class PublishedOutputSchemaCatalog:
    def __init__(self, entries: Mapping[str, CatalogEntry] | None = None) -> None:
        self._entries = dict(_PUBLISHED_ENTRIES if entries is None else entries)

    def resolve(self, request: ModelCallRequest) -> SchemaBinding:
        entry = self._entries.get(request.output_schema_id)
        if entry is None:
            raise SchemaCatalogError(
                f"unknown output schema id: {request.output_schema_id}"
            )
        schema = published_schema(entry.filename)
        if schema.get("$id") != request.output_schema_id:
            raise SchemaCatalogError(
                "published schema $id does not match the requested output schema id"
            )
        schema_hash = canonical_hash(schema)
        if schema_hash != request.output_schema_hash:
            raise SchemaCatalogError(
                "published schema hash does not match the request artifact hash"
            )
        try:
            assert_portable_strict_output_schema(schema)
        except ProviderSchemaPortabilityError as exc:
            raise SchemaCatalogError(f"published schema is not portable: {exc}") from exc
        if schema.get("type") != "object":
            raise SchemaCatalogError("provider output schema root must be an object")
        operation = entry.operation
        if request.operation_name != operation.name:
            raise SchemaCatalogError(
                "operation name does not match the requested output schema: "
                f"{request.operation_name}"
            )
        if request.operation_definition_hash != operation.definition_hash:
            raise SchemaCatalogError(
                "operation definition hash does not match the current operation"
            )
        if operation.output_contract.content_hash != schema_hash:
            raise SchemaCatalogError(
                "operation output contract hash does not match the published schema"
            )
        return SchemaBinding(
            schema_id=request.output_schema_id,
            format_name=entry.format_name,
            schema_hash=schema_hash,
            schema=deepcopy(schema),
        )
