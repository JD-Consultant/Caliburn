from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "Caliburn"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/jobintel"
    database_url_sync: str = "postgresql://postgres:password@localhost:5432/jobintel"

    # jd-ocs-indexer query API
    indexer_base_url: str = "http://localhost:8000"
    indexer_api_key: str = ""
    indexer_timeout_s: float = 30.0

    # OpenRouter LLM gateway（D10）— per-role 模型分層，OpenAI 相容
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model_deep: str = "deepseek/deepseek-chat"       # 強階：STAR 整理（OpenRouter slug，可改）
    model_indicator: str = "deepseek/deepseek-chat"  # 中階：行為指標生成
    model_cheap: str = "deepseek/deepseek-chat"      # 便宜：措辭/雜項

    # Document output
    document_output_dir: str = "./output/documents"

    # CJK font for PDF/XLSX export (empty = auto-detect platform default)
    font_path: str = ""


settings = Settings()
