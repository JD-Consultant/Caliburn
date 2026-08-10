# Caliburn API

現行 API 是本機 Job Analysis 後端。唯一 production route prefix 是 `/api/v1/job-analysis`，健康檢查是 `/healthz`；舊 OCS、interview、vNext 與 job-authoring routes 已移除。

## 結構

```text
app/
  job_analysis/
    domain/         純 domain、Current State、Evidence、Proposal、不變量
    application/    use cases、authority commit、consultation、OPKS、export
    llm/            prompt、wire schema、result mapper、verifier
    providers/      OpenRouter adapter
  adapters/
    job_analysis_postgres/  SQLAlchemy model、repository、serialization
  api/              route、mapper、problem response、dependency composition
  database.py       async SQLAlchemy engine/session
  observability.py  OTel 橫切
```

`domain` 不依賴 FastAPI、SQLAlchemy 或 provider；HTTP 只在 `app/api`；PostgreSQL 只在 adapter。AI 呼叫在 transaction 外執行，寫入前重新驗證 authority snapshot，員工決策才會改 Current JD。

## 資料庫

Alembic `0012`–`0017` 是 current-only migration chain，root 為 `0012_job_analysis_current_state`，head 為 `0017`。資料表只屬於 `job_analysis_*`；舊資料不搬移、不雙寫。

```bash
npm run db:migrate
cd apps/api && uv run pytest -q
```

本機啟動：`cd apps/api && uv run python run_live.py`。API 設定由 `app/config.py` 讀取，LLM provider 使用本機設定的 OpenRouter key；員工不需帳號或登入。

跨 app 流程見 [`docs/design/task-analysis-engine.md`](../../docs/design/task-analysis-engine.md)，API 邊界與測試指引見 [`app/job_analysis/AGENTS.md`](app/job_analysis/AGENTS.md)。
