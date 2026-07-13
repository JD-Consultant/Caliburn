from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "Caliburn"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/caliburn"
    database_url_sync: str = "postgresql://postgres:password@localhost:5432/caliburn"

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
    # 受限解碼(ADR 0024):底層必須原生支援 json_schema strict(OpenAI/Gemini 系);
    # 換模型 = 改這裡 + 重跑 scripts/validate_select_schema.py 留紀錄,不改碼。
    model_select: str = "openai/gpt-4o-mini"        # 純受限 SELECT(survey 池選單等)
    # 訪談回合(role="interview"):同時扛顧問推理+strict 輸出——4o-mini 太弱、變異大
    # (校準#2 實證:同 prompt 0.91↔0.45)。用同一套 OpenAI strict 實作的更強模型,
    # 沿用 0024 零逃逸保證;換模型 = 重跑 validate_select_schema + interview_sim 留紀錄。
    model_interview: str = "openai/gpt-4.1-mini"
    # T13(ADR 0030):OpenRouter models=[主,備] 顯式備援——**備援模型須先過 T11 考卷**
    # (promptfoo)才填;空字串=不帶 models(單模型)。provider 物件恆帶
    # require_parameters(只路由到支援 strict/tools 的 provider)。
    model_interview_fallback: str = ""
    model_select_fallback: str = ""

    # Document output
    document_output_dir: str = "./output/documents"

    # CJK font for PDF/XLSX export (empty = auto-detect platform default)
    font_path: str = ""


settings = Settings()
