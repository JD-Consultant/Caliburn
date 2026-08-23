# Task 7 report — persistent AI document-change review

## Scope delivered

- Completed the public contract hard cut: employee review actions now expose only `add` / `revise` / `withdraw` / `reassign` / `reorder`, active statuses `pending` / `deferred`, and no `target_ids` or historical action lifecycle fields.
- Added `workspace_generation`, employee-facing `workspace_status` (`clean`, `pending`, `invalid`, `conflicted`), and structured diagnostics to `DocumentReviewView`.
- Projected fresh Store-derived manifest generation, effective validation state, derived review diagnostics, and conflict-affected changesets through `DocumentReviewProjection`; the runtime no longer concatenates technical diagnostic messages into `explanation`.
- Added a semantic `acceptance_blocked` changeset flag so conflicted groups reject/defer safely while unrelated groups remain accept/edit-accept reviewable.
- Updated the review UI for employee-safe pending, invalid, conflicted, and clean states. It keeps typed field editing and atomic selection, suppresses raw paths/codes/messages, and clears selection after a 409 before invalidating/refetching the snapshot.

## TDD evidence

### Contract and API projection

1. RED — `cd packages/job-analysis-contract; $env:PYTHONUTF8='1'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_contract.py -q`
   - Failed at collection because `WorkspaceDiagnosticView` was absent from the generated public contract.
2. RED — `cd apps/api; $env:PYTHONUTF8='1'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_api_mapper.py -q`
   - Failed with `DocumentReviewProjection` extra-field validation errors for `workspace_generation`, `workspace_status`, and `diagnostics`.
3. GREEN — after schema/codegen, source projection, runtime, and mapper changes, the same contract and mapper tests passed: `6 passed` and `3 passed`.
4. RED — contract hard-cut assertion for `EmployeeDecisionSummaryView` failed because it still contained `accepted`, `edit_accepted`, `rejected`, and `stale`.
5. GREEN — removed those non-fresh public lifecycle counts and regenerated: contract test later passed `6 passed`.

### Employee semantic-review UI

1. RED — `cd apps/web; npx vitest run ConsultantWorkspace.integration.test.tsx --reporter=verbose`
   - Invalid workspace had no `role=status` and still rendered actionable bundles.
   - Conflicted workspace had no employee-safe `role=alert` or acceptance restriction.
   - A 409 left the old two-action selection displayed.
2. GREEN — after status branch, conflict-safe controls, and 409 selection reset, the focused Task 7 Web run passed `3 files, 25 tests`.
3. RED — a final accessibility audit added a pending-state `role=status` assertion; it failed because the pending heading was not announced.
4. GREEN — added the pending live status announcement; the final focused Task 7 Web run passed `3 files, 26 tests`.
5. The same Testing Library suite verifies the typed editor decisions, atomic subgroup selection, keyboard access, nine-of-ten partial acceptance with one rejection, and no raw technical UI details.

## Verification commands and outcomes

- `npm run codegen -w @caliburn/job-analysis-contract` — completed; regenerated Python and TypeScript contract artifacts.
- `npm run check-codegen -w @caliburn/job-analysis-contract` after staging the generated artifacts — passed.
- `uv run pytest tests/test_consultant_api_mapper.py tests/test_consultant_api.py -q` from `apps/api` with `PYTHONUTF8=1` and `UV_CACHE_DIR=S:\caliburn\.uv-cache-reviewed` — `14 passed`.
- `uv run pytest tests/test_consultant_contract.py -q` from `packages/job-analysis-contract` with the same managed cache — `6 passed`.
- `npm run test -w @caliburn/web -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts consultantApi.test.ts` — final run: `3 files, 26 tests passed`.
- `npx tsc --noEmit -p apps/web/tsconfig.json` — passed.
- `npm run lint -w @caliburn/web` — passed.
- `git diff --check` — no whitespace errors (only Windows LF/CRLF informational warnings).
- `rg` public-contract/UI hard-cut check — no remaining legacy `merge`, `split`, `target_ids`, `employee_after`, or `stale_reason` fields; only ordinary `path.split()` implementation text matched.

## Files changed

- `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- `packages/job-analysis-contract/src/job_analysis_contract/models.py` (generated)
- `packages/job-analysis-contract/src/job_analysis_contract/__init__.py`
- `packages/job-analysis-contract/types/job-analysis-workspace.ts` (generated)
- `packages/job-analysis-contract/tests/test_consultant_contract.py`
- `apps/api/app/consultant/views.py`
- `apps/api/app/adapters/langgraph/postgres.py`
- `apps/api/app/api/consultant_mapper.py`
- `apps/api/app/consultant/understanding.py`
- `apps/api/tests/test_consultant_api_mapper.py`
- `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- `apps/web/src/features/consultant/DocumentChangeEditor.tsx`
- `apps/web/src/features/consultant/consultantWorkspaceTestFixture.ts`
- `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- `apps/web/src/features/consultant/consultantWorkspaceModel.test.ts`

## North-star self-review

- Employee UI is limited to JD content, Chinese decision language, typed editors, and the four employee actions; it shows neither Store/VFS/framework vocabulary, raw paths, UUIDs, raw validator messages, Git, nor file editing.
- Invalid drafts expose no acceptance action. Conflicted groups disable accept/edit-accept while preserving reject/defer, and unaffected changesets retain their normal review actions.
- Review identity remains server-owned by changeset/action IDs plus expected revision; the browser sends no workspace file digest and no new conflict endpoint was added.
- `/workspace` remains the non-authoritative working draft and `/review` is freshly derived from Store state; no second document store or compatibility surface was introduced.

## Concerns

- The repository's `check-codegen` script intentionally compares generated files against the unstaged working tree. Before committing, generated artifacts must be staged so the script verifies regeneration consistency rather than reporting the intended Task 7 diff. This is handled in the final verification sequence.
- The Windows sandbox blocks `uv`'s default user cache and Vite child-process spawning. All test/codegen commands used the managed repo uv cache or the approved local process permission; no PostgreSQL or live-model gate was run.

## Review fix round 1/5 — truthful unloaded review and accessible selections

### Findings resolved

- `snapshot_from_state()` now creates an internal `ConsultantSnapshot` with `document_review=None`. It cannot be mapped to the public `ConsultantSnapshotView`: the mapper raises until the production runtime has read Store and supplied `document_review_projection_from_workspace()`.
- The pre-Store checkpoint path now retains only `safe_interview_work_available` through a dedicated state helper. It no longer creates a fictional clean workspace review, generation, or diagnostics.
- The production PostgreSQL runtime remains the only public snapshot path and already enriches its checkpoint snapshot from a fresh Store read before mapper use. API test runtimes now use that same Store-derived projection helper rather than injecting a final status.
- Each review checkbox now announces a stable visible ordinal, the employee-facing operation, semantic JD field and change summary, plus `必須整組決定` for atomic groups. The 409 edit error is also cleared after a later successful decision.

### TDD evidence

1. RED — `cd apps/api; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_api_mapper.py -q`
   - First corrected two pre-existing expectation shape mismatches (`latest_run`, tuple messages), then failed for the intended reason: `snapshot.document_review` was a fabricated `workspace_generation=0`, `clean` projection instead of unloaded.
2. GREEN — after making the internal review optional, enforcing Store enrichment at the mapper boundary, and preserving safe interview work independently: `uv run pytest tests/test_consultant_api_mapper.py tests/test_consultant_api.py -q` — `14 passed`.
3. The mapper regression derives `clean`, `pending`, `invalid`, and `conflicted` from validation status, diagnostics, workspace bundles, and a conflict-bearing group. It asserts generation, deferred unresolved actions, conflict acceptance blocking, employee diagnostics, and safe interview availability without injecting a final review enum.
4. RED — `npm run test -w @caliburn/web -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts consultantApi.test.ts`
   - The new repeated-action accessibility assertion failed because all checkboxes still announced only `選取修改變更`.
5. GREEN — after semantic names and updated keyboard behavior assertions, the same focused Web command passed `3 files, 27 tests`.

### Verification commands and outcomes

- `uv run pytest tests/test_consultant_api_mapper.py tests/test_consultant_api.py -q` from `apps/api` with `UV_CACHE_DIR=S:\caliburn\.uv-cache-reviewed` — `14 passed` (only non-failing pytest cache permission warnings).
- `npm run test -w @caliburn/web -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts consultantApi.test.ts` — `3 files, 27 tests passed`. The first sandboxed attempt could not spawn Vite; the approved local-process rerun completed.
- `npx tsc --noEmit -p apps/web/tsconfig.json` — passed.
- `npm run lint -w @caliburn/web` — passed.
- `git diff --check` — no whitespace errors (only Windows LF/CRLF informational warnings).
- Contract schema did not change in this fix round, so codegen/check-codegen and contract tests were not rerun.
- No PostgreSQL, live-model, or full-monorepo gate was run.

### Files changed in this fix round

- `apps/api/app/consultant/views.py`
- `apps/api/app/api/consultant_mapper.py`
- `apps/api/tests/test_consultant_api_mapper.py`
- `apps/api/tests/test_consultant_api.py`
- `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- `.superpowers/sdd/2026-08-22-persistent-store-backed-jd-working-draft-plan/task-7-report.md`

### North-star self-review

- Public review state is always fresh Store/runtime truth; an unloaded checkpoint cannot emit an employee-visible clean status or generation.
- Store diagnostics and conflict groups still determine the existing four employee states. No fifth status, no conflict endpoint, and no compatibility surface were added.
- The UI continues to expose only Chinese JD semantics, typed field editors, partial selection, atomic-group constraints, and stale-response handling; accessible labels contain no IDs, paths, Store/VFS/framework terms, or raw technical diagnostics.
- Accept/edit-accept remains blocked only for conflicted groups; reject/defer and unaffected groups retain their existing authority behavior.

### Concerns

- The focused API run emits harmless Windows pytest-cache write warnings in this worktree; assertions and test outcomes are unaffected.
- No public contract changed, so schema generation was intentionally not touched.

## Review fix round 2/5 — distinguish review controls across groups

### Finding resolved

- `DocumentReviewPanel` now passes a one-based employee-visible group ordinal from the displayed review groups to each `ReviewBundle`.
- Every review checkbox announces `第 N 組第 M 項`, then its employee-facing operation, semantic JD field, summary, and—where applicable—`必須整組決定`.
- The UI exposes no UUID, raw path, Store/framework/tool wording, or technical content. No API, contract, or domain code changed.

### TDD evidence

1. RED — added a Testing Library regression with two different bundles intentionally sharing the same operation, path label, and summary. The first sandboxed focused test attempt was blocked by Vite child-process `EPERM`; the approved local-process rerun executed the test.
2. RED outcome — `npm run test -w @caliburn/web -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts consultantApi.test.ts` failed as intended: both controls were named `選取第 1 項修改變更：工作敘述（更新工作內容）；必須整組決定`, and neither matched the required `第 1 組第 1 項` name.
3. GREEN — passed the one-based group ordinal into `ReviewBundle`, incorporated it into the checkbox name, and updated the existing keyboard behavior expectations for their four groups.
4. GREEN outcome — the same exact focused command passed `3 files, 28 tests`.

### Verification commands and outcomes

- `npm run test -w @caliburn/web -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts consultantApi.test.ts` — `3 files, 28 tests passed` (approved local-process run required for Vite on Windows).
- `npx tsc --noEmit -p apps/web/tsconfig.json` — passed.
- `npm run lint -w @caliburn/web` — passed.
- `git diff --check` — no whitespace errors (only Windows LF/CRLF informational warnings).
- No API, contract, PostgreSQL, live-model, or full-monorepo gate was run because this round changes only the Web accessibility boundary.

### Files changed in this fix round

- `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- `.superpowers/sdd/2026-08-22-persistent-store-backed-jd-working-draft-plan/task-7-report.md`

### North-star self-review

- Controls that are otherwise semantically identical across different review groups now have deterministic, employee-understandable accessible names.
- Item selection, atomic whole-group wording, typed editors, partial selection, stale-response handling, and all four employee review states remain unchanged.

### Concerns

- The Windows sandbox still cannot spawn Vite's setup child process; the focused test was rerun with the minimal approved local-process permission.
