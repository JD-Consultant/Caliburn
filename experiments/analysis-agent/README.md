# Analysis-only Agent — isolated conversation and Memory slices

Status: **analysis-only local API + native continuity + Memory read/publication +
B1/B2 extraction/consolidation + explicit summary re-extraction + durable
consolidation requests + automatic background dispatcher + on-demand analysis Skills +
final synchronous Responses context budgeting**. No Web UI yet;
no live-model quality claim and no legacy App imports.

Latest bounded prompt experiment (2026-09-07): **27 real Luna/medium requests,
US$0.01252361 reported** across three runs. All stopped at the first B2's existing
8-model-step limit; no published Memory or later correction/recall quality claim.
Two observed local issues are repaired: known-path B2 discovery uses the official
tool-description override, and Chinese prose parentheses no longer pollute a
reference address. Explicit links/code remain exact. **184 focused tests pass**;
independent review accepted these two fixes only. Analysis prompts/Skills,
publication rules and limits are unchanged; no broad refactor.
[Experiment, evidence, fixes and untested boundaries](../../docs/specs/2026-09-07-memory-prompt-live-calibration.md).

Earlier context/Skills wiring verification (2026-09-07): **514 passed / 0 skipped (71.95s)**,
including dedicated PostgreSQL; one existing TestClient deprecation warning.
Independent Skills, budget and whole-batch reviews are approved; compileall,
offline lock and diff checks pass. Paid model calls in that earlier slice: zero. This covers wiring
and failure handling, not natural interview quality or live endpoint latency.
[Current results, official sources and remaining limits](../../docs/specs/2026-09-07-context-budget-and-analysis-skills-results.md).

## On-demand analysis Skills — SK-01 (2026-09-07)

`AnalysisService` enables three bundled method references for the foreground
consultant: work-scope interviews, case comparison/common work patterns, and
outcomes/success criteria/knowledge and skills. They are initial interview
methods, not new agents, mandatory stages, schemas or employee facts.

The pinned official `SkillsMiddleware` discovers metadata and advertises
`/skills/<name>/SKILL.md`. Only a requested `read_file` result introduces the
body into model input; instructions explicitly say not to load all methods on
every turn. Discovery and reads use the same `CompositeBackend` mount over a
read-only capability backed by `FilesystemBackend(virtual_mode=True)`, rooted
at `src/analysis_agent/skills`, never the project root or the current directory.
Only official `ls`, `grep`, and `read_file` tools are exposed, sharing the
existing Memory tool names. Filesystem middleware offload/scrubbing hooks are
not installed, so native reasoning/compaction and canonical items remain intact.

`MemorySession` retains this asset mount when dynamically rebinding its pinned
Memory version and after C feedback refreshes the read head. Existing Memory
reads/repairs keep their own permissions; Skills add no write, execute, network
or JD capability. The non-Store test service also gets the same assets, with an
empty fallback backend and no host-file or Memory access.

B1/B2 are not given this middleware or asset mount. Skill ToolMessages remain
canonical, but `ConversationReader` excludes tool content from visible source
extraction; B1 does not receive method bodies as employee knowledge. Offline
tests exercise real Service/create_agent/official tools/ChatOpenAI/SDK requests
with synthetic HTTP, including path rejection, C refresh, read recovery and
B1 source isolation. This verifies wiring only: natural selection, interview
quality and prompt tuning are the next owner-authorized gate, not tested here.

## Current application entry — Task3 / Task4

Runtime recovery follow-up (2026-09-07): trusted interrupted reads can resume
or close safely; B2 final content errors return to its bounded Agent loop; B1
persists a precise validation-correction allowance; initial guide freshness is
scoped to the current input. Unknown writes still require reconciliation.
**427 passed / 0 skipped (67.52s)** including dedicated PG, with one existing
upstream TestClient deprecation. Compileall, offline lock check and independent
whole-batch review passed; paid model calls zero. No old pending-job migration,
production integration or live-model quality claim.
[Recovery results, official sources and limits](../../docs/specs/2026-09-07-runtime-recovery-repair-results.md).

Memory reference follow-up (2026-09-07): `MemoryArtifacts(..., source=reader)`
uses the same document's canonical `ConversationReader` at validation, save and
pre-publication. The service provides this reader automatically. Artifact-only
clients may omit it only when Memory contains no `conversation:` references;
omission never bypasses raw-reference validation. The reader must use the
compiled canonical conversation root, not a graph with an older state schema.

Markdown presentation is parsed by markdown-it-py 4.2.0 (CommonMark), with its
official linkify extra (linkify-it-py 2.2.0) recognizing external URI spans. Real detail
links remain valid inside emphasis, code and reference-style links; malformed or
unreadable controlled addresses cannot publish through either B2 or C. External
URLs are not treated as local files. Exact link/code destinations are not silently
rewritten. Validation preserves the stored Markdown and adds no required model
fields, evidence requirement, model calls or semantic truth checks. Tool errors
retain the existing instructive JSON/text and bounded correction path; C now also
sets native `ToolMessage.status` consistently (not a new Responses wire feature).

Current-input source references also retain the nearest visible advisor text and
intervening employee answers across safely closed tool-only turns. An unresolved
turn cannot be silently crossed; runtime notices/tools are not employee words.
The existing 3,000-character paged reader preserves longer ranges. This repairs
C's provenance and B2's repair-context read, not the model's Context selection.

Previous Memory-reference slice verification: **370 passed / 0 skipped (103.66s)**, including real dedicated PG
client reconstruction; compileall and offline lock checks passed. HTTP replies
are synthetic, paid calls zero. At that savepoint, Skills and full request
budgeting were still pending; the current sections above/below supersede that
status. Raw-history discoverability and live interview quality remain separate gates.
[Repair results and official sources](../../docs/specs/2026-09-07-memory-reference-repair-results.md).

Use Python 3.12, the locked dependencies, a separate local `q019_` PostgreSQL
database and one process. Set credentials externally; this entry never loads
the old application's `.env`. Required variables:

| Variable | Meaning |
|---|---|
| `Q019_DATABASE_URL` | Dedicated localhost PostgreSQL DSN, not the production DB |
| `OPENAI_API_KEY` | Provider credential; never commit or print it |
| `Q019_REQUEST_TIMEOUT_SECONDS` | Positive finite per-attempt timeout, passed to the actual SDK |
| `Q019_MAX_OUTPUT_TOKENS` | Positive per-response output bound |
| `Q019_COMPACT_THRESHOLD` | Explicit positive native compaction threshold for the chosen model |
| `Q019_CONTEXT_WINDOW_TOKENS` | Required positive capacity of the configured model; output must be smaller, and compaction threshold + output must fit |
| `Q019_BACKGROUND_POLL_SECONDS` | Positive finite infrastructure wake interval; NOT an interview-idle trigger |
| `Q019_BACKGROUND_MAX_RECOVERIES` | Explicit nonnegative automatic process-interruption recovery allowance per B batch; persisted across restarts |
| `Q019_MEMORY_TEXT_THRESHOLD` (optional) | Positive new visible-character fallback; omitted = notification-trigger only, no guessed default |
| `Q019_MODEL` (optional) | Defaults to `gpt-5.6-luna`; medium / all_turns native binding |

There is no guessed universal output/compaction value. The 32,000 / 1,000 / 13s
values in tests only verify wiring, not recommended product budgets. An output
cap, SDK attempt timeout and 9-model/8-tool turn limits are not a dollar cap.
SDK transient retry remains native; no outer model/graph retry is added.
The configured per-response output bound is carried through A, B1 and B2;
B2's standalone default does not override the application's explicit setting.

CT-01 checks **every synchronous A/B1/B2 Responses request** after the SDK has
serialized its final body, including tool definitions/results, Skill metadata
and reads, pinned Memory guide, native opaque items, and B1's structured-output
schema. A separate OpenAI SDK client calls `responses.input_tokens.count` with
only its supported parameters. Generation proceeds only when counted input +
**final** `max_output_tokens` fits the configured capacity. Reasoning is already
part of the output reserve, not deducted twice. `truncation=disabled` prevents
silent provider truncation; canonical history and opaque items are not mutated.

Both clients share the SDK-resolved public `base_url` (including externally set
`OPENAI_BASE_URL`), have explicit finite timeouts, and close after workers stop.
The hook matches only that Responses origin/path; query/fragment endpoints,
remote prompt templates, unknown request fields, model mismatches, missing
output bounds and invalid count responses fail closed. A custom endpoint/model
must support the official counting schema: no approximate fallback is provided.
Fake-only helper construction may omit the guard; real `open_service` cannot.
Async invocation is **not wired or supported by this budget integration**.

This conservative preflight adds a network count request and latency per
generation attempt; it is not claimed free or a hard monetary cap. The count
endpoint does not accept `context_management`, so it cannot anticipate new
compaction generated by the pending response. Existing inline compaction still
triggers early; an abrupt large input/tool result may stop before generation.
Oversized canonical history is not automatically recoverable and is never
silently deleted or summarized. A ends with existing `configuration_error`
status and distinct `context_budget_exceeded` error code, closes safely and
unlocks, without offering resume. B becomes `blocked` and does not retry each
tick. Local schema/configuration errors are also nonretryable; genuine counter
transport failures use the SDK's own retry and existing service classification.

```powershell
uv sync --locked
uv run --no-sync uvicorn analysis_agent.api:create_app --factory --app-dir src --host 127.0.0.1 --port 8091 --workers 1 --no-proxy-headers
```

Startup initializes the official Saver/Store and small ORM catalog/publication
tables; it reconciles A without invoking it. The background scheduler may resume
eligible B work or process saved notifications, and those B calls can cost money
when using a real key. Empty/no-eligible-source startup does not call a model. Do not use
multiple workers, reload or multiple server processes against this isolated DB.
`/docs` is the generated API reference, **not the planned employee UI**.

- `POST/GET /documents`: create/list independent interview documents.
- `POST /documents/{id}/runs`: `{request_key, text, abandon_pending?}`. The same
  key/text returns the same saved input; different text under that key conflicts.
  Accepted means the input is confirmed in Saver, not that AI has finished.
- `GET /documents/{id}/messages` and `/runs[/{run_id}]`: visible human/assistant
  text and safe status/usage projection. Native reasoning and tool internals
  stay in canonical checkpoints and do not cross this UI seam.
- `GET /documents/{id}/memory-status`: safe background status/error/recovery-count
  projection, not a transcript, source token, or claim of semantic completeness.
- `POST /documents/{id}/runs/{run_id}/stop`: cooperative stop, not thread killing.
  An already entered SDK call (including its retries) or tool reaches its safe
  boundary first. Then the next model/tool is not started. Closing a browser
  request does not stop the worker. Server shutdown joins before closing clients.
- `POST /documents/{id}/runs/{run_id}/resume`: explicit same-checkpoint continuation
  only when `can_resume` is true; counters and resume count survive reopening.
  A pending bound Memory read (`read_conversation`, `read_file`, `ls`, `grep`)
  can resume after a runtime interruption, including service reconstruction.
  Only that pending tool is re-entered; previous model calls and saved tool
  effects are not replayed. Even at the model quota the read may finish; the
  existing framework guard then ends the turn without another model request.
  The known C repair can reconcile/replay its saved operation, including lost
  publication replies. Arbitrary unknown effects are not declared safe to retry.
  A process/transport error label alone never authorizes an unknown pending tool.
- A quiescent interrupted input can be explicitly abandoned when submitting new
  text. Unknown publication must be resolved first. Old employee messages and
  completed Memory publications are never removed or reverted by cancellation.
  Stopping/abandoning a trusted pending read pairs its original call ID with an
  error saying the result is unavailable/discarded, not that it never executed
  or that the data is absent. It does not rerun the read or invoke the model.

ER-A01 recovery uses the actual factory-built `MemorySession.read_tools` and
the current public child checkpoint, not a model-supplied name allow-list or
blanket `runtime_error` retry. Conversation composition rejects conflicting
same-name tools. Direct `close_turn` callers must supply the session bound to
that conversation. No new automatic retry loop, durable state layer or quota
reset is introduced; failures outside the pending trusted read stay classified
by the existing policy, and C still requires its exact receipt reconciliation.

Same-document active work rejects another input. Loopback/Host/same-origin
restrictions match the single-local-operator scope; this is not authentication
or a cloud/multi-user service. Catalog stores routing/hash/status, not another
message body archive. Provider usage comes from returned metadata; unobserved
failed usage is unknown, not zero or an estimated bill.

Current evidence, review and limitations:
[Task3 result](../../docs/specs/2026-09-06-analysis-only-agent-api-results.md),
[Task4 result](../../docs/specs/2026-09-06-background-dispatch-results.md).
The following sections retain the earlier slice history; their “not yet”
statements describe those savepoints, not this current application entry.

## Task4 — nonblocking background consolidation

APScheduler 3.11.3 owns one reconstructible interval job and a one-thread executor.
It calls a dispatcher protected by the application's single-process global B
lock. `coalesce=True` merges missed clock ticks, not interview text. Model work
does not run in the foreground pool, API event loop or notification tool.

Eligibility uses safely closed canonical conversation, saved request receipts,
and the successful publication cursor. A new admission snapshots the whole
eligible target; B1's bounded batches retain the remaining target until published,
even if its request was in the first batch. Interleaved new conversation waits
for the next target. No 90-second idle rule, turn-count trigger, short-input
filter, classifier model, or extra notification/outbox table is introduced.
The optional fallback counts visible new human/AI text once, excluding tools,
reasoning and preceding context. Its product threshold remains undecided.

`q019_background_admission` stores only document routing, exact source/target
references, running/queued/blocked state and recovery count. B1/B2 official
checkpoints still own extracted content and execution progress; Store/publication
still own Memory artifacts and current head. There is no second conversation or
Memory content archive. This metadata is local application wiring, not a claim
that APScheduler or OpenAI supplies these exact fields.

- Resume an interrupted old B before admitting new source. Saved B1 is not
  re-extracted; saved B2 steps continue. A committed publication with a lost
  reply is reconciled through its existing receipt, without model regeneration.
- Ordinary caught failures become durable `blocked`. SDK transport retries and
  model tool-error correction have already had their own bounded opportunity;
  ticks, new notifications and restarting do not reset a blocked job.
- An unclean process exit may leave `running`; resume consumes the configured
  automatic recovery allowance **before** work. Repeated process loss cannot
  refresh it. This is not the removed arbitrary one-manual-retry limit and not
  a dollar cap. Tests choose one only to exercise the boundary, not recommend it.
- Successful B does not wake A or append another tool result. A's next normal
  run reads current availability; unresolved failure adds a short runtime-only
  request hint, not an employee message/Memory fact. A recovered target no longer
  gets that hint. It does not interrupt a model call already in progress.
- Shutdown stops scheduling and joins B and A before clients close. Do not run
  multiple API processes against this DB; this is not a distributed job queue.

Blocked model/configuration errors need their cause fixed and explicit technical
recovery through the existing saved B workflow. No employee-facing manual
consolidation/retry button is added here. Oversize source/context or candidate
input blocks visibly rather than silently truncating; prompt/capacity tuning
belongs to the later bounded live interview stage. Recovery tests reconstruct
clients and inject process-loss boundaries; they are not an OS power-loss test.

Sources: [APScheduler user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html),
[executor](https://apscheduler.readthedocs.io/en/3.x/modules/executors/pool.html),
[approved local policy](S:/caliburn/docs/specs/2026-09-06-memory-consolidation-request-wiring-design.md).

## Application wiring Task4a — consolidation request receipt

`build_conversation` registers `request_memory_consolidation()` as a normal
optional zero-argument tool. It only returns a short acknowledgement and an
official `ToolMessage.artifact`; ToolNode and the existing Saver persist both.
It does not call B1/B2, publish Memory, create an external job or wait for B.
The model normally needs a continuation call to finish its interview answer;
the existing 9-model/8-tool budget is unchanged. This is not zero-token signalling.

The model sees the receipt, not the artifact. A saved receipt means "requested",
not "Memory updated". The framework's no-argument StructuredTool ignores extra
arguments; no model-supplied document, job or reason is consumed. The same-name
tool is reserved in this composition so another effect cannot silently inherit
its pure-notification cancellation rule.

After a safely closed turn, use the read-only projection:

```python
requests = reader.pending_consolidation_turns(
    after_reference=head.processed_source if head else None,
)
```

Here `head` must be the successful current publication, not an in-flight job's
planned range. Each result has the real `input_id` and `end_id`; it is neither a
new message nor a queued job. Only an actual parsed notification call paired
with its saved success/artifact counts. One turn's repeated requests coalesce.
An unresolved earlier source blocks later turns; a partial published cursor
does not consume later requests. Comparison uses canonical order, not UUID
sorting. Reading never clears anything or invokes a model.

After the worker is confirmed quiescent, `close_turn` can seal a notification
whose result was not saved with one paired error. It preserves an already saved
success. This does not weaken `repair_memory` receipt reconciliation or classify
unknown external effects as failed. Both interrupted paths allow a later input
without discarding the employee's earlier message.

**Still not connected:** the rest of Task4 scheduling/new-text
fallback, and next-normal-run background failure context. No notification/outbox
table, idle timer, turn-count trigger, guessed character threshold, UI or paid
model call is added here. No claim yet that a running background worker cannot
block the API: that requires the next service integration test.

Evidence and remaining gates:
[Task4a plan](../../docs/plans/2026-09-06-memory-consolidation-notification-slice.md),
[Task4a results](../../docs/specs/2026-09-06-memory-consolidation-notification-results.md),
[approved notification policy](S:/caliburn/docs/specs/2026-09-06-memory-consolidation-request-wiring-design.md).

## Summary re-extraction — Q019-MEM-SUMMARY-01

This is an explicit runtime maintenance action, not an every-turn tool or a
separate employee conversation. Use existing B1/B2 objects with the same
document, official Saver/Store and publication service:

```python
result = b1.reextract(existing_summary_path)
published = b2.start_reextraction(existing_summary_path)
```

After an interrupted B1 use `b1.resume_reextraction(existing_summary_path)`;
after interrupted B2 use `b2.resume()`. Do not replace a pending job. As with
ordinary B1/B2, callers must serialize background jobs per document; this slice
is not a scheduler or concurrent API admission layer. A deliberate new
`reextract` after success generates new artifacts; replaying the same completed
B2 artifact batch uses its receipt without another model call, even after other
jobs. `reextraction_config(path)` is a technical checkpoint address, not a new
user-visible thread, source copy or case record.

- Runtime reads the saved source/context header and uses that exact range.
  Oversize input fails rather than dropping its middle. No new model fields:
  the existing `rollout_summary`, `raw_memory`, `rollout_slug` remain the schema.
- New summary/candidate paths are saved; old artifacts and original messages
  remain readable. The summary filename is not a case identity. Explicit empty
  context, a file-start format marker and a runtime header terminator prevent generated prose being parsed
  as source metadata. Old experiment artifacts lacking that unambiguous header
  can still be read, but automatic re-extraction fails instead of guessing; no
  old data is migrated or deleted by this slice.
- B2 receives real old/new addresses plus fresh candidates, reviews current
  knowledge and relevant details, then updates conclusions/references as
  appropriate. A case-only correction matters even if the general work pattern
  remains the same. This is an instruction to the model, not a deterministic
  proof of semantic completeness or that every citation was updated correctly.
- Re-extraction publishes via existing `repair` semantics: preserve the ordinary
  processed-source cursor, retain repair source receipts, CAS the head only
  after prepared artifacts validate. A concurrent C change causes bounded B2
  reconsideration, not B1 re-extraction. Failed attempts retain the previous head.
- A follows current knowledge before opening historical details. Old detail
  addresses do not automatically redirect to later corrections; no all-history
  rewriting, case CRUD or direct JD editing was added.

Sources, tests and scope: [slice results](../../docs/specs/2026-09-06-summary-reextraction-results.md).
OpenAI producer/consumer evidence is in the
[main source review](S:/caliburn/docs/specs/2026-09-06-openai-rollout-summary-correction-source-review.md).
This implementation maps the approved concepts onto our frameworks; immutable
versions, technical job IDs and SQL publication are not claims about identical
OpenAI internals.

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
Task 1 did not include admission/cancellation; see the Task 2 local entry below.

Default limits are configurable 9 model calls / 8 tools. These allow the tested
deep-read/correct/re-read/final-answer path; they are not price or HTTP-attempt
limits. Runtime `turn_outcome` distinguishes provider-completed output from
technical limit termination. Raw provider status/usage is preserved: absent
usage is unknown, and synthetic limit messages are not successful AI replies.
Task 1's reader required successful extraction windows; Task 2 adds explicit
runtime boundaries for safely closed unsuccessful turns.
Runtime-generated notices are marked in message metadata and excluded from the
visible source projection (not deleted from canonical history), so a short
correction still references the actual preceding consultant question.

Malformed tool JSON is distinct from schema validation in ToolNode. A public
after-model hook preserves the native function call and returns its paired
error result without executing a tool, then routes back through the official
model budget check. One correction is allowed; a second malformed result ends
with runtime `tool_error`. The retry count survives checkpoint resume. Missing
call identity / unexpected parallel output remains fail-closed; safe abandonment
is now covered by Task 2 below. This is a thin application hook, not a private
converter patch or a claim that ToolErrorMiddleware covers every parse error.

Only synchronous provider invocation is wired. Characterization finds certain
Responses SSE error events do not emerge as adapter exceptions; stream exhaustion
must NOT be interpreted as successful provider completion. Product streaming is
not enabled or certified here. SDK transient retries have no outer model/graph
retry wrapper.

Task 1 full result: **177 passed, 0 skipped** (including 16 existing PG cases + 2 new
root/child/C PG cases). Initial offline result was159 passed/18 skipped; after
Docker recovery the existing dedicated DB was available and all tests passed.
Docker automatic restart remains an unresolved host issue; do not treat DB tests
as proof of that fix. At the Task 1 save point, Task 2 / API / scheduler / UI had
not started. The following section describes the subsequent verified Task 2.
Full evidence, framework links
and review findings: [Task 1 results](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-conversation-lifecycle-results.md).

## Application wiring Task 2 — Checkpoint A passed

`close_turn(graph, config, reason="cancelled" | "configuration_error",
quiescent=True, memory_session=session)` is a synchronous runtime entry, not a
worker cancellation mechanism. The caller must first stop/join the worker and
serialize this document. Pass the latest root document config, not a captured
checkpoint ID or child namespace. No active thread is killed by this function.

For a new employee input use `send_input(graph, config, HumanMessage(..., id=...))`.
It rejects pending work by default. An explicit `abandon_pending=True` plus
`quiescent=True` first closes the previous turn; if reconciliation is unknown,
the new input is not accepted. A previously saved message ID is rejected, not
appended again. To explicitly resume the original work, keep using the official
`graph.invoke(None, config, durability="sync")`; cancellation never calls it.
This is not Task 3's concurrent API admission/idempotency implementation.

**C binding:** public `MemorySession.after_model` saves a runtime-only binding
from canonical AI message ID / tool-call ID to an operation UUID in the same
Saver. UUID5 includes document and employee-input identity; C uses that exact
UUID in its existing durable `PublishRequest`. The model still supplies only
edits, not IDs or receipts. No new store/table, publication schema change,
private namespace discovery, extra model call or custom Agent loop is used.
The tool-hidden C graph is intentionally not claimed as discoverable.

Closure distinguishes these cases: a saved pre-ToolNode after-model checkpoint
proves not-started; an existing ToolMessage or exact C receipt proves a known
result; the reserved pure notification and bound Memory reads can be safely
closed with honest unavailable-result feedback. An entered unknown tool without
a known result remains unknown. Missing receipt
is not proof of failure. Reconciliation only reads `receipt(operation_id)` and
`current()`, never invokes C or publishes. A recovered receipt reports both its
applied head and the current read head, without reverting later publications.
Unknown results retain pending work and cannot advance extraction or accept a
replacement input. Generic unknown tool outcomes likewise remain pending.

Public `get_state(..., subgraphs=True)` supplies the actual child config.
`update_state(values, as_node="TurnOutcome.after_agent")` saves head, tool result,
and terminal outcome together on the final owned child node; a root update
`as_node="analysis"` then merges canonical messages and the boundary. Neither
update runs a model/tool. If the root write fails, repeating `close_turn` merges
the already-terminal child without relabelling it or appending another notice.
The two checkpoints are not one SQL transaction; while the root is pending,
B1 remains blocked. Historical raw checkpoints remain intact.

`closed_turns` maps saved input IDs to actual end-message IDs and outcomes.
`ConversationReader.read(reference, offset)` retains its role-aware 3,000-character
pagination and adds `turns` metadata (`input_id`, `status`, `answer_succeeded`).
B1 receives this metadata in both source/context payloads, so safely closed
failures still supply employee text and prior consultant questions without a
fabricated successful answer. Runtime notices/tools/opaque items remain in
canonical storage but are excluded from visible extraction text. Whole-turn
size bounds still apply, and new B1 ranges cannot skip intervening turns.
Legacy genuinely provider-completed windows remain readable; an unmarked
incomplete response does not become an eligible source.

T2-R01: context first locates the nearest genuinely visible assistant message
before the new window, crossing safely closed turns without visible AI. Its
canonical range continues through the preceding turn's end, retaining all
intervening answers/corrections (e.g. the question, then "不是，是處長"). A short
previous Human-only turn cannot replace this required range. Whole-prior-turn
context remains optional only when it also contains the required question.
Runtime notices are not questions; the original roles and visible text remain
unchanged, with no summary, new reference format or duplicate source store.
The entire required range must fit both `context_chars` and the combined
`max_chars` budget; otherwise planning explicitly rejects before B1 runs.
`context_chars=0` therefore cannot silently discard a necessary question.
R01 focused source/extraction/lifecycle regression: **88 passed**, including
consecutive safely closed failures and complete-range budget rejection.
Independent limited review closed R01 with no newly introduced Important
findings. `capture_input` / C lookup is unchanged.

Final controller verification: **209 passed / 0 skipped in 25.83s**, including
dedicated real PG tests and four root/child/C lifecycle combinations
(resume/cancel × pre/post commit reply loss). Compileall, offline lock and diff
checks passed. Earlier 196/198/204 counts describe intermediate snapshots.
Models use fake HTTP transport; paid calls are zero, not a live-model quality
evaluation. No Docker restart/reset, production changes or API/scheduler/UI
implementation. Stop here before Task3. Detailed history and sources:
[Task2 results](../../docs/specs/2026-09-06-analysis-only-agent-safe-turn-closure-results.md).

Public mechanisms: [middleware hooks/state](https://docs.langchain.com/oss/python/langchain/middleware/custom),
[checkpoint updates/reducers/as_node](https://docs.langchain.com/oss/python/langgraph/checkpointers#update-state),
[subgraph inspection and tool-hidden limitation](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#view-subgraph-state).
Operation binding and closure policy are Caliburn application wiring, not
vendor-prescribed semantic memory or a claim of vendor consensus.

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
and in-run read-view refresh, UI, paid Luna/medium smoke.
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

### B1 bounded validation feedback (2026-09-07, ER-B02)

The [runtime repair plan's public API decision](../../docs/plans/2026-09-07-runtime-recovery-repairs.md)
keeps the identical `ExtractionOutput.model_json_schema()` on native
`with_structured_output(method="json_schema", strict=True, include_raw=True)`.
No tools, manager, model-authored identifiers or extra output fields are added.
The native candidate/raw response is checkpointed first; a separate application
validation step retains the existing 2,000-character line boundary and rejects
empty summaries. Lossless newline normalization remains deterministic; there is
no truncation or automatic Markdown wrapping.

`max_validation_corrections=1` permits at most one application correction per
source window (configurable nonnegative integer; zero disables correction).
This is an engineering initial setting, not vendor consensus. The original
source input and unchanged native AI candidate, including opaque reasoning,
precede private Runtime feedback containing only known failing fields/reasons,
not a Pydantic dump or employee message. No invalid artifacts are saved or
published. Successful extraction still takes one model call per window and
retains the configured per-response output cap.

Candidate, error, correction limit and used count are checkpointed before the
corrective call. Reopening/resuming cannot replenish the saved allowance, even
if constructor settings change; only the next successfully reached window
resets its count. Exhaustion remains pending with a precise error. Refusal,
incomplete responses, malformed native output and transport errors do not enter
the format-correction loop. A transport-interrupted correction resumes that
same reserved call under the SDK's existing transport policy, not a new format
allowance. Saved windows and validated results pending Store writes are not
re-extracted; explicit summary re-extraction uses the same correction boundary
without changing the ordinary source cursor or old artifacts.

Old completed checkpoints remain readable. Old *partial* checkpoints lacking
correction-budget metadata stop explicitly before resume; no allowance is
guessed and no migration/reset is supplied. A response lost before checkpoint
can still be recomputed; this is not an exactly-once HTTP or monetary guarantee.
Offline SDK/MockTransport tests cover correction, exhaustion/reopen, native
reasoning, source isolation, multiple windows and re-extraction; final full-suite
and PostgreSQL verification belong to the controller.

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

Final completed responses without tool calls also validate the staged files via
public `AgentMiddleware.after_model(can_jump_to=["model"])`. A known application
format/reference error returns one private, Runtime-labelled Human message with
the failing file/address and reason, then jumps back to the same Agent. This is
not employee speech, canonical conversation/source, or a fabricated tool result.
The hook is first in the middleware list so existing reverse-order after hooks
count the response before correction returns through the original quota gate.
There is no outer retry, new correction quota, B1 rerun, or extra successful-path
model call; `native_context_view` remains in place. The shared validator is reused
per staged file to identify the location; only known error reasons are classified
as correctable, including checking the cause of wrapped reference errors.

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
cannot become successful no-op publications or final-validation correction.
Unknown backend/configuration errors still fail closed. Collect, immutable save
and publication retain their validation defenses. On interruption, `resume()`
continues the saved correction state, messages, staged edits and official counters;
it cannot reset exhausted limits. Invalid intermediate files never publish.
Budget exhaustion is a safe background failure, not autonomous recovery. The
production retry/cancel/replan interface remains out of scope; do not tell users
all errors are automatically repaired.

This correction path covers new executions and their saved in-agent resumes.
A pre-upgrade checkpoint already paused at outer `collect` may bypass the new
hook; recovering that historical state is not supported/proven by this slice.
No old-job migration, forced replay or rebase is introduced.

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

New employee input pins head, guide, its publication revision, and a real saved
input Q/A reference. The revision is Runtime-owned (0 means no publication).
Read tools use public middleware `request.override(tool=...)` to select this
immutable version. A background publication does not silently switch it.
C uses exact StateBackend edits in private per-invocation staging; all edits
must succeed before save -> durable request -> existing publication/receipt.
No fuzzy edits and no creation of missing Memory. Guide and knowledge publish
together; C leaves B's processed-source cursor unchanged.

Command updates A's read head and ToolMessage together on success/stale;
initial system guide and revision stay fixed within the input, including resume.
Every C result carries the existing Runtime-owned `source_reference`; only a
result matching the Current input reference can supersede that input's initial
view when it supplies a refreshed head/guide. Prior-input C results remain
unchanged canonical history and cannot override a new input's pinned guide.
An old pending checkpoint without the initial revision is labelled `unknown`,
never inferred from a refreshed read head or newer publication; no migration.
This adds no model-authored field, model step, or source-text copy.
On a reconciled older successful request, the result distinguishes
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
