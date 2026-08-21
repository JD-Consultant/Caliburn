# Task 6 完成報告：hard-cut virtual JD model interface

## Scope

Branch: `refactor/langgraph-consultant-runtime`
Base: `1b2ef07`
Commit message: `refactor: hard-cut to virtual JD model interface`

`docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md` was already dirty before this task and was not edited, staged, restored, or included. `progress.md` was not edited.

## Exact RED evidence

Before implementation, the new contract test was run with:

```text
uv run pytest tests/test_consultant_task6_contract.py -p no:cacheprovider -q
5 failed, 1 passed
```

The failures covered the old source/candidate Tool surface in agent assembly, the old five-call/default policy, provider-owned quote offsets, full check receipt serialization, and candidate-path lookup-wave accounting. The framework eight-call middleware test was the one passing contract.

## Implemented GREEN contract

The model-facing interface is exactly these seven Tools over one shared five-root Deep Agents workspace:

```text
ls / read_file / grep / write_file / edit_file / delete / check_candidate_document
```

The roots are `/skills`, `/sources`, `/approved`, `/pending`, and the current `/candidate/<run-id>`. The framework `ModelCallLimitMiddleware` permits eight model calls and rejects the ninth. Lookup waves are path-aware and count only `ls`/`read_file`/`grep` reads under the four read-only roots; candidate reads, mutations, and check do not consume lookup waves.

Provider evidence now carries only source handle, exact quote, optional occurrence, and Skill IDs. The existing catalog/resolver deterministically produces the rich source UUID and quote offsets. Final candidate publication carries only revision, digest, and ordered action handles. The check observation is compact and excludes the durable receipt, changeset, and full before/after payload. Context retains focus, understanding, gaps, progress, pending counts, required clarification, and the exact employee turn while full details remain in VFS projections.

## Task5 safety migration

The current `check -> receipt -> publish -> clear -> replay` regression from the mixed legacy candidate-loop file was migrated to:

```text
tests/test_consultant_durable_authority_postgres.py::test_workspace_check_only_records_receipt_then_publishes_once_and_replays
```

It asserts that check leaves `review_queue` empty, persists `checked_candidate`, publication creates exactly one review bundle and clears the checked receipt, one publication command receipt is durable, and exact publication replay is idempotent. A companion regression proves changed post-check files fail closed without mutating the queue or clearing the receipt.

Task 6 does not claim the complete run-level lifecycle migration. Employee authority, check-repair-recheck, 9-accept-1-reject with decision memory, and direct-edit-stale full-run scenarios remain pending the already-planned Task 7 real-agent/PostgreSQL scope. This task preserves the current check/publication/receipt PostgreSQL canary without recreating the retired candidate loop or Task 7 E2E suite.

## Exact GREEN evidence

```text
uv run pytest tests/test_consultant_task6_contract.py -p no:cacheprovider -q
6 passed in 1.56s

uv run pytest tests/test_consultant_model_output.py tests/test_consultant_model_runtime.py tests/test_consultant_run_service.py tests/test_consultant_hard_cut.py -p no:cacheprovider -q
39 passed in 1.89s

uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_workspace_backend.py tests/test_consultant_candidate_publication.py -p no:cacheprovider -q
70 passed in 2.75s

TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn_reviewed \
uv run pytest tests/test_consultant_durable_authority_postgres.py -p no:cacheprovider -q
10 passed in 18.12s

TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn_reviewed \
uv run pytest -p no:cacheprovider -q
257 passed in 26.20s
```

Additional current context/agent/runtime regression: `56 passed`. `git diff --check` was clean. `uv run python -m compileall -q app tests` completed with no output or errors.

## Review fix round 1/5

The review fixes remain within the existing catalog, VFS, checked-receipt, and
context seams:

- Check observations and final `OutputCandidatePublication` /
  `CandidatePublication` now expose ordered `action-001`-style aliases only.
  The deterministic pending-action mapping is reused from
  `workspace_resources`; the checked receipt records the ordered aliases next
  to its internal authority changeset. Runtime and graph publication compare
  revision, digest, aliases, receipt action count/order, and the actual current
  response files before authority uses receipt UUIDs.
- `grep` with no path or `/` is counted as a composite-workspace lookup wave;
  explicit candidate paths and candidate mutations/check remain free.
- Required/recent source selection and the unused approved-document slice were
  deleted. Context reads and records only the current employee turn while
  historical/current-only source details remain VFS-on-demand.

The fix-round TDD gate was first run against the new tests and failed with
`17 failed, 74 passed in 2.13s`. The corrected implementation then produced:

```text
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_model_output.py tests/test_consultant_task6_contract.py tests/test_consultant_agent_and_skills.py tests/test_consultant_context.py tests/test_consultant_candidate_publication.py tests/test_consultant_workspace_tools.py -p no:cacheprovider -q
→ 91 passed in 1.79s

$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_task6_contract.py tests/test_consultant_model_output.py tests/test_consultant_model_runtime.py tests/test_consultant_run_service.py tests/test_consultant_context.py tests/test_consultant_agent_and_skills.py -p no:cacheprovider -q
→ 54 passed in 1.80s

$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_workspace_backend.py tests/test_consultant_candidate_publication.py -p no:cacheprovider -q
→ 70 passed in 2.75s

$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_reviewed'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_durable_authority_postgres.py -p no:cacheprovider -q
→ 10 passed in 17.74s, zero skipped

$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_reviewed'; $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest -p no:cacheprovider -q
→ 259 passed in 25.28s

AST hard-cut → python_files=47, forbidden_imports=[], retired_files_present=[]
hard-cut rg → 0 matches
uv run python -m compileall -q app tests → passed with no output
git diff --check → passed with no diff errors
```

## Schema and hard-cut metrics

Provider `ConsultantModelOutput` schema measurement:

```text
properties=59, optional=1, unions=1, open_objects=0, bytes=8971
top-level properties=visible_reply, analysis_bases, reply_basis_ordinal,
used_skill_ids, understanding_changes, attention_changes, gaps,
candidate_publication, question, sufficiency
```

The seven workspace tool schema measurements asserted by the current VFS test are:

```text
ls:                       properties=1 optional=0 unions=0 open_objects=1 depth=3 bytes=165
read_file:                properties=3 optional=2 unions=0 open_objects=1 depth=3 bytes=433
grep:                     properties=5 optional=4 unions=3 open_objects=1 depth=4 bytes=1598
write_file:               properties=2 optional=0 unions=0 open_objects=1 depth=3 bytes=304
edit_file:                properties=4 optional=1 unions=0 open_objects=1 depth=3 bytes=613
delete:                   properties=1 optional=0 unions=0 open_objects=1 depth=3 bytes=172
check_candidate_document: properties=0 optional=0 unions=0 open_objects=0 depth=2 bytes=62
```

AST hard-cut command output:

```text
python_files=47, forbidden_imports=[], retired_files_present=[]
```

Production/test `rg` hard-cut scan for retired module names, aliases, `active_candidate`, source business Tools, provider quote-offset wire, and the old candidate Tool returned:

```text
hard-cut rg: 0 matches
```

## Net deletion / overdesign audit

- Deleted the three retired production implementations: `candidate_tool.py`, `candidate_wire.py`, and `candidate_workspace.py`.
- Deleted tests that only exercised those implementations, and replaced mixed agent/context/PostgreSQL files with current-only VFS, publication, context, and authority canaries.
- Removed the direct Skill backend compatibility adapter, the workspace backend alias, `active_candidate`, candidate staging command/state, and all model-facing employee-source business Tools.
- Reused the existing LangChain/Deep Agents middleware, `PackageSkillBackend`, FilesystemMiddleware, prompt-cache/context middleware, model usage/budget/attempt receipts, catalog/resolver, checked receipt, verifier, publication, and authority graph. No Tool Search, router, new loop, new store, model/provider-only path, sync database, RAG, eval platform, auto-accept, capability level, or A was added.
- No product-flow research implementation example or historical ADR was migrated into the current surface; ADR0064’s catalog-backed deterministic resolver direction is the implementation authority.
