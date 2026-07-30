# Professional Consultant Minimal Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Keep one task per commit and stop at every stated gate.

**Goal:** 把已完成的 Task Analysis durable vertical 接成最小可用的專業顧問迴圈：固定開場、員工回答、一次模型分析與下一題、Proposal 決策、Current JD 編輯，以及關閉後完整恢復。

**Architecture:** 延續 ADR 0046 的 A6：強模型、light schema、one-stage。PostgreSQL Current State／Journal 是產品真相；完整對話由既有 Journal 展開，不新增 message table。FastAPI route 只做 transport mapping；application 在 provider 前先檢查已提交 replay，provider 呼叫在 transaction 外，verified result 才原子提交。Web 使用 TanStack Query，不建立第二份 client state。

**Tech Stack:** Python 3.12、Pydantic v2、FastAPI、SQLAlchemy async、PostgreSQL 16、httpx、pytest、JSON Schema、Next.js 16、React 19、TanStack Query v5、TypeScript、Vitest、ESLint。

**Authority:** [ADR 0046](../adr/0046-professional-consultant-minimal-durable-loop.md)、[研究紀錄](../specs/2026-07-30-professional-consultant-minimal-complete-loop-research.md)、[Task Analysis Engine](../design/task-analysis-engine.md)。

## Global Constraints

- 只做 Task 訪談最小迴圈；不做 Role／Coverage／Story 持久狀態、OPKS、完成 gate、export、compaction、retrieval、Graph、specialist、SSE、背景工作或通用 agent framework。
- 不搬、不整合、不雙寫舊 `app.interview`／`interview_vnext`／`job_authoring`／`evals`；既有 AST guard 必須持續通過。
- 新文件同交易寫固定開場；GET 永遠 read-only；rename 不碰 Journal、active question 或 authority generation。
- 每個 POST 都用 `Idempotency-Key`。只保證已提交請求的循序重送；不宣稱 in-flight exactly-once，不新增 operation ledger。
- Proposal 第一切片只暴露 accept／文字 edit／reject／defer；不暴露尚未接 replacement path 的 `revision_requested`。
- Web 寫入只有 client mutation → FastAPI；不加 Server Actions、autosave、第二份 store、tab/drawer 或新 E2E framework。
- 每個 Task 先寫紅測試，再做最小實作；focused gate 綠後才跑擴大 gate；一個 Task 一個 commit，不 push。

## Baseline

- [ ] Repo 根確認 branch／status；工作樹只允許本 plan。
- [ ] `apps/api`: `uv run pytest -q`。記錄既有 Windows CRLF schema-hash failure fingerprint；不得新增其他 failure。
- [ ] `apps/web`: `npm run test`、`npx tsc --noEmit`、`npm run lint` 全綠。
- [ ] `packages/job-analysis-contract`: `npm run check-codegen` 與 `uv run pytest -q` 全綠。

---

### Task 1: Durable conversation 與 provider 前 replay

**Files:**

- Modify: `apps/api/app/job_analysis/application/persistence.py`
- Modify: `apps/api/app/job_analysis/application/authoring.py`
- Modify: `apps/api/app/job_analysis/application/durable_turn.py`
- Create: `apps/api/app/job_analysis/application/consultation.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/serialization.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/repositories.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/models.py`
- Create: `apps/api/alembic/versions/0013_job_analysis_consultant_opening.py`
- Modify: `apps/api/tests/test_job_analysis_persistence_contracts.py`
- Modify: `apps/api/tests/test_job_analysis_migration.py`
- Modify: `apps/api/tests/test_job_analysis_authoring_postgres.py`
- Modify: `apps/api/tests/test_job_analysis_postgres.py`
- Modify: `apps/api/tests/test_job_analysis_durable_turn_postgres.py`
- Create: `apps/api/tests/test_job_analysis_consultation.py`
- Modify: `docs/design/task-analysis-engine.md`

**Contract:**

```python
CONSULTANT_OPENING_SCHEMA_ID = "job-analysis-consultant-opening/1"

class ConsultantOpeningPayload(DomainModel):
    consultant_turn: ConversationTurn

async def submit_employee_turn(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    adapter: OpenRouterAdapter,
    document_id: UUID,
    operation_id: str,
    text: str,
) -> None: ...
```

Repository 提供按 Journal sequence 展開的 `conversation_turns`：opening 展開一個 consultant turn；completed turn 展開 employee＋consultant。不要新增 chat table。

- [ ] **Step 1: 寫紅測試**

  測新文件同交易只寫一次 opening 並設 active question；metadata PUT replay／rename 不重複 opening；PostgreSQL 可按 sequence 還原 conversation。測 opening 不可成為 employee `SourceRef`。

- [ ] **Step 2: 寫 replay 紅測試**

  已提交的相同 key＋相同 employee text 直接成功且 adapter 呼叫數為 0；相同 key＋不同 text 回 `IdempotencyConflict`；尚未提交才允許一次 provider call。provider／parse／verifier／stale 失敗皆不增加 Journal 或 generation。

- [ ] **Step 3: 最小實作**

  將 turn ID 由 operation ID 決定性產生。`submit_employee_turn()` 先在短 transaction 查 Journal replay，再沿用 `prepare_turn()` → `run_task_analysis_operation()` → `commit_verified_turn()`；不把 provider call 包進 DB transaction，不增加 retry。

- [ ] **Step 4: Gate**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_persistence_contracts.py tests/test_job_analysis_authoring_postgres.py tests/test_job_analysis_postgres.py tests/test_job_analysis_durable_turn_postgres.py tests/test_job_analysis_consultation.py -q
  $tests = Get-ChildItem -LiteralPath tests -Filter 'test_job_analysis_*.py' | Sort-Object Name | ForEach-Object FullName
  uv run pytest @tests -q
  ```

- [ ] **Step 5: Commit**

  ```powershell
  git add apps/api/alembic/versions/0013_job_analysis_consultant_opening.py apps/api/app/job_analysis apps/api/app/adapters/job_analysis_postgres apps/api/tests docs/design/task-analysis-engine.md docs/plans/2026-07-30-professional-consultant-minimal-loop-plan.md
  git commit -m "feat(job-analysis): persist consultant conversation loop"
  ```

---

### Task 2: 顧問 prompt 與 scripted quality smoke

**Files:**

- Modify: `apps/api/app/job_analysis/llm/prompt.py`
- Modify: `apps/api/tests/test_job_analysis_operation.py`
- Modify: `apps/api/tests/test_job_analysis_smoke.py`
- Modify: `docs/design/task-analysis-engine.md`

**Prompt additions:**

- 先由完整回答辨識 0..N 個 work signals，不把 Java／Python／HTML 等 enabler 自立為 Task。
- 由職位目的／服務對象向工作週期展開；故事可深挖，但故事結束後回到未覆蓋的例行／週期／例外責任。
- `next_question` 優先順序：會改變 Task 邊界的矛盾／責任問題 → open issue → 遺漏掃描；一輪只問一題。
- pending/deferred Proposal 是待決假說，不妨礙繼續訪談，也不得當現況事實。
- 沒有完成 gate；不得宣稱訪談或 JD 已完成。

- [ ] **Step 1: 寫紅測試**

  以 scripted provider fixture 覆蓋：一段話多工作、工具不成 Task、含工具工作成立、責任不明追問、故事後回到工作週期、待決 Proposal 存在仍能產生下一題。測 output schema 不新增欄位、operation 仍只有一次 provider call。

- [ ] **Step 2: 最小 prompt 修訂**

  只補決策順序與顧問行為，不加入問卷、分類器、planner、第二次呼叫或硬編 action enum。

- [ ] **Step 3: Gate**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_operation.py tests/test_job_analysis_smoke.py -q
  ```

- [ ] **Step 4: Commit**

  ```powershell
  git add apps/api/app/job_analysis/llm/prompt.py apps/api/tests/test_job_analysis_operation.py apps/api/tests/test_job_analysis_smoke.py docs/design/task-analysis-engine.md
  git commit -m "feat(job-analysis): guide the flexible consultant loop"
  ```

---

### Task 3: Consultation wire contract SSOT

**Files:**

- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Generate: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Modify: `packages/job-analysis-contract/src/job_analysis_contract/__init__.py`
- Generate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Modify: `packages/job-analysis-contract/tests/test_schema.py`

**Wire definitions:**

- `ConversationTurnView { turn_id, speaker, text }`
- `ActiveQuestionView { turn_id, text }`
- `ProposalJdEntryView { task_id, value: JdTaskView | null }`
- `ProposalView { proposal_id, action, status, jd_before, jd_after, edited_jd_after?, rejection_reason?, stale_reason?, evidence_quotes[] }`
- `ConsultationView { document metadata, conversation[], active_question?, proposals[], tasks[] }`
- `EmployeeTurnWrite { text }`
- `ProposalDecisionWrite { decision: accepted|edited|rejected|deferred, edited_jd_after?, reason? }`
- Problem type 增加 `proposal-not-found`、`consultant-unavailable`

所有 DTO 除 RFC 9457 Problem extensions 外皆 `additionalProperties: false`。Wire 不暴露 Work Model、Journal payload、authority generation、internal ordinal mapping 或 provider detail。

- [ ] **Step 1: 寫 schema 紅測試**

  測 decision enum 排除 `revision_requested`；Proposal 可表達 null before/after、edited history、stale reason 與 evidence quotes；兩種 Problem URI 進 TS literal union。

- [ ] **Step 2: 更新 schema 並 codegen**

  ```powershell
  npm run codegen
  npm run check-codegen
  ```

- [ ] **Step 3: Gate**（working directory: `packages/job-analysis-contract`）

  ```powershell
  uv run pytest -q
  npm run check-codegen
  ```

- [ ] **Step 4: Commit**

  ```powershell
  git add packages/job-analysis-contract
  git commit -m "feat(contract): add consultant loop DTOs"
  ```

---

### Task 4: FastAPI Consultation vertical 與 production composition

**Files:**

- Modify: `apps/api/app/config.py`
- Modify: `apps/api/app/job_analysis/application/transition.py`
- Modify: `apps/api/app/api/deps.py`
- Modify: `apps/api/app/api/job_analysis_mapper.py`
- Modify: `apps/api/app/api/job_analysis_problems.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Modify: `apps/api/tests/test_job_analysis_mapper.py`
- Modify: `apps/api/tests/test_job_analysis_transition.py`
- Modify: `apps/api/tests/test_job_analysis_api.py`
- Modify: `apps/api/tests/test_job_analysis_api_postgres.py`
- Modify: `apps/api/tests/test_app_wiring.py`
- Modify: `apps/api/.env.example`
- Modify: `docs/design/task-analysis-engine.md`

**Composition:**

新增 job-analysis 專用的 exact model/provider/output-token/timeout settings，預設 A6 的 `anthropic/claude-opus-5`＋Anthropic endpoint；secret 沿用 `openrouter_api_key`。`get_job_analysis_adapter` 只組現有薄 adapter 與無 retry 的 `httpx` transport，不建立 provider registry、catalog runtime、fallback 或共用 AI framework。

**Routes:**

```text
GET  /api/v1/job-analysis/documents/{document_id}/consultation
POST /api/v1/job-analysis/documents/{document_id}/turns
POST /api/v1/job-analysis/documents/{document_id}/proposals/{proposal_id}/decisions
```

- [ ] **Step 1: mapper／problem 紅測試**

  測全部 Proposal（含 terminal/stale）可投影，evidence quote 只取有效員工來源且去重；兩個新 Problem type 穩定；provider 細節不進 response。

- [ ] **Step 2: route 紅測試**

  以 dependency override 的 fake adapter 測 GET read-only、成功 turn、replay 零 provider call、不同 payload conflict、unavailable、Proposal 404、accept/edit/reject/defer，以及每種決策後 active question 保留。

- [ ] **Step 3: 實作 routes 與 composition**

  Route 只正規化 text／decision payload、呼叫 application use case、再回重新載入的 Consultation View。`consultant-unavailable` 對外不洩漏 provider／parse／verifier detail；server log 保留分類。

- [ ] **Step 4: PostgreSQL route smoke**

  使用真 repository／transaction、fake provider transport，驗證 create → opening → turn → proposal decision → reload；不得打外網。

- [ ] **Step 5: Gate**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_mapper.py tests/test_job_analysis_api.py tests/test_job_analysis_api_postgres.py tests/test_app_wiring.py -q
  $tests = Get-ChildItem -LiteralPath tests -Filter 'test_job_analysis_*.py' | Sort-Object Name | ForEach-Object FullName
  uv run pytest @tests -q
  ```

- [ ] **Step 6: Commit**

  ```powershell
  git add apps/api/app apps/api/tests apps/api/.env.example docs/design/task-analysis-engine.md
  git commit -m "feat(api): expose the consultant loop"
  ```

---

### Task 5: Local Web 雙欄顧問工作區

**Files:**

- Modify: `apps/web/src/lib/jobAnalysisApi.ts`
- Modify: `apps/web/src/lib/jobAnalysisApi.test.ts`
- Modify: `apps/web/src/lib/jobAnalysisQueries.ts`
- Modify: `apps/web/src/lib/jobAnalysisQueries.test.ts`
- Create: `apps/web/src/lib/jobAnalysisProposals.ts`
- Create: `apps/web/src/lib/jobAnalysisProposals.test.ts`
- Create: `apps/web/src/components/workspace/ConsultationWorkspace.tsx`
- Create: `apps/web/src/components/workspace/ConsultationPanel.tsx`
- Create: `apps/web/src/components/workspace/ProposalCard.tsx`
- Modify: `apps/web/src/components/workspace/TaskEditor.tsx`
- Modify: `apps/web/src/components/workspace/UnsavedChangesGuard.tsx`
- Modify: `apps/web/src/app/workspace/[document_id]/page.tsx`
- Modify: `apps/web/README.md`

**UI:**

- 寬畫面左 conversation/composer、右 Proposal cards＋Current JD editor；窄畫面上下排列。
- conversation 使用 `role="log"`；送出狀態 `role="status"`；錯誤 `role="alert"`。
- Enter 換行、Ctrl/Cmd+Enter 送出；pending 停用重複送出。
- 失敗保留 draft 與同一 idempotency key；內容改變才換 key。
- 待決／deferred Proposal 顯示 action、before/after、員工原話與 accept/edit/reject/defer；terminal/stale 歷史預設摺疊，stale reason 可見。
- edit 只送完整 `edited_jd_after` 文字 map，不改 topology。
- Current JD 仍用既有同一套 FastAPI direct-edit seam；AI Proposal 與人類編輯不另建第二條資料庫寫入路徑。

- [x] **Step 1: client／pure helper 紅測試**

  測新 API path/header/body、兩種新 Problem 文案、Proposal 分組、editable entry map、retry key 保留規則與 query invalidation。

- [x] **Step 2: 最小元件實作**

  將 `TaskEditor` 變成可嵌入右欄的 Task 面板，header/back/整頁 dirty guard 提升到 `ConsultationWorkspace`；不引入新 state library。可見文字與 Proposal 決策都留在同頁。

- [x] **Step 3: Gate**（working directory: `apps/web`）

  ```powershell
  npm run test
  npx tsc --noEmit
  npm run lint
  npm run build
  ```

- [x] **Step 4: Commit**

  ```powershell
  git add apps/web
  git commit -m "feat(web): add the consultant workspace"
  ```

---

### Task 6: Closure verification 與文檔同步

**Files:**

- Modify: `docs/design/task-analysis-engine.md`
- Modify: `docs/README.md` only if a new durable design entry is required
- Modify: `AGENTS.md` only if orientation is stale

- [x] **Step 1: 全 repo verification**

  ```powershell
  npx turbo test
  ```

  再分別跑 API full pytest、Web test/tsc/lint/build、contract codegen check。既有 CRLF hash failure 只可在 fingerprint 與 baseline 完全相同時列為既有失敗。

- [x] **Step 2: No-network vertical review**

  用真 PostgreSQL adapter＋fake provider 完成：create → opening → employee turn → Task/issue/Proposal → accept/edit/reject/defer → direct edit → reload。確認同 key replay 零 provider call、GET 零寫入、Current JD 與 conversation 一致。

- [x] **Step 3: Browser smoke**

  在本機 Web 實際檢查：opening 可見、換行與快捷鍵、pending 禁止重送、Proposal 與 JD 同頁、Task 可編輯、reload 後狀態恢復、窄畫面堆疊。若沒有 live provider，不為 smoke 加 fake production mode；成功 turn 由 API fake-provider vertical 證明，browser 只驗產品 UI 行為。

- [x] **Step 4: Strongest-case closure**

  逐條重查 ADR 0046 的 W1–W6。任何實作若需要 Role/Coverage state、第二模型呼叫、compaction、background workflow 或新持久表才可工作，停止並回 ADR，不在收尾臨場補框架。

- [x] **Step 5: 文檔與 commit**

  `docs/design/task-analysis-engine.md` 必須用真實 route、函式與資料流描述完整閉環，並明列仍沒有 completion gate、OPKS、export、long-context compaction 與 in-flight deduplication。

  ```powershell
  git add docs/design/task-analysis-engine.md docs/README.md AGENTS.md
  git commit -m "docs(job-analysis): close the consultant loop vertical"
  ```

  Closure evidence（2026-07-30）：Web `90 passed`，TypeScript／ESLint／Next production build 通過；
  contract `8 passed` 且 codegen 無漂移；API＋真 PostgreSQL `1689 passed`，唯一失敗仍是動工前已存在的
  vNext 歷史 prompt Windows raw-bytes hash。Codex in-app browser 可載入 Next shell，但其 client policy
  封鎖跨埠 `localhost:8001`，故未冒充完整 browser round-trip；沒有為此加入 proxy 或 fake production mode。

- [x] **Step 6: Tag**

  全部必要 gate 綠且工作樹乾淨後，依 repo 規則建立 annotated tag；tag 名於收尾時依既有 tag 命名檢查後決定，不預先猜測。
