# Caliburn 架構

> 現行架構分兩層：current 產品（`apps/api`／`apps/web`／`packages/job-analysis-contract`）是唯一可執行、被 production 消費的系統；OCS、indexer、PDF ETL、embedder 已依 [ADR 0057](docs/adr/0057-current-only-runtime-and-data-boundary.md) 保留為與 current 完全隔離的獨立 RAG bounded context（見下方「RAG 供應鏈」與 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)），不是已刪除的歷史架構。舊訪談（`app.interview`／`app.interview_vnext`）與 `job_authoring` 才是真正在 current-only 硬切中移除、不得恢復的部分；相關 ADR／研究只保留作決策歷史，不能作為新程式入口。

## 鳥瞰

Caliburn 是給員工使用的本機 Web AI 職務分析與職務說明書應用程式。單一本機操作者可保存多份彼此隔離的職務說明書，不提供登入、多租戶、權限、計費或多人協作。

```
本機 Web ──HTTP──▶ FastAPI job-analysis ──▶ PostgreSQL
                         │
                         └────────一次 LLM request──▶ OpenRouter
```

## Monorepo 成員

| 路徑 | 職責 | 埠位 |
|---|---|---|
| [`apps/api/`](apps/api/README.md) | FastAPI；Job Analysis domain、application、OpenRouter provider、PostgreSQL adapter | `8001` |
| [`apps/web/`](apps/web/README.md) | Next.js 本機工作台；文件庫、顧問回合、Proposal 與 Current JD 編輯 | `3000` |
| [`packages/job-analysis-contract/`](packages/job-analysis-contract/) | Job Analysis JSON Schema 生成的 Python／TypeScript 契約 | — |

PostgreSQL 是唯一基礎服務，資料表由 `apps/api/alembic/versions/0012`–`0017` 建立。API 與 Web 在 host 執行；Docker 只負責資料庫。

## RAG 供應鏈（保留、隔離，非 current runtime）

repo 另外保留一組與 current 產品完全隔離的 RAG bounded context——`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract`、`packages/indexer-contract`（PDF → OCS contract → OCS JSON → indexer → embedder/Qdrant）。它們是可獨立安裝、測試、執行的 monorepo 成員，但**不是** current API/Web 的 runtime dependency：`npm run up`／`npm run dev` 不啟動它們，Qdrant／embedder 只在 Compose `rag` profile 下啟動（`npm run rag:up`）。完整資料流、package 責任與資料落地見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)；決策依據見 [ADR 0057](docs/adr/0057-current-only-runtime-and-data-boundary.md) Decision 5。

## API 邊界

API 依 ADR 0058 拆成功能模組（不再有單一 `app/job_analysis` namespace），依賴方向是 DAG：

- `app/core/`：共同 Current State、authority transaction／port、journal、識別碼與跨模組共享的穩定 domain language；不得 import FastAPI、SQLAlchemy、HTTPX、OpenPyXL 或任何 feature／adapter 模組。
- `app/documents/`：文件生命週期、header、readiness、Duty／Task 員工直接編輯。
- `app/task_analysis/`：Task context、LLM wire／prompt、operation、verifier、Task Proposal。
- `app/opks/`：OPKS context、child operation、scheduler、員工編輯、verifier、OPKS Proposal；與 `task_analysis` 互不 import 對方。
- `app/consultation/`：員工回合 orchestration；唯一允許的跨功能方向——只能透過 `task_analysis`／`opks` 的 root public API 協調，不得 reach 進對方 implementation file。
- `app/export/`：純 deterministic Current State → 公版表格投影；不知道任何具體 render 格式。
- `app/adapters/`：具體 IO 實作——`postgres/`（SQLAlchemy models、repository、serialization）、`openrouter/`（唯一 LLM provider）、`xlsx/`（OpenPyXL renderer；OpenPyXL 只存在這裡）。
- `app/api/`：HTTP route（`routes/documents.py`／`consultation.py`／`opks.py`／`export.py`，共用 `/job-analysis/documents` prefix）、對應 mapper、problem response、dependency composition（`deps.py`）；`router.py` 是唯一 composition root。只能 import 各 feature module 的 root public API 與 `app/adapters/*`，不得直接 reach 進 feature module 的 implementation file。

唯一 production route prefix 是 `/api/v1/job-analysis`；`/healthz` 是服務健康檢查。AI 只能提出 Proposal，員工決策或直接編輯才可改變 Current JD；所有 authority writer 經同一個 transaction seam，provider 呼叫在 transaction 外執行。依賴規則由 `apps/api/tests/test_job_analysis_dependencies.py` 的 AST guard 強制。

## 文檔與退役邊界

跨 app 流程見 [`docs/design/task-analysis-engine.md`](docs/design/task-analysis-engine.md)（current 產品）與 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)（RAG 供應鏈，隔離），決策見 [`docs/adr/README.md`](docs/adr/README.md)，操作見 [`docs/runbook.md`](docs/runbook.md)。current-only 硬切見 [ADR 0057](docs/adr/0057-current-only-runtime-and-data-boundary.md)。

不要新增或恢復 `app.interview`、`app.interview_vnext` 或 `app.job_authoring`；它們已從 repo 移除，不在 runtime／schema 邊界內。OCS contract、indexer、Qdrant、embedder 與 PDF→JSON pipeline 已依 ADR 0057 保留為獨立 RAG bounded context（monorepo 成員、可獨立執行），但同一條邊界仍然成立：不要把它們 import、wrapper 或接回 current API/Web 的 production composition root。
