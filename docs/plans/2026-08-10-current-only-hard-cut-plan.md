# Current-only hard cut 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to execute this plan task-by-task.

**Goal:** 將 Caliburn 收斂成只含本機 `job_analysis` API／Web／PostgreSQL current state 的 monorepo，移除舊引擎、舊表、舊 route、舊 OCS stack，並以可重建資料庫與完整測試證明 current-only 邊界。

**Architecture:** 保留 `apps/api`、`apps/web`、`packages/job-analysis-contract`；API 只掛 `/api/v1/job-analysis`，Web 只掛 `/workspace`。Alembic 以 current migration 0012–0017 為唯一歷史，0012 重新成為 root。不得新增相容層、資料搬遷、dual write、SaaS 或登入。

**Tech Stack:** FastAPI、SQLAlchemy/Alembic、Pydantic、HTTPX、OpenPyXL、Next.js、TypeScript、Turborepo、npm workspace、per-app uv、PostgreSQL。

## Global constraints

- 先研究與護欄，再刪除；刪除前列出 exact tracked paths 並確認只在本 worktree 內。
- owner 已允許丟棄既有本機 DB；不執行舊資料 migration，也不保留舊 table 相容層。
- 每一 task 完成 focused verification 後獨立 commit；不 push。
- 歷史 ADR/spec/design 不刪；Accepted ADR 不改，current-only 以 ADR 0057 與現行 docs/index 重新指路。
- 刪除 legacy test 不等於降低品質：保留 current API、domain、persistence、migration、Web、contract 與 negative boundary tests。

---

### Task 1: 固定 current-only route、import、table inventory

**Files:** current API/Web tests、`docs/specs/2026-08-10-current-only-hard-cut-design.md`、必要時新增 `apps/api/tests/test_current_only_boundaries.py`。

**Verification:** route set 只含 `/api/v1/job-analysis` 與 healthz；current code 不含 legacy imports；migration contract 明確列出七個 `job_analysis_*` table 與零舊 table。

### Task 2: 切斷 API composition 並移除舊 Python runtime

**Files:** `apps/api/app/api/router.py`、`config.py`、`pyproject.toml`、舊 routes/adapters/models/schemas/services、`app/interview/**`、`app/interview_vnext/**`、`app/job_authoring/**`。

**Verification:** current API focused suite、AST import boundary、`uv run python -c "from app.main import app"`；移除 LangChain/LangGraph、indexer contract 與舊 capture/knowledge 依賴。

### Task 3: 只保留 current Web 與 contract

**Files:** `/workspace` 及其 current components/helpers 保留；刪除 `/dashboard`、`/documents/**`、`components/interview/**`、舊 hooks/client/types/store、`@caliburn/ocs-contract` dependency；移除 `packages/ocs-contract`。

**Verification:** Web Vitest、`npx tsc --noEmit`、lint、current import scan；首頁仍導向 `/workspace`，current workspace 可建／開啟 document。

### Task 4: 建立 current-only migration 與 Postgres 啟動面

**Files:** 刪除 Alembic 0001–0011；把 0012 `down_revision` 改為 `None`；改寫 migration test 為 fresh DB current-only；`docker-compose.yml` 只保留 db；更新 API migration／runbook script。

**Verification:** disposable PostgreSQL `alembic upgrade head` 只建立七張 current table；`alembic downgrade base` 可清空；`uv run pytest tests/test_job_analysis_migration.py -q`。

### Task 5: 移除 OCS/indexer/embedder monorepo members 與文件漂移

**Files:** `apps/ocs-indexer`、`apps/pdf-to-json`、`apps/embedder`、`packages/indexer-contract`；root package/lock、Turborepo；`AGENTS.md`、`ARCHITECTURE.md`、`CONTRIBUTING.md`、`docs/README.md`、`docs/runbook.md`、app READMEs、current design index。

**Verification:** `npm install`／workspace graph、`rg` 無現行文件把舊 app 宣稱為 deployable、`docker compose config` 只列 db、current docs links 不指向 deleted runtime。

### Task 6: 完整 gates、審核與交接

**Verification:** `npx turbo test --force --env-mode=loose`、Web typecheck/lint、contract codegen check、API migration focused test、`git diff --check`、clean status；以 reviewer 審查 deletion list、路由與 migration 風險，再建立 task tag。除非 owner 另行要求，不 push。
