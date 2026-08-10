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

    # Greenfield Task Analysis consultant (ADR 0046).
    job_analysis_model: str = "anthropic/claude-opus-5"
    job_analysis_provider: str = "anthropic"
    job_analysis_max_output_tokens: int = 4096
    job_analysis_timeout_s: float = 90.0


settings = Settings()
