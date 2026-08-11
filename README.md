# Caliburn

Caliburn 是給員工使用的本機 Web AI 職務分析與職務說明書應用程式。現行版本只保留 Job Analysis：API、Web、Job Analysis contract 與 PostgreSQL；不需要登入、帳號、多租戶或遠端產品網址。

## 快速開始

```bash
npm install
cd apps/api && uv sync
cd ../..
npm run up
npm run db:migrate
```

工作台：<http://localhost:3000/workspace>。API：<http://localhost:8001>。停止：`npm run down`。

## 現行成員

- `apps/api`：FastAPI Job Analysis、OpenRouter provider、PostgreSQL current state。
- `apps/web`：Next.js 文件庫、顧問、Proposal 與 Current JD 工作台。
- `packages/job-analysis-contract`：API／Web 共用的 JSON Schema 生成契約。

## RAG 供應鏈（保留、隔離，非 current runtime）

repo 另外保留一組與 current 產品完全隔離的 RAG bounded context：`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract`、`packages/indexer-contract`。可獨立安裝、測試、執行，但不是 current API/Web 的 runtime 依賴；`npm run up`／`npm run dev` 不啟動它們，Qdrant／embedder 需 `npm run rag:up` 才啟動。細節見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)。

## 文件與測試

- 架構：[`ARCHITECTURE.md`](ARCHITECTURE.md)
- 開發：[`CONTRIBUTING.md`](CONTRIBUTING.md)
- 操作：[`docs/runbook.md`](docs/runbook.md)
- current-only 決策：[`docs/adr/0057-current-only-runtime-and-data-boundary.md`](docs/adr/0057-current-only-runtime-and-data-boundary.md)

```bash
npx turbo test
cd apps/api && uv run pytest -q
cd ../web && npm run test && npx tsc --noEmit && npm run lint
```

interview 與 job-authoring 已移除；OCS、PDF→JSON、indexer、Qdrant、embedder 已依 ADR 0057 保留為獨立 RAG bounded context（見上方）。current 產品舊資料不搬移，既有本機 DB 需依 runbook 重建。
