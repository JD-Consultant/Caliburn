# Job Analysis Local Web First Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Keep one task per commit and stop at every stated gate.

**Goal:** 把已完成的 `job_analysis` PostgreSQL durable vertical 接成可操作的本機 Web：文件庫、一次開啟一份 JD，以及 Current JD Task 的新增、完整編輯、刪除、排序與 reload。

**Architecture:** 先把 direct edit 與 Proposal decision 收斂到 application-level `commit_authority_change`；再以 `packages/job-analysis-contract` JSON Schema 產生 Python／TypeScript wire types。FastAPI route 只做 transport mapping，Web 以 TanStack Query 呼叫唯一 FastAPI 寫入路徑。文件標題是 metadata，不屬於模型 authority，使用窄 `DocumentRepository.update_title` port，不走 authority seam。

**Tech Stack:** Python 3.12、Pydantic v2、FastAPI 0.115.0、SQLAlchemy 2.0.51 async、PostgreSQL 16、pytest、JSON Schema、Next.js 16.2.6、React 19、TanStack Query v5、TypeScript、Vitest、ESLint。

**Authority:** [ADR 0045](../adr/0045-job-analysis-local-web-contract-and-shared-authority-commit.md)、[研究紀錄](../specs/2026-07-30-job-analysis-local-web-contract-and-authority-commit-seam-research.md)、[Task Analysis Engine](../design/task-analysis-engine.md)。

## Global Constraints

- 本計畫只交付文件庫與 Task 編輯；不做 AI 對話 UI、Proposal review UI、OPKS、export、document delete、search、pagination 或 drag-and-drop。
- 不 import、搬移、轉換、整合或雙寫舊 user／profile／OCS／interview 資料流。
- 不新增 auth、tenant、SaaS、autosave、ETag、revision history、通用 API framework、通用 error middleware 或 E2E framework。
- `app.job_analysis` 不得 import `job_analysis_contract`；transport contract 只在 `app/api` mapper／route 使用，AST guard 強制。
- Task mutation 只有 Client mutation → FastAPI 一條 Web 寫入路徑；不得再加 Server Actions／`useActionState` 寫同一份資料。
- 每個 Task 先寫紅測試，再做最小實作；focused gate 綠後才跑擴大 gate；一個 Task 一個 commit，不 push。
- 動到子系統行為時，同 commit 更新 `docs/design/task-analysis-engine.md` 或 `apps/web/README.md`，不得留過時敘述。

## Baseline

- [x] 在 `apps/api` 執行 `uv run pytest -q`，記錄既有結果；已知無關的 `test_interview_vnext_execution_schemas.py` 若仍失敗，須確認 failure fingerprint 與動工前相同。
- [x] 在 `apps/web` 執行 `npm run test`、`npx tsc --noEmit`、`npm run lint`，三項必須先綠。
- [x] 確認 `git status --short` 只有本計畫檔；若有其他變更，不得混入後續 commit。

---

### Task 1: 收斂 `commit_authority_change`

**Files:**

- Create: `apps/api/app/job_analysis/application/errors.py`
- Create: `apps/api/app/job_analysis/application/authority_commit.py`
- Modify: `apps/api/app/job_analysis/application/authoring.py`
- Modify: `apps/api/app/job_analysis/application/proposal_decisions.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`
- Create: `apps/api/tests/test_job_analysis_authority_commit.py`
- Modify: `apps/api/tests/test_job_analysis_authoring_postgres.py`
- Modify: `apps/api/tests/test_job_analysis_proposal_decisions_postgres.py`
- Modify: `docs/design/task-analysis-engine.md`

**Contract:**

```python
async def commit_authority_change(
    uow: JobAnalysisUnitOfWork,
    *,
    record: DocumentRecord,
    state: JobAnalysisState,
    journal_entry: JournalEntry | None,
    updated_at: datetime,
) -> None: ...
```

它必須先建立／重驗完整 `JobAnalysisState`，通過後才依序 replace Current JD Tasks、replace Proposals、選擇性 append Journal、以 `record.authority_generation` CAS 更新 authority，最後 commit 一次。CAS 失敗丟 `ConcurrentAuthorityChange`；任何驗證或 repository 失敗都不得留下部分寫入。

- [x] **Step 1: 寫紅測試**

  Characterize direct edit 與 Proposal decision 都會呼叫共用 seam；非法完整狀態時 repository 零寫入；CAS false 時不 commit；journal `None` 時不 append。把 application errors 移到 `errors.py`，既有 import 維持可用。

- [x] **Step 2: 跑 focused red gate**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_authority_commit.py tests/test_job_analysis_authoring_postgres.py tests/test_job_analysis_proposal_decisions_postgres.py -q
  ```

- [x] **Step 3: 做 move-first refactor**

  從 `proposal_decisions._persist` 移出共同順序，讓 `_commit_direct_edit` 與 Proposal use cases 只保留各自的入口規則與狀態推導。Durable turn 不接入此 helper。

- [x] **Step 4: 跑 focused 與全 `job_analysis` gate**

  ```powershell
  uv run pytest tests/test_job_analysis_authority_commit.py tests/test_job_analysis_authoring_postgres.py tests/test_job_analysis_proposal_decisions_postgres.py tests/test_job_analysis_durable_turn_postgres.py -q
  $tests = Get-ChildItem -LiteralPath tests -Filter 'test_job_analysis_*.py' | Sort-Object Name | ForEach-Object FullName
  uv run pytest @tests -q
  ```

- [x] **Step 5: Commit**

  ```powershell
  git add apps/api/app/job_analysis apps/api/tests docs/design/task-analysis-engine.md
  git commit -m "refactor(job-analysis): share authority commit seam"
  ```

---

### Task 2: 建立契約 #4 的 JSON Schema SSOT

**Files:**

- Create: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Create: `packages/job-analysis-contract/src/job_analysis_contract/__init__.py`
- Generate: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Generate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Create: `packages/job-analysis-contract/scripts/check-codegen.sh`
- Create: `packages/job-analysis-contract/scripts/strip-index-sig.mjs`
- Create: `packages/job-analysis-contract/package.json`
- Create: `packages/job-analysis-contract/pyproject.toml`
- Create: `packages/job-analysis-contract/tests/test_schema.py`
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/uv.lock`
- Modify: `apps/web/package.json`
- Modify: `package-lock.json`
- Modify: `apps/api/tests/test_job_analysis_dependencies.py`

**Wire definitions:**

- `DocumentMetadataWrite { title }`
- `DocumentMetadataView { document_id, title, updated_at }`
- `DocumentSummary { document_id, title, task_count, updated_at }`
- `DocumentView { document_id, title, updated_at, tasks[] }`
- `EnablerWrite/View { kind, name }`
- `JdTaskWrite { statement, purpose_result?, context?, frequency_text?, responsibility_role?, enablers[] }`
- `JdTaskView` 加 `task_id`、`display_order`
- `TaskOrderWrite { ordered_task_ids[] }`
- `ProblemDetail { type, title, status, detail?, errors? }`

`ProblemDetail.type` 必須是 ADR 0045 六個絕對 URI 的 enum；`errors` 固定為 `[{field, message}]`，Problem object 允許未知 RFC extension。其他 DTO `additionalProperties: false`。Optional text 在 wire 允許 `string | null` 及 `""`，因為 trim／空字串轉 null 是 mapper 責任；不得讓 generated model 在 mapper 前誤殺可正規化的表單值。

- [x] **Step 1: 寫 schema 與紅測試**

  測 `$id`、required/nullable、六種 Problem URI、未知 Problem extension 可被忽略、TS 產生 literal union、generated Python model 可接 optional `""`。

- [x] **Step 2: 建 package 與 codegen**

  只複用 `packages/ocs-contract` 的 codegen 形狀，不 import 其 OCS schema。加入 API path dependency 與 Web workspace dependency。

- [x] **Step 3: 強化 dependency guard**

  `apps/api/tests/test_job_analysis_dependencies.py` 必須拒絕 `app/job_analysis` import `job_analysis_contract`；`app/api` 不在禁單。

- [x] **Step 4: Gate**

  ```powershell
  npm run codegen --workspace=@caliburn/job-analysis-contract
  npm run check-codegen --workspace=@caliburn/job-analysis-contract
  ```

  Working directory `packages/job-analysis-contract`:

  ```powershell
  uv run pytest tests/test_schema.py -q
  ```

  Working directory `apps/api`:

  ```powershell
  uv run pytest tests/test_job_analysis_dependencies.py -q
  ```

  Working directory `apps/web`:

  ```powershell
  npx tsc --noEmit
  ```

- [x] **Step 5: Commit**

  ```powershell
  git add packages/job-analysis-contract apps/api/pyproject.toml apps/api/uv.lock apps/api/tests/test_job_analysis_dependencies.py apps/web/package.json package-lock.json
  git commit -m "feat(contract): add job analysis workspace schema"
  ```

---

### Task 3: 文件 metadata 與讀取 API

**Files:**

- Modify: `apps/api/app/job_analysis/application/persistence.py`
- Modify: `apps/api/app/job_analysis/application/authoring.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/repositories.py`
- Create: `apps/api/app/api/job_analysis_mapper.py`
- Create: `apps/api/app/api/job_analysis_problems.py`
- Create: `apps/api/app/api/routes/job_analysis.py`
- Modify: `apps/api/app/api/router.py`
- Modify: `apps/api/app/api/deps.py`
- Modify: `apps/api/app/app_factory.py`
- Modify: `apps/api/tests/test_job_analysis_authoring_postgres.py`
- Create: `apps/api/tests/test_job_analysis_api.py`
- Modify: `apps/api/tests/test_app_wiring.py`
- Modify: `docs/design/task-analysis-engine.md`

**Application change:**

```python
class DocumentRepository(Protocol):
    async def update_title(
        self,
        document_id: UUID,
        *,
        title: str,
        updated_at: datetime,
    ) -> bool: ...
```

`create_document` 保持單一 create-or-replace metadata use case：不存在時 create；同 ID、同 title 重送成功；同 ID、不同 title 呼叫 `update_title`。後兩者都不 bump `authority_generation`、不寫 Journal、不走 `commit_authority_change`。

**HTTP scope:**

```text
GET /api/v1/job-analysis/documents
PUT /api/v1/job-analysis/documents/{document_id}
GET /api/v1/job-analysis/documents/{document_id}
```

- [x] **Step 1: 寫 application／adapter 紅測試**

  測 rename 只改 title/updated_at；tasks/work model/proposals/generation/journal 逐一不變；不存在的 update 回 false。同 ID、不同 title 不再丟 `IdempotencyConflict`。

- [x] **Step 2: 寫 route 紅測試**

  測 list、201 create、200 rename、open、document 404、輸出不含 generation/work model/journal。先以 dependency override/fake UoW 測 transport，不要求 PostgreSQL。

- [x] **Step 3: 實作窄 port、mapper 與 route**

  Route 使用 generated Pydantic wire models；domain/wire mapping 只在 `app/api`。不要讓 route 直接操作 repositories。

- [x] **Step 4: 加 path-scoped validation handler**

  新 `RequestValidationError` handler 只對 `/api/v1/job-analysis/*` 回 `application/problem+json`；其他 path 委派 FastAPI 既有 handler。加入 legacy 422 body regression，避免誤傷舊 routes。

- [x] **Step 5: Gate**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_authoring_postgres.py tests/test_job_analysis_api.py tests/test_app_wiring.py -q
  $tests = Get-ChildItem -LiteralPath tests -Filter 'test_job_analysis_*.py' | Sort-Object Name | ForEach-Object FullName
  uv run pytest @tests -q
  ```

- [ ] **Step 6: Commit**

  ```powershell
  git add apps/api/app apps/api/tests docs/design/task-analysis-engine.md
  git commit -m "feat(api): expose job analysis documents"
  ```

---

### Task 4: Current JD Task mutation API

**Files:**

- Modify: `apps/api/app/api/job_analysis_mapper.py`
- Modify: `apps/api/app/api/job_analysis_problems.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Modify: `apps/api/tests/test_job_analysis_api.py`
- Create: `apps/api/tests/test_job_analysis_mapper.py`
- Modify: `docs/design/task-analysis-engine.md`

**HTTP scope:**

```text
POST   /api/v1/job-analysis/documents/{document_id}/tasks
PUT    /api/v1/job-analysis/documents/{document_id}/tasks/{task_id}
DELETE /api/v1/job-analysis/documents/{document_id}/tasks/{task_id}
PUT    /api/v1/job-analysis/documents/{document_id}/task-order
```

所有 Task mutation 讀 `Idempotency-Key` 並原樣映射到 `entry_id`，不建 middleware、不 retry。Mapper 對 optional text trim 後空字串轉 null；`statement` trim 後空白回 `invalid-request`。

- [x] **Step 1: 寫 route 紅測試**

  覆蓋 add/edit/delete/reorder；缺 header；document/task 404；同 key 同 payload replay；同 key 不同 payload 409；authority conflict 409；非法順序與空 statement 422；六種 Problem type 與 `Content-Type`；unknown Problem extension 不影響 Web consumer contract。

  DELETE 明定：同 key 重送回原成功結果；不同新 key 刪已不存在 Task 回 `task-not-found` 404。

- [x] **Step 2: 寫 mapper 紅測試**

  覆蓋所有 `JdTaskFields` 公開欄位、空 optional 正規化、enabler kind/name、responsibility role；禁止 mapper 遺漏 domain 欄位。

- [x] **Step 3: 實作最小 route mapping**

  Application errors 只在新 route 映射為六種 Problem type；Web 不得需要解析 `detail`。Mutation 成功回 Task 或排序後 Tasks；DELETE 回 204。

- [x] **Step 4: Gate**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_api.py tests/test_job_analysis_authoring_postgres.py -q
  $tests = Get-ChildItem -LiteralPath tests -Filter 'test_job_analysis_*.py' | Sort-Object Name | ForEach-Object FullName
  uv run pytest @tests tests/test_app_wiring.py -q
  ```

- [ ] **Step 5: Commit**

  ```powershell
  git add apps/api/app/api apps/api/tests docs/design/task-analysis-engine.md
  git commit -m "feat(api): expose current JD task editing"
  ```

---

### Task 5: Web 文件庫

**Prerequisite reading:** 依 `apps/web/AGENTS.md` 讀 repo 內 Next 16 官方文件；至少讀 Server/Client Components、data fetching，以及 `node_modules/next/dist/docs/01-app/03-api-reference/02-components/link.md` 的 `onNavigate` 章節。以實際安裝文件為準，不憑記憶寫 API。

**Files:**

- Create: `apps/web/src/lib/jobAnalysisApi.ts`
- Create: `apps/web/src/lib/jobAnalysisApi.test.ts`
- Create: `apps/web/src/lib/jobAnalysisQueries.ts`
- Create: `apps/web/src/lib/jobAnalysisQueries.test.ts`
- Create: `apps/web/src/components/workspace/DocumentLibrary.tsx`
- Create: `apps/web/src/app/workspace/page.tsx`
- Modify: `apps/web/src/app/page.tsx`
- Modify: `apps/web/README.md`

- [x] **Step 1: 寫純函式紅測試**

  測 URL、query keys、document create/rename payload、六種 Problem `type` exhaustive mapping 與 generic fallback；不解析 `detail`，忽略未知 extension。使用 generated TS types，不手抄 DTO。

- [x] **Step 2: 實作小型 API client**

  新 client 只服務 `/job-analysis`，不 import 舊 user/profile/OCS client。Mutation 每次產生 operation key，重送同一次操作時保持同 key；PUT document 不送 key。

- [x] **Step 3: 實作 `/workspace`**

  Server Component page 只提供 shell；`DocumentLibrary` 是小型 Client Component，列出、建立、改名、開啟文件。建立後導向 `/workspace/{document_id}`；首頁 redirect 改為 `/workspace`。不要持久化 current-document pointer。

- [x] **Step 4: Gate**（working directory: `apps/web`）

  ```powershell
  npm run test
  npx tsc --noEmit
  npm run lint
  ```

- [ ] **Step 5: Commit**

  ```powershell
  git add apps/web
  git commit -m "feat(web): add local JD workspace"
  ```

---

### Task 6: Web Task editor 與明確儲存

**Files:**

- Create: `apps/web/src/lib/jobAnalysisForm.ts`
- Create: `apps/web/src/lib/jobAnalysisForm.test.ts`
- Create: `apps/web/src/components/workspace/TaskForm.tsx`
- Create: `apps/web/src/components/workspace/TaskEditor.tsx`
- Create: `apps/web/src/components/workspace/UnsavedChangesGuard.tsx`
- Create: `apps/web/src/app/workspace/[document_id]/page.tsx`
- Modify: `apps/web/src/lib/jobAnalysisApi.ts`
- Modify: `apps/web/src/lib/jobAnalysisApi.test.ts`
- Modify: `apps/web/src/lib/jobAnalysisQueries.ts`
- Modify: `apps/web/README.md`

- [ ] **Step 1: 寫 form／API 紅測試**

  測 DTO↔form mapping、只有 statement 合法、optional 空值送 null、所有 enabler 與 responsibility role、相同 mutation retry key、成功後要 invalidate 的 document/library query keys、Problem type 顯示文字。

- [ ] **Step 2: 實作共用 `TaskForm`**

  呈現 statement、purpose/result、context、frequency、responsibility role、enablers。所有 input 有 visible label；空值顯示「尚未填寫」，不製造 placeholder 內容。此 form 日後可被 Proposal review 重用，但本 Task 不接 AI。

- [ ] **Step 3: 實作 Task CRUD 與排序**

  每個 Task 使用「編輯 → 儲存／取消」；刪除先確認；排序用可鍵盤操作的上移／下移。Mutation pending 時鎖該操作，成功後 invalidate/refetch，失敗保留草稿並以 `aria-live` 顯示錯誤。

- [ ] **Step 4: 實作 dirty guard**

  使用 Next `<Link onNavigate>`、`beforeunload`、Ctrl/Cmd+Enter 儲存、Esc 取消。不得加入 debounce autosave 或第二份 document store。

- [ ] **Step 5: Gate**（working directory: `apps/web`）

  ```powershell
  npm run test
  npx tsc --noEmit
  npm run lint
  ```

- [ ] **Step 6: Commit**

  ```powershell
  git add apps/web
  git commit -m "feat(web): edit current JD tasks"
  ```

---

### Task 7: 真實 PostgreSQL／HTTP 與 browser smoke

**Files:**

- Create: `apps/api/tests/test_job_analysis_api_postgres.py`
- Modify: `docs/design/task-analysis-engine.md`
- Modify: `docs/README.md`
- Modify: `apps/web/README.md`

- [ ] **Step 1: 寫 real PostgreSQL HTTP vertical**

  使用真實 migration schema 與 TestClient/ASGI client，完成：建立文件 → 新增只有 statement 的 Task → 補 optional 欄位 → 新增第二 Task → 排序 → 關閉 UoW → reload。另測 rename 前後 Tasks、generation、Journal 不變。

- [ ] **Step 2: 跑 API gates**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_api_postgres.py -q
  uv run pytest -q
  ```

  若唯一既有 vNext hash failure 仍存在，須比對 baseline 的 test name 與 failure fingerprint；不得把新 failure 稱為既有問題。

- [ ] **Step 3: 跑 Web gates**（working directory: `apps/web`）

  ```powershell
  npm run test
  npx tsc --noEmit
  npm run lint
  ```

- [ ] **Step 4: 本機 browser smoke（不新增 E2E framework）**

  使用既有 `npm run up`：建立兩份 JD、任一時間只開一份、重新整理後資料仍在、空 optional 欄位可保存、改名不影響 Tasks、CRUD／排序可 reload、dirty draft 離站會警告、鍵盤儲存／取消有效。只記實際結果，不把手動 smoke 宣稱成自動測試。

- [ ] **Step 5: 更新端到端文檔**

  把 `task-analysis-engine.md` 的「無 route／Web」改成實際函式／route／資料流，列出仍未交付的 AI conversation／Proposal UI、ETag、export、OPKS；同步文件索引與 Web run 說明。

- [ ] **Step 6: Final diff checks and commit**

  ```powershell
  git diff --check
  git status --short
  git add apps/api/tests/test_job_analysis_api_postgres.py docs/design/task-analysis-engine.md docs/README.md apps/web/README.md
  git commit -m "test(job-analysis): verify local web vertical"
  ```

## Completion Gate

- 文件庫能建立、改名、列出、重開多份 JD；畫面一次只載入一份。
- 員工可新增只有 statement 的 Task，也可稍後補寫或清空 optional 欄位。
- 員工新增、編輯、刪除、排序均走同一組 application 規則、完整狀態驗證與 PostgreSQL 原子寫入。
- AI 沒有 direct-edit route；AI conversation／Proposal review 尚未接 Web，文件誠實標示。
- Contract codegen、API focused/full tests、Web Vitest/tsc/lint、real PostgreSQL vertical 與 browser smoke 均有實際結果。
- 無舊資料整合、無 autosave、無 ETag、無通用 framework、無額外欄位預建。
