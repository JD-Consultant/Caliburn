# B2 工作理解 Agent graph 施工計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將既有 B2 staged maintainer 接成可 checkpoint／resume 的離線 Agent workflow，並在沿案例引用核對原話後發現 B1 有實質錯誤時，以結構化、不可發布的結果要求上層 Runtime 重做 B1。

**Architecture:** `UnderstandingMaintenanceSession` 繼續擁有 B2 stage 與語意不變量；新增的 `UnderstandingMaintenanceWorkflow` 只負責模型迴圈、受控來源讀取、完成修正及 durable attempt。B2 可以沿已讀案例所列的 canonical reference 分頁讀取原話；若原話證明案例有會影響工作理解的錯誤或缺漏，B2 以 `case_rework_required` 結束，保留診斷但不產生可發布候選。真正的 B1→B2 有界重跑由下一片完整背景 job 消費，不在本片實作。

**Tech Stack:** Python 3.12、LangChain 1.4.0 `create_agent`／middleware、LangGraph 1.2.11 state／checkpointer、既有 `ExtractionSourceReader`／`UnderstandingMaintenanceSession`。

**Spec:** `docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md`

**2026-09-17 successor：**本計畫原先讓模型提交 `case_id／source_reference／offset` 的來源工具接口，已由[訪談證據引用與 Runtime 權責施工計畫](2026-09-17-interview-evidence-citations.md)取代。現行接口是 `read_case` 配發 case-bound、attempt-scoped `evidence_key`，`read_case_source(evidence_key)` 由 Runtime 從 checkpoint 解析正式 `(case_id, source_reference)` 與 paging cursor；`request_case_rework` 只收已讀 key＋reason。以下已完成步驟仍是 durable graph 的歷史施工證據，但舊參數形狀不是現行契約。

## Global Constraints

**2026-09-20 執行步數補驗：**既有每模型三步估算不足，B2 正式128／120配置在390步先中止；只將 framework headroom 改為每模型六步＋16入口／收尾保留（正式784），thread模型／工具額度、生命週期與產品語意不變。120工具可完成且第121工具仍拒絕，見[精確證據](../specs/evidence/2026-09-20-agent-recursion-headroom-review.md)。

- B2 管理工作理解，不直接建立、修訂、拆分、合併或淘汰 B1 案例。
- B2 只能沿已成功 `read_case` 回傳的該案例 canonical evidence key 讀原話；不能自行提交 reference／offset，也不能任意掃描對話、latest 或另一文件。
- `case_rework_required` 是 attempt terminal control result，不是新 Memory、案例證據或 publication outcome；下一個 B1 必須重新讀 canonical source 並自行判斷。
- 原話只由 source owner 讀取並完整保存；B2 request compaction 不得摘要、替換或冒充原話。
- 同一 B2 attempt 固定 completed B1 stage 與 exact base；resume 不配置新模型／工具／修正額度。
- 本片不做 B1→B2 自動重跑、candidate bundle publication、CAS、dispatcher、C、compaction、App model factory、provider 呼叫或自然模型驗收。

---

### Task 1: B2 來源核對與不可發布 rework 結果

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/understanding_maintenance.py`
- Modify: `packages/consultant-memory/tests/test_understanding_maintenance.py`
- Modify: `packages/consultant-memory/src/caliburn_memory/__init__.py`

**Interfaces:**
- Produces: `CaseReworkIssue`、`CaseReworkIssueInput`、`CaseSourceRead`、`UnderstandingMaintenanceStage.read_source_references`（case／source 配對證據）、`UnderstandingMaintenanceStage.case_rework_issues`。
- 最終接口：`register_case_evidence／advance_case_evidence` 由 Runtime 維護 case-bound key 與 cursor；`request_case_rework(stage, issues)` 的模型輸入只含已讀 key＋reason，正式 case／reference 由 Runtime 解析。
- Changes: `UnderstandingMaintenanceStage.outcome` becomes `Literal["changed", "no_op", "case_rework_required"] | None`；`current_understandings()` only accepts publishable `changed`／`no_op` stages。

- [x] **Step 1: Write failing stage tests**

  Add tests proving that an unread case cannot authorize raw-source access; an unlisted or cross-case reference is rejected; a listed reference becomes durable read evidence; and serialized stage tampering with read references or rework issues is rejected.

- [x] **Step 2: Run focused RED tests**

  Run:
  `uv run pytest -q ../../packages/consultant-memory/tests/test_understanding_maintenance.py -p no:cacheprovider -k "source_reference or case_rework"`

  Expected: collection or attribute failures because the new API and fields do not exist.

- [x] **Step 3: Implement minimal stage semantics**

  最終 successor 實作由 `read_case` 登記 case-bound evidence keys，Runtime 以 `advance_case_evidence()` 推進 key 對應的 exact-source cursor；`request_case_rework()` 要求一至八筆已讀 `evidence_key＋reason`，再由 Runtime 解析成 distinct `(case_id, source_reference)` issues。它以 `outcome="case_rework_required"` 結束 attempt，不改 B1，也不宣稱 B2 已完成到可發布狀態。

- [x] **Step 4: Run focused GREEN tests**

  Run the same command and require all selected tests to pass.

### Task 2: 受控來源工具與 durable B2 Agent graph

**Files:**
- Create: `packages/consultant-memory/src/caliburn_memory/understanding_workflow.py`
- Create: `packages/consultant-memory/tests/test_understanding_workflow.py`
- Modify: `packages/consultant-memory/src/caliburn_memory/__init__.py`

**Interfaces:**
- Consumes: `UnderstandingMaintenanceSession.open/load()`、`understanding_maintenance_tools()`、`ExtractionSourceReader.read(reference, offset)`。
- Produces: `UNDERSTANDING_MAINTENANCE_INSTRUCTIONS`、`UnderstandingMaintenanceResponseGuard`、`UnderstandingMaintenanceWorkflow.start(case_stage)`／`resume()`。
- Produces two workflow-only tools: `read_case_source(evidence_key)` and `request_case_rework(issues=[{evidence_key, reason}])`；they update the same `understanding_stage` through `Command`，reference 與 cursor 不屬於模型參數。

- [x] **Step 1: Write failing workflow tests**

  Cover a normal multi-tool changed result, a semantic no-op with explicit binding revalidation, paginated raw-source reading limited to an observed case reference, and `case_rework_required` that exposes no publishable understandings. Verify the initial request contains only base metadata, both guides, B1 change summary and required IDs—not preloaded case／understanding prose or raw interview.

- [x] **Step 2: Write failing durability and guard tests**

  Cover transport failure after a checkpointed tool call followed by `resume()` without replaying that semantic operation; same completed input returns the saved result; changed B1/base creates a fresh attempt and clears old messages; incomplete/refused model replies cannot execute tools; model/tool limits and one bounded completion correction survive resume.

- [x] **Step 3: Verify RED**

  Run:
  `uv run pytest -q ../../packages/consultant-memory/tests/test_understanding_workflow.py -p no:cacheprovider`

  Expected: import failure because `UnderstandingMaintenanceWorkflow` does not exist.

- [x] **Step 4: Implement the workflow and prompt**

  The prompt must state: B2 derives stable shared work from complete current cases; preserves meaningful case differences, uncertainty, time scope, responsibility and exceptions; never treats one example as frequency or shared truth; reads changed cases and directly affected understandings before finishing; uses case guide for neighboring cases; reads raw only through case references when needed; and requests B1 rework instead of compensating around a materially wrong case. Runtime payload shape:

  ```python
  {
      "BASE": {"publication_revision": stage.base_publication_revision},
      "CASE_GUIDE": case_stage.case_guide,
      "UNDERSTANDING_GUIDE": stage.understanding_guide,
      "B1_CHANGES": [change_dict, ...],
      "REQUIRED_CASE_IDS": list(stage.required_case_ids),
      "DIRECTLY_AFFECTED_UNDERSTANDING_IDS": list(stage.required_understanding_ids),
  }
  ```

  Build one `create_agent` with existing ten staged tools plus the two workflow-only tools, response guard, thread-scoped model/tool limits and one bounded completion reminder. Configure the injected model with the explicit output-token ceiling, derive a document-scoped deterministic thread ID, and compile with the injected checkpointer. `start()` fixes the exact completed B1 stage; `resume()` invokes the same pending checkpoint and never resets counters.

- [x] **Step 5: Verify GREEN**

  Run the complete new workflow test file and the existing staged-maintainer test file.

  2026-09-17 實際結果：workflow **10 passed**；連同 staged maintainer **30 passed**。審查另發現同一 canonical batch 可被多案例共同引用，故來源讀取證據由單獨 reference 收緊為 `(case_id, source_reference)` 配對，B2 stage 格式升為 v2；共享來源不能跨案例冒充已核對。全程 0 provider、0 publication。

### Task 3: 文件、回歸與本地交付

**Files:**
- Modify: `packages/consultant-memory/README.md`
- Modify: `docs/current-decisions.md`
- Modify: `docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md`
- Modify: `docs/plans/2026-09-16-b2-understanding-agent.md`

**Interfaces:**
- Documents the completed B2 graph and keeps B1→B2 rework orchestration/publication explicitly pending.

- [x] **Step 1: Update status without overstating completion**

  Record only evidence actually produced by this slice. Keep provider, natural-model quality, production App assembly, compaction, dispatcher, C and publication marked incomplete.

- [x] **Step 2: Run affected verification**

  Run the two B2 test files, the full `consultant-memory` suite, adjacent old B1/B2 App tests required by the earlier plans, `compileall`, `git diff --check`, and inspect author/committer identity before commit.

  2026-09-17 實際結果：兩個 B2 檔 **30 passed**；`consultant-memory` 全套 **218 passed**；相鄰舊 extraction／consolidation App **33 passed／11 skipped**（本輪未啟用真 PG fixture）；compileall、`git diff --check` 通過。author／committer 均為 `ArIs0x145 <aris0x145@gmail.com>`。0 provider、0 正式 publication。

- [x] **Step 3: Commit one precise work unit**

  Commit message: `feat(memory): add durable B2 understanding agent`

  Do not push. Create a local completion tag only after fresh verification.
