# Analysis-only Agent — isolated conversation slices

Status: **native continuity + synchronous compiled Agent wiring**. This is not a runnable Web app,
a Memory implementation, or a live model-quality result. No legacy App imports.

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
conversation reader, Memory-guide injection, context token/run budget,
B extraction/consolidation, C publication, Skills, UI, paid Luna/medium smoke.
There is intentionally no JD editor. Standard serializer round-trip is not a
database durability test. The code is not connected to the existing application.

## Design / evidence

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
