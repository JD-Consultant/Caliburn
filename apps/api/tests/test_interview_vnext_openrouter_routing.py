"""V3-5A R4 — pure OpenRouter routing normalizer tests (§6/§12.1).

純函式、零 network/env/DB;涵蓋 official nested endpoints、legacy flat、pipeline
classification matrix、cache header 判定、endpoint attestation 與 malformed
fail-closed 行為。normalizer 不得輸出 eligibility verdict。

規格:docs/plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md
"""

from __future__ import annotations

from typing import Any

import pytest

from app.interview_vnext.llm.execution import CacheStatus, TransformationStatus

from evals.interview_vnext.providers.openrouter_routing import (
    LIMITATION_ATTEMPTS_CONTRADICTORY,
    LIMITATION_CACHE_HEADER_UNRECOGNIZED,
    LIMITATION_CACHE_UNKNOWN,
    LIMITATION_ENDPOINTS_MALFORMED,
    LIMITATION_METADATA_MISSING,
    LIMITATION_PIPELINE_MALFORMED,
    LIMITATION_SELECTED_NOT_UNIQUE,
    OpenRouterRoutingFacts,
    attest_upstream_endpoint,
    normalize_openrouter_routing,
)


REQUESTED_MODEL = "testlab/analyst-large"
CANONICAL_MODEL = "testlab/analyst-large-20260717"
PROVIDER_NAME = "TestHost"
ENDPOINT_SLUG = "testhost"
ACCEPTED_UPSTREAM = (REQUESTED_MODEL, CANONICAL_MODEL)


def clean_metadata(**overrides: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "requested": REQUESTED_MODEL,
        "strategy": "direct",
        "attempt": 1,
        "endpoints": {
            "total": 1,
            "available": [
                {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "selected": True}
            ],
        },
        "attempts": [
            {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "status": 200}
        ],
        "pipeline": [],
    }
    metadata.update(overrides)
    return metadata


def attest(facts: OpenRouterRoutingFacts) -> str | None:
    return attest_upstream_endpoint(
        facts,
        outbound_requested_model=REQUESTED_MODEL,
        configured_endpoint_slug=ENDPOINT_SLUG,
        expected_upstream_provider=PROVIDER_NAME,
        accepted_upstream_models=ACCEPTED_UPSTREAM,
    )


class TestNormalizerIsPure:
    def test_no_policy_vocabulary_in_facts(self):
        facts = normalize_openrouter_routing(clean_metadata())
        field_names = set(vars(facts))
        assert "eligible" not in field_names
        assert "clean" not in field_names
        assert "failures" not in field_names
        assert not any(name.startswith("conformance") for name in field_names)


class TestEndpointSelection:
    def test_official_nested_available_unique_selection(self):
        facts = normalize_openrouter_routing(clean_metadata())
        assert facts.metadata_present is True
        assert facts.metadata_requested_model == REQUESTED_MODEL
        assert facts.route_strategy == "direct"
        assert facts.router_attempt == 1
        assert facts.selected_provider == PROVIDER_NAME
        assert facts.selected_model == REQUESTED_MODEL
        assert facts.selected_count == 1
        assert facts.transformation_status == TransformationStatus.CLEAN
        assert facts.limitations == ()

    def test_nested_selected_object_duplicated_in_available_counts_once(self):
        entry = {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "selected": True}
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints={"total": 2, "selected": dict(entry), "available": [entry]}
            )
        )
        assert facts.selected_count == 1
        assert facts.selected_provider == PROVIDER_NAME
        assert facts.selected_model == REQUESTED_MODEL

    def test_legacy_flat_endpoint_array_still_reads(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints=[
                    {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "selected": True},
                    {"provider": "OtherHost", "model": REQUESTED_MODEL, "selected": False},
                ]
            )
        )
        assert facts.selected_count == 1
        assert facts.selected_provider == PROVIDER_NAME
        assert facts.selected_model == REQUESTED_MODEL
        assert facts.limitations == ()

    def test_zero_selected_endpoints_null_facts_with_limitation(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints={
                    "total": 1,
                    "available": [
                        {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "selected": False}
                    ],
                }
            )
        )
        assert facts.selected_count == 0
        assert facts.selected_provider is None
        assert facts.selected_model is None
        assert LIMITATION_SELECTED_NOT_UNIQUE in facts.limitations

    def test_two_selected_endpoints_null_facts_with_limitation(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints=[
                    {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "selected": True},
                    {"provider": "OtherHost", "model": REQUESTED_MODEL, "selected": True},
                ]
            )
        )
        assert facts.selected_count == 2
        assert facts.selected_provider is None
        assert facts.selected_model is None
        assert LIMITATION_SELECTED_NOT_UNIQUE in facts.limitations

    @pytest.mark.parametrize("endpoints", ["not-a-shape", 7, True])
    def test_malformed_endpoints_shape_is_limitation_not_exception(self, endpoints):
        facts = normalize_openrouter_routing(clean_metadata(endpoints=endpoints))
        assert facts.selected_count is None
        assert facts.selected_provider is None
        assert facts.selected_model is None
        assert LIMITATION_ENDPOINTS_MALFORMED in facts.limitations

    def test_missing_endpoints_key_is_not_unique_selection(self):
        metadata = clean_metadata()
        del metadata["endpoints"]
        facts = normalize_openrouter_routing(metadata)
        assert facts.selected_count == 0
        assert LIMITATION_SELECTED_NOT_UNIQUE in facts.limitations

    def test_non_string_selected_provider_and_model_become_null(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints=[{"provider": 42, "model": None, "selected": True}]
            )
        )
        assert facts.selected_count == 1
        assert facts.selected_provider is None
        assert facts.selected_model is None

    def test_unknown_additive_metadata_keys_do_not_disturb_known_facts(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                future_router_field={"anything": True},
                summary="direct route to TestHost",
            )
        )
        assert facts.selected_provider == PROVIDER_NAME
        assert facts.route_strategy == "direct"
        assert facts.limitations == ()


class TestMetadataMissing:
    @pytest.mark.parametrize("metadata", [None, "text", 3, ["list"]])
    def test_missing_or_non_object_metadata_is_all_unknown(self, metadata):
        facts = normalize_openrouter_routing(metadata)
        assert facts.metadata_present is False
        assert facts.metadata_requested_model is None
        assert facts.route_strategy is None
        assert facts.router_attempt is None
        assert facts.selected_count is None
        assert facts.transformation_status == TransformationStatus.UNKNOWN
        assert facts.cache_status == CacheStatus.UNKNOWN
        assert LIMITATION_METADATA_MISSING in facts.limitations
        assert LIMITATION_CACHE_UNKNOWN in facts.limitations


def attempt_entry(status: int = 200) -> dict[str, Any]:
    return {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "status": status}


class TestAttemptFacts:
    @pytest.mark.parametrize(
        ("attempt", "attempts", "expected"),
        [
            (0, [], 0),
            (1, [attempt_entry()], 1),
            (2, [attempt_entry(503), attempt_entry()], 2),
        ],
    )
    def test_consistent_attempt_integers_are_recorded_verbatim(
        self, attempt, attempts, expected
    ):
        facts = normalize_openrouter_routing(
            clean_metadata(attempt=attempt, attempts=attempts)
        )
        assert facts.router_attempt == expected
        assert LIMITATION_ATTEMPTS_CONTRADICTORY not in facts.limitations

    def test_attempt_with_omitted_attempts_detail_is_kept(self):
        metadata = clean_metadata(attempt=1)
        del metadata["attempts"]
        facts = normalize_openrouter_routing(metadata)
        assert facts.router_attempt == 1

    @pytest.mark.parametrize("attempt", [True, "1", -1, None, 1.5])
    def test_non_countable_attempt_is_null(self, attempt):
        facts = normalize_openrouter_routing(clean_metadata(attempt=attempt))
        assert facts.router_attempt is None

    @pytest.mark.parametrize(
        ("attempt", "attempts"),
        [
            (1, [attempt_entry(503), attempt_entry()]),
            (2, [attempt_entry()]),
            (0, [attempt_entry()]),
        ],
    )
    def test_attempt_contradicting_attempts_count_is_nulled(self, attempt, attempts):
        """R4-C blocker 2:attempt 與 attempts 筆數自相矛盾時,單次 execution 的
        事實無法證立——attempt fact 必須變 unknown(fail closed),不得 eligible。"""

        facts = normalize_openrouter_routing(
            clean_metadata(attempt=attempt, attempts=attempts)
        )
        assert facts.router_attempt is None
        assert LIMITATION_ATTEMPTS_CONTRADICTORY in facts.limitations

    def test_attempts_are_preserved_as_sanitized_raw(self):
        raw_attempts = [
            {"provider": "OtherHost", "model": REQUESTED_MODEL, "status": 503},
            {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "status": 200},
        ]
        facts = normalize_openrouter_routing(clean_metadata(attempts=raw_attempts))
        assert facts.attempts == tuple(raw_attempts)


class TestBlankStringFacts:
    """R4-C blocker 3:blank-only 字串不是可用的 fact,必須 null 化,否則 typed
    evidence(NonEmptyText)會在 adapter 內拋 ValidationError 而非回 envelope。"""

    def test_blank_requested_and_strategy_are_null(self):
        facts = normalize_openrouter_routing(
            clean_metadata(requested=" ", strategy="  \t")
        )
        assert facts.metadata_requested_model is None
        assert facts.route_strategy is None

    def test_blank_selected_provider_and_model_are_null(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints=[{"provider": " ", "model": "\t", "selected": True}]
            )
        )
        assert facts.selected_count == 1
        assert facts.selected_provider is None
        assert facts.selected_model is None

    def test_whitespace_padded_values_are_kept_verbatim(self):
        # 非 blank-only 的值照實保留(mismatch 由 conformance 判),不 strip 改寫。
        facts = normalize_openrouter_routing(clean_metadata(strategy="direct "))
        assert facts.route_strategy == "direct "


class TestPipelineClassification:
    def _stages(self, pipeline: Any) -> OpenRouterRoutingFacts:
        return normalize_openrouter_routing(clean_metadata(pipeline=pipeline))

    def test_absent_pipeline_key_is_clean(self):
        metadata = clean_metadata()
        del metadata["pipeline"]
        facts = normalize_openrouter_routing(metadata)
        assert facts.transformation_status == TransformationStatus.CLEAN
        assert facts.pipeline_stages == ()

    def test_empty_pipeline_is_clean(self):
        facts = self._stages([])
        assert facts.transformation_status == TransformationStatus.CLEAN
        assert facts.pipeline_stages == ()

    def test_explicit_null_pipeline_is_unknown_not_clean(self):
        """R4-C blocker 1:key 存在但值是 null ≠ 官方「no-op stage 省略」;
        不可與 key 缺失同視為 clean,必須 fail closed 為 unknown。"""

        facts = self._stages(None)
        assert facts.transformation_status == TransformationStatus.UNKNOWN
        assert facts.pipeline_stages == ()
        assert LIMITATION_PIPELINE_MALFORMED in facts.limitations

    @pytest.mark.parametrize(
        "stage_type", ["guardrail", "moderation", "content_filter"]
    )
    def test_inspection_stages_are_inspected(self, stage_type):
        facts = self._stages([{"type": stage_type, "name": "policy", "status": "ok"}])
        stage = facts.pipeline_stages[0]
        assert stage.transformation_status == TransformationStatus.INSPECTED
        assert stage.stage_type == stage_type
        assert stage.name == "policy"
        assert stage.status == "ok"
        assert facts.transformation_status == TransformationStatus.INSPECTED

    def test_guardrail_not_flagged_is_still_inspected(self):
        facts = self._stages(
            [{"type": "guardrail", "name": "moderation", "flagged": False}]
        )
        assert facts.pipeline_stages[0].transformation_status == (
            TransformationStatus.INSPECTED
        )

    @pytest.mark.parametrize(
        "stage_type",
        ["context_compression", "response_healing", "server_tools"],
    )
    def test_mutating_stage_types_are_mutated(self, stage_type):
        facts = self._stages([{"type": stage_type}])
        assert facts.pipeline_stages[0].transformation_status == (
            TransformationStatus.MUTATED
        )
        assert facts.transformation_status == TransformationStatus.MUTATED

    @pytest.mark.parametrize("plugin_name", ["web-search", "file-parser", "web"])
    def test_known_mutating_plugins_are_mutated(self, plugin_name):
        facts = self._stages([{"type": "plugin", "name": plugin_name}])
        assert facts.pipeline_stages[0].transformation_status == (
            TransformationStatus.MUTATED
        )

    @pytest.mark.parametrize(
        "stage",
        [
            {"type": "plugin", "name": "future-unknown-plugin"},
            {"type": "plugin"},
            {"type": "totally_new_stage"},
            {"type": "", "name": "x"},
            {"name": "no-type"},
            "not-an-object",
        ],
    )
    def test_unknown_stage_shapes_are_unknown_with_opaque_hash(self, stage):
        facts = self._stages([stage])
        normalized = facts.pipeline_stages[0]
        assert normalized.transformation_status == TransformationStatus.UNKNOWN
        assert normalized.details_hash.startswith("sha256:")
        assert facts.transformation_status == TransformationStatus.UNKNOWN

    def test_stage_name_and_status_only_read_top_level_scalars(self):
        facts = self._stages(
            [
                {
                    "type": "guardrail",
                    "name": {"nested": "ignored"},
                    "status": 200,
                    "data": {"name": "never-mined", "status": "never-mined"},
                }
            ]
        )
        stage = facts.pipeline_stages[0]
        assert stage.name is None
        assert stage.status is None

    def test_stage_indices_are_contiguous_from_one(self):
        facts = self._stages(
            [{"type": "guardrail"}, {"type": "response_healing"}, {"type": "x"}]
        )
        assert tuple(stage.index for stage in facts.pipeline_stages) == (1, 2, 3)

    def test_overall_priority_unknown_over_mutated_over_inspected(self):
        inspected_and_mutated = self._stages(
            [{"type": "guardrail"}, {"type": "context_compression"}]
        )
        assert inspected_and_mutated.transformation_status == (
            TransformationStatus.MUTATED
        )
        with_unknown = self._stages(
            [
                {"type": "guardrail"},
                {"type": "context_compression"},
                {"type": "mystery"},
            ]
        )
        assert with_unknown.transformation_status == TransformationStatus.UNKNOWN

    def test_details_hash_is_deterministic_and_content_addressed(self):
        stage = {"type": "guardrail", "name": "policy", "data": {"flagged": False}}
        first = self._stages([stage]).pipeline_stages[0]
        second = self._stages([dict(stage)]).pipeline_stages[0]
        assert first.details_hash == second.details_hash
        different = self._stages(
            [{"type": "guardrail", "name": "policy", "data": {"flagged": True}}]
        ).pipeline_stages[0]
        assert different.details_hash != first.details_hash

    def test_pipeline_not_an_array_is_overall_unknown_with_limitation(self):
        facts = self._stages("not-a-pipeline")
        assert facts.pipeline_stages == ()
        assert facts.transformation_status == TransformationStatus.UNKNOWN
        assert LIMITATION_PIPELINE_MALFORMED in facts.limitations

    def test_raw_pipeline_is_preserved_in_order(self):
        pipeline = [{"type": "guardrail"}, {"type": "response_healing"}]
        facts = self._stages(pipeline)
        assert facts.raw_pipeline == tuple(pipeline)


class TestCacheStatus:
    def test_header_hit(self):
        facts = normalize_openrouter_routing(
            clean_metadata(), cache_header_value="HIT"
        )
        assert facts.cache_status == CacheStatus.HIT

    def test_header_miss(self):
        facts = normalize_openrouter_routing(
            clean_metadata(), cache_header_value="MISS"
        )
        assert facts.cache_status == CacheStatus.MISS

    def test_header_absent_with_metadata_present_is_absent(self):
        facts = normalize_openrouter_routing(clean_metadata(), cache_header_value=None)
        assert facts.cache_status == CacheStatus.ABSENT

    def test_header_absent_and_metadata_missing_is_unknown(self):
        facts = normalize_openrouter_routing(None, cache_header_value=None)
        assert facts.cache_status == CacheStatus.UNKNOWN
        assert LIMITATION_CACHE_UNKNOWN in facts.limitations

    def test_unrecognized_header_value_is_unknown_with_limitation(self):
        facts = normalize_openrouter_routing(
            clean_metadata(), cache_header_value="STALE"
        )
        assert facts.cache_status == CacheStatus.UNKNOWN
        assert LIMITATION_CACHE_HEADER_UNRECOGNIZED in facts.limitations

    def test_zero_usage_never_implies_cache_hit(self):
        # §6.6:normalizer 依官方 header/metadata 判定,不接受 token/cost/latency
        # heuristics——usage 根本不是輸入,零用量下事實仍是 ABSENT。
        facts = normalize_openrouter_routing(clean_metadata(), cache_header_value=None)
        assert facts.cache_status == CacheStatus.ABSENT


class TestEndpointAttestation:
    def test_clean_direct_route_attests_configured_slug(self):
        facts = normalize_openrouter_routing(clean_metadata())
        assert attest(facts) == ENDPOINT_SLUG

    def test_canonical_model_in_selected_route_still_attests(self):
        entry = {"provider": PROVIDER_NAME, "model": CANONICAL_MODEL, "selected": True}
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints=[entry],
                attempts=[
                    {"provider": PROVIDER_NAME, "model": CANONICAL_MODEL, "status": 200}
                ],
            )
        )
        assert attest(facts) == ENDPOINT_SLUG

    def test_metadata_missing_cannot_attest(self):
        assert attest(normalize_openrouter_routing(None)) is None

    def test_requested_model_mismatch_cannot_attest(self):
        facts = normalize_openrouter_routing(
            clean_metadata(requested="testlab/other")
        )
        assert attest(facts) is None
        # actual facts remain recorded — expectation is never copied over them
        assert facts.metadata_requested_model == "testlab/other"
        assert facts.selected_provider == PROVIDER_NAME

    def test_selected_count_not_one_cannot_attest(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints=[
                    {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "selected": True},
                    {"provider": "OtherHost", "model": REQUESTED_MODEL, "selected": True},
                ]
            )
        )
        assert attest(facts) is None

    def test_provider_mismatch_cannot_attest_but_keeps_actual_facts(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints=[
                    {"provider": "OtherHost", "model": REQUESTED_MODEL, "selected": True}
                ]
            )
        )
        assert attest(facts) is None
        assert facts.selected_provider == "OtherHost"

    def test_unbound_selected_model_cannot_attest(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                endpoints=[
                    {
                        "provider": PROVIDER_NAME,
                        "model": "testlab/unbound-model",
                        "selected": True,
                    }
                ]
            )
        )
        assert attest(facts) is None
        assert facts.selected_model == "testlab/unbound-model"

    def test_conflicting_attempts_cannot_attest(self):
        facts = normalize_openrouter_routing(
            clean_metadata(
                attempts=[
                    {"provider": "OtherHost", "model": REQUESTED_MODEL, "status": 503},
                    {"provider": PROVIDER_NAME, "model": REQUESTED_MODEL, "status": 200},
                ]
            )
        )
        assert attest(facts) is None

    def test_non_object_attempt_entry_cannot_attest(self):
        facts = normalize_openrouter_routing(clean_metadata(attempts=["opaque"]))
        assert attest(facts) is None


class TestLimitations:
    def test_limitations_are_sorted_and_unique(self):
        facts = normalize_openrouter_routing(
            clean_metadata(endpoints="broken", pipeline="broken"),
            cache_header_value="STALE",
        )
        assert list(facts.limitations) == sorted(set(facts.limitations))
        assert len(facts.limitations) == 3
