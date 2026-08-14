# Task 3 Evidence Report — Fifth Candidate Edit Tool

## Scope and starting state

- Worktree: `S:\caliburn\.worktrees\langgraph-consultant-runtime`
- Branch: `refactor/langgraph-consultant-runtime`
- Starting HEAD: `aaa5e0f4f89844a2147b3386962aace1d4e62a69`
- Pre-existing dirty file: `docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md` (line-ending-only stat). It was not edited or staged.
- No subagents, Task 4 work, push, merge, tag, Tool Search, MCP, RAG, shell/VFS Tool, multi-agent, or auto-accept were added.

## TDD evidence

### Baseline

The first baseline invocation could not open the user-level uv cache (`Access is denied`), before collection. The same read-only test command was rerun with the repo-scoped reviewed cache:

```powershell
$env:PYTHONUTF8='1'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest -p no:cacheprovider tests/test_consultant_agent_and_skills.py tests/test_consultant_model_runtime.py -q
```

Result: `65 passed in 1.50s`.

### RED

New candidate Tool tests were written before any production code. The brief's RED command was run:

```powershell
$env:PYTHONUTF8='1'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest -p no:cacheprovider tests/test_consultant_candidate_tool.py tests/test_consultant_agent_and_skills.py -q
```

Result: expected collection failure, `ModuleNotFoundError: No module named 'app.consultant.candidate_tool'` (`1 error in 1.12s`).

### GREEN

The brief's final focused gate was run after the minimal implementation and then rerun after the final schema/surface assertions:

```powershell
$env:PYTHONUTF8='1'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest -p no:cacheprovider tests/test_consultant_candidate_tool.py tests/test_consultant_agent_and_skills.py tests/test_consultant_model_runtime.py -q
```

Final result: `70 passed in 1.56s`.

The added receipt projection was also checked through its pure workspace and existing durable PostgreSQL test module:

```powershell
$env:PYTHONUTF8='1'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest -p no:cacheprovider tests/test_consultant_candidate_workspace.py tests/test_consultant_durable_authority_postgres.py -q
```

Result: `18 passed, 30 skipped in 0.63s`. PostgreSQL cases were skipped because no PostgreSQL test URL was supplied; this is not claimed as a PostgreSQL integration pass.

## Implementation and audit

- One model-facing Tool exists: `job_document_candidate_edit`.
- Its `tool_call_schema is CandidateEditBatch`; the schema has exactly the four batch fields and rejects extra fields. `ToolRuntime` remains only in a private execution-validation input schema so LangChain can inject the provider Tool call ID without exposing it to the model.
- `CandidateEditToolBinding` closes over document ID, run ID, baseline revision, selected Skills and stage port. Loaded Skills come from `PackageSkillBackend.loaded_skill_ids`; the Tool does not use raw state or checkpoints.
- Successful Tool JSON is serialized from the persisted `CandidateEditReceipt`, whose action projections are copied from the actual materialized `DocumentChangeSet`: revision/digest, before/after, action IDs, dependency IDs, atomic subgroup IDs, status/stale reason and supersession IDs.
- Deterministic candidate mapping, document, Evidence, current-source and stale-base failures are converted to compact rejected JSON with baseline/candidate revisions and actionable issues. The Tool has only narrow catches; unknown infrastructure exceptions propagate for existing retry/failure classification.
- Explicit agent binding produces exactly five Tools: `read_file`, three employee-source read Tools and the candidate Tool. Candidate edit is omitted from lookup waves but is covered by the unchanged total Tool cap. The interactive model-call ceiling is five; the sixth is rejected.
- Candidate staging continues to use the existing LangGraph graph, PostgreSQL Saver/Store and document lock. There is no inner checkpointer/store/table and no approved-document write edge.

## Authorized file-list deviation

The brief listed `candidate_workspace.py` and `postgres.py` only in the hard constraints, not its initial files block. They were changed under the brief's explicit authorization because the previous `CandidateEditReceipt` could not return the actual materialized action projection. Focused tests were correspondingly extended in:

- `apps/api/tests/test_consultant_candidate_workspace.py`
- `apps/api/tests/test_consultant_durable_authority_postgres.py`

No other file-list deviation is present.

## Pre-review PostgreSQL fix

Controller RED (against `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn`):

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn'; uv run pytest -p no:cacheprovider tests/test_consultant_candidate_workspace.py tests/test_consultant_durable_authority_postgres.py -q
```

Result reported by the controller: `2 failed, 46 passed in 86.59s`; both failures asserted pre-Task-3 raw exceptions rather than the intentional `CandidateEditRejected` contract.

The two affected PostgreSQL regression functions now assert `CandidateEditRejected` with the current baseline/candidate revisions, exact actionable issue text, and unchanged candidate/approved state. The persisted-source replay additionally asserts `SourceConflict` is retained as `__cause__`. While reaching the previously masked second assertion in the first function, the same deterministic adapter contract was also asserted for its unbound entity handle: compact rejection plus `CandidateWireMappingError` cause.

Focused RED/GREEN evidence:

- The two revised tests first exposed that masked wire-mapping expectation (`CandidateWireMappingError` rather than the translated rejection); after aligning that regression assertion, the targeted PostgreSQL command passed: `2 passed, 30 deselected in 4.17s`.
- Task 3 focused gate: `70 passed in 1.52s`.
- Real PostgreSQL gate with `TEST_DATABASE_URL`: `48 passed in 86.55s (0:01:26)`, zero skips.

### Sequential pre-review rerun and residue resolution

The earlier nonzero residue was diagnosed as test-run concurrency, not a candidate persistence defect: the local disposable database was zero before the overlapping 07:25–07:28 invocations; `consultant_documents` was zero afterwards, and every residual checkpoint thread and Store prefix/key matched the controller's explicit orphan inventory. After owner authorization, parameterized SQL deleted only those exact rows in FK-safe order: `77` `checkpoint_writes`, `29` `checkpoint_blobs`, `22` `checkpoints`, and one matching Store row. No truncate, drop, catalog row, or unlisted namespace was touched.

The gates were then run strictly sequentially:

```powershell
$env:PYTHONUTF8='1'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest -p no:cacheprovider tests/test_consultant_candidate_tool.py tests/test_consultant_agent_and_skills.py tests/test_consultant_model_runtime.py -q
```

Result: `70 passed in 1.48s`.

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn'; $env:PYTHONUTF8='1'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest -p no:cacheprovider tests/test_consultant_candidate_workspace.py tests/test_consultant_durable_authority_postgres.py -q
```

Result: `48 passed in 86.45s (0:01:26)`, zero skips. A post-gate read-only query confirmed all five tables are zero: `consultant_documents`, `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, and `store`.

## Concern

No remaining Task 3 pre-review concern. The regression update changes test expectations only; sequential real-PostgreSQL verification did not reveal a product cleanup defect.

## Review round: replayed receipt evidence

Review finding A (Task 2 checkpoint backward compatibility) is technically true only for a deployed checkpoint written before the private receipt projection existed. It is not a release blocker here: Task 2 and Task 3 are unpushed, unmerged commits on the same big-bang feature branch; no product deployment or release occurred at the intermediate Task 2 SHA; and the disposable local database was verified empty. Under the current-only direction, no speculative migration, versioning, or compatibility path was added for that unreleased intermediate state.

Review finding B was confirmed. Exact replay previously called `_require_current_committed_sources` with `active.changeset.source_ids`, which belongs to the newest candidate revision, rather than the replayed Tool receipt. `CandidateToolReceipt` now persists its own private `source_ids` projection from that revision's materialized `DocumentChangeSet`; the latest receipt validator requires it to equal `workspace.changeset.source_ids`; and replay validates `replay.source_ids`. `CandidateEditReceipt` and model-facing applied JSON remain unchanged and do not expose source IDs. Infrastructure errors are still not caught by this replay translation path.

TDD evidence for the confirmed bug:

- Initial fixture attempt failed before the target branch with `CandidateEditRejected: expected baseline revision 2, found 1`; adding source B after candidate revision 1 correctly clears the active candidate under existing authority rules. The fixture was corrected by storing B before both candidate revisions.
- RED: the corrected real-PostgreSQL test built revision 1 from source A and revision 2 from source B, then made only A superseded while preserving the checkpoint. It asserted latest `changeset.source_ids == (B,)` and failed as required with `Failed: DID NOT RAISE CandidateEditRejected`, proving replay incorrectly used latest evidence.
- GREEN: the same regression passed (`1 passed, 32 deselected in 3.35s`). It proves revision-1 replay rejects with `CandidateEditRejected` caused by `SourceConflict` for A, leaves candidate/document/review state unchanged, and revision-2 exact replay still succeeds.
- Additional workspace invariant coverage: `17 passed in 0.25s`, including private receipt/source projection matching and confirmation that public `CandidateEditReceipt` JSON omits `source_ids`.
- Sequential final gates: Task 3 non-DB focused `70 passed in 1.51s`; real PostgreSQL candidate workspace/durable authority `50 passed in 89.43s (0:01:29)`, zero skips. Post-gate query confirmed `consultant_documents`, `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, and `store` are all zero.
