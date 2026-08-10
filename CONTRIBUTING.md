# Caliburn 開發指南

Caliburn 是以 Turborepo、npm workspaces 與 per-app `uv` 組成的 monorepo。現行成員只有 API、Web 與 Job Analysis contract；完整邊界見 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

## 專案結構

```text
apps/
  api/       FastAPI + PostgreSQL + OpenRouter（:8001）
  web/       Next.js 本機工作台（:3000）
packages/
  job-analysis-contract/  JSON Schema → Python／TypeScript
docs/       架構、ADR、研究、計畫與 runbook
```

## 先備與安裝

- Node 22、npm 10、uv、Docker Desktop。
- `npm install`
- `cd apps/api && uv sync`
- `npm run db:migrate`

## 開發

```bash
npm run up          # 起 db，並啟動 API + Web
npm run down        # 停 db，並收 API/Web 埠位
npx turbo dev --filter=@caliburn/web
```

API 與 Web 都在 host 執行；Docker compose 只有 PostgreSQL。首次硬切或 schema 不相容時，刪除本機 PostgreSQL volume 後重新 `docker compose up -d db` 再跑 migration；舊資料不提供遷移。

## 測試與提交閘門

```bash
npx turbo test
cd apps/api && uv run pytest -q
cd apps/web && npm run test && npx tsc --noEmit && npm run lint
npm run check-codegen -w @caliburn/job-analysis-contract
```

使用 Conventional Commits，例如 `feat(api): ...`、`refactor(web): ...`、`docs: ...`。一個 task 一個 commit；不要 push，除非 owner 明確要求。破壞性資料庫動作須有明確授權（本次 current-only 硬切已授權）。

## 平台注意

- API `run_live.py` reload 已關閉，改後端碼要手動重啟。
- uv venv 沒有 pip，使用 `uv sync`／`uv pip`。
- 根目錄只有一份 `package-lock.json`；不要在 workspace 子目錄建立 lockfile。
