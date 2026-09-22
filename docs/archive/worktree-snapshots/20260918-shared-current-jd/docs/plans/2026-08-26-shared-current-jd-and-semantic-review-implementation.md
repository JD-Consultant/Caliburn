# Shared Current JD and Semantic Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the employee-visible approved-editor/AI-draft split with one durable current JD editing surface, preserve an approved-only export baseline, simplify review to accept/reject, keep chat usable after failures, and ship the agreed hierarchical semantic-diff UI.

**Architecture:** Deep Agents `StoreBackend` remains the current JD working-copy owner and LangGraph remains the durable conversation/authority runtime. The API projects the validated current document beside the read-only approved baseline; employee edits are computed server-side from exact current before/after state and update only the touched semantic closure in both states. React renders current, review, and approved comparison from the generated contract without recomputing domain validity.

**Tech Stack:** Python 3.13, Pydantic v2, LangGraph Postgres Saver/Store, Deep Agents VFS, FastAPI, JSON Schema codegen, React 19, Next.js, TanStack Query, Tailwind CSS, Vitest/Testing Library, pytest.

**Spec:** `docs/specs/2026-08-25-shared-current-jd-working-copy-and-semantic-approval-research.md`

**ADR:** `docs/adr/0069-shared-current-jd-working-copy-and-semantic-approval.md`

## Global Constraints

- `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json` is the cross-language SSOT; generated Python and TypeScript files must never be edited by hand.
- The employee sees and edits one `current_document`; `approved_document` is read-only and remains the only export authority.
- AI edits never write `approved_document`; accept, employee edit-and-accept, or employee direct edit are the only authority edges.
- Pending review never blocks chat. Only `required_clarification` may interrupt dependent analysis.
- Remove review `defer`; untouched changes persist naturally as pending.
- A direct edit uses server-derived before/after paths and must not approve unrelated AI changes.
- Failure leaves the answer box usable; correction is expressed in normal chat, not by selecting an old utterance in the primary UI.
- Reuse LangGraph, Deep Agents, Pydantic and the generated contract. Do not add Git, JSON Patch authority, CRDT/OT, another workflow engine, document store or UI framework.
- Keep RAG/Reference, ability-level analysis, A analysis, auto-accept, multi-agent behavior and a formal eval platform out of scope.
- Follow red-green-refactor and commit each task independently. After every task, compare behavior with ADR 0069 decision 14.

---

### Task 1: Public current-document projection and guarded edit contract

**Files:**
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Modify (generated): `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Modify (generated): `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Modify: `packages/job-analysis-contract/tests/test_consultant_contract.py`
- Modify: `apps/api/app/consultant/views.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/app/api/consultant_mapper.py`
- Modify: `apps/api/tests/test_consultant_api_mapper.py`

**Interfaces:**
- Produces `ConsultantSnapshotView.current_document: ApprovedJobDocumentView`.
- Produces `DocumentReviewView.workspace_digest: str` paired with `workspace_generation`.
- Produces `DirectDocumentEditWrite(document, workspace_generation, workspace_digest)`.
- Preserves the existing review decision/blocker fields until Task 4 removes their backend and contract lifecycle together.

- [ ] **Step 1: Write the failing contract test**

```python
def test_snapshot_contract_exposes_current_document_and_guarded_edit() -> None:
    snapshot = schema()["$defs"]["ConsultantSnapshotView"]
    review = schema()["$defs"]["DocumentReviewView"]
    direct_edit = schema()["$defs"]["DirectDocumentEditWrite"]
    assert "current_document" in snapshot["required"]
    assert "workspace_digest" in review["required"]
    assert {"document", "workspace_generation", "workspace_digest"} <= set(
        direct_edit["required"]
    )
```

- [ ] **Step 2: Verify RED**

Run: `cd packages/job-analysis-contract && uv run pytest tests/test_consultant_contract.py -q`

Expected: FAIL because the current document, digest and guarded-edit fields are absent.

- [ ] **Step 3: Change only the JSON Schema SSOT and regenerate**

Run: `npm run codegen -w @caliburn/job-analysis-contract`. Never hand-edit generated Python/TypeScript.

- [ ] **Step 4: Write the failing Store projection test**

```python
view = to_consultant_snapshot_view(store_derived_snapshot)
assert view.approved_document.tasks[0].statement == "核准內容"
assert view.current_document.tasks[0].statement == "AI 工作中內容"
assert view.document_review.workspace_digest == workspace_digest
```

- [ ] **Step 5: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_consultant_api_mapper.py -q`

- [ ] **Step 6: Implement the Store-derived projection**

Add `current_document: ApprovedJobDocument | None` to the internal snapshot. Populate it in `_snapshot()` from `validation.document.approved_document`; when canonical JSON cannot parse, expose the last safe approved baseline while returning diagnostics. Add `workspace_digest` to `DocumentReviewProjection`. Public mapping must require Store-derived review/current fields.

- [ ] **Step 7: Verify GREEN**

```text
cd packages/job-analysis-contract && uv run pytest tests/test_consultant_contract.py -q
cd apps/api && uv run pytest tests/test_consultant_api_mapper.py -q
npm run check-codegen -w @caliburn/job-analysis-contract
```

- [ ] **Step 8: Commit**

```text
git add packages/job-analysis-contract apps/api/app/consultant/views.py apps/api/app/adapters/langgraph/postgres.py apps/api/app/api/consultant_mapper.py apps/api/tests/test_consultant_api_mapper.py
git commit -m "feat: expose the shared current JD projection"
```

---

### Task 2: Server-derived employee semantic delta

**Files:**
- Create: `apps/api/app/consultant/current_document_edit.py`
- Create: `apps/api/tests/test_consultant_current_document_edit.py`
- Modify: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/tests/test_consultant_workspace_authority.py`

**Interfaces:**
- Produces `CurrentDocumentEditPlan(approved_after, employee_override_paths, accepted_pending_action_ids, employee_text_paths)`.
- Produces `plan_current_document_edit(approved, current, submitted, workspace_files, handle_registry, review) -> CurrentDocumentEditPlan`.
- Consumes canonical `project_workspace_files`/`parse_workspace_files`, `WorkspaceReviewProjection` and `build_workspace_rebase_plan`.

- [ ] **Step 1: Write a failing test for non-overlapping edits**

```python
def test_employee_edit_approves_only_touched_field_and_keeps_other_ai_diff() -> None:
    plan = plan_current_document_edit(
        approved=document(task_statement="核准敘述", frequency="每月"),
        current=document(task_statement="AI 新敘述", frequency="每月"),
        submitted=document(task_statement="AI 新敘述", frequency="每週"),
        workspace_files=current_files,
        handle_registry=registry,
        review=review,
    )
    assert plan.approved_after.tasks[0].statement == "核准敘述"
    assert plan.approved_after.tasks[0].frequency_text == "每週"
    assert "/workspace/tasks/task-001.json/frequency_text" in plan.employee_override_paths
    assert not any(path.endswith("/statement") for path in plan.employee_override_paths)
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_consultant_current_document_edit.py -q`

- [ ] **Step 3: Implement exact changed-path derivation**

Project `current` and `submitted` with one stable handle registry. Recursively compare JSON dictionaries; emit leaf JSON-pointer paths, treat lists as one field, and treat resource add/delete as the resource root. Never derive touched paths from approved and never trust client-provided paths.

- [ ] **Step 4: Add failing dependency tests**

- `test_editing_ai_added_task_promotes_required_new_duty_but_not_unrelated_opks`: approved starts without the proposed Duty/Task; current adds the Duty, its Task and an unrelated OPKS item; employee edits that Task; assert `approved_after` contains the required Duty and Task, excludes the unrelated OPKS item, and reports exactly the accepted dependency closure.
- `test_editing_one_member_of_a_split_promotes_its_atomic_subgroup`: current replaces one approved Task with two split Tasks sharing one atomic subgroup; employee edits one split result; assert both split results and the original withdrawal are promoted together, while unrelated pending actions remain excluded.
- `test_removing_an_ai_only_entity_cleans_current_without_changing_approved`: employee deletes an AI-only entity from current; assert the approved document remains byte-equivalent and the corresponding pending action disappears after rebase.

Each test asserts exact resulting entities, accepted action IDs and remaining pending actions.

- [ ] **Step 5: Verify RED again**

Run the same test file; failure must identify missing dependency/atomic closure.

- [ ] **Step 6: Implement the smallest semantic closure**

Match touched canonical paths to current review actions, expand same `atomic_subgroup_id` and transitive `depends_on_action_ids`, apply only that closure to approved, then overlay employee after-values at touched paths. Merge direct changes without pending actions only at touched fields/entities. Parse and validate the prospective approved resources; never accept the whole submitted document as fallback.

- [ ] **Step 7: Apply employee override semantics**

Pass `employee_override_paths=plan.employee_override_paths` when calling `build_workspace_rebase_plan`. Touched values become employee values, untouched AI values remain current, and this flow emits no `workspace-rebase-conflict`. Preserve stale checks and recovery records.

- [ ] **Step 8: Verify GREEN**

Run: `cd apps/api && uv run pytest tests/test_consultant_current_document_edit.py tests/test_consultant_workspace_authority.py -q`

- [ ] **Step 9: Commit**

```text
git add apps/api/app/consultant/current_document_edit.py apps/api/app/consultant/workspace_authority.py apps/api/tests/test_consultant_current_document_edit.py apps/api/tests/test_consultant_workspace_authority.py
git commit -m "feat: make employee edits authoritative on touched JD content"
```

---

### Task 3: Current-document HTTP authority and crash recovery

**Files:**
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: `apps/api/tests/test_consultant_api.py`
- Modify: `apps/api/tests/test_consultant_durable_authority_postgres.py`
- Modify: `apps/api/tests/test_consultant_workspace_recovery_postgres.py`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/shared/api/consultantApi.test.ts`

**Interfaces:**
- Replaces `PUT /{document_id}/approved-document` with `PUT /{document_id}/current-document`.
- Produces `editCurrentDocument(documentId, key, expectedRevision, workspaceGeneration, workspaceDigest, document)`.
- Consumes `CurrentDocumentEditPlan`.

- [ ] **Step 1: Write failing API/client tests**

```typescript
await editCurrentDocument(DOCUMENT_ID, "edit-1", 3, 8, "workspace-sha", document);
expect(fetch).toHaveBeenCalledWith(
  expect.stringContaining("/current-document"),
  expect.objectContaining({
    method: "PUT",
    body: JSON.stringify({
      document,
      workspace_generation: 8,
      workspace_digest: "workspace-sha",
    }),
  }),
);
```

API tests also assert stale generation/digest returns 409 and changes neither current nor approved.

- [ ] **Step 2: Verify RED**

```text
cd apps/api && uv run pytest tests/test_consultant_api.py -q
cd apps/web && npm run test -- consultantApi.test.ts
```

- [ ] **Step 3: Implement the current-document command**

Inside the employee-admission/document lock, re-read Store, compare both workspace guards, build Task 2's plan, mint direct-edit Evidence only from `current before -> submitted after`, commit `approved_after` through the existing LangGraph authority seam, then apply/replay the persisted workspace plan. Rename the public endpoint/client; keep internal action names when renaming has no product effect.

- [ ] **Step 4: Write crash-window tests**

Cover failure after source Store write, after approved checkpoint and before workspace rebase. Exact replay with one idempotency key converges to one source/revision/current document; a changed payload under the same key fails.

- [ ] **Step 5: Verify GREEN**

```text
cd apps/api && uv run pytest tests/test_consultant_current_document_edit.py tests/test_consultant_api.py tests/test_consultant_durable_authority_postgres.py tests/test_consultant_workspace_recovery_postgres.py -q
cd apps/web && npm run test -- consultantApi.test.ts
```

- [ ] **Step 6: Commit**

```text
git add apps/api/app/adapters/langgraph/postgres.py apps/api/app/api/routes/consultant.py apps/api/tests apps/web/src/shared/api packages/job-analysis-contract
git commit -m "feat: edit the current JD through guarded authority"
```

---

### Task 4: Remove defer and unlock conversation after failure

**Files:**
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Modify (generated): `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Modify (generated): `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Modify: `packages/job-analysis-contract/tests/test_consultant_contract.py`
- Modify: `apps/api/app/consultant/state.py`
- Modify: `apps/api/app/consultant/workspace_review.py`
- Modify: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/app/consultant/understanding.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: `apps/api/tests/test_consultant_workspace_review.py`
- Modify: `apps/api/tests/test_consultant_workspace_authority.py`
- Modify: `apps/api/tests/test_consultant_understanding_and_sufficiency.py`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/features/consultant/ConsultantConversation.tsx`
- Modify: `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`

**Interfaces:**
- Review decisions are exactly accept, edit-and-accept and reject.
- Removes `defer_changes`, deferred action status, `blocked_branches`, `safe_interview_work_available`, `decision_required_before_more_interview` and review `explanation` from the public contract.
- Failed runs expose retry but never disable a new normal employee message.
- The primary conversation has no source-selection correction mode.

- [ ] **Step 1: Write failing contract and domain tests for natural pending**

Assert the generated contract exposes only accept/edit-and-accept/reject and no latent blocker fields. Remove defer-specific domain expectations and add a behavior test proving an untouched action stays pending across reopen and a later AI mutation without a decision record.

- [ ] **Step 2: Verify RED**

```text
cd packages/job-analysis-contract && uv run pytest tests/test_consultant_contract.py -q
cd apps/api && uv run pytest tests/test_consultant_workspace_review.py tests/test_consultant_workspace_authority.py -q
```

- [ ] **Step 3: Remove the deferred lifecycle**

Delete `DEFER` enum/branches, `_deferred_action_ids`, deferred action status and API mapping. Remove the latent blocker fields from the JSON Schema SSOT and regenerate Python/TypeScript. Pending remains represented solely by baseline/current diff. Remove deferred counts and labels from Web.

- [ ] **Step 4: Write failing component tests**

```tsx
expect(screen.getByRole("textbox", { name: "回覆顧問" })).toBeEnabled();
expect(screen.getByRole("button", { name: /送出回答/ })).toBeEnabled();
expect(screen.getByRole("button", { name: /重試同一則回答/ })).toBeVisible();
expect(screen.queryByRole("button", { name: /更正這段原話/ })).toBeNull();
```

- [ ] **Step 5: Verify RED then implement**

Run: `cd apps/web && npm run test -- ConsultantWorkspace.integration.test.tsx`

Remove `answerBlockedByFailure`, `answerBlockedByDecision`, `correctionSourceId` and the primary source-correction controls. Keep a short failed-run explanation and retry shortcut while normal typing remains available.

- [ ] **Step 6: Verify GREEN**

Run the focused contract, API and Web tests from this task, then run `npm run check-codegen -w @caliburn/job-analysis-contract`.

- [ ] **Step 7: Commit**

```text
git add apps/api/app/consultant apps/api/app/api/routes/consultant.py apps/api/tests packages/job-analysis-contract apps/web/src/features/consultant
git commit -m "refactor: simplify pending review and failure recovery"
```

---

### Task 5: Durable conversational source supersession

**Files:**
- Modify: `apps/api/app/consultant/model_output.py`
- Modify: `apps/api/app/consultant/results.py`
- Modify: `apps/api/app/consultant/verification.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/consultant/agent.py`
- Modify: `apps/api/tests/test_consultant_model_output.py`
- Modify: `apps/api/tests/test_consultant_run_service.py`
- Modify: `apps/api/tests/test_consultant_durable_authority_postgres.py`

**Interfaces:**
- Adds required provider output `source_supersessions[]` with only `superseded_source_handle`; the current answer source is the replacement.
- The model returns source handles; application maps and validates IDs.

- [ ] **Step 1: Write failing mapping/verification tests**

Cover zero corrections, one valid prior-current source, unknown handle, self-target, already-superseded target, and ambiguous correction represented by `required_clarification` plus an empty supersession list.

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && uv run pytest tests/test_consultant_model_output.py tests/test_consultant_run_service.py -q`

- [ ] **Step 3: Add the smallest strict wire shape**

```python
class OutputSourceSupersession(OutputModel):
    superseded_source_handle: Handle

class ConsultantModelOutput(OutputModel):
    # existing fields remain required
    source_supersessions: tuple[OutputSourceSupersession, ...]
```

Do not add confidence, free-form correction text, relation variants or optional objects.

- [ ] **Step 4: Implement replay-safe lineage**

Validate targets are current sources in this document. Persist previous/current source pair atomically in Store, carry supersession into the graph command so `apply_source_correction()` reopens affected understanding/work/gaps, and make retry reconcile an already-written lineage instead of creating a second source.

- [ ] **Step 5: Update the consultant policy**

Emit supersession only when the employee clearly replaces one uniquely identifiable earlier statement. Treat additions normally. If multiple prior sources fit, ask required clarification and emit no supersession.

- [ ] **Step 6: Verify GREEN**

Run: `cd apps/api && uv run pytest tests/test_consultant_model_output.py tests/test_consultant_run_service.py tests/test_consultant_interview_flow.py tests/test_consultant_durable_authority_postgres.py -q`

- [ ] **Step 7: Commit**

```text
git add apps/api/app/consultant apps/api/app/adapters/langgraph/postgres.py apps/api/tests
git commit -m "feat: understand conversational source corrections"
```

---

### Task 6: One current-JD workspace and hierarchical UI

**Files:**
- Create: `apps/web/src/features/consultant/CurrentDocumentEditor.tsx`
- Create: `apps/web/src/features/consultant/CurrentDocumentOutline.tsx`
- Create: `apps/web/src/features/consultant/ConsultantWorkMap.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantInsightPanel.tsx`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Delete: `apps/web/src/features/consultant/ApprovedDocumentEditor.tsx`

**Interfaces:**
- `CurrentDocumentEditor` edits `snapshot.current_document` and submits Task 3 guards.
- `CurrentDocumentOutline` groups Duty -> Task -> O/P/K/S and supplies stable labels; it never validates domain rules.
- `ConsultantWorkMap` is navigation/summary only; Focus and Gap are not forced onto JD entity IDs.

- [ ] **Step 1: Write failing hierarchy and shell tests**

```tsx
expect(screen.getByRole("heading", { name: "目前 JD" })).toBeVisible();
expect(within(dutyOne).getByText("處理申訴案件")).toBeVisible();
expect(within(unassigned).getByText("尚待歸類的工作")).toBeVisible();
expect(screen.getByText("共用於 2 項工作")).toBeVisible();
expect(screen.queryByRole("heading", { name: /AI 草稿/ })).toBeNull();
```

Also assert `開啟訪談/收合訪談` and `開啟工作地圖/收合工作地圖` alter in-flow layout without hiding the unassigned section.

- [ ] **Step 2: Verify RED**

Run: `cd apps/web && npm run test -- ConsultantWorkspace.integration.test.tsx`

- [ ] **Step 3: Build the clean in-flow shell**

Use one responsive grid: optional work-map column, flexible document column and optional interview column. Stack on narrow screens; do not use fixed overlays for persistent content. Preserve header, connection, export, unsaved guard and accessible names.

- [ ] **Step 4: Build the hierarchical current editor**

Base local draft persistence on `current_document + revision + workspace_generation + workspace_digest`. Group Tasks by `duty_id`, show empty Duties and one `尚未歸屬` section. Nest all linked O/P/K/S under each Task, label by type plus task-local ordinal, keep stable IDs only for keys/advanced details, and mark shared K/S as shared rather than duplicating records. Keep A/document-level items in their own section without adding AI analysis.

- [ ] **Step 5: Make direct-save scope explicit**

When editing an AI-created entity, show one concise pre-save note naming the affected semantic group count. Save remains one action; add no staging tray or per-field dialog.

- [ ] **Step 6: Verify GREEN and accessibility**

```text
cd apps/web && npm run test -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts
npx tsc --noEmit
npm run lint
```

- [ ] **Step 7: Commit**

```text
git add apps/web/src/features/consultant apps/web/src/shared/api
git commit -m "feat: make the current JD the primary workspace"
```

---

### Task 7: In-document semantic review and final gates

**Files:**
- Create: `apps/web/src/features/consultant/CurrentDocumentReview.tsx`
- Modify: `apps/web/src/features/consultant/CurrentDocumentOutline.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.tsx`
- Modify: `apps/web/src/features/consultant/DocumentChangeEditor.tsx`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Delete: `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- Modify: `docs/design/consultant-runtime.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Main modes: `目前 JD` and `審核變更 N`; `查看已核准版本` is secondary and read-only.
- Controls consume existing changeset/action IDs and send only accept, edit-and-accept or reject.

- [ ] **Step 1: Write failing semantic-review tests**

```tsx
expect(screen.getByText("每月彙整")).toHaveStyle({ textDecoration: "line-through" });
expect(screen.getByText("每週追蹤；重大修法即時通報")).toBeVisible();
expect(screen.getByRole("button", { name: "接受這項變更" })).toBeVisible();
expect(screen.getByRole("button", { name: "拒絕這項變更" })).toBeVisible();
expect(screen.queryByRole("button", { name: /稍後處理/ })).toBeNull();
```

For reassignment, assert one Task is a red departure under old Duty and green arrival under new Duty, with one shared change identity/decision. Selecting one split member must select its whole atomic subgroup.

- [ ] **Step 2: Verify RED**

Run: `cd apps/web && npm run test -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts`

- [ ] **Step 3: Implement document-context review**

Reuse the current hierarchy and decorate affected fields in place. Neutral surfaces dominate; red is only before/removal and green only after/addition. Provide `全部變更` and previous/next group navigation; keep accept/reject controls beside the selected difference and a compact sticky bar for multi-action selection.

- [ ] **Step 4: Add approved-only comparison**

Open `snapshot.approved_document` in a read-only drawer or secondary panel labelled `匯出版本`. Do not create a third editable tab. With pending changes, explain that export excludes them.

- [ ] **Step 5: Update design docs**

Document current projection, approved-only export, direct-edit delta, no-defer review, failure-unlocked chat, conversational correction and responsive in-flow UI. Change AGENTS only if its authority summary would otherwise be wrong.

- [ ] **Step 6: Run full gates**

```text
npm run check-codegen -w @caliburn/job-analysis-contract
cd apps/api && uv run pytest -q
cd apps/web && npm run test && npx tsc --noEmit && npm run lint
npx turbo test
git diff --check
```

The known pre-existing PostgreSQL FK failure may be reported only if its test/signature matches prior evidence; every new failure is fixed.

- [ ] **Step 7: Run real browser validation**

Start the current product, not the HTML prototype, then verify desktop and narrow layouts:

1. open/close interview and work map;
2. Duty -> Task -> OPKS and unassigned content remain visible;
3. frequency review shows crossed-out old and green new value in place;
4. Task reassignment appears at old/new positions but has one decision;
5. accept/reject update current and approved correctly;
6. failed run leaves normal typing and retry available;
7. close/reopen preserves pending current JD;
8. export omits pending AI content.

Every defect first becomes a failing automated test.

- [ ] **Step 8: Recheck product direction**

Re-read ADR 0069 decision 14 and the product-flow research. Confirm no wizard, fake percentage, Task-bound Focus, review-induced chat block, RAG, hidden AI approval or second editable JD.

- [ ] **Step 9: Commit and tag**

```text
git add apps/web docs/design/consultant-runtime.md AGENTS.md
git commit -m "feat: review AI JD changes in document context"
git tag shared-current-jd-v1
```
