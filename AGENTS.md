# Caliburn — agent orientation

Caliburn 是給員工使用的**本機 Web AI 職務分析與職務說明書應用程式**。目前只保留新的 Job Analysis 系統：本機單一操作者、可保存多份彼此隔離的職務說明書，不做登入、帳密、多租戶、organization/member/ACL、計費、雲端部署或多人協作。維護者使用繁體中文，回覆也用繁中。

`AGENTS.md` 與 `docs/` 是本 repo 權威；`CLAUDE.md` 只 import 本檔。若歷史文檔與本檔衝突，以現行 code、共用目前 JD ADR 0069、顧問 runtime ADR 0060、current／RAG 邊界 ADR 0057 與本檔為準。

## 工作紀律

1. 重大變更先研究，將來源、診斷、選項與取捨寫入 `docs/specs/<date>-*.md`。
2. 架構決策寫 Nygard 式 ADR，預設 `Proposed`，並更新 `docs/adr/README.md`；翻案開新號。
3. 多步變更先寫 `docs/plans/`，拆成可獨立驗證的工作。
4. 保留測試作安全網；綠燈後一個 task 一個 commit，收尾建立本地 tag。
5. 新 API／共用格式依 [`docs/contract-strategy.md`](docs/contract-strategy.md) 選契約機制。
6. 不 push、不做對外動作，除非 owner 明確要求。
7. 改跨 app seam 或子系統時，同 commit 更新對應 `docs/design/` 或 app README。

## 現行架構

- Current 產品 monorepo 成員是 `apps/api`、`apps/web` 與 `packages/job-analysis-contract`；PostgreSQL 是唯一預設 Docker 基礎服務。repo 另外保留一組與 current 完全隔離的 RAG bounded context（`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract`、`packages/indexer-contract`），各自可獨立安裝／測試／執行，但不是 current 產品的 runtime 依賴；`npm run up`／`npm run dev` 不啟動它們，要用才 `npm run rag:up`（Qdrant／embedder，opt-in）；細節見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)。
- API 的 Job Analysis 是唯一 production AI 工作面，依 ADR 0060／0069 由 `app/consultant`（職務分析政策、Skills、typed state／command／projection）＋ `adapters/langgraph`（PostgreSQL Saver／Store durable owner）＋ `adapters/openrouter`（LangChain model binding）＋ `export`／`adapters/xlsx`（deterministic export）＋ `api`（唯一 composition root）組成；依賴規則由 `tests/test_consultant_foundation_boundaries.py` 與 `tests/test_consultant_hard_cut.py` 強制。
- Authority 規則：LangGraph checkpoint 持有可修訂理解、訪談工作、Gap、核准／匯出基線與 command receipt；LangGraph Store 持有員工逐字來源、更正 lineage，以及 Deep Agents `StoreBackend` 的唯一 current working document。review 是 approved ↔ current 的即時 semantic diff，不是另一份 document truth。LLM 只能改 current workspace；員工 accept／edit-and-accept／reject 或 direct edit 才能經 deterministic authority seam 改 approved。direct edit 的 touched semantic delta 由 server 推導，Web 不得自稱 paths 或重算 domain invariant。沒有 `defer`，pending review 不阻擋聊天。
- Web 只提供 `/workspace` 與文件詳情頁，吃 `job-analysis-contract` 生成的 TypeScript 契約；主要編輯面只有「目前 JD」，`審核變更` 在同骨架顯示 semantic diff，`匯出版本` 只讀 approved baseline。
- 新資料從 fresh root migration `0018_consultant_runtime_root` 建立最小 catalog，再由 `npm run consultant-storage:setup` 初始化 LangGraph 官方 Saver／Store tables。舊資料不搬移、不雙寫、不相容；若需開發環境，依 runbook 重建資料庫。
- 已刪除的 `app.interview`、`app.interview_vnext`、`app.job_authoring`、`app.core`、`app.documents`、`app.task_analysis`、`app.opks`、`app.consultation` 與舊 `adapters.postgres` 不得重新 import、wrapper 或接回 production。OCS／indexer／embedder／PDF ETL 依 ADR 0057 保留為獨立 RAG bounded context，但本次產品尚未接 RAG／Reference；同樣不得 import、wrapper 或接回 current API/Web composition root。

## 本地開發與驗證

```text
npm install
npm run infra                       # fresh DB 時先只啟動 PostgreSQL
npm run db:migrate                  # fresh root 0018
npm run consultant-storage:setup    # LangGraph Saver／Store tables
npm run dev                         # API/Web dev；不含 RAG
npx turbo test
```

API：`cd apps/api && uv sync && uv run pytest -q`。Web：`cd apps/web && npm run test && npx tsc --noEmit && npm run lint`。改契約後執行 `npm run check-codegen -w @caliburn/job-analysis-contract`。

Windows 上動手前確認 `pwd` 與 `git branch --show-current`；後端 reload 已關閉，改碼要重啟。`uv` 環境不用 pip；CJK 指令設定 `PYTHONUTF8=1`。

## 指路

[`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/README.md`](docs/README.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`docs/runbook.md`](docs/runbook.md) · [`docs/design/consultant-runtime.md`](docs/design/consultant-runtime.md) · [`docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`](docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) · [`docs/adr/0069-shared-current-jd-working-copy-and-semantic-approval.md`](docs/adr/0069-shared-current-jd-working-copy-and-semantic-approval.md)
