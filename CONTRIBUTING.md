# Caliburn 開發指南

Caliburn 是以 Turborepo、npm workspaces 與 per-app `uv` 組成的 monorepo。current 產品成員是 API、Web 與 Job Analysis contract；完整邊界見 [`ARCHITECTURE.md`](ARCHITECTURE.md)。repo 另外保留一組與 current 完全隔離、可獨立安裝與測試的 RAG bounded context（`pdf-to-json`／`ocs-indexer`／`embedder`／`ocs-contract`／`indexer-contract`），見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)；本指南預設的安裝／開發／測試指令都以 current 產品為主，RAG 一律明確 opt-in。

## 專案結構

```text
apps/
  api/            FastAPI + PostgreSQL + OpenRouter（:8001，current 產品）
  web/            Next.js 本機工作台（:3000，current 產品）
  pdf-to-json/    PDF → OCS JSON（RAG，獨立、隔離）
  ocs-indexer/    OCS JSON → Qdrant 索引與查詢（RAG，獨立、隔離）
  embedder/       BGE-M3 embedding GPU service（RAG，獨立、隔離，Docker only）
packages/
  job-analysis-contract/  JSON Schema → Python／TypeScript（current 產品）
  ocs-contract/           OCS document schema／contract（RAG，獨立、隔離）
  indexer-contract/       indexer 查詢 wire model（RAG，獨立、隔離，Python-only）
docs/       架構、ADR、研究、計畫與 runbook
```

## 先備與安裝

- Node 22、npm 10、uv、Docker Desktop。
- `npm install`
- `cd apps/api && uv sync`
- `npm run db:migrate`
- `npm run consultant-storage:setup`

RAG bounded context 不在上面的預設安裝路徑內；要用才 `cd apps/pdf-to-json && uv sync`／`cd apps/ocs-indexer && uv sync --all-extras`（各自獨立 `uv.lock`），細節見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)。

## 開發

```bash
npm run up          # 起 db，並啟動 API + Web（current 產品；不含 RAG）
npm run down        # 停 db，並收 API/Web 埠位
npx turbo dev --filter=@caliburn/web
npm run rag:up      # opt-in：起 Qdrant + embedder（docker compose --profile rag）
npm run rag:down    # opt-in：停 Qdrant + embedder
npm run rag:dev     # opt-in：起 ocs-indexer 查詢 API（:8000）
```

API 與 Web 都在 host 執行；Docker compose 預設只啟動 PostgreSQL（`db` 沒有 profile）。Qdrant／embedder 標記 `profiles: [rag]`，只有 `npm run rag:up`（或 `docker compose --profile rag up -d`）才會啟動，`npm run up`／`npm run dev` 不會意外拉起它們。首次硬切或 schema 不相容時，刪除本機 PostgreSQL volume 後重新 `docker compose up -d db` 再跑 migration；舊資料不提供遷移。

## 測試與提交閘門

```bash
npx turbo test
cd apps/api && uv run pytest -q
cd apps/web && npm run test && npx tsc --noEmit && npm run lint
npm run check-codegen -w @caliburn/job-analysis-contract
```

未加 `--filter` 的 `npx turbo test` 會連 RAG app（`pdf-to-json`／`ocs-indexer`，兩者都定義了 `test` script）一起跑，但這不代表它們是 current 產品的一部分；`apps/api/tests/test_consultant_foundation_boundaries.py` 與 `test_consultant_hard_cut.py` 會擋下 RAG import 與舊 runtime 復活。

使用 Conventional Commits，例如 `feat(api): ...`、`refactor(web): ...`、`docs: ...`。一個 task 一個 commit；不要 push，除非 owner 明確要求。破壞性資料庫動作須有明確授權（本次 current-only 硬切已授權）。

## 平台注意

- API `run_live.py` reload 已關閉，改後端碼要手動重啟。
- uv venv 沒有 pip，使用 `uv sync`／`uv pip`。
- 根目錄只有一份 `package-lock.json`；不要在 workspace 子目錄建立 lockfile。
