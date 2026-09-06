# Analysis-only Agent — isolated conversation and Memory slices

Status: **native continuity + synchronous Agent + Memory read/publication + B1/B2 extraction/consolidation**.
Not a runnable Web app, completed Memory generation/publication system, or live
model-quality result. No legacy App imports.

## Application wiring Task 1 — offline and PG verified

`analysis_agent.conversation.build_conversation` adds a canonical `MessagesState`
root with a directly registered official Agent subgraph. The child inherits the
root Saver (`checkpointer=None`) and has fresh state per invocation, including
the official persisted limits. The root retains full messages between inputs;
it does not inherit the child's private counter channels. This is an execution
scope, not a second model or independent conversation archive.

Use a stable document `thread_id`, `durability="sync"`, and saved HumanMessage
identity for a new input. To resume pending work use `invoke(None, config)`;
inspect `get_state(config, subgraphs=True)` for its pending child messages and
errors, not just root values. While pending, an older root `turn_outcome` is NOT
the outcome of that pending child. Do not submit new input over pending work;
admission, cancellation and safe abandonment are not implemented in this slice.

Default limits are configurable 9 model calls / 8 tools. These allow the tested
deep-read/correct/re-read/final-answer path; they are not price or HTTP-attempt
limits. Runtime `turn_outcome` distinguishes provider-completed output from
technical limit termination. Raw provider status/usage is preserved: absent
usage is unknown, and synthetic limit messages are not successful AI replies.
The existing source reader still rejects non-successful extraction windows.
Runtime-generated notices are marked in message metadata and excluded from the
visible source projection (not deleted from canonical history), so a short
correction still references the actual preceding consultant question.

Malformed tool JSON is distinct from schema validation in ToolNode. A public
after-model hook preserves the native function call and returns its paired
error result without executing a tool, then routes back through the official
model budget check. One correction is allowed; a second malformed result ends
with runtime `tool_error`. The retry count survives checkpoint resume. Missing
call identity / unexpected parallel output remains fail-closed; safe abandonment
still belongs to the next task. This is a thin application hook, not a private
converter patch or a claim that ToolErrorMiddleware covers every parse error.

Only synchronous provider invocation is wired. Characterization finds certain
Responses SSE error events do not emerge as adapter exceptions; stream exhaustion
must NOT be interpreted as successful provider completion. Product streaming is
not enabled or certified here. SDK transient retries have no outer model/graph
retry wrapper.

Latest full result: **177 passed, 0 skipped** (including 16 existing PG cases + 2 new
root/child/C PG cases). Initial offline result was159 passed/18 skipped; after
Docker recovery the existing dedicated DB was available and all tests passed.
Docker automatic restart remains an unresolved host issue; do not treat DB tests
as proof of that fix. Task 2 / API / scheduler / UI remain unstarted at this save point.
Full evidence, framework links
and review findings: [Task 1 results](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-conversation-lifecycle-results.md).

## Run

Python 3.12 and uv, from this directory:

```powershell
$env:PYTHONUTF8 = '1'
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --locked
uv run --no-sync pytest -q
uv run --no-sync python -m compileall -q src tests
```

Tests use the real pinned LangChain adapter, OpenAI SDK and LangGraph serializer;
only HTTP is synthetic (`httpx.MockTransport`). No `.env`, valid API key or paid
call is required. Test tracing is disabled. Synthetic encrypted strings verify
preservation, not actual server-side reasoning or compaction quality.

## What exists

- `provider.build_model`: public `ChatOpenAI` Responses binding, `store=False`,
  medium / `all_turns`, native content blocks and sequential tool calls. A positive
  `compact_threshold` is opt-in configuration; there is no universal default.
- `context.server_compaction_view`: detached request-only conversation from the
  latest **inline server** compaction item, retaining later items and matching
  tool metadata. Instructions and Memory guide must be added separately by the
  caller. Never use this to prune standalone `/responses/compact` output.
- `runtime.build_agent`: official `create_agent` with a request-only middleware;
  no custom model/tool loop, message repository, or state machine. Caller owns
  the model/client and Saver lifetime, and invokes with `durability="sync"`.
- Failed pending step: reopen with the same thread ID and invoke with `None`.
  Do not append the same employee input again. The offline regression exercises
  reuse of a committed deterministic tool result, NOT exactly-once external effects.
- Tests cover configuration, opaque reasoning/phase/function call round-trip,
  canonical serialization, compaction slicing and canonical non-mutation.

The adapter may omit response-top-level effective `reasoning.context` metadata.
Sending `all_turns` does **not** prove the server selected it. A later tiny native
response/adapter live comparison is required; do not fabricate this metadata.

## Dedicated PostgreSQL check (passed on 2026-09-06)

Install uses the pinned official `langgraph-checkpoint-postgres` package. The
integration test uses `PostgresSaver.from_conn_string(...)` and `.setup()` directly,
not an additional persistence wrapper. It only allows a database named
`q019_agent_test`, which must already exist on a test PostgreSQL service. Never
point it at the application database. Supply `Q019_TEST_DATABASE_URL` externally
with a bounded `connect_timeout` (for example 5 seconds); do not commit credentials.

```powershell
uv run --no-sync pytest tests/test_postgres_conversation.py -q -rs
```

This test runs two separate Python processes, stops the first at a synthetic
provider error, and resumes its saved model step in the second. It checks input
visibility from another DB connection before a model response, native items,
tool-result reuse, compaction view vs full conversation, and thread isolation.
It deletes only its own random test thread using the official Saver API.
No DSN means an explicit **skip, not a durability pass**; a provided but failing
DSN fails the test. Model HTTP is synthetic in both processes (zero paid calls).

Docker Desktop initially failed on an inaccessible internal socket. After an
owner-approved, non-destructive backup/recreation of its socket directories,
the engine recovered. The dedicated `caliburn-q019-postgres` container now uses
PostgreSQL 16.14, user `q019`, database `q019_agent_test`, localhost port `55433`,
and its own `caliburn-q019-postgres-data` volume. Its random password stays out of
the repo/output. No Docker factory reset or existing-data deletion was performed.

The single PG test passed, then the full suite passed **12 tests, zero skipped**.
Both worker processes use synthetic provider HTTP: this proves database/process
continuity, not a live model's reasoning quality or arbitrary power-loss recovery.
Test thread rows were cleaned; the dedicated DB/schema remains for another run.

## Not yet implemented / proved

Streaming/async transport, abrupt host/DB crash or failover recovery,
total context token budget, background scheduling, C editing
and in-run read-view refresh, Skills, UI, paid Luna/medium smoke.
There is intentionally no JD editor. Standard serializer round-trip is not a
database durability test. The code is not connected to the existing application.

## Memory read slice (2026-09-06)

- `memory.MemoryArtifacts`: fresh StoreBackend extraction files and prepared
  knowledge/guide versions. Runtime generates addresses and source headers.
  `save_memory` does **not publish current**; caller selects a `MemoryVersion`.
- `sources.ConversationReader`: captures completed exact snapshot/message ranges;
  reads saved visible human/assistant text, with bounded continuation and omitted
  block kinds. No new archive and no model call; opaque reasoning is not exposed.
- `memory_tools.memory_access`: fixed document/version guide plus official
  read-only file tools and `read_conversation`. Pass the returned middleware/tools
  into `build_agent`. Build a new access bundle when intentionally selecting a
  new version; no hidden mid-run refresh. Only filesystem `.tools` are registered,
  not generic offload/scrubbing hooks. Native Responses continuity stays intact.
- Direct file reads support full fixed-version enumeration; model-visible pages
  use official size-based pagination. Engineering limits: line <=2,000 chars,
  guide <=4,000 chars, read output about16,000 chars, source page3,000 chars.
  Too-large directory listings fail explicitly; keyword top-k isn't inventory.
- Generated artifacts normalize line separators before storage so backend and
  native formatter pagination agree; original conversation text is unchanged.
  Literal runtime interview links are checked across presentation styles,
  including bare links followed by sentence punctuation.
- Full suite **32 passed / 0 skipped**, including actual PostgreSQL Store/Saver
  reopen. Model HTTP synthetic, no API spend. B/C generation/concurrency still
  needs the next slice; prepared artifacts aren't a publication authority.

[Memory read results](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-read-path-results.md)
records source links, scoped test cleanup, custom seams and remaining gates.

## Memory publication slice (2026-09-06)

SQLAlchemy 2.0.52 provides ORM version checking and transaction scope for two
small metadata tables: current head and durable operation receipts. Full text
remains in the official Store; this is not another Memory or conversation store.

`PublicationStore(engine, artifacts)` is fixed to one document. Call `setup()`
explicitly in the isolated database setup, never during a model run. Runtime
calls `prepare(version, expected_revision=..., kind=...)` after saving artifacts,
persists that request in its workflow, and sends it to `publish(request)`.
An absent head has revision 0. `current()` returns a fixed published version
for `artifacts.reader(head.memory)` and `artifacts.guide(head.memory)` together.

Stale updates fail without overwriting the winning version. Retry an uncertain
commit with the **same request**, or read its `receipt(operation_id)`; absence
does not prove the old transaction failed. An existing receipt returns the old
operation's result without rolling current back. Different content requires a
new operation after resolving the previous attempt. No automatic model retry.
No SQL transaction spans model work or Store artifact preparation.

Full suite: **49 passed, zero skipped** with the dedicated PG database. New
tests exercise first-insert and subsequent-update races and commit-reply loss.
Failure injection is synthetic, transactions and contention are real. This is
not production failover or model-quality evidence; paid calls remain zero.
Reconciliation-query disconnects preserve the same uncertain-result contract;
they do not imply a previous attempt failed. The B/C model workflows and
automatic read-view refresh are still not built.

[Publication results](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-publication-results.md)
contains references, custom seams, test limitations, and the next gate.

## Interview extraction slice (2026-09-06)

`ExtractionWorkflow(reader, artifacts, model, checkpointer)` runs B1 only:
completed source references → native three-field extraction → durable checkpoint
→ Store artifacts. `start(reference)` handles a bounded batch; `resume()` resumes
the pending node without replacing its input. The caller serializes jobs per
document. This technical workflow is not another employee conversation.

The model writes detailed notes, candidate information and a short label.
Runtime supplies real paths and new-source/optional-context references. It does
not publish current Memory. Empty candidates are valid; incomplete/refused/
invalid model results are errors. Source completion requires explicit provider
`completed` status, not only a graph with no next node.

Defaults: 6,000 visible characters per window, up to1,500 previous-turn context,
4,096 output tokens and16 windows per batch. All are engineering settings, not
vendor guarantees. Oversize individual turns fail rather than silently truncate.
Only visible interview text is extracted; opaque reasoning remains canonical.

The latest completed identical source returns its saved result. Older or
overlapping source ranges are rejected before another call; there is no implicit
force-reextract or arbitrary historical-result lookup. Message order is read
from the canonical snapshot, not inferred from UUIDs.

A Store failure after the model-result checkpoint resumes saving, not the model.
Partial unreferenced artifacts may remain; no current version is changed and no
GC is provided. A model response lost before checkpoint can still be recomputed.
Real PG tests reopen all connections after injected pre-write/partial-write
failures. Full suite: **71 passed / zero skipped**, synthetic HTTP, zero paid calls.
This proves wiring/recovery, not semantic extraction quality.

[Extraction results](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-extraction-results.md)
records framework sources, review findings, repairs and the remaining B2/C gates.

## Design / evidence

### Consolidation slice (2026-09-06)

`ConsolidationWorkflow(extraction, publication, model, checkpointer)` consumes
the completed `ExtractionWorkflow` checkpoint. Call `start()` for a completed
B1 batch and `resume()` only for its pending job. A read-only admission check
rejects invalid/oversize input without reserving a new job. Caller still
serializes B jobs; this is not a scheduler or a second employee conversation.

B2 receives bounded candidates, real detail-note links and the small guide.
DeepAgents `StateBackend` holds a private copy of the base knowledge/guide;
official `ls`, `grep`, `read_file`, `write_file`, `edit_file` tools expose that
staging and read-only interview artifacts. `validate_memory()` has no model
arguments and returns format/reference errors for correction within the loop.
It is application validation, not semantic truth or coverage verification.

A per-invocation LangGraph subgraph checkpoints the official Agent's tool steps.
The completed pair is checked again, saved as immutable Store artifacts, then
the publication request is checkpointed before the existing CAS/receipt seam.
Stale publication keeps B1 and starts a fresh B2 attempt from the winning head
plus actual bounded repair-source Q/A. It does not reuse the old model output
with a new expected revision. No raw-search tool or additional summary layer.

Initial limits: 8 successful model steps / 12 tool calls across the B2 job,
4,096 output tokens per request, candidates24,000 visible chars, repair input
12,000 chars; 20 repair receipts is a fixed safety limit, not a configurable
parameter. Stale attempts get only remaining budget; a resumed agent keeps
its official counters. These are engineering limits, not vendor
guarantees or a hard billing cap: SDK network retries and calls lost before a
checkpoint may add HTTP requests. No paid API was used.

Incomplete/refused responses or `invalid_tool_calls` anywhere in the attempt
cannot become successful no-op publications. An invalid final artifact stops
at validation; `resume()` does not automatically rewrite that invalid artifact.
Likewise budget exhaustion is a safe stop, not autonomous recovery. The
production retry/cancel/replan interface remains out of scope; do not tell users
all errors are automatically repaired. Tool-time validation failures can be
repaired by the model before it finishes.

Full suite: **96 passed / 0 skipped**, including actual PG client/Saver/Store
reopen after tool failure, before artifact save and after lost commit reply.
Synthetic responses prove wiring/recovery, not real consolidation quality.
[Consolidation results](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-consolidation-results.md)
records the review, official sources, limits and next C/A gate.

### Live repair / primary-agent refresh slice (2026-09-06)

Create `MemorySession(publication, source)` and pass it to
`build_agent(..., middleware=[session], tools=session.tools)`. This sync-only
composition adds `repair_memory(edits)` to the four existing read tools.
C is a no-model tool subgraph, not a third agent. The caller owns clients,
serializes primary runs per document, and invokes with `durability="sync"`.
Use `invoke(None, config, durability="sync")` to resume a pending run, not a
second copy of its input. App admission/retry/cancel endpoints are not included.

New employee input pins head, guide, and a real saved input Q/A reference.
Read tools use public middleware `request.override(tool=...)` to select this
immutable version. A background publication does not silently switch it.
C uses exact StateBackend edits in private per-invocation staging; all edits
must succeed before save -> durable request -> existing publication/receipt.
No fuzzy edits and no creation of missing Memory. Guide and knowledge publish
together; C leaves B's processed-source cursor unchanged.

Command updates A's read head and ToolMessage together on success/stale;
initial system guide stays fixed. The visible result is authoritative about
the refresh. On a reconciled older successful request, the result distinguishes
the applied version from the latest read version. Canonical visible Q/A can
be read from C receipts without exposing opaque reasoning or duplicating text.

Engineering limits: 1–8 edits / 12,000 combined old+new chars per C call; two
correctable failures per employee input (initial plus one retry), including
framework schema errors. New input resets; resume does not. This is not an
overall A cost cap. Storage/uncertain commit faults propagate as pending work.
No paid API or natural-model repair-quality claims.

Full suite: **120 passed / 0 skipped**, including four real PG reopen cases.
Independent review found no Critical/Important blockers for this isolated
savepoint (reviewer reran live20 tests, not the entire PG suite).
Verification and boundaries:
[Live repair results](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-live-memory-results.md).

### Earlier design and provider evidence

Current design lives in the main checkout (not this branch's historical register):
[Q019](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design.md),
[first slice plan](S:/caliburn/docs/plans/2026-09-06-analysis-only-agent-native-continuity-slice.md),
[second slice plan](S:/caliburn/docs/plans/2026-09-06-analysis-only-agent-durable-conversation-slice.md).
[Results and Docker recovery record](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-durable-conversation-results.md).
The branch keeps an execution copy in `docs/plans` for review/reproduction.

- [Native reasoning / preserve all output items](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)
- [Server vs standalone compaction](https://developers.openai.com/api/docs/guides/compaction)
- [ChatOpenAI public Responses API](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [LangGraph persistence / serializer](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Transient model context vs persistent state](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [Official PostgreSQL setup](https://docs.langchain.com/oss/python/langchain/short-term-memory)
- [Sync durability](https://reference.langchain.com/python/langgraph/types/Durability)
- [HTTPX MockTransport](https://www.python-httpx.org/advanced/transports/#mock-transports)

Version evidence: `uv.lock`, generated 2026-09-06 against PyPI. Core direct pins:
LangChain 1.4.0, langchain-openai 1.6.0, LangGraph 1.2.11,
langgraph-checkpoint 4.2.0, OpenAI SDK 3.8.0. Python 3.12.13 used locally.
Second slice: langgraph-checkpoint-postgres 3.1.2, psycopg/binary 3.3.5
(resolved in `uv.lock`).
Third slice: Deep Agents0.7.13 (public StoreBackend and filesystem tools).
