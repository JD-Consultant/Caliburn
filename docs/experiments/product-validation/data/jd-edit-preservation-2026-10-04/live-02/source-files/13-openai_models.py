"""Reviewed text model capabilities; explicit selection, never alias resolution or fallback."""

from dataclasses import dataclass
from typing import TypedDict

from openai.types.shared.reasoning_effort import ReasoningEffort

from caliburn.adapters.openai_pricing import (
    GPT_6_1_SOL_STANDARD_2026_10_01,
    GPT_6_LUNA_STANDARD_2026_09_30,
    TextResponsePricing,
)


class ModelCapacityLimits(TypedDict):
    model: str
    max_input_tokens: int
    context_window_tokens: int
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class OpenAIModelProfile:
    pricing: TextResponsePricing
    reasoning_efforts: frozenset[ReasoningEffort]
    max_input_tokens: int
    context_window_tokens: int
    max_output_tokens: int

    def capacity_limits(self) -> ModelCapacityLimits:
        return {
            "model": self.pricing.model,
            "max_input_tokens": self.max_input_tokens,
            "context_window_tokens": self.context_window_tokens,
            "max_output_tokens": self.max_output_tokens,
        }


def model_profile(model: str) -> OpenAIModelProfile:
    """Keep provider capacity, effort and accounting aligned for both role runners.

    Official model pages verified 2026-10-01:
    https://developers.openai.com/api/docs/models/gpt-6-luna
    https://developers.openai.com/api/docs/models/gpt-6.1-sol
    """
    match model:
        case "gpt-6-luna":
            return OpenAIModelProfile(
                GPT_6_LUNA_STANDARD_2026_09_30,
                frozenset({"none", "low", "medium", "high", "xhigh", "max"}),
                922_000,
                1_050_000,
                128_000,
            )
        case "gpt-6.1-sol":
            return OpenAIModelProfile(
                GPT_6_1_SOL_STANDARD_2026_10_01,
                frozenset({"low", "medium", "high", "xhigh", "max"}),
                922_000,
                1_050_000,
                128_000,
            )
        case _:
            raise ValueError("Configure a model with a researched capacity and pricing policy")
