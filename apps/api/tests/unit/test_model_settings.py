"""Model access is explicit, bounded, and cannot silently use legacy providers."""

from decimal import Decimal

import pytest

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


@pytest.mark.parametrize("limit", ["NaN", "Infinity", "0", "-1"])
def test_explicit_evaluation_budget_must_be_positive_and_finite(limit: str) -> None:
    with pytest.raises(ValueError):
        ModelSettings(api_key="synthetic", max_cost_usd=Decimal(limit))
