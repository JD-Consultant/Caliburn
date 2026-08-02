"""OpenRouter catalog／route evidence parser(attributed live smoke Task 1)。

全程 no-network:兩個純函式各吃一份 payload。這裡的測試同時鎖住兩種**相反**的
失敗方向:

- catalog 是**付費前的門**——任何看不懂就 raise,寧可停線也不要拿舊價格去估預算;
- route evidence 是**付費後的歸因**——永遠不 raise,只把「這次能不能拿來判品質」
  降級成 limitation。產品回合不因為 metadata 缺失而失敗(研究紀錄 §4.1)。
"""

from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any

import pytest

from app.job_analysis.providers import (
    LIMITATION_COST_UNUSABLE,
    LIMITATION_METADATA_MISSING,
    LIMITATION_REQUESTED_MISMATCH,
    LIMITATION_RESPONSE_MODEL_MISMATCH,
    LIMITATION_ROUTER_RETRIED,
    LIMITATION_SELECTED_MODEL_MISMATCH,
    LIMITATION_SELECTED_NOT_UNIQUE,
    LIMITATION_SELECTED_PROVIDER_MISMATCH,
    LIMITATION_STRATEGY_NOT_DIRECT,
    OUTPUT_CAP_PARAMETERS,
    REQUIRED_ENDPOINT_PARAMETERS,
    OpenRouterCatalogError,
    OpenRouterEndpointSnapshot,
    inspect_openrouter_execution,
    select_catalog_endpoint,
    select_output_cap_parameter,
)


MODEL = "anthropic/claude-opus-5"
TAG = "anthropic"


def catalog_payload() -> dict[str, Any]:
    """2026-07-31 公開 model detail 的最小 fixture(只留 parser 讀的欄位＋雜訊)。"""
    return {
        "data": {
            "id": MODEL,
            "name": "Anthropic: Claude Opus 5",
            "canonical_slug": MODEL,
            "created": 1780000000,
            "endpoints": [
                {
                    "name": "Anthropic | anthropic/claude-opus-5",
                    "tag": TAG,
                    "provider_name": "Anthropic",
                    "status": 0,
                    "context_length": 200000,
                    "max_completion_tokens": 64000,
                    "quantization": None,
                    "uptime_last_30m": 99.8,
                    "supported_parameters": [
                        "max_tokens",
                        "reasoning",
                        "reasoning_effort",
                        "response_format",
                        "structured_outputs",
                        "stop",
                        "temperature",
                    ],
                    "pricing": {
                        "prompt": "0.000005",
                        "completion": "0.000025",
                        "request": "0",
                        "image": "0",
                    },
                },
                {
                    "name": "Amazon Bedrock | anthropic/claude-opus-5",
                    "tag": "amazon-bedrock",
                    "provider_name": "Amazon Bedrock",
                    "status": 0,
                    "supported_parameters": ["max_tokens", "response_format"],
                    "pricing": {"prompt": "0.000006", "completion": "0.00003"},
                },
            ],
        }
    }


def endpoint_snapshot() -> OpenRouterEndpointSnapshot:
    return select_catalog_endpoint(
        catalog_payload(), expected_model=MODEL, expected_tag=TAG
    )


def chat_payload() -> dict[str, Any]:
    """具品質歸因資格的成功回應(直路由、attempt 1、單一 selected endpoint)。"""
    return {
        "id": "gen-live-smoke-001",
        "object": "chat.completion",
        "created": 1785000000,
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "{}"},
            }
        ],
        "usage": {
            "prompt_tokens": 3120,
            "completion_tokens": 1450,
            "total_tokens": 4570,
            "completion_tokens_details": {"reasoning_tokens": 900},
            "cost": 0.052,
        },
        "openrouter_metadata": {
            "requested": MODEL,
            "strategy": "direct",
            "attempt": 1,
            "summary": "routed directly to Anthropic",
            "is_byok": False,
            "endpoints": {
                "total": 1,
                "available": [
                    {"provider": "Anthropic", "model": MODEL, "selected": True}
                ],
            },
            "pipeline": [],
        },
    }


def inspect(payload: dict[str, Any]):
    return inspect_openrouter_execution(
        payload, expected_model=MODEL, expected_endpoint=endpoint_snapshot()
    )


def with_metadata(**overrides: Any) -> dict[str, Any]:
    payload = chat_payload()
    payload["openrouter_metadata"].update(overrides)
    return payload


def with_pipeline(*stages: dict[str, Any]) -> dict[str, Any]:
    return with_metadata(pipeline=list(stages))


# --------------------------------------------------------------------------
# catalog:付費前的門
# --------------------------------------------------------------------------


def test_required_parameters_are_exactly_the_capabilities_this_request_uses():
    """輸出上限不在這裡:它的參數名由 catalog 決定,見 OUTPUT_CAP_PARAMETERS。"""

    assert REQUIRED_ENDPOINT_PARAMETERS == frozenset(
        {
            "reasoning",
            "reasoning_effort",
            "response_format",
            "structured_outputs",
        }
    )


def test_output_cap_parameter_prefers_the_new_name_but_accepts_the_advertised_one():
    """OpenRouter 已把 max_tokens 標為 deprecated,但 per-endpoint 的 supported_parameters
    未必跟著更名(2026-08-02 實測 openai/gpt-5.6-luna-pro 只列 max_tokens)。因為 request 帶
    require_parameters,送一個沒宣告的名字會被拒或被靜默丟掉——後者等於沒有上限。"""

    assert OUTPUT_CAP_PARAMETERS == ("max_completion_tokens", "max_tokens")
    assert select_output_cap_parameter({"max_tokens"}) == "max_tokens"
    assert (
        select_output_cap_parameter({"max_completion_tokens"})
        == "max_completion_tokens"
    )
    assert (
        select_output_cap_parameter({"max_tokens", "max_completion_tokens"})
        == "max_completion_tokens"
    )


def test_endpoint_without_any_output_cap_parameter_is_refused_before_paying():
    payload = catalog_payload()
    endpoint = payload["data"]["endpoints"][0]
    endpoint["supported_parameters"] = sorted(
        set(endpoint["supported_parameters"]) - set(OUTPUT_CAP_PARAMETERS)
    )

    with pytest.raises(OpenRouterCatalogError, match="output cap parameter"):
        select_catalog_endpoint(payload, expected_model=MODEL, expected_tag=TAG)


def test_snapshot_carries_the_output_cap_parameter_the_endpoint_advertises():
    assert endpoint_snapshot().output_cap_parameter == "max_tokens"


def test_catalog_selects_the_single_matching_endpoint_and_normalizes_prices():
    snapshot = endpoint_snapshot()

    assert snapshot.model_id == MODEL
    assert snapshot.tag == TAG
    assert snapshot.provider_name == "Anthropic"
    assert snapshot.prompt_price_per_token == Decimal("0.000005")
    assert snapshot.completion_price_per_token == Decimal("0.000025")
    assert REQUIRED_ENDPOINT_PARAMETERS <= snapshot.supported_parameters


def test_catalog_snapshot_is_frozen_so_a_retained_reference_cannot_drift():
    snapshot = endpoint_snapshot()
    with pytest.raises(Exception):
        snapshot.prompt_price_per_token = Decimal("0")  # type: ignore[misc]


def test_catalog_ignores_unknown_additive_fields():
    payload = catalog_payload()
    payload["data"]["some_future_field"] = {"nested": True}
    payload["data"]["endpoints"][0]["future_endpoint_field"] = ["anything"]
    payload["data"]["endpoints"][0]["pricing"]["future_price"] = "0.1"

    snapshot = select_catalog_endpoint(
        payload, expected_model=MODEL, expected_tag=TAG
    )

    assert snapshot.provider_name == "Anthropic"


@pytest.mark.parametrize(
    "mutate, expected",
    [
        pytest.param(
            lambda p: p["data"].__setitem__("id", "anthropic/claude-opus-4"),
            "model",
            id="model-mismatch",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"].__setitem__(0, {"tag": "other"}),
            "matched 0",
            id="missing-endpoint",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"].append(
                copy.deepcopy(p["data"]["endpoints"][0])
            ),
            "matched 2",
            id="duplicate-endpoint",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0].__setitem__("status", -1),
            "status",
            id="endpoint-not-active",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0].pop("status"),
            "status",
            id="endpoint-status-absent",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0]["supported_parameters"].remove(
                "structured_outputs"
            ),
            "structured_outputs",
            id="missing-capability",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0]["supported_parameters"].remove(
                "reasoning_effort"
            ),
            "reasoning_effort",
            id="missing-reasoning-effort",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0]["pricing"].__setitem__(
                "prompt", "-0.000005"
            ),
            "price",
            id="negative-price",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0]["pricing"].__setitem__(
                "completion", "NaN"
            ),
            "price",
            id="nan-price",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0]["pricing"].__setitem__(
                "completion", "Infinity"
            ),
            "price",
            id="infinite-price",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0]["pricing"].__setitem__("prompt", ""),
            "price",
            id="empty-price",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0]["pricing"].__setitem__("prompt", None),
            "price",
            id="null-price",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0].pop("pricing"),
            "pricing",
            id="missing-pricing",
        ),
        pytest.param(
            lambda p: p["data"]["endpoints"][0].pop("provider_name"),
            "provider_name",
            id="missing-provider-name",
        ),
        pytest.param(
            lambda p: p["data"].__setitem__("endpoints", {}),
            "endpoints",
            id="endpoints-not-a-list",
        ),
        pytest.param(lambda p: p.pop("data"), "data", id="missing-data"),
    ],
)
def test_catalog_fails_closed(mutate, expected: str):
    payload = catalog_payload()
    mutate(payload)

    with pytest.raises(OpenRouterCatalogError) as caught:
        select_catalog_endpoint(payload, expected_model=MODEL, expected_tag=TAG)

    assert expected in str(caught.value)


# --------------------------------------------------------------------------
# route evidence:付費後的歸因
# --------------------------------------------------------------------------


def test_direct_single_attempt_response_is_quality_eligible():
    evidence = inspect(chat_payload())

    assert evidence.quality_eligible is True
    assert evidence.attribution_limitations == ()
    assert evidence.response_id == "gen-live-smoke-001"
    assert evidence.requested_model == MODEL
    assert evidence.response_model == MODEL
    assert evidence.strategy == "direct"
    assert evidence.attempt == 1
    assert evidence.selected_provider == "Anthropic"
    assert evidence.selected_model == MODEL
    assert evidence.pipeline_stage_names == ()
    assert evidence.prompt_tokens == 3120
    assert evidence.completion_tokens == 1450
    assert evidence.reasoning_tokens == 900
    assert evidence.cost_usd == Decimal("0.052")


def test_flat_endpoint_array_shape_is_also_understood():
    """metadata 的 endpoints 有巢狀與扁平兩種形狀;讀不懂就白花一次呼叫。"""
    evidence = inspect(
        with_metadata(
            endpoints=[{"provider": "Anthropic", "model": MODEL, "selected": True}]
        )
    )

    assert evidence.quality_eligible is True
    assert evidence.selected_provider == "Anthropic"


def test_unknown_additive_metadata_fields_are_ignored():
    evidence = inspect(with_metadata(future_router_field={"anything": [1, 2]}))

    assert evidence.quality_eligible is True


def test_evidence_never_raises_on_a_totally_unusable_payload():
    evidence = inspect_openrouter_execution(
        {}, expected_model=MODEL, expected_endpoint=endpoint_snapshot()
    )

    assert evidence.quality_eligible is False
    assert LIMITATION_METADATA_MISSING in evidence.attribution_limitations
    assert evidence.selected_provider is None


@pytest.mark.parametrize(
    "payload_factory, limitation",
    [
        pytest.param(
            lambda: {k: v for k, v in chat_payload().items() if k != "openrouter_metadata"},
            LIMITATION_METADATA_MISSING,
            id="metadata-missing",
        ),
        pytest.param(
            lambda: with_metadata(requested="anthropic/claude-opus-4"),
            LIMITATION_REQUESTED_MISMATCH,
            id="requested-mismatch",
        ),
        pytest.param(
            lambda: with_metadata(strategy="fallback"),
            LIMITATION_STRATEGY_NOT_DIRECT,
            id="strategy-not-direct",
        ),
        pytest.param(
            lambda: with_metadata(attempt=2),
            LIMITATION_ROUTER_RETRIED,
            id="router-retried",
        ),
        pytest.param(
            lambda: with_metadata(endpoints={"total": 2, "available": []}),
            LIMITATION_SELECTED_NOT_UNIQUE,
            id="zero-selected",
        ),
        pytest.param(
            lambda: with_metadata(
                endpoints={
                    "total": 2,
                    "available": [
                        {"provider": "Anthropic", "model": MODEL, "selected": True},
                        {"provider": "Amazon Bedrock", "model": MODEL, "selected": True},
                    ],
                }
            ),
            LIMITATION_SELECTED_NOT_UNIQUE,
            id="multiple-selected",
        ),
        pytest.param(
            lambda: with_metadata(endpoints="anthropic"),
            LIMITATION_SELECTED_NOT_UNIQUE,
            id="endpoints-malformed",
        ),
        pytest.param(
            lambda: with_metadata(
                endpoints={
                    "total": 1,
                    "available": [
                        {
                            "provider": "Amazon Bedrock",
                            "model": MODEL,
                            "selected": True,
                        }
                    ],
                }
            ),
            LIMITATION_SELECTED_PROVIDER_MISMATCH,
            id="selected-provider-mismatch",
        ),
        pytest.param(
            lambda: with_metadata(
                endpoints={
                    "total": 1,
                    "available": [
                        {
                            "provider": "Anthropic",
                            "model": "anthropic/claude-opus-4",
                            "selected": True,
                        }
                    ],
                }
            ),
            LIMITATION_SELECTED_MODEL_MISMATCH,
            id="selected-model-mismatch",
        ),
    ],
)
def test_route_metadata_defects_disqualify_the_trial(payload_factory, limitation: str):
    evidence = inspect(payload_factory())

    assert evidence.quality_eligible is False
    assert limitation in evidence.attribution_limitations


def test_response_model_mismatch_disqualifies_the_trial():
    payload = chat_payload()
    payload["model"] = "anthropic/claude-opus-4"

    evidence = inspect(payload)

    assert evidence.quality_eligible is False
    assert LIMITATION_RESPONSE_MODEL_MISMATCH in evidence.attribution_limitations
    assert evidence.response_model == "anthropic/claude-opus-4"


@pytest.mark.parametrize(
    "usage",
    [
        pytest.param({"prompt_tokens": 10, "completion_tokens": 5}, id="cost-missing"),
        pytest.param({"cost": None}, id="cost-null"),
        pytest.param({"cost": -0.01}, id="cost-negative"),
        pytest.param({"cost": "NaN"}, id="cost-nan"),
        pytest.param({"cost": "Infinity"}, id="cost-infinite"),
        pytest.param({"cost": "not-a-number"}, id="cost-unparseable"),
        pytest.param({"cost": True}, id="cost-boolean"),
    ],
)
def test_unusable_cost_disqualifies_the_trial(usage: dict[str, Any]):
    payload = chat_payload()
    payload["usage"] = usage

    evidence = inspect(payload)

    assert evidence.quality_eligible is False
    assert LIMITATION_COST_UNUSABLE in evidence.attribution_limitations
    assert evidence.cost_usd is None


def test_zero_cost_is_recorded_but_not_treated_as_missing():
    payload = chat_payload()
    payload["usage"]["cost"] = 0

    evidence = inspect(payload)

    assert evidence.cost_usd == Decimal("0")
    assert evidence.quality_eligible is True


def test_missing_usage_object_only_costs_attribution():
    payload = chat_payload()
    payload.pop("usage")

    evidence = inspect(payload)

    assert evidence.quality_eligible is False
    assert evidence.prompt_tokens is None
    assert evidence.reasoning_tokens is None


def test_non_mutating_guardrail_stays_eligible_but_is_recorded():
    evidence = inspect(
        with_pipeline(
            {
                "type": "guardrail",
                "name": "moderation",
                "data": {"flagged": False, "blocked": False},
            }
        )
    )

    assert evidence.quality_eligible is True
    assert evidence.pipeline_stage_names == ("guardrail:moderation",)


@pytest.mark.parametrize(
    "stage",
    [
        pytest.param(
            {"type": "guardrail", "name": "moderation", "data": {"flagged": True}},
            id="guardrail-flagged",
        ),
        pytest.param(
            {"type": "guardrail", "name": "moderation", "data": {"blocked": True}},
            id="guardrail-blocked",
        ),
        pytest.param(
            {
                "type": "guardrail",
                "name": "pii",
                "data": {"flagged": False, "detected": True},
            },
            id="guardrail-detected",
        ),
        pytest.param(
            {"type": "guardrail", "name": "moderation", "data": {}},
            id="guardrail-without-proof",
        ),
        pytest.param(
            {"type": "guardrail", "name": "moderation"},
            id="guardrail-without-data",
        ),
        pytest.param(
            {"type": "guardrail", "name": "moderation", "data": {"flagged": "no"}},
            id="guardrail-non-boolean-proof",
        ),
        pytest.param(
            {"type": "context_compression", "name": "auto-compress", "data": {}},
            id="context-compression",
        ),
        pytest.param(
            {"type": "response_healing", "name": "json-repair", "data": {}},
            id="response-healing",
        ),
        pytest.param({"type": "plugin", "name": "web", "data": {}}, id="plugin"),
        pytest.param(
            {"type": "server_tools", "name": "search", "data": {}}, id="server-tools"
        ),
        pytest.param(
            {"type": "future_stage_type", "name": "whatever", "data": {}},
            id="unknown-stage-type",
        ),
        pytest.param({"name": "no-type"}, id="stage-without-type"),
        pytest.param("guardrail", id="stage-not-an-object"),
    ],
)
def test_pipeline_stages_that_may_have_altered_the_request_disqualify_the_trial(stage):
    evidence = inspect(with_pipeline(stage))

    assert evidence.quality_eligible is False
    assert evidence.pipeline_stage_names != ()
    assert any(
        "pipeline" in limitation for limitation in evidence.attribution_limitations
    )


def test_malformed_pipeline_container_disqualifies_the_trial():
    evidence = inspect(with_metadata(pipeline="none"))

    assert evidence.quality_eligible is False
    assert any(
        "pipeline" in limitation for limitation in evidence.attribution_limitations
    )


def test_every_limitation_is_collected_not_just_the_first():
    evidence = inspect(with_metadata(strategy="fallback", attempt=3))

    assert LIMITATION_STRATEGY_NOT_DIRECT in evidence.attribution_limitations
    assert LIMITATION_ROUTER_RETRIED in evidence.attribution_limitations


def test_evidence_does_not_retain_free_form_pipeline_telemetry():
    """pipeline `data` 是 free-form;讓它進 DTO 就等於把不可控欄位帶進 capture。"""
    evidence = inspect(
        with_pipeline(
            {
                "type": "guardrail",
                "name": "moderation",
                "data": {"flagged": False, "secret_upstream_note": "do-not-persist"},
            }
        )
    )

    assert "do-not-persist" not in evidence.model_dump_json()
