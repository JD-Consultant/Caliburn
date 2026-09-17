# Layered Background App Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the isolated JD App's legacy two-stage background dispatch contract with the completed document-scoped `BackgroundMemoryWorkflow`, while preserving saved notification admission, bounded host execution, durable recovery, and one atomic layered Memory publication.

**Architecture:** `BackgroundDispatcher` remains the only cheap, repeatable wake entry. It owns only admission and one fixed source batch; `BackgroundMemoryWorkflow` owns B1, B2, rework, stale handling, bundle assembly, and publication. A focused App factory binds one document's canonical conversation source, shared Postgres Store/Saver, and `PublicationStore` to injected offline models; provider and compaction assembly remain outside this slice.

**Tech Stack:** Python 3.12, LangChain 1.4.0, LangGraph 1.2.11, langgraph-checkpoint-postgres 3.1.2, psycopg 3.3.5, SQLAlchemy 2.0.52, pytest 9.1.1.

**Spec:** `docs/specs/2026-09-17-layered-memory-background-workflow-design.md`

## Global Constraints

- Follow `MEM-L001`: B1 maintains current cases, B2 maintains current work understanding, and both publish as one bundle.
- Preserve canonical interview messages; dispatcher and compaction never replace source evidence.
- Reuse `jd_memory_admission`, the existing host worker, Saver, Store, `PublicationStore`, and source owner. Add no table, migration, queue, scheduler, registry authority, or setup-on-open behavior.
- A wake admits at most one bounded host job. No polling loop and no hidden retry loop.
- Use fixed offline models only. Do not read credentials, call OpenRouter, switch provider, or claim natural-model quality.
- Do not implement C bundle repair, A/B1/B2 compaction, JD writing, UI, document archive behavior, artifact GC, migration, or production-authority switch.
- Preserve the current designated branch; do not create another worktree, merge, or push.

---

### Task 1: Make admission reconcile one outer layered workflow

**Files:**
- Modify: `experiments/jd-relational-app/src/jd_relational/background_admission.py`
- Test: `experiments/jd-relational-app/tests/test_background_admission.py`

**Interfaces:**
- Consumes: `BackgroundMemoryWorkflow.graph`, `.config`, `.publication`, and persisted state fields `source_reference`, `status`, `error_code`, `result`.
- Produces: `require_handed_over(workflow, publication) -> None` and `reconcile(admission, *, workflow, publication, windows, document_id) -> Literal["wait", "resume_workflow", "start_workflow", "next_batch", "settle_idle", "record_blocked", "blocked"]`.

- [x] **Step 1: Write failing tests for the new durable observations**

  Add cases proving: pending outer state resumes; queued/running source never changes; completed publication advances; outer blocked maps to `record_blocked`; idle plus no notification stays `wait`; and a previous unpublished/mismatched terminal cannot admit a new target.

- [x] **Step 2: Run the focused test and verify RED**

  Run from `experiments/jd-relational-app`:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_background_admission.py -q -p no:cacheprovider
  ```

  Expected: failures because `reconcile()` and `require_handed_over()` still require separate extraction/consolidation workflows.

- [x] **Step 3: Implement the minimal outer-workflow reconciliation**

  Remove legacy B1/B2 imports from the admission decision. Inspect the outer snapshot only to distinguish empty, pending, completed, and blocked; validate that its fixed source agrees with the admitted batch. Keep target/source/error/recovery ownership in `BackgroundAdmissions` and publication progress in `PublicationStore`.

- [x] **Step 4: Run the focused test and verify GREEN**

  Use the Step 2 command. Expected: all admission tests pass.

---

### Task 2: Make the dispatcher execute one layered workflow

**Files:**
- Modify: `experiments/jd-relational-app/src/jd_relational/background_dispatch.py`
- Modify: `experiments/jd-relational-app/tests/test_background_dispatch_postgres.py`
- Test: `experiments/jd-relational-app/tests/test_layered_background_dispatch.py`

**Interfaces:**
- Consumes: Task 1 `reconcile()`, `BackgroundMemoryWorkflow.start(source_reference)`, and `.resume()`.
- Produces: `BackgroundDispatcher(..., workflow=workflow, publication=publication).wake() -> str` using the existing wake/result vocabulary plus `start_workflow`, `resume_workflow`, and `record_blocked`.

- [x] **Step 1: Write failing dispatcher tests**

  Cover no saved request, one saved request, repeated wake while Future is live, pending resume, completed publication followed by target-tail advance, and outer blocked result persisted to the admission row. Assert the dispatcher never invokes B1/B2 directly.

- [x] **Step 2: Run the focused dispatcher tests and verify RED**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_layered_background_dispatch.py -q -p no:cacheprovider
  ```

  Expected: constructor/signature failures because the dispatcher still accepts `extraction` and `consolidation`.

- [x] **Step 3: Implement the minimal dispatcher replacement**

  Replace the two-stage branches with `start_workflow` and `resume_workflow`. After a terminal result, advance/settle only when publication proves the batch covered; persist workflow terminal blocks by their bounded public error code. Preserve `_running` busy protection, fixed target planning, commit-before-invoke, and one worker submission per wake.

- [x] **Step 4: Run dispatcher and admission tests and verify GREEN**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_background_admission.py tests\test_layered_background_dispatch.py -q -p no:cacheprovider
  ```

  Expected: all selected tests pass.

---

### Task 3: Assemble one document's formal layered Memory resources

**Files:**
- Create: `experiments/jd-relational-app/src/jd_relational/background_memory_app.py`
- Modify: `experiments/jd-relational-app/src/jd_relational/host_runtime.py`
- Test: `experiments/jd-relational-app/tests/test_background_memory_app.py`

**Interfaces:**
- Consumes: `ConversationSourceService`, `ExtractionSourceAdapter`, caller-owned Store, Saver, SQLAlchemy memory engine, and injected B1/B2 chat models.
- Produces: `build_background_memory_workflow(*, service, document_id, store, checkpointer, memory_engine, case_model, understanding_model, max_stale_retries=...) -> BackgroundMemoryWorkflow`.
- Produces: `ManualHost.saver`, exposing the already process-owned `PostgresSaver` without opening or setting up another database resource.

- [x] **Step 1: Write a failing composition test**

  Build two workflows for different document IDs over the same in-memory Saver/Store and fixed models. Assert each workflow's B1/B2/publication share one document authority, thread IDs differ, source adapters enforce document scope, and building performs no model call or schema setup.

- [x] **Step 2: Run the composition test and verify RED**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_background_memory_app.py -q -p no:cacheprovider
  ```

  Expected: import failure because `background_memory_app` does not exist.

- [x] **Step 3: Implement the thin App factory**

  Construct exactly one `ExtractionSourceAdapter`, `MemoryArtifacts`, `CaseMaintenanceSession`, `CaseMaintenanceWorkflow`, `UnderstandingMaintenanceSession`, `UnderstandingMaintenanceWorkflow`, `PublicationStore`, and `BackgroundMemoryWorkflow`. Pass models through without selecting provider. Expose the host's existing Saver as a dataclass field; do not open a pool, connection, registry, or schema setup path.

- [x] **Step 4: Run composition and host lifecycle tests and verify GREEN**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_background_memory_app.py tests\test_background_host.py tests\test_configured_host_native.py -q -p no:cacheprovider
  ```

  Expected: all selected tests pass.

---

### Task 4: Prove the layered dispatcher on real PostgreSQL and a fresh process

**Files:**
- Create: `experiments/jd-relational-app/tests/test_layered_background_dispatch_postgres.py`
- Create: `experiments/jd-relational-app/tests/test_layered_background_new_process_postgres.py`
- Create: `experiments/jd-relational-app/tests/support/layered_background_recovery_probe.py`
- Modify: `docs/specs/2026-09-17-layered-memory-background-workflow-design.md`
- Modify: `docs/current-decisions.md`

**Interfaces:**
- Consumes: Tasks 1–3 and the explicit isolated test database initialized by existing scripts.
- Produces: evidence for one notification → one layered publication, pending outer resume, B1-complete/B2-pending resume through the parent workflow, publication reply-loss reconciliation, admission update after commit, and no duplicate revision in a genuinely new Windows process.

- [x] **Step 1: Write the real-PostgreSQL integration tests**

  Use synthetic conversation data and deterministic offline chat models. Tests are opt-in under `JD_RELATIONAL_TEST_DB=1`; they must never read a provider key or perform network I/O.

- [x] **Step 2: Run the tests and verify the intended first failure**

  ```powershell
  $env:JD_RELATIONAL_TEST_DB='1'; .\.venv\Scripts\python.exe -m pytest tests\test_layered_background_dispatch_postgres.py -q -p no:cacheprovider
  ```

  Expected: failure at the first not-yet-connected App resource or recovery boundary, not because the database is uninitialized.

- [x] **Step 3: Add only the fixture/probe wiring required by the failing boundary**

  Reopen Saver, Store, publication, source service, admission row, and workflow from database identity only. The child process receives document/dataset IDs and a named stop point, never Python objects or secrets. Reuse the original operation/checkpoint; do not replay a completed semantic action.

- [x] **Step 4: Run PostgreSQL and new-process tests and verify GREEN**

  ```powershell
  $env:JD_RELATIONAL_TEST_DB='1'; .\.venv\Scripts\python.exe -m pytest tests\test_layered_background_dispatch_postgres.py tests\test_layered_background_new_process_postgres.py -q -p no:cacheprovider
  ```

  Expected: all selected tests pass with one publication revision per admitted batch.

- [x] **Step 5: Update durable status without overstating completion**

  Record that dispatcher/resource/PG recovery is complete only if the tests ran. Keep B1 and B2 App-side compaction, OpenRouter model factory, C bundle repair, managed App callback, paid smoke, and full App acceptance explicitly incomplete. Correct the existing omission that could make new B2 compaction appear complete.

---

### Task 5: Regression, drift check, review, and local delivery

**Files:**
- Modify only files already listed if review finds a concrete defect.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: one reviewable local commit and tag; no push.

- [x] **Step 1: Run affected offline suites**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_background_admission.py tests\test_layered_background_dispatch.py tests\test_background_wakeup.py tests\test_background_memory_app.py tests\test_consultant_memory_context.py -q -p no:cacheprovider
  ```

  From `packages/consultant-memory`:

  ```powershell
  ..\..\experiments\jd-relational-app\.venv\Scripts\python.exe -m pytest tests\test_background_workflow.py tests\test_case_maintenance_workflow.py tests\test_understanding_workflow.py -q -p no:cacheprovider
  ```

- [x] **Step 2: Run compile and repository checks**

  ```powershell
  .\.venv\Scripts\python.exe -m compileall -q src tests
  git diff --check
  git status --short
  ```

- [x] **Step 3: Re-read the binding spec and inspect the diff**

  Confirm dispatcher does not own B1/B2 semantics, no generic queue/registry/setup was introduced, source and publication cursors did not merge, and the docs do not claim compaction/provider/full App completion.

- [x] **Step 4: Request an independent code review and close findings**

  Review the exact diff against `MEM-L001`, the six-field admission responsibility, and the no-provider/no-production-authority boundary. Add a failing regression before fixing any behavioral finding.

  Review closure: same-instance concurrent wake submission, outer checkpoint status／pending-node consistency, and pre-settle new-process target evidence were reproduced or corrected with focused regressions. Narrow re-review marked all three findings closed and found no scope expansion.

- [x] **Step 5: Commit and tag locally after fresh verification**

  ```powershell
  git add docs/current-decisions.md docs/specs/2026-09-17-layered-memory-background-workflow-design.md docs/superpowers/plans/2026-09-17-layered-background-app-dispatch.md experiments/jd-relational-app/src/jd_relational/background_admission.py experiments/jd-relational-app/src/jd_relational/background_dispatch.py experiments/jd-relational-app/src/jd_relational/background_memory_app.py experiments/jd-relational-app/src/jd_relational/host_runtime.py experiments/jd-relational-app/tests
  git commit -m "feat(memory): connect layered background dispatcher"
  git tag -a jd-layered-background-dispatch-20260917 -m "Layered background dispatcher and PostgreSQL recovery"
  ```

  Do not push.

  Fresh evidence before local delivery: affected App `61 passed, 6 skipped`; adjacent `consultant-memory` workflows `46 passed`; real PostgreSQL／new-process recovery `7 passed`; compileall and `git diff --check` passed. No provider call or credential read occurred.
