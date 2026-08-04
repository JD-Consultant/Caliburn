"""OPKS v1 的 compact strict wire contract；不觸網。"""

from __future__ import annotations

import json
import re

from app.job_analysis.domain import OpksEntityKind
from app.job_analysis.llm import (
    OPKS_RESULT_WIRE_SCHEMA_NAME,
    OPKS_WIRE_SCHEMA_PATH,
    OpksDecision,
    OpksResultWire,
    OpksWireItem,
    committed_opks_wire_schema,
    opks_result_wire_provider_schema,
    opks_wire_to_result,
    render_opks_wire_schema_file,
)
from app.job_analysis.llm.portable_schema import (
    assert_portable_strict_output_schema,
    schema_complexity,
)


def schema() -> dict:
    return opks_result_wire_provider_schema()


def test_opks_wire_is_tiny_strict_and_has_no_nullable_union_or_internal_ids():
    rendered = json.dumps(schema(), ensure_ascii=False)
    counts = schema_complexity(schema())

    assert counts["union_parameters"] == 0
    assert counts["optional_parameters"] == 0
    assert counts["properties"] == 5
    assert counts["nesting_levels"] <= 3
    assert len(rendered.encode("utf-8")) < 2_500
    assert '"title"' not in rendered
    assert '"$ref"' not in rendered
    for forbidden in ("task_id", "entity_id", "proposal_id", "source_id"):
        assert forbidden not in rendered
    assert OpksEntityKind.ATTITUDE.value not in rendered

    assert_portable_strict_output_schema(schema())


def test_every_wire_field_is_required_and_unknown_fields_are_forbidden():
    root = schema()
    item = root["properties"]["items"]["items"]

    assert root["required"] == ["items"]
    assert root["additionalProperties"] is False
    assert item["required"] == [
        "entity_kind",
        "decision",
        "target_ordinal",
        "text",
    ]
    assert item["additionalProperties"] is False


def test_wire_neutral_values_map_to_internal_none_without_hiding_invalid_combinations():
    wire = OpksResultWire(
        items=(
            OpksWireItem(
                entity_kind=OpksEntityKind.KNOWLEDGE,
                decision=OpksDecision.REUSE_EXISTING,
                target_ordinal=2,
                text="",
            ),
            OpksWireItem(
                entity_kind=OpksEntityKind.OUTPUT,
                decision=OpksDecision.ADD_NEW,
                target_ordinal=0,
                text="  每週營運週報  ",
            ),
            # coupling 刻意不在 parse 時拒絕；deterministic verifier 要回可診斷違規。
            OpksWireItem(
                entity_kind=OpksEntityKind.SKILL,
                decision=OpksDecision.UNCERTAIN,
                target_ordinal=9,
                text="不該有文字",
            ),
        )
    )

    result = opks_wire_to_result(wire)

    assert result.items[0].target_ordinal == 2
    assert result.items[0].text is None
    assert result.items[1].target_ordinal is None
    assert result.items[1].text == "每週營運週報"
    assert result.items[2].target_ordinal == 9
    assert result.items[2].text == "不該有文字"


def test_opks_wire_schema_name_and_committed_golden_are_stable():
    assert re.fullmatch(r"[A-Za-z0-9_-]+", OPKS_RESULT_WIRE_SCHEMA_NAME)
    assert OPKS_RESULT_WIRE_SCHEMA_NAME == "opks_result_v1"
    assert committed_opks_wire_schema() == schema()
    assert OPKS_WIRE_SCHEMA_PATH.read_text(encoding="utf-8") == (
        render_opks_wire_schema_file()
    )
