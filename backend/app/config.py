from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "JobIntel AI"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/jobintel"
    database_url_sync: str = "postgresql://postgres:password@localhost:5432/jobintel"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM provider selection: "openai" | "google" | "anthropic"
    llm_provider: str = "openai"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Google Gemini
    google_api_key: str = ""
    google_model: str = "gemini-2.5-flash"

    # Anthropic Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # jd-ocs-indexer query API
    indexer_base_url: str = "http://localhost:8000"
    indexer_api_key: str = ""
    indexer_timeout_s: float = 30.0

    # iCAP RAG — 三段式信心門檻
    icap_high_threshold: float = 0.70    # >= 此值 → high → reference mode
    icap_medium_threshold: float = 0.55  # >= 此值 → medium → hybrid mode；< 此值 → company_defined
    icap_similarity_threshold: float = 0.55  # 保留向下相容（等同 icap_medium_threshold）
    icap_top_k: int = 5

    # Document output
    document_output_dir: str = "./output/documents"

    # CJK font for PDF/XLSX export (empty = auto-detect platform default)
    font_path: str = ""


settings = Settings()
