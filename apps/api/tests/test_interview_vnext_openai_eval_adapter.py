"""V3-4 OpenAI Responses eval adapter — mocked-HTTP conformance tests.

規格:docs/plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md
不打 live API;所有 provider 行為經 httpx mock + 官方 SDK deserialization。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.interview_vnext.domain.hashing import canonical_json

from evals.interview_vnext.provider_config import OpenAIResponsesEvalConfig


class TestOpenAIResponsesEvalConfig:
    def test_default_dump_and_hash_cover_hard_invariants(self):
        config = OpenAIResponsesEvalConfig()
        assert config.config_hash == OpenAIResponsesEvalConfig().config_hash
        dump = config.model_dump(mode="json")
        assert dump["schema_version"] == "openai_responses_eval_config.v1"
        assert dump["provider"] == "openai"
        assert dump["requested_model"] == "gpt-5.6"
        assert dump["accepted_resolved_models"] == ["gpt-5.6", "gpt-5.6-sol"]
        assert dump["reasoning_mode"] == "standard"
        assert dump["reasoning_effort"] == "medium"
        assert dump["service_tier"] == "default"
        assert dump["store"] is False
        assert dump["background"] is False
        assert dump["stream"] is False
        assert dump["truncation"] == "disabled"
        assert dump["sdk_max_retries"] == 0
        assert dump["contains_test_data"] is True

    def test_config_hash_tracks_versionable_eval_knobs(self):
        default = OpenAIResponsesEvalConfig()
        assert default.config_hash != OpenAIResponsesEvalConfig(
            reasoning_effort="high"
        ).config_hash
        assert default.config_hash != OpenAIResponsesEvalConfig(
            requested_model="gpt-5.6-sol"
        ).config_hash

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("provider", "anthropic"),
            ("reasoning_mode", "pro"),
            ("service_tier", "auto"),
            ("store", True),
            ("background", True),
            ("stream", True),
            ("truncation", "auto"),
            ("sdk_max_retries", 2),
            ("contains_test_data", False),
        ],
    )
    def test_hard_invariants_cannot_be_overridden(self, field, value):
        with pytest.raises(ValidationError):
            OpenAIResponsesEvalConfig(**{field: value})

    def test_config_is_frozen(self):
        config = OpenAIResponsesEvalConfig()
        with pytest.raises(ValidationError):
            config.requested_model = "gpt-5.6-sol"

    def test_secret_fields_are_rejected_and_absent(self):
        for secret_field in ("api_key", "organization", "project"):
            assert secret_field not in OpenAIResponsesEvalConfig.model_fields
            with pytest.raises(ValidationError):
                OpenAIResponsesEvalConfig(**{secret_field: "sk-eval-secret"})
        assert "sk-" not in canonical_json(OpenAIResponsesEvalConfig())

    @pytest.mark.parametrize(
        "models",
        [
            (),
            ("gpt-5.6", "gpt-5.6"),
            ("gpt-5.6-sol", "gpt-5.6"),
        ],
    )
    def test_accepted_resolved_models_must_be_nonempty_unique_sorted(self, models):
        with pytest.raises(ValidationError):
            OpenAIResponsesEvalConfig(accepted_resolved_models=models)

    def test_requested_model_need_not_be_in_allowlist(self):
        config = OpenAIResponsesEvalConfig(
            requested_model="gpt-5.6",
            accepted_resolved_models=("gpt-5.6-sol",),
        )
        assert config.requested_model not in config.accepted_resolved_models

    @pytest.mark.parametrize("seconds", [0.0, -1.0, 120.0])
    def test_connect_timeout_bounds(self, seconds):
        with pytest.raises(ValidationError):
            OpenAIResponsesEvalConfig(connect_timeout_seconds=seconds)
