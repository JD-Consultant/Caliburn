# Caliburn API

現行 API 是本機 Job Analysis 後端。唯一 production route prefix 是 `/api/v1/job-analysis`，健康檢查是 `/healthz`；舊 OCS editor、interview、vNext 與 job-authoring routes 已移除，不在本 app 恢復。

repo 另外保留與本 app 完全隔離的 RAG bounded context（`apps/pdf-to-json`／`apps/ocs-indexer`／`apps/embedder`／`ocs-contract`／`indexer-contract`，見 [`docs/design/rag-pipeline.md`](../../docs/design/rag-pipeline.md)）；本 app 不得 import 它們的任何 runtime 模組，由 `tests/test_job_analysis_dependencies.py` 的 AST guard 強制。

## 結構

現行 API 拆成功能模組（ADR 0058），不再有單一 `job_analysis` 大 namespace：

```text
app/
  core/             共同 Current State、authority transaction／port、journal、domain language
  documents/        文件生命週期、header、readiness、Duty／Task 員工直接編輯
  task_analysis/    Task context、LLM wire／prompt、operation、verifier、Task Proposal
  opks/             OPKS context、child operation、scheduler、員工編輯、verifier、OPKS Proposal
  consultation/     員工回合 orchestration（只透過 task_analysis／opks 的 public API 協調）
  export/           純 deterministic Current State → 公版表格投影
  adapters/
    postgres/       SQLAlchemy model、repository、serialization
    openrouter/     OpenRouter adapter（唯一 LLM provider）
    xlsx/           OpenPyXL renderer（唯一存在 OpenPyXL 的地方）
  api/              route（documents／consultation／opks／export）、mapper、problem response、
                    dependency composition、`router.py` 是唯一 composition root
  database.py       async SQLAlchemy engine/session
  observability.py  OTel 橫切
```

`core` 與各 feature module 不依賴 FastAPI、SQLAlchemy 或 provider；HTTP 只在 `app/api`；PostgreSQL／OpenRouter／OpenPyXL 只在對應 adapter。AI 呼叫在 transaction 外執行，寫入前重新驗證 authority snapshot，員工決策才會改 Current JD。

## 資料庫

Alembic `0012`–`0017` 是 current-only migration chain，root 為 `0012_job_analysis_current_state`，head 為 `0017`。資料表只屬於 `job_analysis_*`；舊資料不搬移、不雙寫。

```bash
npm run db:migrate
cd apps/api && uv run pytest -q
```

本機啟動：`cd apps/api && uv run python run_live.py`。API 設定由 `app/config.py` 讀取，LLM provider 使用本機設定的 OpenRouter key；員工不需帳號或登入。

跨 app 流程見 [`docs/design/task-analysis-engine.md`](../../docs/design/task-analysis-engine.md)，API 邊界與測試指引見根目錄 [`AGENTS.md`](../../AGENTS.md)。
