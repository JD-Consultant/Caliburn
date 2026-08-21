# Task 7 完成報告：close the virtual JD authority loop

## Scope

- Worktree：`S:\caliburn\.worktrees\langgraph-consultant-runtime`
- Branch：`refactor/langgraph-consultant-runtime`
- Base：`02d06aa5977bddae448afd29a09055b0fe4e3299`
- Commit message：`test: close virtual JD authority loop`
- Commit SHA：請在該 worktree 執行 `git rev-parse HEAD` 取得。

本任務維持一位 local employee-facing consultant、current run 的 virtual candidate JD、既有 LangChain／LangGraph／Deep Agents／PostgreSQL runtime 與唯一 employee authority graph。沒有恢復 retired API／Tool／candidate class，也沒有新增 store、orchestrator、diff engine、router、sync DB、VFS persistence layer 或第二個 scripted model。

## Exact changed files

- `apps/api/app/consultant/graph.py`
  - direct-edit authority transition 明確清除尚未 publication 的 `checked_candidate` receipt。
- `apps/api/app/consultant/workspace_backend.py`
  - 將 raw `/pending` dump 收窄為 current `WorkspaceCatalog`／`pending_action_handles` 驅動的 handle-based semantic projection。
- `apps/api/tests/test_consultant_candidate_loop.py`
  - 新增六個 current-only PostgreSQL lifecycle tests；中央 scenario 使用真 `create_agent`、單一 scripted model、真七個 workspace/check Tools。
- `docs/design/consultant-runtime.md`
  - 同步 `/pending` public-internal VFS shape；僅記錄 alias、semantic fields、`approved: false` 與正式 UUID 不外露規則。
- 本報告：`.superpowers/sdd/2026-08-21-deep-agents-virtual-jd-workspace-plan/task-7-report.md`

明確未修改、未 stage、未 restore、未納入 commit：

- `docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`（task 前已 dirty）
- `progress.md`

## RED / GREEN evidence

### Initial harness-only REDs（非 product RED）

第一次執行新測試時，先修正三個 harness contract 問題，沒有因此修改 production：

- `ScriptedConsultantModel responses Field required`：test double 明確提供 `responses=[]`。
- `ConsultantOutputMappingError`：scripted sufficiency 使用符合 min-length 的 continuing benefit。
- `AttributeError: 'dict' object has no attribute 'actions'`：測試依現行 dict-shaped check result 取值。

另一次嘗試把 scalar duty relation 放入 verifier 不允許的直接 revise，得到：
`candidate verification failed: revise operation requires one non-structural document field path`。依 current contract 將 defer scenario 保持為兩個獨立 header actions；structural relation proof 改放在既有 atomic split scenario，沒有放寬 verifier。

### Valid product REDs

1. 原始 pending lifecycle RED：

   ```text
   cd apps/api
   $env:PYTHONUTF8='1'; $env:DEBUG='false'; $env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_reviewed'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_candidate_loop.py -p no:cacheprovider -q
   ```

   舊 raw projection 對模型需要的 `/reviews/review-001.json` 不存在：
   `AssertionError: File '/reviews/review-001.json' not found`，result `1 failed in 5.24s`。

2. checked-but-unpublished RED：同一六測試 command 在補上 receipt assertion 後為 `1 failed, 5 passed`；direct edit 後：
   `assert (await runtime.raw_state(document_id))["checked_candidate"] is None`，實際 receipt 仍非 `None`。這是 `graph.py` 唯一的 state-transition production root cause。

3. handle projection RED：既有 split candidate 的 `/opks/*/task_ids` action 將 UUID list 原樣放入 pending `before`／`after`；完整 pending surface 的 UUID regex 命中。這是 `workspace_backend.py` 的 action-path mapping root cause，不是 generic sanitizer 問題。

### GREEN

最後六個 scenario command：

```text
$env:PYTHONUTF8='1'; $env:DEBUG='false'; $env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_reviewed'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_candidate_loop.py -p no:cacheprovider -q
6 passed in 21.24s
```

六個 scenario 為：

1. 真 agent：exact source + Skill VFS reads → bad check → repair → good check → final receipt reference → pending-only publication。
2. partial accept/reject：accepted header 進 `/approved`，rejected O 不進 approved／新 candidate baseline，`/pending` 保留 `approved=false`、status、reason。
3. defer/direct edit：兩個獨立 pending actions；只改其中一個欄位時只有衝突 action `STALE`，另一個維持 `DEFERRED`／可 review，approved 只含 direct edit。
4. atomic Task split：Task／OPKS structural relation 的 pending before／after 以 handles 表示，split 不能部分接受。
5. 新 run 看不到舊 run scratch。
6. PostgreSQL failed-run restart 與 exact admission replay。

Partial scenario 刻意使用兩個獨立 action，而非建立十個近乎相同的 semantic action。這是 brief 允許的 smallest-equivalent test minimization：仍證明 independent accept/reject 與 rejected-O memory；不是產品行為改成只支援兩個 action。

## Required gate results

所有 PostgreSQL command 都使用 explicit disposable URL，結果沒有 skip。

```text
uv run pytest tests/test_consultant_candidate_loop.py tests/test_consultant_durable_authority_postgres.py tests/test_consultant_interview_flow.py tests/test_consultant_context.py tests/test_app_wiring.py -p no:cacheprovider -q
27 passed in 39.43s

uv run pytest tests/test_consultant_task6_contract.py tests/test_consultant_agent_and_skills.py tests/test_consultant_context.py -p no:cacheprovider -q
20 passed in 1.62s

uv run pytest tests/test_consultant_model_output.py tests/test_consultant_model_runtime.py tests/test_consultant_run_service.py tests/test_consultant_hard_cut.py -p no:cacheprovider -q
39 passed in 2.18s

uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_workspace_backend.py tests/test_consultant_candidate_publication.py -p no:cacheprovider -q
70 passed in 3.12s

uv run pytest tests/test_consultant_candidate_loop.py tests/test_consultant_durable_authority_postgres.py -p no:cacheprovider -q
16 passed in 38.51s

uv run pytest -p no:cacheprovider -q
266 passed in 44.97s

uv run python -m compileall -q app tests
exit 0; no output

git diff --check
exit 0; only expected LF→CRLF working-copy warnings, including the pre-existing ADR0060.
```

## `/pending` projection

The projection is read-only and not approved truth:

- `/index.json`：`approved: false`、overall status、stable-per-snapshot `review-###`／`action-###` handles。
- `/reviews/review-###.json`：`approved: false`、status、summary、action handles、dependency handles。
- `/actions/action-###.json`：handle、`approved: false`、status、operation、handle-based path／targets、semantic before／after、dependency handles；rejected／stale action includes decision reason。

Formal changeset/action/dependency/source UUID、authority revision 與 raw durable payload 不會進入 pending paths 或 JSON。Known `duty_id`／`task_id`／`task_ids`／`indicator_ids` relations are mapped by explicit action-path semantics and existing `WorkspaceCatalog`; this is not a generic recursive UUID sanitizer or a second projection framework. Tests scan emitted pending paths plus all emitted JSON with a UUID-shaped regex.

## North-star audit

- One consultant、single current run workspace；沒有 multi-agent、RAG、Reference、A/capability analysis、auto-accept、UI 或 formal eval platform。
- Employee authority remains the only path to approved JD：check/final only create pending review；accept、edit-accept、reject、defer、direct-edit remain graph authority commands。
- Approved／pending separation is explicit；partial rejection memory is readable on demand and never overlaid into approved or a new run baseline。
- Dynamic Duty／Task／OPKS structure remains supported；split relation handles preserve current catalog identity without exposing formal IDs。
- Exact employee words／corrections remain in the existing source and authority runtime; direct edit invalidates checked candidate and stales only the conflicting pending action.
- Focus、gaps、progress、required clarification、close/reopen、restart/idempotence remain owned by existing checkpoint/state components; no context duplication was added。
- Compact prompt remains unchanged；full approved/pending details stay in `/approved` and `/pending`, and only the exact current employee turn is full injected context。

## Overdesign audit and deviations

- Reused `WorkspaceCatalog`、`pending_action_handles`、existing candidate parser/check/publication/review/StateBackend and existing PostgreSQL graph。
- Added no new Tool, store, document model, diff engine, router, serializer framework, persistence layer, sync database path, or scripted model。
- Production additions are limited to one receipt invalidation transition and one small explicit pending action semantic projection. The projection whitelists only the semantic fields proven by the lifecycle actions; it does not recursively sanitize arbitrary durable payloads.
- Pending helper necessity audit：
  - `_pending_status` is needed because `/index.json` and each review need a deterministic status for empty, uniform, and mixed action states; it cannot be deleted without duplicating status aggregation or exposing raw enums.
  - `_pending_dependency_handles` is needed to preserve review ordering information while replacing formal dependency IDs with usable aliases; it cannot be removed while the brief requires dependency information without UUIDs.
  - `_pending_action_projection` is the single assembly point for `approved`、status、operation、semantic values、targets、dependencies and decision reason; inlining it would duplicate the same public shape for every action without reducing behavior.
  - `_pending_action_value` is the smallest action-path seam proven by the split RED: only known `duty_id`／`task_id`／`task_ids`／`indicator_ids` paths are mapped to catalog handles. Deleting it would reproduce the UUID leak; broadening it into a generic sanitizer would violate the brief.
  - `_pending_path` is needed to replace entity UUIDs in model-facing paths with existing catalog handles; `_pending_target_handles` is separately needed because collection ADD actions can identify their targets only through action path/after semantics. Both reuse `WorkspaceCatalog` and have no new identity abstraction.
  - `_pending_semantic_value` is needed to retain human-readable before/after content while omitting formal IDs, evidence UUIDs and durable-only fields. Its keys are an explicit semantic allowlist, not a general recursive UUID scrubber. Removing it would either leak raw durable payloads or move the same filtering into duplicated call sites.
  - No helper can be removed without dropping one of the tested invariants; the only possible further reduction would be mechanical inlining, which would increase duplication and make the UUID/semantic boundary less auditable. No additional abstraction is justified by the six scenarios.
- The brief's 9-accept/1-reject setup was minimized to two independent actions (header + O) because the invariant, not the count, is under test. This is recorded in both the test and this report.
- Two invalid fixture attempts (`/notes` and `/occupation_name`) were rejected by the current candidate verifier; tests use the already-supported `/job_title`／`/work_description` contract instead. No verifier/product contract was broadened.
- No VFS persistence layer was added; checked receipt and candidate files remain existing graph/runtime state.

## Commit

The single task commit is created after this report and uses exactly:

```text
test: close virtual JD authority loop
```

Commit SHA: run `git rev-parse HEAD` in this worktree to obtain it.

## Review round 1/5

### RED and root causes

- The fresh structural-relation regression was a valid product RED: after `edit_and_accept_changes`, an action such as `/tasks/<handle>/task_ids` still emitted the formal UUID in `employee_after` on the accepted-action pending surface. The cause was the existing `_pending_action_projection` branch calling `_pending_semantic_value` without the action path.
- The first scratch assertion that called `StateBackend` directly produced a framework-only RED because the real backend requires LangGraph execution context. It was corrected in the test harness with the existing `FilesystemMiddleware` and `ToolNode`; no production isolation layer was added.
- The defer/direct-edit evidence now uses the latest revision and accepts only the independent `/work_description` action. The conflicting `/job_title` action remains stale and absent from approved. The new-run evidence performs a real first-run scratch write/read, then real second-run read/ls/glob attempts against the old run path.

### GREEN and minimal fix

- The six existing lifecycle scenarios remain the only full-agent scenarios. The partial-review fixture keeps two independent semantic actions as the brief's smallest-equivalent proof of independent accept/reject and rejected-O memory; this is a test minimization, not a product cardinality change.
- Production change is one path-aware reuse in `workspace_backend.py`: `employee_after` now goes through `_pending_action_value(catalog, action.path, ...)`, so the existing explicit scalar/list relation mapping applies to both before and after values. No `graph.py` change was needed.
- The test-only filesystem probe runs existing framework tools inside a real graph state context. It adds no Tool, store, serializer, VFS persistence layer, or second scripted model.

### Changed files in this review round

- `apps/api/app/consultant/workspace_backend.py`
- `apps/api/tests/test_consultant_candidate_loop.py`
- `.superpowers/sdd/2026-08-21-deep-agents-virtual-jd-workspace-plan/task-7-report.md`

### Review gate commands and results

All PostgreSQL commands used the explicit disposable `TEST_DATABASE_URL` from the Task 7 gate instructions and completed with zero skips. The following commands were rerun and passed:

```text
uv run pytest tests/test_consultant_candidate_loop.py -p no:cacheprovider -q
uv run pytest tests/test_consultant_candidate_loop.py tests/test_consultant_durable_authority_postgres.py tests/test_consultant_interview_flow.py tests/test_consultant_context.py tests/test_app_wiring.py -p no:cacheprovider -q
uv run pytest tests/test_consultant_task6_contract.py tests/test_consultant_agent_and_skills.py tests/test_consultant_context.py -p no:cacheprovider -q
uv run pytest tests/test_consultant_model_output.py tests/test_consultant_model_runtime.py tests/test_consultant_run_service.py tests/test_consultant_hard_cut.py -p no:cacheprovider -q
uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_workspace_backend.py tests/test_consultant_candidate_publication.py -p no:cacheprovider -q
uv run pytest tests/test_consultant_candidate_loop.py tests/test_consultant_durable_authority_postgres.py -p no:cacheprovider -q
uv run pytest -p no:cacheprovider -q
uv run python -m compileall -q app tests
git diff --check
```

### North-star and overdesign audit

The north star remains intact: one employee-facing consultant, employee-only authority, no hidden acceptance, dynamic Duty/Task/OPKS editing, exact employee corrections preserved, and no UI/VFS detail leakage. Approved truth is still changed only by the existing authority graph; `/pending` remains a read-only, `approved: false` semantic projection.

Each pending helper remains justified by a proven surface: `_pending_action_value` for path-specific scalar/list structural relations; `_pending_action_projection` for the shared action envelope; `_pending_path` and `_pending_target_handles` for model-facing identity paths and collection targets; `_pending_dependency_handles` for review dependency visibility; `_pending_semantic_value` for the explicit human-readable semantic allowlist; and `_pending_status` for deterministic aggregate status. None can be removed without either reintroducing a tested UUID leak, losing review context, or duplicating the same public shape. No helper was generalized, and no further reduction is justified without weakening one of the six lifecycle invariants.

### Review commit

Create the review commit with exactly:

```text
fix: close Task 7 review gaps
```

After commit, obtain the reproducible identifier with `git rev-parse HEAD` in this worktree; no SHA or commit count is recorded here.
