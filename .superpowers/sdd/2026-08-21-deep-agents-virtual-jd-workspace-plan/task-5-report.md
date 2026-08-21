# Task 5 report — verified virtual JD candidate publication (fix round 1/5)

## Scope and controller ruling

Task 5 adds only the narrow resource-after-state publication path:

- `candidate_publication.py` parses the canonical candidate resources, computes
  the semantic `DocumentChangeSet`, resolves Evidence, validates Skills and
  review-group handles, and creates `CheckedCandidateReceipt`.
- `state.py` and `graph.py` carry the receipt through the existing LangGraph
  checkpoint.  Check stores only the receipt and never mutates the review
  queue.  Publication moves the exact checked changeset into the existing
  review queue and clears the receipt in the same graph transition.
- `PostgresConsultantRuntime` uses the runtime-owned per-document authority
  lock, current run/source checks, revision CAS, exact resource digest/read-set
  validation, and idempotent check/publication calls.  No second document
  store was introduced.

The controller ruling was applied: this intermediate commit leaves the
existing `CandidateWorkspace`, `active_candidate`, `candidate_tool`,
`context`, and `run_service` seam untouched and loadable.  No compatibility
adapter or alias was added.  Task 6 owns the atomic deletion of that old seam
and its consumers.  No Web, RAG, generic diff engine, new Tool, new store,
workflow product concept, or ADR0060 change is included.

## RED evidence

The required semantic tests were written before the production publication
path.  The initial pure gate failed at import time because the new module did
not exist:

```text
cd apps/api
uv run pytest tests/test_consultant_candidate_publication.py tests/test_consultant_candidate_loop.py -p no:cacheprovider -q
→ ModuleNotFoundError: No module named 'app.consultant.candidate_publication'
```

The graph transition test then failed with the expected unsupported command
before the graph branch was implemented:

```text
cd apps/api
uv run pytest tests/test_consultant_candidate_publication.py -k graph_check_then_publication_moves_exact_receipt_atomically -p no:cacheprovider -q
→ ValueError: unsupported consultant command: check_candidate_document
```

After the PostgreSQL tests were added, their first runs reached the real
database fixture and failed because the runtime port had not yet been added:

```text
cd apps/api
$env:DEBUG='false'
$env:TEST_DATABASE_URL='<approved disposable local PostgreSQL URL>'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run pytest tests/test_consultant_candidate_loop.py -k workspace_check_only_records_receipt_then_publishes_exactly_once -p no:cacheprovider -q
→ AttributeError: PostgresConsultantRuntime has no attribute check_candidate_document

uv run pytest tests/test_consultant_durable_authority_postgres.py -k checked_candidate_stale_digest_run_and_baseline_leave_review_queue_empty -p no:cacheprovider -q
→ AttributeError: PostgresConsultantRuntime has no attribute check_candidate_document
```

One intermediate focused run reported `75 passed, 1 failed`.  The failure was
diagnosed as an indentation regression in the newly appended candidate-loop
test: its original `reopen_document` assertion had been dedented.  Restoring
those two lines made the original test pass; no production behavior was
changed for that repair.

## GREEN evidence

The final required focused PostgreSQL gate used the approved disposable local
database, had no skips, and left the existing fixture cleanup paths in place:

```text
cd apps/api
$env:DEBUG='false'
$env:TEST_DATABASE_URL='<approved disposable local PostgreSQL URL>'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run pytest tests/test_consultant_candidate_publication.py tests/test_consultant_candidate_loop.py tests/test_consultant_durable_authority_postgres.py -p no:cacheprovider -q
→ 78 passed in 147.46s (0:02:27)
```

Relevant existing workspace/candidate regressions:

```text
cd apps/api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run pytest tests/test_consultant_workspace_resources.py tests/test_consultant_evidence_anchor.py tests/test_consultant_workspace_backend.py tests/test_consultant_workspace_tools.py tests/test_consultant_candidate_workspace.py -p no:cacheprovider -q
→ 79 passed in 3.25s
```

Related consultant graph/context/review/run-service regressions against the
same disposable PostgreSQL fixture:

```text
cd apps/api
$env:DEBUG='false'
$env:TEST_DATABASE_URL='<approved disposable local PostgreSQL URL>'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run pytest tests/test_consultant_interview_flow.py tests/test_consultant_document_review.py tests/test_consultant_context.py tests/test_consultant_run_service.py -p no:cacheprovider -q
→ 53 passed in 21.38s
```

Static and whitespace checks:

```text
cd apps/api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run python -m py_compile app\adapters\langgraph\postgres.py app\consultant\candidate_publication.py app\consultant\graph.py app\consultant\state.py
→ passed

cd S:\caliburn\.worktrees\langgraph-consultant-runtime
git diff --check
→ passed with no diff errors
```

## Behavior covered

- Header, Duty, Task, Output, Performance Indicator, Knowledge, and Skill
  edit/create/delete paths emit granular review actions.
- New identity and order allocation is application-owned and deterministic;
  UUIDs use the document/run/canonical handle namespace.
- Task split is represented only as two general Task additions, OPKS
  reconnection revisions, and withdrawal of the old Task.  The resulting
  actions share one application-computed atomic component; no split/merge
  operation is introduced.
- Invalid linkage, unknown handles, invalid Evidence, unloaded Skills, and
  malformed review/dependency closure return actionable issues with no receipt
  and an empty review-queue projection.
- A successful check creates only the durable receipt fields required by the
  brief: run, baseline revision, candidate revision, exact resource digest,
  check call ID, used Skills, and the existing `DocumentChangeSet`.
- Publication rejects changed candidate digest, old run, changed baseline,
  changed document read-set, or changed current source set before any queue
  mutation.
- PostgreSQL coverage verifies check-without-queue-mutation, exact queue
  publication, receipt clearing, stale digest/run/baseline rejection, and
  idempotent publication retry.  The graph transition test verifies the queue
  move and receipt clear are one returned state transition.

## Self-review

The new path reuses the existing `Evidence` resolver, `create_document_changeset`,
`_publish_persisted_changeset`, stable IDs, read-set hashes, review queue, and
runtime-owned per-document authority lock, revision CAS, and graph authority
transition.  Fix round 1 extends the existing Task 4 `CandidateCheckPort` with
the selected and loaded Skill receipts already held by
`workspace.skill_backend`; the workspace Tool forwards those exact values and
Postgres consumes them.  No manager, adapter, store, or second transaction seam
was introduced.

No load-bearing existing domain invariant was found to conflict with the
approved plan.  The persistent false-dirty ADR0060 and the progress ledger
were not modified and are excluded from the Task 5 commit.

## Fix round 1/5 — controller findings and evidence

The controller-verified fixes remain narrow:

- Existing general `_link_required_groups` closure now links OPKS
  `/task_ids` and `/indicator_ids` revisions to same-changeset new-entity
  creators.  The split remains two general Task adds, OPKS reconnect revises,
  and old-Task withdraw; all actions receive one common atomic subgroup and
  existing review commands reject partial acceptance.  No split/merge action
  or specialized service was added.
- Candidate semantic changes now pass through
  `verify_candidate_document_changes` before changeset creation.  K/S text
  without an anchored quote fails closed; receipt Skills come from the
  verifier's returned used IDs.  The default basis uses only loaded Skills and
  an empty loaded Skill set is rejected instead of falling back to selected
  Skills.  Existing application-owned `competency_level` and OPKS evidence
  metadata are handled without weakening source/evidence validation.
- The existing check binding/port forwards
  `workspace.skill_backend.selected_skill_ids` and `.loaded_skill_ids` into the
  Postgres runtime.  The full catalog is no longer hardcoded in that path.
- Publication attaches the existing `CommandReceipt` in the same graph update
  that inserts the exact review bundle and clears `checked_candidate`.
- Scope ruling: this single-process product uses the shared runtime-owned
  per-document `asyncio.Lock` plus existing revision CAS/checkpoint authority.
  No PostgreSQL advisory lock, row lock, distributed lock, or new lock store
  was added or implied.

### Fix-round RED

The new regression assertions were run before the fixes:

```text
cd apps/api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run pytest tests/test_consultant_candidate_publication.py -k "task_split or knowledge_text_change or receipt_uses_loaded or graph_check" -p no:cacheprovider -q
→ 4 failed, 29 deselected
```

The failures were the expected old behavior: K/S text was checked without a
quote, the receipt used selected rather than loaded Skills, split actions had
both `None` and non-`None` subgroup IDs, and publication did not attach the
command receipt.

The binding regression also failed before the port change.  This was the exact
invocation used while both test paths were supplied:

```text
cd apps/api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run pytest tests/test_consultant_candidate_publication.py -k "task_split or knowledge_text_change or receipt_uses_loaded or graph_check" -p no:cacheprovider -q tests/test_consultant_workspace_tools.py -k check_tool_uses_hidden_runtime_and_current_files_channel
→ 1 failed, 56 deselected; TypeError: the check port was missing selected_skill_ids and loaded_skill_ids
```

After the verifier was connected, the first full pure run exposed the existing
verifier's missing `competency_level` allowlist entry, application-owned OPKS
evidence metadata, structural withdraw assumptions, and empty-loaded-basis
exception.  The observed intermediate result was:

```text
cd apps/api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run pytest tests/test_consultant_candidate_publication.py -p no:cacheprovider -q
→ 11 failed, 22 passed
```

### Fix-round GREEN

```text
cd apps/api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run pytest tests/test_consultant_candidate_publication.py -p no:cacheprovider -q
→ 33 passed in 0.47s

uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_workspace_backend.py -p no:cacheprovider -q
→ 37 passed in 2.81s

uv run pytest tests/test_consultant_agent_and_skills.py -p no:cacheprovider -q
→ 39 passed in 1.95s
```

The required real PostgreSQL gate used the approved disposable local database
and had zero skips:

```text
cd apps/api
$env:DEBUG='false'
$env:TEST_DATABASE_URL='<approved disposable local PostgreSQL URL>'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run pytest tests/test_consultant_candidate_publication.py tests/test_consultant_candidate_loop.py tests/test_consultant_durable_authority_postgres.py -p no:cacheprovider -q
→ 80 passed in 147.03s (0:02:27)
```

Related consultant regressions remained green:

```text
uv run pytest tests/test_consultant_interview_flow.py tests/test_consultant_document_review.py tests/test_consultant_context.py tests/test_consultant_run_service.py -p no:cacheprovider -q
→ 53 passed in 21.20s

uv run pytest tests/test_consultant_workspace_resources.py tests/test_consultant_evidence_anchor.py tests/test_consultant_workspace_backend.py tests/test_consultant_workspace_tools.py tests/test_consultant_candidate_workspace.py -p no:cacheprovider -q
→ 79 passed in 2.98s
```

Final fix-round static/whitespace checks:

```text
cd apps/api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task5'
uv run python -m py_compile app\adapters\langgraph\postgres.py app\consultant\candidate_publication.py app\consultant\document_review.py app\consultant\graph.py app\consultant\state.py app\consultant\verification.py app\consultant\workspace_tools.py
→ passed

cd S:\caliburn\.worktrees\langgraph-consultant-runtime
git diff --check
→ passed with no diff errors
```
