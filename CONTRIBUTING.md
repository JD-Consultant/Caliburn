# Contributing to Caliburn

Caliburn 是一個 monorepo:**Turborepo**(任務編排)+ **npm workspaces**(JS)+ **per-app `uv`**(Python)。
架構見 [`docs/specs/2026-06-27-system-architecture-design.md`](docs/specs/2026-06-27-system-architecture-design.md);決策見 [`docs/adr/`](docs/adr/);維運見 [`docs/runbook.md`](docs/runbook.md)。

## 專案結構

```
apps/
  api/          Python·uv   FastAPI + LangGraph 後端(:8001)   import 名 = app
  web/          Next.js     前端(:3000)
  ocs-indexer/  Python·uv   Qdrant + BGE-M3 知識服務(:8000)
  pdf-to-json/  Python·uv   PDF → OCS JSON ETL(CLI,非常駐)
packages/       共用套件(Phase 2:ocs-contract)
docs/           系統文檔 / ADR / runbook(見 docs/README.md)
```

## 先備工具

- **Node 22 + npm 10**、**uv**(Astral)、**Docker**(跑 Postgres)。
- Windows + Git Bash / PowerShell 皆可。

## 安裝

```bash
# JS 那側(根,含 web + turbo)
npm install
# 各 Python app(各自 uv 專案)
cd apps/api          && uv sync
cd apps/ocs-indexer  && uv sync --all-extras
cd apps/pdf-to-json  && uv sync --extra dev
```
> uv workspace(共用 lockfile)目前**未啟用**(見 [ADR 0005](docs/adr/0005-per-app-uv-defer-workspace.md)),Phase 2 抽契約時再接。

## 跑開發環境

依賴先起:`docker compose up -d db`(Postgres :5432);需要知識查詢時另起 indexer(見 runbook)。

```bash
npx turbo dev          # 一鍵起 api(:8001)+ web(:3000)
npx turbo dev --filter=web    # 只起某一個
```
詳細起停 / 重啟紀律見 [`docs/runbook.md`](docs/runbook.md)。

## 測試 / Lint(提交前的閘門)

```bash
npx turbo test         # 三個 Python app 全跑(api / ocs-indexer / pdf-to-json)
npx turbo lint         # web eslint(Python ruff 待 Phase 3 清理)
```
單一 app:
```bash
cd apps/api          && uv run pytest -q
cd apps/ocs-indexer  && uv run --all-extras pytest -q
cd apps/pdf-to-json  && uv run --extra dev pytest -q
cd apps/web          && npx tsc --noEmit && npm run lint
```

## 提交規範

Conventional commits,scope = app/package:
```
feat(api): …   fix(web): …   chore(indexer): …   docs(contract): …
```
不要加 Co-Authored-By trailer。破壞性 DB 動作需明確授權。

## 平台 / 工具注意(踩過的坑)

- **Windows + api**:`run_live.py` 需 `WindowsSelectorEventLoopPolicy`(psycopg async checkpointer)—— 已內建,別改。
- **重啟 api 要乾淨**:uvicorn reload 是 reloader+worker 雙進程,殺要 `taskkill /F /T` 整棵樹、確認 :8001 單一 listener,否則殘留 worker 跑舊碼=「改了沒效」。見 runbook。
- **uv venv 沒有 pip**:列套件用 `uv pip list` / `uv pip freeze`,不是 `python -m pip`。
- **依賴以 `pyproject.toml` 為準**:api 舊 `requirements.txt` 已過期(pydantic/dotenv/email-validator/greenlet 都對不上真實環境),勿再依賴它(Phase 3 退役)。新增依賴改 pyproject + `uv lock`。
