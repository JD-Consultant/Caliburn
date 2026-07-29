# Task Analysis Core Closure Corrections Plan

> **For agentic workers:** 逐 task 執行 TDD；每個 task 綠後獨立 commit。

**Goal:** 修正 T1–T7 code review 發現的來源閉包、狀態一致性、provider 歸因與文件權威問題，不擴大產品功能。

**Architecture:** 維持現有 `domain → verifier/context → operation/transition → provider` 邊界。模型只回 ordinal 與語意候選；application 解析 ID、SupportLink 與持久 proposal 形狀。所有新防線放在最靠近不變量的既有型別或 verifier，不新增 framework。

**Tech Stack:** Python 3.12、Pydantic v2、pytest、httpx。

## Global constraints

- 不 import 或修改 `interview`／`interview_vnext`。
- 不碰 DB、Web、SaaS、Graph runtime、OPKS。
- 每個 production 修正先寫最小 failing regression test，確認 RED 後才改碼。
- 不做模糊 semantic dedupe；只拒絕 exact duplicate。
- 全套允許且只允許既有 vNext CRLF hash baseline failure。

---

### Task 1: Merge／split support closure

**Files**

- Modify: `apps/api/app/job_analysis/llm/result.py`
- Modify: `apps/api/app/job_analysis/domain/proposal.py`
- Modify: `apps/api/app/job_analysis/application/verifier.py`
- Modify: `apps/api/app/job_analysis/application/transition.py`
- Test: `apps/api/tests/test_job_analysis_result_schema.py`
- Test: `apps/api/tests/test_job_analysis_verifier.py`
- Test: `apps/api/tests/test_job_analysis_domain.py`
- Test: `apps/api/tests/test_job_analysis_transition.py`

**Interfaces**

- Split child fields carry task-local parent support ordinals only.
- `StagedTask` carries application-built `support_links`.
- Immediate merge unions member effective links plus current anchors.
- Split children receive only explicitly selected parent links plus current anchors.

- [x] Write focused failing tests for immediate merge preservation, child-specific split assignment, and staged active-task support.
- [x] Run the focused tests and confirm each fails for the missing support closure.
- [x] Add the smallest contract/verifier/transition changes.
- [x] Run domain, schema, verifier, and transition focused tests（201 passed）。
- [x] Commit `fix(api): preserve task support across merge and split`.

### Task 2: State and proposal integrity

**Files**

- Modify: `apps/api/app/job_analysis/domain/proposal.py`
- Modify: `apps/api/app/job_analysis/application/verifier.py`
- Modify: `apps/api/app/job_analysis/application/transition.py`
- Test: `apps/api/tests/test_job_analysis_domain.py`
- Test: `apps/api/tests/test_job_analysis_verifier.py`
- Test: `apps/api/tests/test_job_analysis_transition.py`

**Interfaces**

- State input IDs are unique and canonical.
- Dict-backed inserts never overwrite different content.
- Duplicate add signals are deterministic verifier violations.
- Materially re-analysed tasks close overlapping old proposals even without a replacement.
- Retirement provenance is selected from the signal anchors.

- [x] Write failing tests for duplicate signal, duplicate IDs, operation collision, invalid staged delta, visible stale closure, and unanchored retirement.
- [x] Run tests and confirm seven expected RED failures.
- [x] Add validators and insert-only helpers without adding a repository/ledger abstraction.
- [x] Run focused domain/verifier/transition tests（208 passed）。
- [x] Commit `fix(api): close task analysis state integrity gaps`.

### Task 3: Provider treatment and response attribution

**Files**

- Modify: `apps/api/app/job_analysis/providers/openrouter.py`
- Test: `apps/api/tests/test_job_analysis_operation.py`

**Interfaces**

- Request includes `reasoning: {effort: high, exclude: true}`.
- A successful response must identify the exact configured model.
- Missing/mismatched response model becomes `MALFORMED_RESPONSE` or a dedicated typed routing failure; no retry.

- [x] Write failing wire-body and response-model tests.
- [x] Run them and confirm three expected RED failures.
- [x] Implement the minimal request and response checks.
- [x] Run operation tests（20 passed；完整 job_analysis focused suite 210 passed）。
- [x] Commit `fix(api): pin task analysis reasoning and response model`.

### Task 4: Documentation authority and writeback

**Files**

- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `apps/api/README.md`
- Modify: `docs/README.md`
- Modify: `AGENTS.md`
- Modify: `docs/design/task-analysis-engine.md`
- Modify: `docs/plans/2026-07-28-task-analysis-core-implementation-plan.md`

- [ ] Replace stale SaaS/consultant/only-AI-brain descriptions with the local employee Web scope.
- [ ] Add ADR 0042, R1a result, and `job_analysis` isolation status to indexes.
- [ ] Mark the T1–T7 plan completed with actual test/writeback information.
- [ ] Replace the PowerShell-incompatible glob command.
- [ ] Run link checks where available and `git diff --check`.
- [ ] Commit `docs: align task analysis authority after closure review`.

### Task 5: Final verification

- [ ] Run all focused `test_job_analysis_*.py` files through PowerShell file expansion.
- [ ] Run full API pytest and compare with the known baseline.
- [ ] Run `git diff --check` and inspect `git status`.
- [ ] Create a new reviewed milestone tag without moving the existing historical tag.
