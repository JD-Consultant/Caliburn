# Caliburn API

> **歷史文件（2026-09-22 退役）：**本目錄的可執行 API 已移除；以下內容只保留開發沿革與研究證據，不是目前啟動方式或正式權責。現行產品見 [`experiments/jd-relational-app`](../../experiments/jd-relational-app/README.md) 與 [ADR 0077](../../docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)。

以下記錄退役前的 API：當時唯一 production prefix 是 `/api/v1/job-analysis/consultant-documents`，健康檢查是 `/healthz`。舊 interview、job-authoring 與 ADR 0058 writer routes 已移除。

## 結構

```text
app/
  consultant/            LangGraph state／commands、顧問 Skills、context、verifier、review、authority
  export/                核准文件 → deterministic export model
  adapters/
    langgraph/           PostgreSQL Saver／Store 與最小 catalog
    openrouter/          LangChain OpenRouter binding
    xlsx/                OpenPyXL renderer
  api/                   consultant route、mapper、problem response、composition
  database.py            lifespan／health connection
  observability.py       payload-free OpenTelemetry
```

`app.consultant` 不依賴 FastAPI、OpenRouter adapter、XLSX 或 RAG。LangGraph checkpoint／Store 是唯一 durable semantic state／員工來源 owner；LLM 只能提出待審 changeset，員工 command 才能寫核准文件。邊界由 `tests/test_consultant_foundation_boundaries.py` 與 `tests/test_consultant_hard_cut.py` 強制。

## 資料庫與啟動

Fresh root migration `0018_consultant_runtime_root` 只建立最小 catalog；LangGraph 官方 tables 由 setup script 初始化。舊資料不搬移、不雙寫。

```bash
npm run infra
npm run db:migrate
npm run consultant-storage:setup
cd apps/api && uv run python run_live.py
```

LLM route 由 `.env` 的 `CONSULTANT_*` 與 `OPENROUTER_*` 設定版本化 profile／policy。跨 app 真相見 [`docs/design/consultant-runtime.md`](../../docs/design/consultant-runtime.md)。RAG bounded context 仍保留，但本 app 不得 import 或呼叫；目前沒有 Reference／RAG consumer。
