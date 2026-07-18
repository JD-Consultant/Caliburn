"""V3-5A R2:schema projection report(§6.2/§14.2)。

Provider constrained decoding 移除 local constraint 時,每一筆 removal/rewrite
都要有 RFC 6901 pointer + value hash 的 deterministic report;prompt obligations
由 policy 固定 tuple 提供,不從 schema 自由文字猜。
"""

from __future__ import annotations

import pytest

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.llm.portable_schema import (
    PORTABLE_STRICT_OUTPUT_POLICY_V2,
    ProviderSchemaPortabilityError,
    SchemaProjectionReport,
    SchemaProjectionReportDefinition,
    portable_strict_output_schema,
    project_portable_strict_output_schema,
)
from app.interview_vnext.llm.turn_interpret import TurnInterpretOutput


SOURCE_ID = "https://caliburn.local/schemas/projection-fixture.v1.schema.json"
TARGET = PORTABLE_STRICT_OUTPUT_POLICY_V2.target_profile


def fixture_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1, "pattern": "^[a-z]+$"},
            "count": {
                "anyOf": [
                    {"type": "integer", "minimum": 0},
                    {"type": "null"},
                ],
                "default": None,
            },
            "tags": {
                "type": "array",
                "items": {"type": "string", "maxLength": 5},
                "uniqueItems": True,
            },
            "kind": {"const": "fixed"},
        },
        "required": ["name", "count", "tags", "kind"],
        "additionalProperties": False,
        "$defs": {
            "weird~name/x": {"type": "string", "format": "date"},
        },
    }


def test_projection_records_every_removed_constraint_with_rfc6901_pointer():
    projected = project_portable_strict_output_schema(
        fixture_schema(), source_schema_id=SOURCE_ID, target_profile=TARGET
    )
    report = projected.report
    removed = tuple(
        (item.json_pointer, item.keyword) for item in report.removed_constraints
    )
    assert removed == (
        ("/$defs/weird~0name~1x", "format"),
        ("/properties/count", "default"),
        ("/properties/count/anyOf/0", "minimum"),
        ("/properties/name", "minLength"),
        ("/properties/name", "pattern"),
        ("/properties/tags", "uniqueItems"),
        ("/properties/tags/items", "maxLength"),
    )
    pattern_entry = next(
        item
        for item in report.removed_constraints
        if item.keyword == "pattern"
    )
    assert pattern_entry.value_hash == canonical_hash("^[a-z]+$")
    rewritten = tuple(
        (item.json_pointer, item.keyword) for item in report.rewritten_constraints
    )
    assert rewritten == (("/properties/kind", "const"),)
    assert report.rewritten_constraints[0].value_hash == canonical_hash("fixed")
    assert projected.schema["properties"]["kind"] == {"enum": ["fixed"]}


def test_projection_hashes_and_policy_identity_are_deterministic():
    first = project_portable_strict_output_schema(
        fixture_schema(), source_schema_id=SOURCE_ID, target_profile=TARGET
    )
    second = project_portable_strict_output_schema(
        fixture_schema(), source_schema_id=SOURCE_ID, target_profile=TARGET
    )
    assert canonical_json(first.schema) == canonical_json(second.schema)
    assert first.report.report_hash == second.report.report_hash
    report = first.report
    assert report.schema_version == "schema_projection_report.v1"
    assert report.policy_name == PORTABLE_STRICT_OUTPUT_POLICY_V2.name
    assert report.policy_version == PORTABLE_STRICT_OUTPUT_POLICY_V2.version
    assert report.policy_hash == PORTABLE_STRICT_OUTPUT_POLICY_V2.policy_hash
    assert report.source_schema_id == SOURCE_ID
    assert report.source_schema_hash == canonical_hash(fixture_schema())
    assert report.projected_schema_hash == canonical_hash(first.schema)
    definition = SchemaProjectionReportDefinition.model_validate(
        report.model_dump(exclude={"report_hash"})
    )
    assert report.report_hash == canonical_hash(definition)


def test_forged_report_hash_is_rejected():
    projected = project_portable_strict_output_schema(
        fixture_schema(), source_schema_id=SOURCE_ID, target_profile=TARGET
    )
    with pytest.raises(ValueError, match="hash"):
        SchemaProjectionReport.model_validate(
            {
                **projected.report.model_dump(),
                "report_hash": "sha256:" + "0" * 64,
            }
        )


def test_prompt_obligations_come_from_the_policy():
    with_pattern = project_portable_strict_output_schema(
        fixture_schema(), source_schema_id=SOURCE_ID, target_profile=TARGET
    )
    assert with_pattern.report.prompt_obligations == (
        "local_constraints_require_post_validation",
        "unsupported_pattern_not_enforced_by_provider",
    )
    source = fixture_schema()
    del source["properties"]["name"]["pattern"]
    without_pattern = project_portable_strict_output_schema(
        source, source_schema_id=SOURCE_ID, target_profile=TARGET
    )
    assert without_pattern.report.prompt_obligations == (
        "local_constraints_require_post_validation",
    )


def test_projection_rejects_foreign_target_profile():
    with pytest.raises(ValueError, match="target profile"):
        project_portable_strict_output_schema(
            fixture_schema(),
            source_schema_id=SOURCE_ID,
            target_profile="unknown-profile",
        )


def test_projected_schema_still_passes_the_portable_assertion():
    bad = {
        "type": "object",
        "properties": {
            "value": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"},
                    {"type": "null"},
                ]
            }
        },
        "required": ["value"],
        "additionalProperties": False,
    }
    with pytest.raises(ProviderSchemaPortabilityError):
        project_portable_strict_output_schema(
            bad, source_schema_id=SOURCE_ID, target_profile=TARGET
        )


def test_compat_wrapper_matches_projection_output():
    source = TurnInterpretOutput.model_json_schema()
    projected = project_portable_strict_output_schema(
        TurnInterpretOutput.model_json_schema(),
        source_schema_id=SOURCE_ID,
        target_profile=TARGET,
    )
    assert canonical_json(portable_strict_output_schema(source)) == canonical_json(
        projected.schema
    )
