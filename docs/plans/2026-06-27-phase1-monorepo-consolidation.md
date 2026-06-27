# Phase 1 — Caliburn Monorepo 併合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把三個現有 repo（`jobintel-ai`、`jd-ocs-indexer`、`jd-pdf-to-json`）併進一個新的 `caliburn/` monorepo，保留各自 git 歷史，接好 Turborepo + uv workspace，且三專案的既有測試「原樣全綠」——**一行邏輯都不改**。

**Architecture:** 新建 `caliburn/` git repo（pnpm workspaces + Turborepo 任務編排 + uv workspace 共用 Python lockfile）。三個來源 repo 以 `git subtree add`（保留歷史）併入 `apps/`；`jobintel-ai` 拆成 `apps/api`（後端）+ `apps/web`（前端）。每個 Python app 加一個薄 `package.json` 讓 Turborepo 編排。

**Tech Stack:** git subtree、pnpm（workspaces）、Turborepo、uv（workspace）、Python 3.13（api）/ 3.11+（indexer、pdf-to-json）、Next.js 16（web）、pytest、Windows + Git Bash。

## Global Constraints

- **只搬不改**：本階段不得修改任何業務邏輯、不得改 import package 名（`app` / `jd_ocs_indexer` / `jd_pdf_to_json` 維持原名；`app`→`caliburn_api` 屬 Phase 3）。
- **保留 git 歷史**：三 repo 一律用 `git subtree add`（不可只複製檔案）。
- **驗收 = 既有測試原樣全綠 + 工具指令可跑**（非寫新測試）。
- **平台**：Windows + Git Bash；路徑用 `/s/...`。Python 用各 app 既有版本。
- **來源 repo 路徑**：`/s/jobintel-ai`、`/s/jd-ocs-indexer`、`/s/jd-pdf-to-json`（皆為本機 git repo）。
- **新 monorepo 路徑**：`/s/caliburn`。
- **api 啟動 gotcha 不變**：`run_live.py` 需 `WindowsSelectorEventLoopPolicy`；重啟要 `taskkill /F /T` + 確認 8001 單一 listener（沿用既有紀律）。
- **不 commit `.venv` / `node_modules` / `__pycache__`**。

---

### Task 1: 建立空的 caliburn monorepo 骨架

**Files:**
- Create: `/s/caliburn/.git`（git init）
- Create: `/s/caliburn/package.json`
- Create: `/s/caliburn/pnpm-workspace.yaml`
- Create: `/s/caliburn/turbo.json`
- Create: `/s/caliburn/.gitignore`
- Create: `/s/caliburn/README.md`

**Interfaces:**
- Produces: 一個可 `pnpm install` 的空 monorepo 根；`apps/` 與 `packages/` 由後續 task 填入。

- [ ] **Step 1: 建 repo 與目錄**

```bash
mkdir -p /s/caliburn && cd /s/caliburn
git init
mkdir -p apps packages docs/specs docs/plans
```

- [ ] **Step 2: 寫根 `package.json`**

```json
{
  "name": "caliburn",
  "private": true,
  "packageManager": "pnpm@9.12.0",
  "workspaces": ["apps/*", "packages/*"],
  "scripts": {
    "dev": "turbo dev",
    "build": "turbo build",
    "test": "turbo test",
    "lint": "turbo lint"
  },
  "devDependencies": {
    "turbo": "^2.3.0"
  }
}
```

- [ ] **Step 3: 寫 `pnpm-workspace.yaml`**

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

- [ ] **Step 4: 寫 `turbo.json`**（任務圖；Python app 的 test/lint 之後由各自 package.json 的 script 提供）

```json
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "dev": { "cache": false, "persistent": true },
    "build": { "dependsOn": ["^build"], "outputs": ["dist/**", ".next/**"] },
    "test": { "dependsOn": ["^build"], "outputs": [] },
    "lint": { "outputs": [] }
  }
}
```

- [ ] **Step 5: 寫 `.gitignore`**

```gitignore
node_modules/
.venv/
__pycache__/
*.pyc
.next/
dist/
.turbo/
.env
uv.lock.bak
```

- [ ] **Step 6: 寫 `README.md`**（一行說明 + 指向 spec）

```markdown
# Caliburn

給顧問用的多租戶 B2B SaaS（職能基準 → 職務說明書）。Monorepo：Turborepo + uv workspace。
架構見 `docs/specs/2026-06-27-system-architecture-design.md`。
```

- [ ] **Step 7: 安裝並驗證空 monorepo**

```bash
cd /s/caliburn && pnpm install
```
Expected: pnpm 成功安裝 turbo，無 workspace 套件錯誤（apps/ packages/ 尚空）。

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "chore: scaffold Caliburn monorepo (pnpm workspaces + Turborepo)"
```

---

### Task 2: 以 subtree 併入 pdf-to-json → `apps/pdf-to-json`

**Files:**
- Create: `apps/pdf-to-json/**`（subtree 自 `/s/jd-pdf-to-json`，保留歷史）
- Create: `apps/pdf-to-json/package.json`（薄 shim）

**Interfaces:**
- Consumes: `/s/jd-pdf-to-json`（本機 git repo，uv + pyproject.toml）。
- Produces: `apps/pdf-to-json`（含原 `src/jd_pdf_to_json/`、`tests/`、`pyproject.toml`）；可由 monorepo 跑其 pytest。

- [ ] **Step 1: 確認來源 repo 的預設分支**

```bash
git -C /s/jd-pdf-to-json branch --show-current
```
記下分支名（下稱 `<BR>`，常見 `main` 或 `master`）。

- [ ] **Step 2: 加本機 remote 並 subtree 併入**

```bash
cd /s/caliburn
git remote add src-pdf /s/jd-pdf-to-json
git fetch src-pdf
git subtree add --prefix=apps/pdf-to-json src-pdf <BR>
```
Expected: `apps/pdf-to-json/` 出現原始檔案，`git log -- apps/pdf-to-json` 看得到原 repo 歷史。

- [ ] **Step 3: 加薄 `apps/pdf-to-json/package.json`**（讓 Turborepo 找得到、把 test/lint 指到 uv）

```json
{
  "name": "@caliburn/pdf-to-json",
  "private": true,
  "scripts": {
    "test": "uv run pytest -q",
    "lint": "uv run ruff check src",
    "build": "echo \"no build\""
  }
}
```

- [ ] **Step 4: 驗證既有測試原樣全綠**

```bash
cd /s/caliburn/apps/pdf-to-json && uv sync && uv run pytest -q
```
Expected: 與在原 repo 跑 `uv run pytest -q` 相同的結果（全綠 / 同樣的 skip）。**若有 fail，先確認非搬移造成（與原 repo 比對），不得改邏輯。**

- [ ] **Step 5: Commit**

```bash
cd /s/caliburn
git add apps/pdf-to-json/package.json && git commit -m "chore: add pdf-to-json package.json shim for turbo"
```

---

### Task 3: 以 subtree 併入 ocs-indexer → `apps/ocs-indexer`

**Files:**
- Create: `apps/ocs-indexer/**`（subtree 自 `/s/jd-ocs-indexer`）
- Create: `apps/ocs-indexer/package.json`（薄 shim）

**Interfaces:**
- Consumes: `/s/jd-ocs-indexer`（uv + pyproject.toml；含 Qdrant/BGE-M3 依賴）。
- Produces: `apps/ocs-indexer`，可由 monorepo 跑其 pytest。

- [ ] **Step 1: 確認來源分支**

```bash
git -C /s/jd-ocs-indexer branch --show-current
```
記下 `<BR>`。

- [ ] **Step 2: subtree 併入**

```bash
cd /s/caliburn
git remote add src-indexer /s/jd-ocs-indexer
git fetch src-indexer
git subtree add --prefix=apps/ocs-indexer src-indexer <BR>
```
Expected: `apps/ocs-indexer/` 出現原始檔案 + 歷史。

- [ ] **Step 3: 加薄 `apps/ocs-indexer/package.json`**

```json
{
  "name": "@caliburn/ocs-indexer",
  "private": true,
  "scripts": {
    "test": "uv run pytest -q",
    "lint": "uv run ruff check src",
    "build": "echo \"no build\""
  }
}
```

- [ ] **Step 4: 驗證既有測試原樣全綠**

```bash
cd /s/caliburn/apps/ocs-indexer && uv sync && uv run pytest -q
```
Expected: 與原 repo 相同結果（需 Qdrant 的整合測試該 skip 就 skip）。

- [ ] **Step 5: Commit**

```bash
cd /s/caliburn
git add apps/ocs-indexer/package.json && git commit -m "chore: add ocs-indexer package.json shim for turbo"
```

---

### Task 4: 以 subtree 併入 jobintel-ai → 拆成 `apps/api` + `apps/web`

**Files:**
- Create（暫存）: `_import/jobintel/**`（subtree 自 `/s/jobintel-ai`）
- Move: `_import/jobintel/backend` → `apps/api`
- Move: `_import/jobintel/frontend` → `apps/web`
- Move: `_import/jobintel/docs/specs/*` → `docs/specs/`；`_import/jobintel/docs/plans/*` → `docs/plans/`
- Move: `_import/jobintel/docker-compose.yml` → `/s/caliburn/docker-compose.yml`
- Create: `apps/api/package.json`（薄 shim）
- Create: `apps/api/pyproject.toml`（由 `backend/requirements.txt` 轉成，name=`caliburn-api`，packages=`["app"]`，**import 名仍為 `app`**）

**Interfaces:**
- Consumes: `/s/jobintel-ai`（含 `backend/`〔requirements.txt + `app` 套件 + `.venv` + run_live.py〕、`frontend/`〔Next.js + 既有 package.json〕、`docs/`）。
- Produces: `apps/api`（後端，import 名 `app` 不變）、`apps/web`（前端，沿用其 package.json）。

- [ ] **Step 1: 確認來源分支**

```bash
git -C /s/jobintel-ai branch --show-current
```
記下 `<BR>`（目前為 `feat/v3`）。

- [ ] **Step 2: subtree 併入暫存目錄**

```bash
cd /s/caliburn
git remote add src-jobintel /s/jobintel-ai
git fetch src-jobintel
git subtree add --prefix=_import/jobintel src-jobintel <BR>
```

- [ ] **Step 3: 拆 backend → apps/api、frontend → apps/web，移 docs / compose**

```bash
cd /s/caliburn
git mv _import/jobintel/backend apps/api
git mv _import/jobintel/frontend apps/web
git mv _import/jobintel/docker-compose.yml docker-compose.yml
# docs：把舊 spec/plan 併入根 docs（檔名不撞；撞則保留兩者）
git mv _import/jobintel/docs/specs/* docs/specs/ 2>/dev/null || true
git mv _import/jobintel/docs/plans/* docs/plans/ 2>/dev/null || true
git commit -m "chore: split jobintel-ai into apps/api + apps/web (history preserved)"
```

- [ ] **Step 4: 移除暫存殘餘 + 清掉搬進來的 `.venv`（不該入庫）**

```bash
cd /s/caliburn
git rm -r --cached apps/api/.venv 2>/dev/null || true
rm -rf apps/api/.venv
git rm -r _import 2>/dev/null || true   # 若 _import 仍有殘檔
git status   # 確認 _import 已空/移除
git commit -m "chore: drop committed .venv and temp import dir" || true
```
Expected: `apps/api/`（含 `app/`、`alembic/`、`tests/`、`requirements.txt`、`run_live.py`）、`apps/web/`（含 Next.js 專案）就位；`_import/` 消失；`.venv` 不在版控。

- [ ] **Step 5: 為 api 建 `apps/api/pyproject.toml`（包住既有 requirements，import 名仍 `app`）**

先看依賴：
```bash
cat /s/caliburn/apps/api/requirements.txt
```
據此寫 `apps/api/pyproject.toml`（把 requirements 的釘選照抄進 `dependencies`；以下為依目前 requirements.txt 的對應，執行時以實檔為準）：

```toml
[project]
name = "caliburn-api"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
  "fastapi==0.115.0",
  "uvicorn[standard]==0.30.6",
  "sqlalchemy==2.0.35",
  "asyncpg==0.30.0",
  "alembic==1.13.3",
  "psycopg[binary]==3.3.4",
  "langchain==1.3.9",
  "langchain-core==1.4.7",
  "langgraph==1.2.5",
  "langgraph-checkpoint-postgres==3.1.0",
  "ag-ui-langgraph==0.0.41",
  "langchain-openai==1.3.2",
  "jinja2==3.1.4",
  "python-docx==1.1.2",
  "openpyxl==3.1.5",
  "reportlab==4.2.2",
  "pydantic==2.9.2",
  "pydantic-settings==2.5.2",
  "python-dotenv==1.0.1",
  "python-multipart==0.0.12",
  "httpx==0.27.2",
  "opentelemetry-sdk==1.42.1",
  "opentelemetry-exporter-otlp-proto-http==1.42.1",
]

[dependency-groups]
dev = ["pytest==8.3.3", "pytest-asyncio==0.24.0", "respx==0.21.1"]

[tool.uv.sources]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 6: 加薄 `apps/api/package.json`**

```json
{
  "name": "@caliburn/api",
  "private": true,
  "scripts": {
    "test": "uv run pytest -q",
    "build": "echo \"no build\""
  }
}
```

- [ ] **Step 7: 驗證 api 既有測試原樣全綠**

```bash
cd /s/caliburn/apps/api && uv sync && uv run pytest -q
```
Expected: 與原 `backend/.venv/Scripts/python -m pytest -q` 相同結果（無 DB 時該 skip 就 skip）。**有 fail 先與原 repo 比對，確認非搬移造成。**

- [ ] **Step 8: 驗證 web 既有閘門全綠**

```bash
cd /s/caliburn/apps/web && npm install && npx tsc --noEmit && npm run lint
```
Expected: tsc 0 error、lint 0 error（與原 frontend 相同）。

- [ ] **Step 9: Commit**

```bash
cd /s/caliburn
git add apps/api/pyproject.toml apps/api/package.json
git commit -m "chore: wrap api in pyproject (name=caliburn-api, import pkg unchanged 'app')"
```

---

### Task 5: 接上 uv workspace（共用 lockfile）

**Files:**
- Create: `/s/caliburn/pyproject.toml`（`[tool.uv.workspace]` members）
- Create: `/s/caliburn/uv.lock`（`uv lock` 產生）

**Interfaces:**
- Consumes: `apps/api`、`apps/ocs-indexer`、`apps/pdf-to-json` 各自的 `pyproject.toml`。
- Produces: 根 uv workspace；`uv run --package <name> ...` 可指定成員。

- [ ] **Step 1: 寫根 `pyproject.toml`（純 workspace 宣告）**

```toml
[tool.uv.workspace]
members = ["apps/api", "apps/ocs-indexer", "apps/pdf-to-json"]
```

- [ ] **Step 2: 產生共用 lockfile 並同步**

```bash
cd /s/caliburn && uv lock && uv sync --all-packages
```
Expected: 產生 `uv.lock`；三個 Python 成員的依賴解析成功。**若三者對同一套件釘到衝突版本而無法解，記錄衝突套件並回報（屬 Phase 1 已知風險，不在此改套件版本——改名/改版屬後續），先改用「各 app 各自 `uv sync`」的退路繼續。**

- [ ] **Step 3: 從 workspace 根分別驗證三 app 測試**

```bash
cd /s/caliburn
uv run --package caliburn-api pytest apps/api -q
uv run --package jd-ocs-indexer pytest apps/ocs-indexer -q
uv run --package jd-pdf-to-json pytest apps/pdf-to-json -q
```
（`--package` 值＝各 app `pyproject.toml` 的 `name`；indexer/pdf 的 name 以其實檔為準，執行前 `grep '^name' apps/*/pyproject.toml` 確認。）
Expected: 三者結果與各自獨立跑時相同。

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock && git commit -m "chore: wire uv workspace (shared lockfile across 3 python apps)"
```

---

### Task 6: 接上 Turborepo 編排並全綠驗收

**Files:**
- Modify: `/s/caliburn/turbo.json`（確認 test/lint/dev 任務涵蓋四 app）
- 確認: `apps/web/package.json` 已有 `dev`/`build`/`lint` script（Next.js 既有）

**Interfaces:**
- Consumes: 四個 app 的 `package.json` script（test/lint/build/dev）。
- Produces: `turbo test` / `turbo lint` 一鍵跑全部；`turbo dev` 一鍵起 web+api(+indexer)。

- [ ] **Step 1: 確認 web 的 script 與 dev port**

```bash
cat /s/caliburn/apps/web/package.json
```
確認有 `"dev"`, `"build"`, `"lint"`（Next.js 預設有）。若 `lint` 缺，加 `"lint": "next lint"`。

- [ ] **Step 2: 確認 api 有 `dev` script（起 run_live，保留 SelectorEventLoop）**

在 `apps/api/package.json` 的 `scripts` 加：
```json
    "dev": "uv run python run_live.py"
```
（`run_live.py` 已設 `WindowsSelectorEventLoopPolicy`；不改其內容。）

- [ ] **Step 3: 全倉跑 test（Turborepo 編排）**

```bash
cd /s/caliburn && pnpm install && npx turbo test
```
Expected: turbo 平行跑四個 `test` task；三 Python app 綠、web 無 test 任務則略過或顯示 no-op。整體結果＝各 app 既有結果之和（無新增 fail）。

- [ ] **Step 4: 全倉跑 lint**

```bash
npx turbo lint
```
Expected: 各 app lint 通過（與其原 repo 相同）。

- [ ] **Step 5: 煙霧測試 `turbo dev`（手動起一次再關）**

```bash
npx turbo dev
```
Expected: web(:3000)、api(:8001) 能起來（indexer 視 Qdrant/模型而定）。確認後 `Ctrl-C` 關閉；依紀律 `taskkill /F /T` 清殘留、確認 8001 單一 listener。

- [ ] **Step 6: Commit**

```bash
git add turbo.json apps/web/package.json apps/api/package.json
git commit -m "chore: wire turborepo tasks (test/lint/dev) across api/web/indexer/pdf-to-json"
```

---

### Task 7: 收尾 — 封存舊 repo、打 tag、最終驗收

**Files:**
- 無新檔；移除 subtree remotes、打 tag、舊 repo 標記封存。

- [ ] **Step 1: 移除 subtree 用的本機 remotes**

```bash
cd /s/caliburn
git remote remove src-pdf
git remote remove src-indexer
git remote remove src-jobintel
```

- [ ] **Step 2: 最終全綠驗收（一次到底）**

```bash
cd /s/caliburn
pnpm install
uv sync --all-packages || true
npx turbo test
npx turbo lint
```
Expected: test/lint 全綠（= 三 repo 既有狀態之和，零新增 fail）。

- [ ] **Step 3: 打里程碑 tag**

```bash
git tag -a phase1-monorepo -m "Phase 1: 3 repos consolidated into Caliburn monorepo (history preserved, tests green)"
```

- [ ] **Step 4: 封存舊三 repo（唯讀，不刪）**

在各舊 repo 的 README 頂端加一行（**手動或下列指令**），標明已併入 caliburn：
```bash
for d in /s/jobintel-ai /s/jd-ocs-indexer /s/jd-pdf-to-json; do
  printf '> ⚠️ 已併入 Caliburn monorepo（/s/caliburn，Phase 1 2026-06）。此 repo 封存唯讀，後續開發在 caliburn。\n\n' | cat - "$d/README.md" > "$d/README.tmp" && mv "$d/README.tmp" "$d/README.md"
done
```
（若某 repo 無 README.md 則略過該行手動處理。）此步**不 commit 到 caliburn**；是對舊 repo 的標記，可各自 commit 或僅本地保留。

- [ ] **Step 5: 確認 Phase 1 完成定義**

逐項打勾：
  - [ ] `apps/{api,web,ocs-indexer,pdf-to-json}` 與 `packages/`（空）就位
  - [ ] `git log -- apps/ocs-indexer`（等）看得到原 repo 歷史
  - [ ] `npx turbo test` 全綠、`npx turbo lint` 全綠
  - [ ] `.venv`/`node_modules`/`__pycache__` 不在版控
  - [ ] 無任何業務邏輯/ import 名變更（`git log` 僅 chore: 搬移/接線）

---

## 完成後

Phase 1 完成＝三專案在 caliburn monorepo 內、歷史保留、測試原樣全綠、工具鏈接好。**下一步 Phase 2**：抽 `packages/ocs-contract`（JSON-Schema → codegen + PR schema-diff）。各 app 內部優化（Phase 3）在其後。
