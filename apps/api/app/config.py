from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "Caliburn"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/caliburn"
    database_url_sync: str = "postgresql://postgres:password@localhost:5432/caliburn"

    # OpenRouter LLM gateway for the current job-analysis consultant.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Versioned target consultant profile and interactive run policy (ADR 0060).
    consultant_profile_id: str = "primary-consultant"
    consultant_profile_revision: int = 1
    consultant_model: str = "anthropic/claude-opus-5"
    consultant_provider: str = "Anthropic"
    consultant_temperature: float | None = None
    consultant_top_p: float | None = None
    consultant_max_output_tokens: int = 4096
    consultant_output_token_parameter: str = "max_tokens"
    consultant_reasoning_effort: str | None = "high"
    consultant_timeout_seconds: float = 90.0
    consultant_policy_revision: int = 2
    consultant_max_context_tokens: int = 24_000
    consultant_max_model_calls: int = 11
    consultant_max_lookup_waves: int = 2
    consultant_max_total_tool_calls: int = 48
    consultant_model_retry_count: int = 1
    consultant_tool_retry_count: int = 1
    consultant_max_elapsed_seconds: float = 180.0
    consultant_max_total_tokens: int = 160_000
    consultant_max_cost_usd: Decimal | None = Decimal("2.00")


settings = Settings()
