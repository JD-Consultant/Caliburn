# Memory Foundation Isolated Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:using-git-worktrees` before execution, then `superpowers:executing-plans` or `superpowers:subagent-driven-development` task by task. Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before any completion claim.

**Status:** Approved for isolated spike only. This plan does not authorize production integration, an ADR status change, RAG, UI work, or a push.

**Goal:** Determine, with the smallest credible experiment, whether the pinned LangGraph PostgreSQL Saver/Store plus a public LangMem semantic-writer interface can preserve one JD's detailed, revisable Memory across process reconstruction and bounded replay without scope leaks, duplicate logical Memory, hidden model-call growth, or a second authority system.

**Architecture:** Build an experiment-only Python project under `docs/experiments/2026-09-02-memory-foundation/`. PostgreSQL Store owns long-term source and semantic Memory; PostgreSQL Checkpointer owns only the minimal durable test run. The harness compares LangMem core manager (C1) and Store manager (C2) through their public APIs, eliminates an arm when its documented contract requires an out-of-scope dependency, and runs a two-invocation Luna smoke only for arms that pass deterministic gates. Production `apps/api`, `apps/web`, contracts, migrations, dependency locks, and runtime authority remain unchanged.

**Tech Stack:** Python 3.13; a separate `uv` project and lock; `langchain==1.3.15`; `langgraph==1.2.11`; `langgraph-checkpoint-postgres==3.1.2`; `langchain-openrouter==0.2.7`; `langmem==0.0.30`; PostgreSQL; pytest/pytest-asyncio; the existing `ReceiptChatOpenRouter` and model-attempt receipt types for the live smoke only.

**Design authority:**

- [`Memory Foundation 最小垂直切片設計`](../specs/2026-09-02-memory-foundation-vertical-slice-design.md), approved baseline SHA-256 `FC0BFDD02C4201388BD2F7FC4E4877928BF82B53C67D0952D205AACAB553E55C`.
- [`Design Review Packet`](../specs/2026-09-02-memory-foundation-design-review-packet.md), final verdict `Approve for isolated spike`.
- [`Inventory/versioning/provenance revalidation`](../specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md).
- [`Earlier LangMem narrow experiment`](../specs/2026-08-29-langmem-domain-semantic-memory-spike-experiment.md); use it as prior evidence, not as proof of PostgreSQL durability or replay.

## Non-negotiable constraints

- Work in an isolated worktree/branch. Before every write, confirm `pwd` and `git branch --show-current`.
- Never stage, revert, clean, or otherwise absorb unrelated dirty files from the main checkout.
- Keep all new executable code, tests, fixtures, trial artifacts, and dependency lock inside `docs/experiments/2026-09-02-memory-foundation/`.
- Do not modify `apps/api`, `apps/web`, `packages/*`, production migrations, `apps/api/uv.lock`, Docker Compose, ADRs, or production runtime setup.
- Require an explicitly supplied local disposable `MEMORY_SPIKE_DATABASE_URL` plus `MEMORY_SPIKE_EXPECTED_DATABASE`. The experiment runtime must reject a non-loopback host, a database name that does not match the explicit expected name, a URL equal to the app's configured production database, or a database name without the `memory_spike` marker. Never fall back to production `DATABASE_URL`; namespace every Store item and thread with a fresh experiment run ID.
- Use only anonymous synthetic fixture data. Load only the OpenRouter key/base URL from `apps/api/.env`; never save the key or an unredacted environment dump.
- Do not add embedding, Qdrant, RAG, a query model, a revision/receipt/manifest table, an outbox, a custom repository, a second agent loop, or an unbounded retry.
- C2 may be eliminated in Stage 0. Do not add infrastructure merely to keep two candidates alive. If both candidates fail, stop before the live smoke and report that result.
- Final-audit exact inventory uses one `cap + 1` exact-leaf read at offset zero. It is not normal recall, cursor pagination, or a production guarantee above the configured cap.
- Per eligible candidate, allow at most two Luna provider invocations total, including every framework repair/retry. Configure model/SDK retries to zero and LangMem `max_steps=1`. If call 1 consumes more than one provider attempt, do not start call 2; if a third attempt is observed or required, fail that arm.
- Do not fabricate `results.csv`, trial outputs, costs, or `report.md`. Create them only from an actual run, including failures and eliminated arms.
- Each task ends with a focused commit. Do not push.

## Experiment layout

```text
docs/experiments/2026-09-02-memory-foundation/
├─ README.md
├─ rubric.md
├─ pyproject.toml
├─ uv.lock
├─ artifacts.json
├─ cases/
│  └─ cross-round-memory-v1.json
├─ src/memory_foundation_spike/
│  ├─ __init__.py
│  ├─ artifacts.py
│  ├─ contracts.py
│  ├─ scope.py
│  ├─ runtime.py
│  ├─ postgres_store.py
│  ├─ candidates.py
│  ├─ durable_graph.py
│  ├─ fixtures.py
│  ├─ snapshots.py
│  └─ live_smoke.py
├─ tests/
│  ├─ test_artifact_contract.py
│  ├─ test_postgres_store_contract.py
│  ├─ test_exact_inventory.py
│  ├─ test_candidate_contracts.py
│  └─ test_durable_replay.py
├─ trials/                  # created by actual live run
├─ results.csv              # created from actual observations only
└─ report.md                # created after all gates run
```

## Execution preflight

- [ ] Use `superpowers:using-git-worktrees` to create an isolated `codex/memory-foundation-spike` worktree from the reviewed branch baseline. If approved research files are not committed yet, bring only the approved design/review/plan files into the worktree; do not copy unrelated working-tree changes.
- [ ] In the new worktree run `Get-Location`, `git branch --show-current`, `git status --short`, and `git check-ignore .worktrees` (when `.worktrees` is used). Stop if the location or branch is wrong.
- [ ] Recompute the approved design hash before work begins:

```powershell
$actual=(Get-FileHash -Algorithm SHA256 -LiteralPath 'docs\specs\2026-09-02-memory-foundation-vertical-slice-design.md').Hash
if ($actual -ne 'FC0BFDD02C4201388BD2F7FC4E4877928BF82B53C67D0952D205AACAB553E55C') { throw "reviewed design baseline changed: $actual" }
```

- [ ] Capture `$spikeBase=(git rev-parse HEAD)` and record that exact source commit, Python/uv/PostgreSQL versions, and test database host/database name in the experiment README/artifact contract without recording credentials.
- [ ] Set `MEMORY_SPIKE_DATABASE_URL` and `MEMORY_SPIKE_EXPECTED_DATABASE` explicitly to a dedicated local database such as `caliburn_memory_spike`. The shared experiment runtime must normalize the psycopg URL, query `current_database()`, reject a mismatch/production DSN/non-loopback host, and idempotently call official `AsyncPostgresStore.setup()` and `AsyncPostgresSaver.setup()` only on that verified database.

---

### Task 1: Freeze the experiment contract and exact dependency artifact

**Files:**

- Create: `docs/experiments/2026-09-02-memory-foundation/README.md`
- Create: `docs/experiments/2026-09-02-memory-foundation/rubric.md`
- Create: `docs/experiments/2026-09-02-memory-foundation/pyproject.toml`
- Create: `docs/experiments/2026-09-02-memory-foundation/artifacts.json`
- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/__init__.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/artifacts.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/tests/test_artifact_contract.py`
- Generate: `docs/experiments/2026-09-02-memory-foundation/uv.lock`

**Interfaces:**

- `ArtifactContract` records exact package versions, LangMem wheel/sdist SHA-256, source tag/commit, and the public signatures/behavior that later stages may rely on.
- `load_artifact_contract()` fails closed on a version/hash/signature mismatch.
- The isolated `pyproject.toml` pins all direct dependencies and configures pytest paths to the experiment `src/` plus `apps/api` for read-only reuse of the existing OpenRouter adapter.

- [ ] **Step 1: Write the RED artifact canary**

Assert exact installed versions, `langmem==0.0.30`, the recorded PyPI artifact hashes, and presence of public `create_memory_manager` / `create_memory_store_manager` parameters needed by the design. Freeze and assert C1/C2 default delete behavior, C2 `query_limit`, namespace template, return shape, and any other default later gates rely on. Assert that `artifacts.json` contains no URL credentials and that `apps/api/uv.lock` is outside the experiment write set.

- [ ] **Step 2: Verify RED**

Run:

```powershell
uv run --project docs/experiments/2026-09-02-memory-foundation pytest docs/experiments/2026-09-02-memory-foundation/tests/test_artifact_contract.py -q
```

Expected: failure because the isolated lock/artifact contract does not yet exist.

- [ ] **Step 3: Create the isolated dependency project and lock**

Pin the versions listed in this plan, run:

```powershell
uv lock --project docs/experiments/2026-09-02-memory-foundation
uv sync --project docs/experiments/2026-09-02-memory-foundation --locked
```

Record the resolved wheel/sdist hashes from the lock and the official release/source reference in `artifacts.json`. Do not infer behavior from GitHub `main` when the installed artifact differs.

- [ ] **Step 4: Implement the smallest artifact loader and contract report**

Use `importlib.metadata` and `inspect.signature`; do not import LangMem private modules. The report must distinguish “documented public contract”, “observed canary behavior”, and “not established”.

- [ ] **Step 5: Verify GREEN and isolation**

Run the artifact test, then:

```powershell
git diff -- apps/api/pyproject.toml apps/api/uv.lock
git diff --check
```

Expected: artifact test passes; both production dependency files have zero diff.

- [ ] **Step 6: Commit**

```powershell
git add docs/experiments/2026-09-02-memory-foundation
git commit -m "test: freeze the memory spike artifact contract"
```

---

### Task 2: Prove PostgreSQL Store scope, source immutability, restart, and bounded exact inventory

**Files:**

- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/contracts.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/scope.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/runtime.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/postgres_store.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/snapshots.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/tests/test_postgres_store_contract.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/tests/test_exact_inventory.py`

**Interfaces:**

- `TrustedExperimentScope(run_id, document_id, thread_id)` derives source and semantic leaf namespaces; model text never supplies any component.
- `append_source(store, scope, source_key, immutable_payload)` returns typed `applied` or `no_change`; same key/different payload raises typed `invalid` before any overwrite.
- `put_semantic`, `get_semantic`, and `delete_semantic` expose only the experiment's trusted leaf and framework key.
- `exact_inventory(store, scope, cap)` performs one exact-leaf `cap + 1` query, validates every returned namespace/key, returns all entries only when count is at most cap, and raises typed `overflow` without returning a partial collection otherwise.
- `canonical_snapshot()` must call `exact_inventory()` and emit the complete exact semantic leaf as sorted key/topic/content JSON only; timestamps and connection-local objects are excluded. Overflow, duplicate keys, or a foreign namespace fails instead of producing a snapshot.
- `open_experiment_runtime()` is the only Store/Saver constructor and is an async context manager. It validates the dedicated local database identity, normalizes the connection string, executes the framework-owned idempotent setup methods, then yields a usable runtime owner; only temporary admission/setup connections close before `yield`, while Store/Saver clients and batch workers close on context exit through one explicit `aclose` path.

- [ ] **Step 1: Write RED Store/source tests**

Cover source append/get, same-key same-payload no-op, same-key different-payload rejection with old value unchanged, correction under a new key, semantic add/overwrite/delete, same key in two JD scopes, source/semantic same key, child/sibling/foreign leaf rejection, unknown document/mismatched thread rejection before Store mutation, `alist_namespaces` behavior, verified framework setup, and client/connection reconstruction.

- [ ] **Step 2: Write RED exact-inventory tests**

With a small fixed cap, cover zero, one, cap, cap+1 overflow, near-simultaneous writes, overwrite, delete, adjacent JD, adjacent leaf, child namespace, restart, duplicate detection, and actual key-set equality. Assert there is no second offset page and overflow returns no entries.

- [ ] **Step 3: Verify RED against the unimplemented seam**

```powershell
$env:MEMORY_SPIKE_DATABASE_URL='<explicit disposable PostgreSQL URL>'
$env:MEMORY_SPIKE_EXPECTED_DATABASE='caliburn_memory_spike'
uv run --project docs/experiments/2026-09-02-memory-foundation pytest docs/experiments/2026-09-02-memory-foundation/tests/test_postgres_store_contract.py docs/experiments/2026-09-02-memory-foundation/tests/test_exact_inventory.py -q
```

- [ ] **Step 4: Implement with official `AsyncPostgresStore` only**

Use framework `aget/aput/adelete/asearch/alist_namespaces` and a fresh per-test run ID. The source collision check, trusted database/scope admission, and cap+1 fail-closed check are the only Caliburn-specific guards in this task; do not introduce a repository/table/manifest/pager.

- [ ] **Step 5: Verify GREEN twice across fresh clients**

Run the two files twice. The second run must use new clients and new run IDs while still exercising explicit close/reopen inside each restart case.

- [ ] **Step 6: Commit**

```powershell
git add docs/experiments/2026-09-02-memory-foundation
git commit -m "test: verify postgres memory store boundaries"
```

---

### Task 3: Characterize C1/C2 public contracts and eliminate ineligible arms

**Files:**

- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/candidates.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/fixtures.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/tests/test_candidate_contracts.py`
- Modify: `docs/experiments/2026-09-02-memory-foundation/rubric.md`
- Modify: `docs/experiments/2026-09-02-memory-foundation/artifacts.json`

**Interfaces:**

- `SemanticMemory` has exactly model-authored `topic` and `content`; Runtime/framework owns scope, key, timestamps, run ID, retry policy, and any existing-memory handle.
- `CandidateObservation` records public input, public return, Store before/after, mutation kind, physical envelope, identity owner, retrieval calls, and eligibility reason without pretending to be a production wire schema.
- C1 uses `create_memory_manager`; C2 uses `create_memory_store_manager` with a public-protocol recording Store that delegates to the real PostgreSQL Store.
- Candidate state is `eligible`, `eliminated`, or `failed`. “Eliminated because an out-of-scope index/model is required” is a valid result, not a skipped failure.

- [ ] **Step 1: Write RED public-seam contract tests**

Use a deterministic public chat-model fake only for semantic output. Do not monkeypatch LangMem private functions, supply canonical IDs from the test, or bypass candidate apply behavior. For C1, verify add/update/delete/`RemoveDoc`, documented default delete behavior, existing handle selection, identity ownership, and typed `no_change` apply wiring. For C2, verify documented `query_limit` and namespace-template defaults, the `kind + content` Store envelope, side effects, delete omission from `final_puts`, and that an empty return is not automatically classified as no-op. Any mismatch with the frozen public artifact stops that arm; do not compensate with glue.

- [ ] **Step 2: Add a retrieval-spy eligibility test for C2**

Record every Store search/read request. If correct candidate selection requires an absent semantic index, embedding, query model, unrestricted namespace, or hidden extra call, assert `eliminated` with the exact observed reason. Do not add that dependency.

- [ ] **Step 3: Verify RED**

Run `test_candidate_contracts.py`; it must fail before the candidate harness exists.

- [ ] **Step 4: Implement only observation/admission glue**

Do not rewrite extraction/consolidation logic. Validate candidate output before publication, reject unknown handles/foreign scope/source leaf/Runtime metadata, and derive typed outcome from the documented return plus Store before/after when required.

- [ ] **Step 5: Verify GREEN and freeze eligibility**

Run the contract test twice. Save the exact matrix to README/artifacts. Continue only when at least one candidate is eligible; otherwise stop and write the failure report in Task 6 without running Tasks 4–5.

- [ ] **Step 6: Commit**

```powershell
git add docs/experiments/2026-09-02-memory-foundation
git commit -m "test: characterize langmem candidate contracts"
```

---

### Task 4: Exercise durable replay and multi-mutation failure windows

**Files:**

- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/durable_graph.py`
- Create: `docs/experiments/2026-09-02-memory-foundation/tests/test_durable_replay.py`
- Modify: `docs/experiments/2026-09-02-memory-foundation/rubric.md`

**Interfaces:**

- A minimal LangGraph functional entrypoint uses official PostgreSQL Checkpointer and one public candidate call inside a durable `@task`.
- The task result stores only bounded operation/result references needed for replay; the complete semantic collection remains in Store.
- Experiment-only fault hooks exist exactly at: before candidate call; after Store commit/before durable task result; after durable task result/before entrypoint completion.
- Each case permits one injected failure and one explicit resume under the same thread/config. Attempt counts are recorded and bounded.

- [ ] **Step 1: Write RED single-mutation replay tests**

For each eligible candidate, define exact initial state and intended final state. At every fault boundary assert after one resume: one logical Memory, correct current content, durable task result present, terminal entrypoint completion, no resurrected content, and no unbounded retries. A same Store key test alone is not sufficient.

- [ ] **Step 2: Write RED two-mutation partial-order tests**

Inject A-written/B-fails and B-written/A-fails. Require convergence to the same intended final state plus durable task/entrypoint completion. If the public candidate seam cannot expose a deterministic provider output or failure boundary, mark that candidate failed; do not monkeypatch private internals.

- [ ] **Step 3: Add deterministic authority rejection cases**

Try unknown handles, child/foreign/source namespaces, Runtime metadata, and instruction-shaped low-trust content. The first four must fail before mutation; low-trust text may be stored as data only when supported by the synthetic employee content and must never alter scope/policy/metadata.

- [ ] **Step 4: Verify RED**

Run `test_durable_replay.py`; expected failure is missing graph/fault-boundary implementation.

- [ ] **Step 5: Implement the minimal official Saver/Store graph**

Use `AsyncPostgresSaver`, `AsyncPostgresStore`, LangGraph public functional/task APIs, and candidate public APIs. Do not import or modify the production consultant graph and do not add a receipt/outbox table.

- [ ] **Step 6: Verify GREEN and stop on an invalid arm**

Run all deterministic tests. An arm that duplicates, loses data, cannot finish the run, or needs custom recovery is failed and excluded from Task 5; do not patch around it.

- [ ] **Step 7: Commit**

```powershell
git add docs/experiments/2026-09-02-memory-foundation
git commit -m "test: exercise durable memory replay boundaries"
```

---

### Task 5: Run the bounded cross-round Luna smoke

**Files:**

- Create: `docs/experiments/2026-09-02-memory-foundation/cases/cross-round-memory-v1.json`
- Create: `docs/experiments/2026-09-02-memory-foundation/src/memory_foundation_spike/live_smoke.py`
- Create from actual runs: `docs/experiments/2026-09-02-memory-foundation/trials/<candidate>/request-*.json`
- Create from actual runs: `docs/experiments/2026-09-02-memory-foundation/trials/<candidate>/response-*.json`
- Create from actual runs: `docs/experiments/2026-09-02-memory-foundation/trials/<candidate>/receipt-*.json`
- Create from actual runs: `docs/experiments/2026-09-02-memory-foundation/trials/<candidate>/snapshot-*.json`
- Create from actual runs: `docs/experiments/2026-09-02-memory-foundation/results.csv`
- Modify: `docs/experiments/2026-09-02-memory-foundation/rubric.md`

**Frozen fixture:**

- The deterministic seed contains one detailed recurring synthetic lunar-greenhouse work topic with sentinel facts for cadence, a low-frequency exception, collaborator, final accountability, and a time boundary.
- Call 1 omits those sentinel details while adding: a same-topic supplement; one separate one-off case; one independent unknown whose answer remains unavailable; and an unresolved cadence conflict.
- Close candidate/runtime/Store connections and construct fresh objects against the same PostgreSQL run/JD/thread. Do not pass the old Python collection, object, list, or cache.
- Call 2 only resolves the cadence conflict. It does not restate sentinel facts, the separate case, or answer the independent unknown.

- [ ] **Step 1: Freeze fixture and rubric before any provider call**

The rubric defines exact structural checks, required sentinel facts, allowed paraphrase boundaries, unresolved/clarified claims, duplicate criteria, and stop conditions. It also freezes: requested model `openai/gpt-5.6-luna`; provider `OpenAI`; reasoning `medium`; `max_output_tokens=2000`; `max_context_tokens=12000`; `max_total_tokens=20000` per candidate; `max_cost_usd=0.10` per candidate; timeout 90 seconds; model/SDK retry zero; LangMem `max_steps=1`; and two provider invocations total. Missing/malformed attempt, usage, provider/model, or cost receipt is a failed evidence chain, not a free pass. Commit the frozen case/rubric and record their SHA-256 before executing live calls; changing either later requires an explicit experiment revision.

```powershell
git add docs/experiments/2026-09-02-memory-foundation/cases/cross-round-memory-v1.json docs/experiments/2026-09-02-memory-foundation/rubric.md
git commit -m "test: freeze the cross-round memory fixture"
```

- [ ] **Step 2: Implement the invocation/cost guard**

Build the exact frozen profile, SDK/model retries zero, LangMem `max_steps=1`, and attempt receipts. Refuse to run unless `MEMORY_SPIKE_LIVE=1`, an eligible arm exists, the explicit verified local database identity is set, and `apps/api/.env` yields a key. Never print the key. Before call 2, fail if call 1 has not produced exactly one complete attempt receipt or has exhausted any frozen token/cost boundary.

Run from the isolated worktree root:

```powershell
$env:MEMORY_SPIKE_LIVE='1'
$env:MEMORY_SPIKE_DATABASE_URL='<explicit disposable local PostgreSQL URL>'
$env:MEMORY_SPIKE_EXPECTED_DATABASE='caliburn_memory_spike'
$env:PYTHONPATH=((Resolve-Path 'docs/experiments/2026-09-02-memory-foundation/src').Path + ';' + (Resolve-Path 'apps/api').Path)
uv run --project docs/experiments/2026-09-02-memory-foundation --locked python -m memory_foundation_spike.live_smoke --case docs/experiments/2026-09-02-memory-foundation/cases/cross-round-memory-v1.json --env-file apps/api/.env
```

- [ ] **Step 3: Seed through the candidate public seam**

Use deterministic provider output through the same candidate entrypoint to create the old detailed Memory. Save canonical `snapshot-0-seed.json` from complete exact-leaf inventory; never write framework tables directly.

- [ ] **Step 4: Execute call 1 and validate immediately**

Save exact model-visible input, final public output, complete `receipt-1.json`, and `snapshot-1-after-call.json` from complete exact-leaf inventory. Before proceeding, require: no duplicate logical Memory; every old sentinel detail preserved; supplement and separate case retained; conflict not auto-resolved; independent unknown still unknown. If the first call produced more than one provider attempt or an incomplete receipt, fail the arm and do not run call 2.

- [ ] **Step 5: Rebuild all clients and cold-read**

Close connections/objects, reopen from the same database/JD/thread, and save `snapshot-2-cold-read.json` from complete exact-leaf inventory. It must be byte-equivalent to the canonical call-1 snapshot. Any dependence on old in-memory objects fails the arm.

- [ ] **Step 6: Execute call 2 and validate only the intended convergence**

Save request/response/complete `receipt-2.json` and `snapshot-3-final.json` from complete exact-leaf inventory. Require the clarification to replace only the unresolved cadence claim while preserving sentinel details, separate case, and independent unknown. Require no duplicate logical Memory, no budget breach, and no third provider invocation.

- [ ] **Step 7: Record actual cost and outcomes**

Write one `results.csv` row per candidate with requested/resolved model, provider, invocation count, input/output/reasoning/cache tokens, latency, cost, four-snapshot results, mutation summary, eligibility, and failure reason. Do not average away failures or claim a general eval result.

- [ ] **Step 8: Commit actual evidence**

```powershell
git add docs/experiments/2026-09-02-memory-foundation
git commit -m "test: record the bounded cross-round memory smoke"
```

---

### Task 6: Produce the decision report and independently review the spike

**Files:**

- Create from actual evidence: `docs/experiments/2026-09-02-memory-foundation/report.md`
- Modify: `docs/experiments/2026-09-02-memory-foundation/README.md`
- Modify: `docs/experiments/README.md`

- [ ] **Step 1: Run the complete deterministic suite**

```powershell
$env:MEMORY_SPIKE_DATABASE_URL='<explicit disposable PostgreSQL URL>'
$env:MEMORY_SPIKE_EXPECTED_DATABASE='caliburn_memory_spike'
uv run --project docs/experiments/2026-09-02-memory-foundation pytest docs/experiments/2026-09-02-memory-foundation/tests -q
```

Record exact counts and failures. Do not rerun a failing live model case until green; only deterministic implementation defects may be fixed under the existing rubric.

- [ ] **Step 2: Write the report from evidence**

For every candidate, report Stage 0 contract, eligibility/elimination reason, Store/restart/scope outcomes, replay/fault outcomes, live smoke outcome, model receipts/cost, proven M1–M11 slices, unproven capabilities, and every stop condition encountered. Clearly separate framework fact, observed result, and inference.

- [ ] **Step 3: Apply the design Go/stop gate**

Apply the design's ranking in order: semantic correctness/detail preservation; reliable publication/failure boundary; required functional coverage; token/cost/latency; and only then code responsibility/size. Possible conclusions are exactly:

1. one candidate is the preferred foundation for a successor ADR;
2. neither qualifies and framework/substrate selection must reopen.

List every failed gate and the corresponding mature fallback named by the approved design, with the exact evidence that triggered it. This fallback list is for the Owner's next decision; do not implement a fallback, write a successor ADR, or accept an ADR in this task.

- [ ] **Step 4: Request independent review**

Use `superpowers:requesting-code-review`. Ask the reviewer to inspect the approved design baseline, all tests, actual trial inputs/outputs, receipts, results, and report. Every finding gets an ID, severity, evidence, disposition, and re-review status. Fix only verified implementation/report defects; do not move the rubric after observing results.

- [ ] **Step 5: Final mechanical verification**

```powershell
git diff --check
git status --short
$base=(Get-Content -LiteralPath 'docs/experiments/2026-09-02-memory-foundation/artifacts.json' -Encoding utf8 | ConvertFrom-Json).source_commit
git diff "$base...HEAD" -- apps/api apps/web packages docker-compose.yml
uv run --project docs/experiments/2026-09-02-memory-foundation pytest docs/experiments/2026-09-02-memory-foundation/tests -q
```

Expected: no production diff; deterministic suite passes or the report explicitly records a framework stop result; no secrets; all review findings resolved or honestly left as blockers.

- [ ] **Step 6: Commit and stop**

```powershell
git add docs/experiments/2026-09-02-memory-foundation docs/experiments/README.md
git commit -m "docs: report the memory foundation spike"
git tag memory-foundation-spike-v1
```

Verify `git rev-parse memory-foundation-spike-v1` equals final `HEAD`. Stop with the branch/worktree preserved, unmerged and unpushed. Present the report and reviewer verdict to the Owner. Production work begins only after a separate Owner decision and successor ADR.

## Completion handoff

The executor must return:

- branch, worktree path, and commit list;
- exact deterministic test commands/results;
- eligible/eliminated candidate table;
- actual provider/model, invocation count, tokens, latency, and cost;
- links to the four snapshots per live candidate and the final report;
- explicit list of what the spike did **not** prove;
- confirmation that production files, production dependency locks, ADRs, and remote branches were untouched.
