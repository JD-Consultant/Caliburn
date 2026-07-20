"""V3-5A R2:schema projection report(§6.2/§14.2)。

Provider constrained decoding 移除 local constraint 時,每一筆 removal/rewrite
都要有 RFC 6901 pointer + value hash 的 deterministic report;prompt obligations
由 policy 固定 tuple 提供,不從 schema 自由文字猜。
"""

from __future__ import annotations

import pytest

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.llm.operation import ContractIdentity
from app.interview_vnext.llm.portable_schema import (
    PORTABLE_STRICT_OUTPUT_POLICY_V2,
    ProviderSchemaPortabilityError,
    SchemaProjectionMismatch,
    SchemaProjectionReport,
    SchemaProjectionReportDefinition,
    portable_strict_output_schema,
    project_portable_strict_output_schema,
    require_projection_report,
    resolve_schema_projection_policy,
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


# ---- R3-C1 exact projection policy identity(修正計畫 §5.3/§6.2)-----------


ACTIVE_POLICY = PORTABLE_STRICT_OUTPUT_POLICY_V2


def active_identity(**overrides) -> ContractIdentity:
    values = dict(
        name=ACTIVE_POLICY.name,
        version=ACTIVE_POLICY.version,
        content_hash=ACTIVE_POLICY.policy_hash,
    )
    values.update(overrides)
    return ContractIdentity(**values)


def active_report() -> SchemaProjectionReport:
    return project_portable_strict_output_schema(
        fixture_schema(), source_schema_id=SOURCE_ID, target_profile=TARGET
    ).report


def forged_report(**overrides) -> SchemaProjectionReport:
    """A tampered report whose self-hash is nonetheless correctly recomputed.

    重現 code review §2.2:report_hash 依竄改後 definition 正確重算,只有
    exact policy validation 能擋。
    """

    report = active_report()
    definition = SchemaProjectionReportDefinition.model_validate(
        {**report.model_dump(exclude={"report_hash"}), **overrides}
    )
    return SchemaProjectionReport(
        **definition.model_dump(), report_hash=canonical_hash(definition)
    )


class TestResolveSchemaProjectionPolicy:
    def test_active_identity_resolves_to_the_registry_policy(self):
        assert resolve_schema_projection_policy(active_identity()) is ACTIVE_POLICY

    @pytest.mark.parametrize(
        "overrides",
        [
            {"name": "portable-lenient-output"},
            {"version": "9.9.9"},
            {"content_hash": "sha256:" + "0" * 64},
            {
                "name": "unknown-policy",
                "version": "0.0.1",
                "content_hash": "sha256:" + "f" * 64,
            },
        ],
        ids=["name", "version", "hash", "unknown"],
    )
    def test_unknown_or_partial_identity_fails_closed(self, overrides):
        with pytest.raises(SchemaProjectionMismatch):
            resolve_schema_projection_policy(active_identity(**overrides))


class TestRequireProjectionReport:
    def test_exact_active_report_passes(self):
        report = active_report()
        assert (
            require_projection_report(
                policy=ACTIVE_POLICY,
                report=report,
                projected_schema_hash=report.projected_schema_hash,
            )
            is None
        )

    def test_forged_policy_version_with_recomputed_hashes_is_rejected(self):
        """回歸向量:`2.0.0 -> 9.9.9` 且 report hash 完整重算(§7.2)。"""

        forged = forged_report(
            policy_version="9.9.9", policy_hash="sha256:" + "0" * 64
        )
        with pytest.raises(SchemaProjectionMismatch, match="version|hash"):
            require_projection_report(
                policy=ACTIVE_POLICY,
                report=forged,
                projected_schema_hash=forged.projected_schema_hash,
            )

    @pytest.mark.parametrize(
        "overrides,match",
        [
            ({"policy_name": "portable-lenient-output"}, "name"),
            ({"policy_version": "9.9.9"}, "version"),
            ({"policy_hash": "sha256:" + "0" * 64}, "hash"),
            ({"target_profile": "portable-lenient"}, "target profile"),
        ],
        ids=["name", "version", "hash", "target_profile"],
    )
    def test_single_field_report_drift_is_rejected(self, overrides, match):
        forged = forged_report(**overrides)
        with pytest.raises(SchemaProjectionMismatch, match=match):
            require_projection_report(
                policy=ACTIVE_POLICY,
                report=forged,
                projected_schema_hash=forged.projected_schema_hash,
            )

    def test_projected_schema_hash_mismatch_is_rejected(self):
        report = active_report()
        with pytest.raises(SchemaProjectionMismatch, match="projected"):
            require_projection_report(
                policy=ACTIVE_POLICY,
                report=report,
                projected_schema_hash="sha256:" + "0" * 64,
            )

    def test_round_tripped_report_passes_the_same_validator(self):
        """§7.2.9(pure 面):序列化後載回的 report 走同一 validator。"""

        reloaded = SchemaProjectionReport.model_validate(
            active_report().model_dump(mode="json")
        )
        require_projection_report(
            policy=ACTIVE_POLICY,
            report=reloaded,
            projected_schema_hash=reloaded.projected_schema_hash,
        )
