# B2 工作理解 staged maintainer 施工計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 B2 的 durable staged state、窄語意工具與多對多影響核對，讓完成的 B1 候選案例可被整理成可修訂的穩定工作理解候選，但本片不發布 Memory。

**Architecture:** `UnderstandingMaintenanceSession` 固定一份已完成的 `CaseMaintenanceStage` 與其精確 base bundle，Runtime 從 base manifest 推導受 B1 變更直接影響的既有理解，並擁有 ID、guide route、support bindings 與驗證。模型只能讀取 Runtime 提供的目前／被取代案例與目前理解，再提出 create／revise／revalidate／split／merge／retire／route／finish 等語意操作；所有結果只存在 checkpoint-safe B2 stage。

**Tech Stack:** Python 3.12、LangChain 1.4.0 tools、LangGraph 1.2.11 state／ToolNode、既有 `MemoryArtifacts`／`CaseMaintenanceSession`／V4A text patch。

**Spec:** `docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md`

## Global Constraints

- canonical 訪談、B1 current cases、工作理解及其引用各司其職；B2 不把案例重新壓成單一摘要。
- B2 以完成的 B1 stage 與精確 base bundle 為固定輸入；本片沒有 publication、CAS、dispatcher、C、compaction、App 組裝或 provider 呼叫。
- `understanding_id`、路徑、digest、document scope、base version、case digest 與 operation identity 都由 Runtime 管理。
- 工作理解正文使用 Markdown；supporting cases 是多對多 Runtime binding，不要求模型填版本或 digest。
- 語意 no-op 仍須讀取所有 B1 改變後的 current cases、重驗直接受影響的既有理解，並明確提交其目前支持案例；不能只機械換 case digest。
- 新案例即使沒有既有反向 binding，B2 仍必須讀取並判斷是否揭露新工作理解；Runtime 只驗證此讀取發生，不用關鍵詞替模型下語意結論。
- 已發布理解在修訂、重驗、拆分、合併或退休前必須先讀；所有作為新 support 的 current case 也必須先讀。
- 同一模型訊息只允許一個 B2 工具呼叫，避免 checkpoint state 競爭更新。

---

### Task 1: 固定 B1 candidate 與 B2 影響範圍

**Files:**
- Create: `packages/consultant-memory/src/caliburn_memory/understanding_maintenance.py`
- Create: `packages/consultant-memory/tests/test_understanding_maintenance.py`

**Interfaces:**
- Consumes: `CaseMaintenanceStage`、`CaseMaintenanceSession.current_cases()`、`MemoryArtifacts.bundle_manifest()`／`case()`／`understanding()`。
- Produces: `UnderstandingMaintenanceStage`、`UnderstandingChange`、`UnderstandingSupportSelection`、`UnderstandingMaintenanceError`、`UnderstandingMaintenanceSession.open()`／`load()`。

- [x] **Step 1: Write failing tests for opening and impact discovery**

  測試建立含 CASE-A／CASE-B 與 UNDERSTANDING-X 的 base bundle，讓完成的 B1 stage 修訂 CASE-A 並新增 CASE-C；斷言 B2 open 只讀 manifest／guides，不預載全文，且能推導：CASE-A／CASE-C 都是本批需檢視的 current cases，UNDERSTANDING-X 是直接受影響理解。另測跨文件 base、未完成 B1 stage 與竄改的 serialized B2 stage 被拒絕。

- [x] **Step 2: Run the tests and verify RED**

  Run: `uv run pytest -q ../../packages/consultant-memory/tests/test_understanding_maintenance.py -p no:cacheprovider`

  Expected: collection/import failure because the B2 types do not exist.

- [x] **Step 3: Implement the minimal immutable stage and validation**

  `UnderstandingMaintenanceStage` 保存 `format_version`、document/base、完整 B1 stage snapshot、base understanding IDs／guide digest、目前 guide、已讀 case／understanding IDs、binding updates、upserts、supersessions、changes 與 completion。`open()` 驗證 B1 已完成且 scope/base 完全相同；direct impact 由 base `understanding_case_bindings` 與 B1 change previous/current case IDs 推導，不把它交給模型填寫。

- [x] **Step 4: Run the focused tests and verify GREEN**

  Run: `uv run pytest -q ../../packages/consultant-memory/tests/test_understanding_maintenance.py -p no:cacheprovider`

  Expected: opening／impact tests pass.

### Task 2: 讀取、建立、修訂與 semantic no-op 重驗

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/understanding_maintenance.py`
- Modify: `packages/consultant-memory/tests/test_understanding_maintenance.py`

**Interfaces:**
- Produces: `observe_case()`、`observe_understanding()`、`create_understanding()`、`revise_understanding()`、`revalidate_understanding()`、`current_understandings()`。

- [x] **Step 1: Write failing tests for read-before-write and binding revalidation**

  覆蓋：新理解只能綁已讀 current cases；修訂既有理解前必須先讀；support case 未讀／已被取代時拒絕；B1 修訂 CASE-A 但理解正文不變時，`revalidate_understanding(X, [A, B])` 保存明確支持集合，`finish(no_op)` 成功，且沒有建立新 understanding prose artifact。

- [x] **Step 2: Verify RED**

  Run focused test names and confirm each fails because the operation is absent.

- [x] **Step 3: Implement minimal operations**

  Runtime 產生新 UUID、正規化 Markdown、解析 current case IDs；`revise_understanding()` 使用既有 V4A matcher 並保留未修改內容。`revalidate_understanding()` 只記錄實際讀過的 current support IDs，不改正文、不把 binding-only refresh 算成 semantic change。

- [x] **Step 4: Verify GREEN**

  Run the focused tests and the full new test file.

### Task 3: 理解身分生命週期與完成界線

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/understanding_maintenance.py`
- Modify: `packages/consultant-memory/tests/test_understanding_maintenance.py`

**Interfaces:**
- Produces: `UnderstandingReplacementInput`、`split_understanding()`、`merge_understandings()`、`retire_understanding()`、`set_understanding_route()`、`finish()`。

- [x] **Step 1: Write failing tests for split／merge／retire／route**

  驗證穩定 ID、guide 唯一路由、supersession 指向 current IDs、不能 supersede 同 attempt 新建理解，以及 supporting cases 全部屬於同一 candidate case set。

- [x] **Step 2: Write failing completion tests**

  `finish()` 必須拒絕：尚未讀 B1 改變後的 current case、尚未處理直接受影響理解、guide 缺 route、語意 change 與 outcome 不符。被 revise／revalidate／split／merge／retire 的直接影響理解都算已處理；新案例讀過後允許模型判定沒有新穩定理解。

- [x] **Step 3: Implement minimal lifecycle and completion validation**

  對 published IDs 採 read-before-write；guide 每個 current understanding 恰有一條 Runtime route。`finish(changed|no_op)` 的 outcome 只反映工作理解正文／身分／guide 是否語意變更，binding refresh 本身不將 no-op 升成 changed。

- [x] **Step 4: Verify GREEN**

  Run the new test file and confirm every lifecycle/completion case passes.

### Task 4: LangChain 窄工具與 checkpoint-safe 更新

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/understanding_maintenance.py`
- Modify: `packages/consultant-memory/tests/test_understanding_maintenance.py`
- Modify: `packages/consultant-memory/src/caliburn_memory/__init__.py`

**Interfaces:**
- Produces: `UnderstandingMaintenanceAgentState`、`understanding_maintenance_tools(session)`。

- [x] **Step 1: Write failing tool-schema and ToolNode tests**

  工具 schema 不暴露 runtime、document、base、version、path、digest、operation 或 B2 stage；ToolNode 成功操作會 checkpoint 新 stage；可修正錯誤回傳 unchanged；同訊息多個 B2 calls 全部拒絕且不產生 state race。

- [x] **Step 2: Verify RED**

  Run focused tool tests and confirm missing API failures.

- [x] **Step 3: Implement the tool wrappers**

  建立 read-case/read-understanding/create/revise/revalidate/split/merge/retire/set-route/finish 十個工具。所有成功回應只提供模型後續決策需要的穩定 ID、內容、support IDs、effect；Runtime 欄位從 `ToolRuntime.state` 注入，不進模型 schema。

- [x] **Step 4: Verify GREEN**

  Run the complete new test file.

### Task 5: 文件、全套回歸與本地交付

**Files:**
- Modify: `packages/consultant-memory/README.md`
- Modify: `docs/current-decisions.md`
- Modify: `docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md`
- Modify: `docs/plans/2026-09-16-b2-understanding-maintainer.md`

- [x] **Step 1: Update status without overstating completion**

  記錄 B2 staged contract／tools／impact analysis 已完成；明確保留未完成的 B2 Agent graph、B1→B2 publication、stale 重跑、dispatcher、compaction、C、App 與自然模型驗收。

- [x] **Step 2: Run affected verification**

  Run package tests, adjacent old B1/B2 App tests required by the existing B1 plan, compileall, `git diff --check`, and inspect author/committer identity before commit.

  2026-09-16 實際結果：B2 新檔 **17 passed**；`consultant-memory` 全套 **205 passed**；相鄰既有 extraction／consolidation App **33 passed**；compileall 與 `git diff --check` 通過。全程 0 provider、0 正式 publication。

- [x] **Step 3: Commit one precise work unit**

  Commit message: `feat(memory): add staged B2 understanding maintainer`

  Do not push. Create a local completion tag only after fresh verification.
