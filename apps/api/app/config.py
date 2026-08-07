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
    # deepseek-chat 舊名 2026-07-24 淘汰 → v4-flash(同價;specs/2026-07-13-model-lineup)
    model_deep: str = "deepseek/deepseek-v4-flash"       # 強階：STAR 整理（OpenRouter slug，可改）
    model_indicator: str = "deepseek/deepseek-v4-flash"  # 中階：行為指標生成
    model_cheap: str = "deepseek/deepseek-v4-flash"      # 便宜：措辭/雜項
    # 受限解碼(ADR 0024):底層必須原生支援 json_schema strict(OpenAI/Gemini 系);
    # 換模型 = 改這裡 + 重跑 scripts/validate_select_schema.py 留紀錄,不改碼。
    model_select: str = "openai/gpt-5.4-mini"       # 純受限 SELECT(survey 池選單等)
    # 訪談回合(role="interview"):顧問 chat+tools。gpt-4.1-mini(2025-04)已退役——
    # 2026-07-13 A/B(interview_sim ×3 replicate + v4-flash 對照)定案升 gpt-5.4-mini:
    # 與 select 同家(統一 config/fallback)、實證 prompt cache 命中 ~93%、tools 生態成熟;
    # v4-flash 對照 verify 0.67 明顯落後且 OpenRouter 路無快取,淘汰。紀錄:
    # specs/2026-07-13-model-lineup-cp-review.md。換模 = 改此處 + 重跑 sim/考卷留紀錄。
    model_interview: str = "openai/gpt-5.4-mini"
    # T13(ADR 0030):OpenRouter models=[主,備] 顯式備援——**備援模型須先過 T11 考卷**
    # (promptfoo)才填;空字串=不帶 models(單模型)。provider 物件恆帶
    # require_parameters(只路由到支援 strict/tools 的 provider)。
    model_interview_fallback: str = ""
    model_select_fallback: str = ""

    # Greenfield Task Analysis consultant (ADR 0046). This is deliberately
    # separate from the retired interview model lineup above.
    job_analysis_model: str = "anthropic/claude-opus-5"
    job_analysis_provider: str = "anthropic"
    # 4096 是 ADR 0046 時代的預設，**從未針對 Task Analysis 實測過**。
    # 2026-08-07 真人試跑撞到 `truncated: response hit the output token limit`：
    # Task Analysis 一次要吐 work_signals（每條含逐字 anchor）＋ task_changes
    # （完整 Task 欄位）＋ next_question，員工回答越詳細輸出越長。
    # 註：`docs/experiments/2026-08-02-opks-attributed-live-smoke/` 曾記「4096 綽綽有餘」，
    # 但那量的是 **OPKS** operation（單一 Task 的 O/P/K/S），輸出量小得多，不適用於此。
    job_analysis_max_output_tokens: int = 16384
    job_analysis_timeout_s: float = 90.0

    # Document output
    document_output_dir: str = "./output/documents"

    # CJK font for PDF/XLSX export (empty = auto-detect platform default)
    font_path: str = ""

    # Explicitly consented interview eval capture. Disabled by default so normal
    # product sessions do not duplicate restricted replay artifacts.
    interview_eval_capture_enabled: bool = False
    interview_eval_capture_git_sha: str = ""
    interview_eval_capture_dirty_worktree: bool = True


settings = Settings()
