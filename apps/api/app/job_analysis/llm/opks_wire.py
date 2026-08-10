"""送給模型的 OPKS compact strict wire schema。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from app.core.domain import DomainModel
from app.core.portable_schema import compact_strict_output_schema

from .opks_result import (
    OpksDecision,
    OpksGenerationEntityKind,
    OpksResult,
    OpksResultItem,
)


OPKS_RESULT_WIRE_SCHEMA_NAME = "opks_result_v1"
OPKS_WIRE_SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / f"{OPKS_RESULT_WIRE_SCHEMA_NAME}.json"
)


class OpksWireItem(DomainModel):
    entity_kind: OpksGenerationEntityKind
    decision: OpksDecision
    target_ordinal: int = Field(ge=0)
    text: str


class OpksResultWire(DomainModel):
    items: tuple[OpksWireItem, ...]


def opks_wire_to_result(wire: OpksResultWire) -> OpksResult:
    return OpksResult(
        items=tuple(
            OpksResultItem(
                entity_kind=item.entity_kind,
                decision=item.decision,
                target_ordinal=item.target_ordinal or None,
                text=item.text.strip() or None,
            )
            for item in wire.items
        )
    )


def opks_result_wire_provider_schema() -> dict[str, Any]:
    return compact_strict_output_schema(OpksResultWire.model_json_schema())


def committed_opks_wire_schema() -> dict[str, Any]:
    return json.loads(OPKS_WIRE_SCHEMA_PATH.read_text(encoding="utf-8"))


def render_opks_wire_schema_file() -> str:
    return (
        json.dumps(
            opks_result_wire_provider_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )

