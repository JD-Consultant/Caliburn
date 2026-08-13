# AI Consultant Purpose Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用四個固定、無真實 LLM 的情境，快速確認主框架能忠實承接動態訪談、可修正理解、文件 patch 審核與必要澄清，然後立刻轉入產品升級。

**Architecture:** 沿用隔離 worktree 與 LangGraph 1.2.11，以 typed state、deterministic node、checkpoint 和 `interrupt()/Command(resume=...)` 建立一個可丟棄 probe。新的 state 與命令只按產品目的命名，不包裝現行 Work Model／Focus／Proposal／Current JD；既有 14 項 PostgreSQL probe 已負責 persistence/restart 基線，本計畫只用 `InMemorySaver` 驗產品語意，避免再跑昂貴容量測試。

**Tech Stack:** Python 3.13、LangGraph 1.2.11、pytest、pytest-asyncio

**Spec:** `docs/specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md` §0.2、§3.3、§3.7、§9.11

## Global Constraints

- 第一判準是效果、功能完整、可靠性與員工體驗；自寫量只在效果相當時比較。
- 不呼叫模型、不建立 golden dataset、不修改 production dependency／lockfile／schema／API／Web。
- 不沿用或整合舊元件、舊名稱、舊 schema 或相容 adapter；同目的成熟 framework primitive 可直接替代。
- 文件 patch 審核、必要結構化澄清與待處理 Gap 是三種不同互動。
- Probe 最多新增一個 module、一個 test file；每個目的只保留一個會淘汰錯誤架構的測試。

---

### Task 1: Four-purpose LangGraph conformance

**Files:**
- Create: `apps/api/consultant_purpose_conformance_spike.py`
- Create: `apps/api/tests/test_consultant_purpose_conformance_spike.py`

**Interfaces:**
- Consumes: LangGraph `StateGraph`、`InMemorySaver`、`interrupt`、`Command(resume=...)`。
- Produces: `build_consultant_purpose_graph(checkpointer)`；輸入是 `{"command": {...}}`，輸出／checkpoint 是 neutral purpose state。

- [x] **Step 1: Write four failing behavior tests**

測試必須直接呼叫尚不存在的 `build_consultant_purpose_graph()`，並各自捕捉一種真實錯誤：

```python
async def test_dynamic_control_keeps_gaps_visible_and_reopens_corrected_unit(): ...
async def test_correction_challenges_only_source_dependent_understanding(): ...
async def test_review_queue_allows_defer_continue_edit_and_out_of_order_acceptance(): ...
async def test_required_clarification_resumes_as_employee_evidence_not_document_acceptance(): ...
```

四個 hand-written fixture 使用採購情境：請購下單、缺料協調、供應商績效。斷言至少包含：旁支不搶焦、defer 後可返回、correction reopen、無關理解不變、兩筆 patch 並存、不同路徑可任意順序接受、同路徑 stale 被拒、clarification payload 有原因／選項／affected branch、回答不改核准文件。

- [x] **Step 2: Run RED and verify the failure is the missing probe API**

Run:

```powershell
$env:PYTHONUTF8='1'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-langgraph-spike'
uv run --offline --with langgraph==1.2.11 -- pytest tests/test_consultant_purpose_conformance_spike.py -q -W error -p no:cacheprovider
```

Expected: collection fails because `consultant_purpose_conformance_spike` or `build_consultant_purpose_graph` does not exist; it must not fail from fixture syntax or dependency resolution.

- [x] **Step 3: Implement the smallest neutral-purpose graph**

Implement one typed state and one graph with deterministic commands:

```python
class ConsultantPurposeState(TypedDict, total=False):
    command: dict[str, Any]
    interview_units: dict[str, dict[str, Any]]
    active_unit_id: str | None
    issue_queue: dict[str, dict[str, Any]]
    evolving_understanding: dict[str, dict[str, Any]]
    review_queue: dict[str, dict[str, Any]]
    approved_artifact: dict[str, Any]
    required_inputs: dict[str, dict[str, Any]]
    employee_evidence: dict[str, dict[str, Any]]
    revision: int

def build_consultant_purpose_graph(checkpointer: Any) -> Any: ...
```

Use LangGraph checkpoint as the only probe owner. Product-specific code may define eligibility, source dependency, path-level read-set and patch application, but must not recreate framework persistence, replay or interrupt machinery.

- [x] **Step 4: Run GREEN and the existing lightweight framework smoke**

Run the new four tests, then the existing five bounded-runtime tests. Do not rerun the 14-test storage-growth suite unless the new graph changes shared probe code.

```powershell
$env:PYTHONUTF8='1'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-langgraph-spike'
uv run --offline --with langgraph==1.2.11 -- pytest tests/test_consultant_purpose_conformance_spike.py -q -W error -p no:cacheprovider
```

Expected: `4 passed`, no warnings.

- [x] **Step 5: Commit the disposable probe**

```powershell
git add apps/api/consultant_purpose_conformance_spike.py apps/api/tests/test_consultant_purpose_conformance_spike.py docs/plans/2026-08-13-ai-consultant-purpose-conformance-plan.md
git commit -m "test: probe consultant product purposes"
```

### Task 2: Record the decision and stop probing

**Files:**
- Modify: `docs/specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`

**Interfaces:**
- Consumes: four test results plus existing §9.7–§9.9 evidence.
- Produces: one architecture decision input and the exact boundary for the production implementation plan.

- [ ] **Step 1: Record pass/fail per product purpose**

Add one compact result table: purpose, framework primitive, observed effect, remaining product policy, hard gap. Explicitly record the Pydantic Planning 0.13.0 API drift and do not reopen broad framework research.

- [ ] **Step 2: Apply the stop rule**

If all four effects pass, select the LangChain/LangGraph family for these mechanisms and immediately write the successor ADR plus product implementation plan. If one effect fails, test exactly one second candidate for that failed purpose only; do not rebuild the other three slices.

- [ ] **Step 3: Verify and commit research conclusion**

Run `git diff --check`, inspect branch status, and commit only the research conclusion. Do not push or merge.

## Self-review

- Spec coverage: four remaining §9.11 purposes each have one test; provider/context/skills/RAG/eval are intentionally excluded because already researched or deferred.
- Placeholder scan: no TBD/TODO; all commands and expected outcomes are explicit.
- Type consistency: the only production-like API is `build_consultant_purpose_graph(checkpointer)` and both implementation and tests use it.
