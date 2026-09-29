"""Local arithmetic for official text rates; no claims about account invoices."""

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from openai.types.responses import Response
from openai.types.responses.compacted_response import CompactedResponse

from caliburn.adapters.openai_pricing import GPT_6_LUNA_STANDARD_2026_09_30, TokenRates

PRICING = GPT_6_LUNA_STANDARD_2026_09_30


def response_fixture() -> Response:
    raw = json.loads(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(encoding="utf-8")
    )
    raw["service_tier"] = "default"
    raw["usage"] = {
        "input_tokens": 1000,
        "input_tokens_details": {"cached_tokens": 400, "cache_write_tokens": 200},
        "output_tokens": 100,
        "output_tokens_details": {"reasoning_tokens": 60},
        "total_tokens": 1100,
    }
    return Response.construct(**raw)


def test_disjoint_input_buckets_and_reasoning_already_in_output() -> None:
    response = response_fixture()
    before = response.model_dump()
    assert PRICING.estimate_response_cost(response) == Decimal("0.000119")
    assert response.model_dump() == before


@pytest.mark.parametrize("tokens, cost", [(272000, "0.027219"), (272001, "0.0544132")])
def test_long_context_price_uses_all_input_and_strictly_above_threshold(tokens, cost) -> None:
    response = response_fixture()
    response.usage.input_tokens = tokens
    response.usage.total_tokens = tokens + 100
    assert PRICING.estimate_response_cost(response) == Decimal(cost)


@pytest.mark.parametrize(
    "field,value",
    [("model", "gpt-6-sol"), ("service_tier", "priority"), ("service_tier", None), ("usage", None)],
)
def test_unpriced_result_is_unknown_not_free(field, value) -> None:
    response = response_fixture().model_copy(update={field: value})
    assert PRICING.estimate_response_cost(response) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_tokens", -1),
        ("input_tokens", True),
        ("input_tokens", 1000.0),
        ("total_tokens", 999),
        ("output_tokens", "100"),
    ],
)
def test_invalid_usage_is_unknown(field, value) -> None:
    response = response_fixture()
    response.usage = response.usage.model_copy(update={field: value})
    assert PRICING.estimate_response_cost(response) is None


@pytest.mark.parametrize(
    "details",
    [
        {"cached_tokens": 0},
        {"cached_tokens": 900, "cache_write_tokens": 200},
        {"cached_tokens": -1, "cache_write_tokens": 0},
        {"cached_tokens": 0, "cache_write_tokens": True},
    ],
)
def test_invalid_or_missing_cache_counts_cannot_release_reservation(details) -> None:
    raw = response_fixture().model_dump()
    raw["usage"]["input_tokens_details"] = details
    response = Response.construct(**raw)
    # The SDK constructor coerces booleans to integers. Exercise an actual invalid
    # retained value, rather than claiming we can recover its pre-SDK wire type.
    response.usage.input_tokens_details = response.usage.input_tokens_details.model_copy(
        update=details
    )
    assert PRICING.estimate_response_cost(response) is None


@pytest.mark.parametrize(
    "missing", ["input_tokens", "output_tokens", "total_tokens", "input_tokens_details"]
)
def test_missing_usage_fields_are_unknown(missing) -> None:
    raw = response_fixture().model_dump()
    del raw["usage"][missing]
    assert PRICING.estimate_response_cost(Response.construct(**raw)) is None


def test_valid_zero_consumption_is_distinct_from_unavailable_usage() -> None:
    raw = response_fixture().model_dump()
    raw["usage"] = {
        "input_tokens": 0,
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "output_tokens": 0,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 0,
    }
    assert PRICING.estimate_response_cost(Response.construct(**raw)) == Decimal(0)


@pytest.mark.parametrize(
    "tokens,output,cost", [(1000, 100, "0.000175"), (272001, 100, "0.06807525")]
)
def test_reservation_covers_cache_writes_and_full_output_limit(tokens, output, cost) -> None:
    assert PRICING.reserve_response_cost(input_tokens=tokens, max_output_tokens=output) == Decimal(
        cost
    )


def test_cost_basis_changes_when_rate_model_or_threshold_changes() -> None:
    alternatives = [
        replace(PRICING, model="gpt-6-sol"),
        replace(
            PRICING,
            short_context=replace(PRICING.short_context, output_usd_per_million=Decimal("1")),
        ),
        replace(PRICING, long_context_above_tokens=200000),
    ]
    assert all(other.cost_basis != PRICING.cost_basis for other in alternatives)
    assert PRICING.cost_basis == replace(PRICING).cost_basis


@pytest.mark.parametrize("invalid", [Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), 0.1])
def test_bad_rate_configuration_is_rejected(invalid) -> None:
    with pytest.raises(ValueError):
        TokenRates(invalid, Decimal(0), Decimal(0), Decimal(0))


def test_fractional_nanodollar_is_rounded_up_once_after_adding_buckets() -> None:
    small = TokenRates(Decimal("0.0001"), Decimal("0.0001"), Decimal("0.0001"), Decimal("0.0001"))
    pricing = replace(PRICING, short_context=small)
    raw = response_fixture().model_dump()
    raw["usage"] = {
        "input_tokens": 3,
        "input_tokens_details": {"cached_tokens": 1, "cache_write_tokens": 1},
        "output_tokens": 1,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 4,
    }
    assert pricing.estimate_response_cost(Response.construct(**raw)) == Decimal("0.000000001")


@pytest.mark.parametrize(
    "extra,expected",
    [
        ({}, "0.000119"),
        ({"model": "gpt-6-luna", "service_tier": "default"}, "0.000119"),
        ({"model": "gpt-6-sol"}, None),
        ({"service_tier": "flex"}, None),
    ],
)
def test_compact_estimate_uses_bound_request_but_never_ignores_contradictory_metadata(
    extra, expected
) -> None:
    compact = CompactedResponse.construct(
        id="cmp_test",
        object="response.compaction",
        created_at=1,
        output=[],
        usage=response_fixture().usage,
        **extra,
    )
    estimate = PRICING.estimate_compaction_cost(compact)
    assert estimate == (Decimal(expected) if expected else None)
