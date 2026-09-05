# Analysis-only Agent — first isolated slice

Status: **offline native-continuity wiring only**. This is not a runnable Web app,
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
- Tests cover configuration, opaque reasoning/phase/function call round-trip,
  canonical serialization, compaction slicing and canonical non-mutation.

The adapter may omit response-top-level effective `reasoning.context` metadata.
Sending `all_turns` does **not** prove the server selected it. A later tiny native
response/adapter live comparison is required; do not fabricate this metadata.

## Not yet implemented / proved

Compiled agent loop, streaming/async transport, PostgreSQL restart recovery,
conversation reader, instructions/Memory middleware, context token budget,
B extraction/consolidation, C publication, Skills, UI, paid Luna/medium smoke.
There is intentionally no JD editor. Standard serializer round-trip is not a
database durability test. The code is not connected to the existing application.

## Design / evidence

Current design lives in the main checkout (not this branch's historical register):
[Q019](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design.md),
[slice plan](S:/caliburn/docs/plans/2026-09-06-analysis-only-agent-native-continuity-slice.md).
The branch keeps an execution copy in `docs/plans` for review/reproduction.

- [Native reasoning / preserve all output items](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)
- [Server vs standalone compaction](https://developers.openai.com/api/docs/guides/compaction)
- [ChatOpenAI public Responses API](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [LangGraph persistence / serializer](https://docs.langchain.com/oss/python/langgraph/persistence)
- [HTTPX MockTransport](https://www.python-httpx.org/advanced/transports/#mock-transports)

Version evidence: `uv.lock`, generated 2026-09-06 against PyPI. Core direct pins:
LangChain 1.4.0, langchain-openai 1.6.0, LangGraph 1.2.11,
langgraph-checkpoint 4.2.0, OpenAI SDK 3.8.0. Python 3.12.13 used locally.
