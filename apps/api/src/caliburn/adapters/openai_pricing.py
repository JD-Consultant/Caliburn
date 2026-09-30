"""Explicit text Responses token rates; estimates are not provider invoices."""

import json
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal, localcontext
from hashlib import sha256

from openai.types.responses import Response
from openai.types.responses.compacted_response import CompactedResponse
from openai.types.responses.response_usage import ResponseUsage


@dataclass(frozen=True, slots=True)
class TokenRates:
    input_usd_per_million: Decimal
    cached_input_usd_per_million: Decimal
    cache_write_usd_per_million: Decimal
    output_usd_per_million: Decimal

    def __post_init__(self) -> None:
        for value in asdict(self).values():
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError("Token rates must be finite, nonnegative Decimal USD")


@dataclass(frozen=True, slots=True)
class TextResponsePricing:
    """Standard/default tier only; the caller pins this record for the execution.

    No network lookup or inferred model aliases. Source revision plus rate fingerprint
    prevents a restarted work from settling against a silently changed rate record.
    """

    model: str
    source_revision: str
    short_context: TokenRates
    long_context: TokenRates
    long_context_above_tokens: int = 272_000

    def __post_init__(self) -> None:
        if not self.model.strip() or not self.source_revision.strip():
            raise ValueError("Pricing requires an explicit model and source revision")
        threshold = _token_count(self.long_context_above_tokens)
        if threshold is None or threshold == 0:
            raise ValueError("The long-context price boundary must be a positive integer")

    @property
    def cost_basis(self) -> str:
        payload = json.dumps(asdict(self), default=str, sort_keys=True, separators=(",", ":"))
        fingerprint = sha256(payload.encode()).hexdigest()
        return f"{self.source_revision}:text-token-estimate-v1:default:{fingerprint}"

    def estimate_response_cost(self, response: Response) -> Decimal | None:
        if response.model != self.model or response.service_tier != "default":
            return None
        return self._estimate_usage_cost(response.usage)

    def estimate_compaction_cost(self, response: CompactedResponse) -> Decimal | None:
        """Estimate from usage and the bound request's model/default tier, not an invoice.

        Compact's current SDK schema omits model/tier. If provider extensions supply
        them, reject contrary values rather than silently overriding observed metadata.
        The workflow must enforce the pinned request model before dispatch.
        """
        if (
            getattr(response, "model", self.model) != self.model
            or getattr(response, "service_tier", "default") != "default"
        ):
            return None
        return self._estimate_usage_cost(response.usage)

    def _estimate_usage_cost(self, usage: ResponseUsage | None) -> Decimal | None:
        if not isinstance(usage, ResponseUsage):
            return None
        input_tokens = _token_count(usage.input_tokens)
        output_tokens = _token_count(usage.output_tokens)
        total_tokens = _token_count(usage.total_tokens)
        cached_tokens = _token_count(getattr(usage.input_tokens_details, "cached_tokens", None))
        cache_write_tokens = _token_count(
            getattr(usage.input_tokens_details, "cache_write_tokens", None)
        )
        if (
            input_tokens is None
            or output_tokens is None
            or total_tokens is None
            or cached_tokens is None
            or cache_write_tokens is None
            or total_tokens != input_tokens + output_tokens
            or cached_tokens + cache_write_tokens > input_tokens
        ):
            return None
        rates = self._rates(input_tokens)
        with localcontext() as context:
            context.prec = 50
            ordinary_tokens = input_tokens - cached_tokens - cache_write_tokens
            weighted = (
                ordinary_tokens * rates.input_usd_per_million
                + cached_tokens * rates.cached_input_usd_per_million
                + cache_write_tokens * rates.cache_write_usd_per_million
                + output_tokens * rates.output_usd_per_million
            )
            return _to_usd(weighted)

    def reserve_response_cost(self, *, input_tokens: int, max_output_tokens: int) -> Decimal:
        if _token_count(input_tokens) is None or _token_count(max_output_tokens) in (None, 0):
            raise ValueError("Reservation requires nonnegative input and positive output tokens")
        rates = self._rates(input_tokens)
        # Cache-write can cost more than ordinary input. Do not promise an invoice cap:
        # these are caller-provided bounds for text generation, not compact output bounds.
        with localcontext() as context:
            context.prec = 50
            maximum_input_rate = max(
                rates.input_usd_per_million,
                rates.cached_input_usd_per_million,
                rates.cache_write_usd_per_million,
            )
            return _to_usd(
                input_tokens * maximum_input_rate + max_output_tokens * rates.output_usd_per_million
            )

    def _rates(self, input_tokens: int) -> TokenRates:
        if input_tokens > self.long_context_above_tokens:
            return self.long_context
        return self.short_context


def _token_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _to_usd(weighted_tokens: Decimal) -> Decimal:
    # Match the existing budget owner's nine-decimal precision without rounding down
    # observed consumption. This is local accounting precision, not provider rounding.
    return (weighted_tokens / 1_000_000).quantize(Decimal("0.000000001"), rounding=ROUND_CEILING)


# Official Standard table verified 2026-09-30; opt-in configuration, not a model switch.
# https://developers.openai.com/api/docs/pricing
GPT_6_LUNA_STANDARD_2026_09_30 = TextResponsePricing(
    model="gpt-6-luna",
    source_revision="openai-standard-2026-09-30",
    short_context=TokenRates(Decimal("0.10"), Decimal("0.01"), Decimal("0.125"), Decimal("0.50")),
    long_context=TokenRates(Decimal("0.20"), Decimal("0.02"), Decimal("0.25"), Decimal("0.75")),
)


# Explicit evaluation option; does not change the product's default model.
GPT_6_1_SOL_STANDARD_2026_10_01 = TextResponsePricing(
    model="gpt-6.1-sol",
    source_revision="openai-standard-2026-10-01",
    short_context=TokenRates(Decimal("2.00"), Decimal("0.10"), Decimal("2.50"), Decimal("10.00")),
    long_context=TokenRates(Decimal("4.00"), Decimal("0.20"), Decimal("5.00"), Decimal("15.00")),
)
