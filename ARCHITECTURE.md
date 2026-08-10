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

- `app/job_analysis/domain/`：純 domain、state、Evidence、Proposal 與不變量。
- `app/job_analysis/application/`：文件、Current JD、顧問回合、OPKS、Proposal 決策、export 與 authority commit。
- `app/job_analysis/llm/`：prompt、wire schema、結果映射與 verifier 邊界。
- `app/job_analysis/providers/`：目前唯一的 OpenRouter provider。
- `app/adapters/job_analysis_postgres/`：SQLAlchemy models、repository、serialization。
- `app/api/`：HTTP route、dependency composition、mapper 與 problem response。

唯一 production route prefix 是 `/api/v1/job-analysis`；`/healthz` 是服務健康檢查。AI 只能提出 Proposal，員工決策或直接編輯才可改變 Current JD；所有 authority writer 經同一個 transaction seam。

## 文檔與退役邊界

跨 app 流程見 [`docs/design/task-analysis-engine.md`](docs/design/task-analysis-engine.md)，決策見 [`docs/adr/README.md`](docs/adr/README.md)，操作見 [`docs/runbook.md`](docs/runbook.md)。current-only 硬切見 [ADR 0057](docs/adr/0057-current-only-runtime-and-data-boundary.md)。

不要新增或恢復 `app.interview`、`app.interview_vnext`、`app.job_authoring`、OCS contract、indexer、Qdrant、embedder 或 PDF→JSON pipeline；它們已不在 repo 的 runtime／schema 邊界內。
