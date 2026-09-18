# Legacy Cleanup 與 Monorepo 邊界實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to execute this plan task-by-task.

**Goal:** 在不改產品行為、不刪資料的前提下，證明本輪可刪範圍、拆開現行 `job_analysis` 與 legacy composition、鎖住 Web/API 邊界，並讓架構文件如實反映 current／legacy／vNext。

**Architecture:** 保留仍有 route、migration、persistence、test 或 codegen 消費者的 legacy／vNext 程式。以 characterization test 和靜態邊界規則先固定現況，再做 move-only dependency seam；若 inventory 找不到 zero-consumer tracked asset，明確記錄「本輪不刪程式碼」，不得為了清理數量硬刪。

**Tech Stack:** Python 3.11、FastAPI、pytest、AST、Next.js、TypeScript、ESLint flat config、Turborepo、npm workspaces、uv、Git。

## Global Constraints

- `app/job_analysis` 與 `/workspace` 是現行第一版；不得導入 `app.interview`、`app.interview_vnext`、`app.job_authoring` 或 `evals`。
- `app/interview` 與舊 OCS Web 仍有 production route／consumer；本輪只標記 legacy，不硬刪、不改 HTTP 行為。
- `app/interview_vnext` 與 `app/job_authoring` 有 schema、persistence、migration、provider 與測試消費者；本輪不接 production route，也不刪。
- 不新增或刪除 migration，不搬資料、不雙寫、不改 schema、不新增 SaaS／登入／多租戶能力。
- 只用 zero-consumer 證據決定刪除；歷史 ADR／migration 留在原位。
- 每個 Task 完成 focused verification 後獨立 commit；不 push。

---

### Task 1: 固定退役 inventory 與 route 安全網

**Files:**

- Create: `docs/specs/2026-08-10-legacy-cleanup-inventory.md`
- Modify: `apps/api/tests/test_app_wiring.py`

**Step 1: 寫 route characterization**

在 `test_app_wiring.py` 新增測試，對 `configure(FastAPI())` 的 path 集合明確斷言：

- legacy live paths `interview:start`、`interview:turn`、`interview:finish`、`GET interview`、`interview:review-events` 仍存在；
- retired paths `interview:curation`、`interview:review`、`task-candidates`、`task-catalogs`、`document:buildTasks` 不存在。

這是對既有行為的 characterization，不製造假的 RED；精確比較 live 與 retired 路徑即可。

**Step 2: 執行 characterization**

Run: `uv run pytest tests/test_app_wiring.py -q`

Expected: PASS；若失敗，以實際 route decorator／mount 為證據判斷文件或程式哪一方過時，不為了綠燈放寬 retired set。

**Step 3: 完成 characterization 與 inventory**

建立 inventory，逐區記錄 `DELETE NOW`、`KEEP LEGACY`、`KEEP VNEXT`、`SEPARATE HARD CUT`，每列附 route/import/migration/test/codegen consumer。必須明寫：盤點沒有發現仍受 Git 追蹤且可安全直接刪除的程式元件；已退役的 CopilotKit、舊 graph、`app.authoring`、`interview.executor/commands/context` 已由既有負向 import test 證明不存在。

**Step 4: 執行 GREEN**

Run: `uv run pytest tests/test_app_wiring.py tests/test_old_chain_removed.py -q`

Expected: PASS，無 warnings。

**Step 5: Commit**

```powershell
git add docs/specs/2026-08-10-legacy-cleanup-inventory.md apps/api/tests/test_app_wiring.py
git commit -m "test: lock legacy route retirement inventory"
```

---

### Task 2: 拆開現行 job-analysis composition dependencies

**Files:**

- Create: `apps/api/app/api/job_analysis_deps.py`
- Modify: `apps/api/app/api/deps.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Modify: `apps/api/tests/test_job_analysis_dependencies.py`
- Modify: `apps/api/tests/test_job_analysis_api.py`
- Modify: `apps/api/tests/test_job_analysis_api_postgres.py`
- Modify: `apps/api/tests/test_job_analysis_header_duty_export_vertical.py`
- Modify: `apps/api/tests/test_job_analysis_opks_reorder_postgres.py`

**Step 1: 寫 composition 邊界測試**

擴充 `test_job_analysis_dependencies.py`：

- `app/api/deps.py` 不得 import `app.job_analysis` 或 `app.adapters.job_analysis_postgres`；
- job-analysis composition surface（`app/api/job_analysis_deps.py`、`app/api/routes/job_analysis.py`、`app/adapters/job_analysis_postgres.py`）不得 import legacy／vNext／`job_authoring`／`evals`。

**Step 2: 執行 RED**

Run: `uv run pytest tests/test_job_analysis_dependencies.py -q`

Expected: FAIL，指出目前 `app/api/deps.py` 仍 import job-analysis application、provider 與 PostgreSQL adapter。

**Step 3: Move-only 拆 dependency seam**

把 `get_job_analysis_uow_factory()`、`get_job_analysis_adapter()` 及其專屬 imports 原樣移到 `app/api/job_analysis_deps.py`；`deps.py` 只留共用 legacy knowledge client。更新 route 與四個測試的 import／dependency override。不得改 dependency function signature、provider config、yield lifecycle 或 route path。

**Step 4: 執行 GREEN**

Run: `uv run pytest tests/test_job_analysis_dependencies.py tests/test_job_analysis_api.py -q`

Run: `uv run pytest tests/test_job_analysis_api_postgres.py tests/test_job_analysis_header_duty_export_vertical.py tests/test_job_analysis_opks_reorder_postgres.py -q`

Expected: 兩組皆 PASS；若 PostgreSQL 不可用，保留第一組結果並明確記錄環境阻擋，不以 skip 冒充驗證。

**Step 5: Commit**

```powershell
git add apps/api/app/api/deps.py apps/api/app/api/job_analysis_deps.py apps/api/app/api/routes/job_analysis.py apps/api/tests/test_job_analysis_dependencies.py apps/api/tests/test_job_analysis_api.py apps/api/tests/test_job_analysis_api_postgres.py apps/api/tests/test_job_analysis_header_duty_export_vertical.py apps/api/tests/test_job_analysis_opks_reorder_postgres.py
git commit -m "refactor: isolate job analysis composition dependencies"
```

---

### Task 3: 鎖住 current／legacy Web import 邊界

**Files:**

- Modify: `apps/web/eslint.config.mjs`

**Step 1: 加入 flat-config restricted imports**

新增兩個有 `files` 範圍的 config block：

- current workspace (`src/app/workspace/**`、`src/components/workspace/**`、`src/lib/jobAnalysis*.ts`) 禁止 import `@/components/interview/**`、`@/hooks/**`、`@/lib/api`、`@/lib/ocsDoc`、`@/lib/pack`、`@/types/**`；
- legacy OCS (`src/app/documents/**`、`src/app/dashboard/**`、`src/components/interview/**`、`src/hooks/**`、`src/lib/api.ts`、`src/types/**`) 禁止 import `@/components/workspace/**`、`@/lib/jobAnalysis*`。

訊息需直接指出 current 與 legacy seam 不可交叉。只加 lint guard，不搬 component、不改 route。

**Step 2: 執行 Web gates**

Run: `npm run lint`

Run: `npx tsc --noEmit`

Run: `npm run test`

Working directory: `apps/web`

Expected: PASS，現有 source 沒有跨界 import。

**Step 3: 驗證規則真的會擋**

暫時在一個 current workspace 檔加入 legacy type-only import，執行該檔 ESLint 並確認 FAIL；立即回復這個 probe，再重跑 `npm run lint` 確認 PASS。probe 不得進 commit。

**Step 4: Commit**

```powershell
git add apps/web/eslint.config.mjs
git commit -m "chore: enforce web current legacy boundaries"
```

---

### Task 4: 校正 monorepo 與模組權威文件

**Files:**

- Modify: `AGENTS.md`
- Modify: `ARCHITECTURE.md`
- Modify: `apps/api/README.md`
- Modify: `apps/web/README.md`
- Modify: `apps/api/app/job_authoring/AGENTS.md`
- Create: `apps/api/app/job_analysis/AGENTS.md`
- Create: `packages/job-analysis-contract/README.md`
- Create: `packages/ocs-contract/README.md`
- Modify: `docs/README.md`
- Modify: `docs/specs/2026-08-10-legacy-cleanup-and-monorepo-boundary-design.md`

**Step 1: 修正 current／legacy／vNext 描述**

- `ARCHITECTURE.md` 分開列出五個 deployable app/service、三個 contract package，以及 API 內部 current／legacy／future module；不再用「三 bounded contexts + one frontend」掩蓋 embedder 與 contract 現況。
- 根 `AGENTS.md` 與 API README 改成：vNext 沒有 production route／產品 authority，但已存在 persistence、migration、provider 與測試；`job_authoring` 是 vNext support，不是現行 canonical truth。
- Web README 先寫 `/workspace` 現行流程，再把 `/documents`、`/dashboard`、interview components 標成 legacy；移除已不存在的 `CellFillerPanel` 施工說明。

**Step 2: 補 colocated boundary instructions**

- `app/job_analysis/AGENTS.md` 記錄允許層次、禁止 imports、composition root、測試與文檔同步規則。
- 兩個 contract README 記錄 schema 是 source of truth、Python／TS 生成物不可手改、consumer 與 `check-codegen` 指令。
- `job_authoring/AGENTS.md` 保留模組內部不變量，但移除「現行 canonical truth」誤導。

**Step 3: 更新中央索引與設計狀態**

在 `docs/README.md` 索引本計畫、inventory 與新增 colocated docs；把設計研究狀態更新為 owner 已核准執行並連回本計畫。不得改 Accepted ADR 原文。

**Step 4: 文件防腐檢查**

Run: `rg -n "no route/DB/live LLM|CellFillerPanel|Canonical truth lives here|3 bounded contexts.*one frontend" AGENTS.md ARCHITECTURE.md apps/api/README.md apps/web/README.md apps/api/app/job_authoring/AGENTS.md`

Expected: 無過時主張；若詞彙在歷史說明中保留，必須同段標明 historical／retired。

Run: `git diff --check`

Expected: PASS。

**Step 5: Commit**

```powershell
git add AGENTS.md ARCHITECTURE.md apps/api/README.md apps/web/README.md apps/api/app/job_authoring/AGENTS.md apps/api/app/job_analysis/AGENTS.md packages/job-analysis-contract/README.md packages/ocs-contract/README.md docs/README.md docs/specs/2026-08-10-legacy-cleanup-and-monorepo-boundary-design.md
git commit -m "docs: clarify monorepo current legacy boundaries"
```

---

### Task 5: 整體驗證與執行紀錄

**Files:**

- Modify: `docs/specs/2026-08-10-legacy-cleanup-inventory.md`

**Step 1: API focused architecture gate**

Run from `apps/api`:

```powershell
uv run pytest tests/test_app_wiring.py tests/test_old_chain_removed.py tests/test_job_analysis_dependencies.py tests/test_interview_vnext_dependencies.py tests/test_job_authoring_dependencies.py tests/test_job_analysis_api.py -q
```

Expected: PASS，無 warnings。

**Step 2: Web gates**

Run from `apps/web`:

```powershell
npm run test
npx tsc --noEmit
npm run lint
```

Expected: 全部 PASS。

**Step 3: Contract 與 repository gates**

Run from repo root:

```powershell
npm run check-codegen -w @caliburn/job-analysis-contract
git diff --check
git status --short
```

Expected: codegen 無 drift、diff check PASS；status 只剩本步 inventory 執行紀錄。

**Step 4: 寫執行結果**

在 inventory 追加日期、commit、各 gate 精確結果與限制；明確記錄本輪實際刪除數為 0，原因是沒有 zero-consumer tracked asset，而不是清理未完成。另列 hard-cut 前置條件：移除 legacy route/UI 入口、資料策略、rollback、HTTP/browser smoke、owner sign-off。

**Step 5: Commit**

```powershell
git add docs/specs/2026-08-10-legacy-cleanup-inventory.md
git commit -m "docs: record legacy cleanup verification"
```
