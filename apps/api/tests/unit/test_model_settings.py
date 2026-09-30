"""Model access is explicit, bounded, and cannot silently use legacy providers."""

from decimal import Decimal

import pytest

from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.request_capacity import require_request_limits
from caliburn.settings import ModelSettings, Settings


def test_only_explicit_openai_key_enables_model_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "legacy-secret")
    assert Settings.from_environment().model is None
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    settings = Settings.from_environment()
    assert settings.model is not None
    assert settings.model.model == "gpt-6-luna"
    assert "synthetic-secret" not in repr(settings)


def test_product_ignores_retired_cost_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    monkeypatch.setenv("CALIBURN_TURN_MAX_COST_USD", "NaN")
    settings = Settings.from_environment()
    assert settings.model is not None
    assert settings.model.max_cost_usd is None


def test_default_model_settings_have_no_monetary_stop() -> None:
    assert ModelSettings(api_key="synthetic").max_cost_usd is None


def test_explicit_sol_evaluation_uses_its_own_capacity_and_rates() -> None:
    settings = ModelSettings(api_key="synthetic", model="gpt-6.1-sol")
    profile = model_profile(settings.model)
    request = ResponseRequest(
        model=settings.model,
        instructions="synthetic",
        input_items=[],
        tools=[],
        reasoning_effort=settings.reasoning_effort,
        max_output_tokens=128_000,
    )
    require_request_limits(request, profile.capacity_limits())
    # Cache writes reserve at $2.50/M and output at $10/M, not Luna's rates.
    assert profile.pricing.reserve_response_cost(
        input_tokens=1000,
        max_output_tokens=100,
    ) == Decimal("0.003500000")
    assert profile.pricing.reserve_response_cost(
        input_tokens=272001,
        max_output_tokens=100,
    ) == Decimal("1.361505000")


@pytest.mark.parametrize("effort", ["none", "minimal"])
def test_sol_rejects_unsupported_effort_before_outbound_work(effort) -> None:
    with pytest.raises(ValueError, match="reasoning"):
        ModelSettings(api_key="synthetic", model="gpt-6.1-sol", reasoning_effort=effort)


def test_unresearched_model_is_not_a_silent_fallback() -> None:
    with pytest.raises(ValueError, match="model"):
        ModelSettings(api_key="synthetic", model="unresearched")


@pytest.mark.parametrize("limit", ["NaN", "Infinity", "0", "-1"])
def test_explicit_evaluation_budget_must_be_positive_and_finite(limit: str) -> None:
    with pytest.raises(ValueError):
        ModelSettings(api_key="synthetic", max_cost_usd=Decimal(limit))
