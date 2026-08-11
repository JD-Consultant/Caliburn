# Caliburn 架構

> 現行架構只描述可執行的新系統。歷史 OCS、indexer、PDF ETL、embedder、舊訪談與 `job_authoring` 已在 current-only 硬切中移除；相關 ADR／研究只保留作決策歷史，不能作為新程式入口。

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

跨 app 流程見 [`docs/design/task-analysis-engine.md`](docs/design/task-analysis-engine.md)，決策見 [`docs/adr/README.md`](docs/adr/README.md)，操作見 [`docs/runbook.md`](docs/runbook.md)。current-only 硬切見 [ADR 0057](docs/adr/0057-current-only-runtime-and-data-boundary.md)。

不要新增或恢復 `app.interview`、`app.interview_vnext`、`app.job_authoring`、OCS contract、indexer、Qdrant、embedder 或 PDF→JSON pipeline；它們已不在 repo 的 runtime／schema 邊界內。
