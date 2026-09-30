"""Model access is explicit, bounded, and cannot silently use legacy providers."""

import pytest

from caliburn.settings import Settings


def test_only_explicit_openai_key_enables_model_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "legacy-secret")
    assert Settings.from_environment().model is None
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    settings = Settings.from_environment()
    assert settings.model is not None
    assert settings.model.model == "gpt-6-luna"
    assert "synthetic-secret" not in repr(settings)


def test_invalid_cost_limit_stops_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    monkeypatch.setenv("CALIBURN_TURN_MAX_COST_USD", "NaN")
    with pytest.raises(ValueError):
        Settings.from_environment()
