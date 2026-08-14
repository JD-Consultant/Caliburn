# Caliburn 架構

> 現行產品是 `apps/api`、`apps/web` 與 `packages/job-analysis-contract`。repo 另保留 ADR 0057 的 RAG bounded context，但尚未接入 current API／Web；兩者必須保持 runtime、contract 與啟動邊界隔離。

## 鳥瞰

Caliburn 是給員工使用的本機 Web AI 職務分析與職務說明書顧問。單一本機操作者可保存多份彼此隔離的文件，不提供登入、多租戶、權限、計費、雲端或多人協作。

```text
Next.js workspace ──HTTP／SSE──▶ FastAPI consultant API
                                      │
                                      ├── LangGraph PostgreSQL Saver／Store
                                      ├── consultant_documents 最小 catalog
                                      ├── LangChain bounded agent ──▶ OpenRouter
                                      └── deterministic projection ──▶ XLSX
```

PostgreSQL 是唯一預設基礎服務。API／Web 在 host 執行；OpenRouter model call 在資料庫交易外執行。Qdrant、embedder 與 indexer 不在 current 啟動路徑。

## Monorepo 成員

| 路徑 | 職責 | 埠位 |
|---|---|---|
| [`apps/api/`](apps/api/README.md) | FastAPI、LangChain／LangGraph 顧問、OpenRouter、PostgreSQL、XLSX | `8001` |
| [`apps/web/`](apps/web/README.md) | Next.js 員工顧問工作區 | `3000` |
| [`packages/job-analysis-contract/`](packages/job-analysis-contract/) | durable consultant JSON Schema 生成的 Python／TypeScript 契約 | — |

## API 邊界

ADR 0060 的 production 依賴方向如下：

- `app/consultant/`：職務分析政策、Task／Duty／O／P／K／S Skills、typed result、deterministic verifier、adaptive interview、required clarification、document review／authority 與 purpose-first projection。它不 import FastAPI、OpenRouter adapter、XLSX 或 RAG。
- `app/adapters/langgraph/`：以 `AsyncPostgresSaver` 與 `AsyncPostgresStore` 承接 durable state、員工逐字來源、checkpoint command、crash reconciliation 與 catalog 存取。
- `app/adapters/openrouter/`：把 versioned model profile／run policy 綁到 LangChain `ChatOpenRouter`；不擁有產品狀態或職務分析方法。
- `app/export/`：只把核准文件組成 deterministic export model；pending changeset 不可進入。
- `app/adapters/xlsx/`：唯一使用 OpenPyXL 的 renderer；官方 iCAP code cells 固定留白。
- `app/api/`：唯一 HTTP composition root、purpose-first mapper、RFC 9457 problem response 與 `/api/v1/job-analysis/consultant-documents` routes。
- `app/database.py`：只供 app lifespan／health check 使用的 SQLAlchemy connection；不是 document store。

舊 `app.core`、`app.documents`、`app.task_analysis`、`app.opks`、`app.consultation`、`app.adapters.postgres` 及其 routes／DTO／writers 已刪除。`apps/api/tests/test_consultant_hard_cut.py` 以 AST、migration 與 schema guard 防止復活；`test_consultant_foundation_boundaries.py` 驗證 framework 與 RAG 邊界。

## Durable authority

- Alembic fresh root `0018_consultant_runtime_root` 只建立 `consultant_documents` 與 `alembic_version`。
- `npm run consultant-storage:setup` 再由 LangGraph 官方 `.setup()` 建立 Saver／Store tables；Caliburn 不鏡像 framework state。
- Store 保存員工逐字來源與 correction lineage；checkpoint 保存可修訂理解、訪談工作、Gap、待審 changeset、核准文件與 command receipts。每項持久事實只有一個 owner。
- LLM 產生的內容一律先進 typed changeset。只有員工 accept／edit-accept command 能寫入核准文件；reject／defer 不改文件。員工直接編輯走同一 deterministic invariant，但不必假裝成 AI 提案。
- 必要澄清使用 LangGraph interrupt／resume，只阻擋 affected branch；一般 Gap 留在待處理投影。關閉頁面不是 pause／finish command，重開直接讀 durable snapshot。
- 模型 profile、provider、參數與 run policy 可版本化替換；Skills 不選模型。能力級別與 A 暫不由 LLM 產生，官方 iCAP 代碼也不由模型或 export 補造。

## Contract 與 Web

`packages/job-analysis-contract/schema/job-analysis-workspace.schema.json` 是唯一 transport source。它只發布 consultant catalog、snapshot、review／clarification／direct-edit commands、approved document、export readiness 與 problem models；不發布舊 document／consultation／Proposal surface。

Web 只有 `/workspace` 與 `/workspace/[document_id]`，以 TanStack Query 管 server cache、原生 `EventSource` 接 refetch notification、本機草稿保護 dirty editor。UI 不解析 raw checkpoint、framework interrupt、context receipt 或 model attempt，也不保存第二份 server authority。

## RAG 供應鏈（保留、隔離）

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract` 與 `packages/indexer-contract` 是可獨立安裝／測試／執行的 RAG bounded context。它們不是 current runtime dependency；`npm run up`／`npm run dev` 不啟動，只有 `npm run rag:up`／`rag:dev` 明確 opt-in。current API 不得 import、呼叫或發布它們的 contract／route／tool。詳見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)。

## 指路

現行跨 app 真相見 [`docs/design/consultant-runtime.md`](docs/design/consultant-runtime.md)，決策見 [ADR 0060](docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)，本機操作見 [`docs/runbook.md`](docs/runbook.md)。
