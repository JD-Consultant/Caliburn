# Consultant Execution Guardrails and Safe Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every A consultant child run enforce the approved 64 model request／63 admitted tool call ceiling, bounded correction episodes, and a final no-tools reply without leaking framework limit messages or replaying uncertain side effects.

**Architecture:** Keep the existing LangChain／LangGraph consultant, OpenRouter Luna model, request-only compaction, Saver messages, JD tool owner, Memory tools and App run closure. Add one App-owned synchronous request guard at the innermost model boundary. It derives correction state from the current run's canonical AI／Tool message pairs, uses the framework's persisted thread counters as the only call counters, turns the last allowed request or a stopped correction episode into `tools=[]` plus `tool_choice="none"`, and leaves generic LangChain limit middleware as error-only backstops. No second state authority or retry loop is introduced.

**Tech Stack:** Python 3.12, LangChain 1.4.0, LangGraph 1.2.11, Pydantic 2, pytest, existing OpenRouter adapter and generated JD contracts.

**Spec:** `docs/specs/2026-09-18-consultant-execution-budget-and-safe-finalization.md` §§1–10; `docs/specs/2026-09-12-jd-relational-agent-tool-contract.md` §§6–7; `docs/specs/evidence/2026-09-10-jd-error-recovery-contract-closure.md` §§2–4

## Decision Preflight

- **Topic ID:** `JD-R002／A-R001`
- **Current stage:** G4 Owner confirmed; this plan prepares G7 and does not change production authority.
- **Binding decisions:** 64 model requests, 63 admitted tool calls, two replacement submissions after the original correctable failure, SDK hidden retry 0, final request has no tools, existing App failure state is the only fallback.
- **This plan's only implementation question:** how to express those decisions through the pinned LangChain middleware and existing canonical messages without a parallel counter／retry authority.
- **Already reviewed evidence:** pinned LangChain 1.4.0 source, current A graph／runtime／tool result code, current compaction and public-history projection, OpenAI Responses request controls, Anthropic tool error guidance, AWS bounded retry／idempotency guidance.
- **Out of scope:** Prompt or Skill tuning, Memory／B1／B2／C redesign, compaction policy changes, provider calls, schema／migration, Web copy changes, production authority, browser journey and paid model validation.

## Official Facts and Caliburn Mapping

- OpenAI Responses accepts an empty tool surface and `tool_choice="none"`; `max_output_tokens` includes visible and reasoning output. This supports the final no-tools request but does not prescribe 64／63. [OpenAI Responses create](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- Anthropic recommends returning an instructive tool error tied to the original tool ID and reports that invalid or missing tool arguments are commonly corrected two or three times. This supports a bounded correction opportunity, not automatic replay of writes. [Anthropic Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- AWS advises limiting retries at one understood layer and requiring idempotency before replaying mutations. This supports keeping model correction separate from provider, Node, SQL and receipt recovery. [AWS REL05-BP03](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_limit_retries.html)
- Pinned LangChain source proves `exit_behavior="end"` inserts artificial AI／Tool messages; `exit_behavior="error"` raises without adding those messages. It also proves thread counters are checkpointed while run counters are invocation-local. The current document graph gives each employee input a new native consultant child namespace, so thread counters are the correct same-run／new-turn boundary.
- The existing A runtime uses `recursion_limit=96`. That cannot be relied on for 64 model plus 63 tool transitions. Reuse the B1／B2 package convention `max(100, max_model_steps * 3 + 6)`, producing 198 for A. This is a framework headroom setting, not a larger product budget.

## Global Constraints

- The authoritative counters remain LangChain's persisted `thread_model_call_count` and `thread_tool_call_count`; do not add a table, checkpoint field, queue, global cache or model-authored counter.
- Derive correction episodes only from the current employee run's canonical `AIMessage.tool_calls` and matched, schema-valid `ToolMessage` results. Never infer an episode from free text.
- A corrected JD operation is a new model-selected submission inside the same run. It is not an HTTP retry, SQL replay, Node replay, receipt replay or whole-agent restart.
- Any call admitted to the tool node consumes the shared 63-call budget even when its structured result is an input／domain error. Reads used as evidence consume the total tool budget but do not reset the correction-submission budget.
- Unknown or unconfirmed effects are reconciled only through the existing operation identity. The guard never creates a replacement operation for `outcome_unknown` or `reconcile_operation`.
- Finalization transforms only the request sent to the model. Canonical messages, compaction state, Prompt, Skills, JD／Memory notices and tool receipts remain unchanged.
- The finalization instruction is a short Runtime constraint appended after request context composition; it is not a new consultant Prompt version.
- The App continues to use synchronous `invoke()`. Do not add an async execution path or `awrap_model_call`; the current product compaction middleware is synchronous as already accepted.
- Do not change B1／B2 profiles, model factory, credential, provider route, output limit, timeout, Web contract or generated schemas.
- All tests are offline with fixed models or existing local test infrastructure. Do not read the real OpenRouter key and do not make provider requests.
- Commit each green task locally as Aris. Do not push.

## Responsibility and File Map

| Responsibility | File／symbol | Planned action |
|---|---|---|
| A model／tool ceilings | `experiments/jd-relational-app/src/jd_relational/consultant_model.py:19-23` | Change only 16／15 to 64／63 and expose derived recursion headroom. |
| Correction reconstruction and final request transform | new `experiments/jd-relational-app/src/jd_relational/consultant_execution.py` | Add pure message inspection plus one synchronous middleware; no persistence. |
| Middleware order and fail-closed framework limits | `experiments/jd-relational-app/src/jd_relational/consultant_context.py:294-341` | Install error-only built-in limits and put the execution guard after request-only context middleware. |
| Root recursion headroom | `experiments/jd-relational-app/src/jd_relational/ai_runtime.py:793-833` | Replace literal 96 with the derived A constant. |
| Real structured JD tool results | `experiments/jd-relational-app/src/jd_relational/consultant_tools.py:397-489` | No schema or behavior rewrite; use its canonical ToolMessages in integration tests. |
| Run closure and receipt preservation | `experiments/jd-relational-app/src/jd_relational/ai_runtime.py:837-972` | Expected verify-only; change only if a failing acceptance test proves a narrow mismatch. |
| Public chat／source filtering | `chat_history.py:142-176`, `conversation_sources.py:338-411` | Verify-only; no new fallback message. |
| Existing UI failure wording | `experiments/jd-relational-app/web/src/components/ChatPanel.tsx:12-15` | Verify-only; retain `原話已保存，回覆未完成`. |
| Durable decision／status | current decision register, approved spec, App README | Update only after code and tests establish the result. |

---

### Task 1: Specify correction episodes as a pure canonical-message decision

**Files:**
- Create: `experiments/jd-relational-app/src/jd_relational/consultant_execution.py`
- Create: `experiments/jd-relational-app/tests/test_consultant_execution.py`
- Read-only dependency: `experiments/jd-relational-app/src/jd_relational/result_transport.py`
- Read-only dependency: `experiments/jd-relational-app/src/jd_relational/generated/reads.py`
- Read-only dependency: `experiments/jd-relational-app/src/jd_relational/transport.py`

**Interface:**

```python
@dataclass(frozen=True)
class ExecutionDecision:
    finalize: bool
    reason: Literal[
        "model_budget", "correction_exhausted",
        "nonrecoverable_result", "no_progress",
    ] | None

def decide_consultant_execution(
    messages: Sequence[BaseMessage],
    *,
    run_id: str,
    model_requests_used: int,
    max_model_requests: int = 64,
    max_correction_submissions: int = 2,
) -> ExecutionDecision:
    """Derive the next request policy from one current run's saved messages."""
```

The function must not return or save a mutable episode object. It reconstructs the open episode on every model boundary as follows:

1. Slice messages from the exactly matching current `HumanMessage.id == run_id`; reject duplicate or missing current-run boundaries.
2. Pair each known JD read／mutation call with exactly one matching ToolMessage by call ID and tool name.
3. Validate mutation results with the existing generated result SSOT and typed read failures with the existing `ReadFailure`; malformed results from known tools fail closed with a fixed internal code instead of being ignored.
4. Treat only `correct_arguments`, `reread_current` and `resolve_dependencies` as model-correctable. `stop` and `reconcile_operation` force finalization.
5. For a mutation-origin episode, later JD／Memory evidence reads do not count as replacement submissions; later mutation submissions do. For a read-origin episode, a corrected call to that same read tool counts as a replacement. A successful corrected read or a mutation `committed／no_change` closes the episode.
6. A second failed replacement exhausts the episode. An exact repeat of canonical tool name＋arguments＋result stops earlier as no progress.
7. `dependent_items` receives no new cascade permission. Existing reads and business-tool validation must still prove an explicit supported reassignment／removal; otherwise the model finalizes by asking the employee.
8. Repair Memory's separate typed `repair_memory` outcome／retry contract remains untouched. This task does not reinterpret it as a JD mutation result.

- [ ] **Step 1: Write RED unit tests for the pure decision**

Add named cases covering:

- `test_original_invalid_input_allows_two_replacements_then_finalizes`
- `test_successful_replacement_closes_the_episode`
- `test_stale_reread_does_not_reset_or_consume_mutation_submissions`
- `test_exact_request_and_result_repeat_stops_without_a_third_try`
- `test_stop_and_reconcile_results_never_authorize_another_tool`
- `test_dependent_items_never_implies_cascade_or_set_null`
- `test_previous_employee_runs_do_not_consume_the_new_child_budget`
- `test_malformed_known_tool_result_fails_closed`

- [ ] **Step 2: Run the new test file and preserve the first RED evidence**

Run from `S:\caliburn\experiments\jd-relational-app`:

```powershell
uv run --frozen pytest tests/test_consultant_execution.py -q
```

Expected before implementation: import failure because `consultant_execution.py` does not exist.

- [ ] **Step 3: Implement the pure decoder and decision**

Use canonical JSON and hashes only to detect exact repeats. Do not compare natural-language meaning, target names or inferred intent. Keep the public tool schemas and stored ToolMessages byte-for-byte unchanged.

- [ ] **Step 4: Run the focused tests to green**

Run:

```powershell
uv run --frozen pytest tests/test_consultant_execution.py -q
```

Expected: all tests pass; no provider call and no new schema artifact.

- [ ] **Step 5: Commit the green unit**

```powershell
git add experiments/jd-relational-app/src/jd_relational/consultant_execution.py experiments/jd-relational-app/tests/test_consultant_execution.py
git commit -m "feat(agent): define bounded consultant correction episodes"
```

---

### Task 2: Install the 64／63 fail-closed guard and final no-tools request

**Files:**
- Modify: `experiments/jd-relational-app/src/jd_relational/consultant_model.py`
- Modify: `experiments/jd-relational-app/src/jd_relational/consultant_context.py`
- Modify: `experiments/jd-relational-app/src/jd_relational/consultant_execution.py`
- Modify: `experiments/jd-relational-app/tests/test_consultant_execution.py`
- Modify: `experiments/jd-relational-app/tests/test_consultant_context.py`
- Modify: `experiments/jd-relational-app/tests/test_consultant_app.py`

**Required assembly:**

```python
middleware = [
    JdNoticeMiddleware(),
    *extra_middleware,
    ModelCallLimitMiddleware(
        thread_limit=MAX_MODEL_STEPS,
        exit_behavior="error",
    ),
    ToolCallLimitMiddleware(
        thread_limit=MAX_TOOL_CALLS,
        exit_behavior="error",
    ),
    *([context_middleware] if context_middleware is not None else []),
    ConsultantExecutionMiddleware(),
]
```

LangChain composes the first wrapper as outermost. This order therefore makes the execution guard the last request transformer before the model: JD／source／Memory／Skills／background context is assembled first, request-only compaction runs second, and only then does finalization remove tools.

The final transform must be equivalent to:

```python
final_request = request.override(
    system_message=append_finalization_instruction(request.system_message),
    tools=[],
    tool_choice="none",
)
```

The instruction permits only a truthful user-facing answer, confirmed saved effects, and unfinished／next-turn items. It forbids any further read, mutation, repair or background request. The middleware validates that the returned AIMessage has no tool calls; a provider violation raises a fixed `ConsultantExecutionError("invalid_final_response")` and creates no synthetic assistant text.

- [ ] **Step 1: Write RED middleware and assembly tests**

Cover:

- `test_request_64_has_no_tools_and_explicit_none_tool_choice`
- `test_framework_limit_backstops_raise_without_artificial_messages`
- `test_early_public_answer_does_not_create_an_extra_request`
- `test_finalization_runs_after_notice_skills_and_compaction_projection`
- `test_finalization_does_not_mutate_canonical_messages_or_compaction_state`
- `test_a_constants_are_64_and_63_without_changing_model_profile`

The composed-context test must assert the actual model request still contains the same JD notice, source notice, Memory notice, Skills／background additions and compacted continuation view that the ordinary request would receive. Only tools, tool choice and the short finalization constraint may differ.

- [ ] **Step 2: Run the focused tests and record RED**

Run:

```powershell
uv run --frozen pytest tests/test_consultant_execution.py tests/test_consultant_context.py tests/test_consultant_app.py -q
```

Expected before implementation: 16／15 assertions, artificial `exit_behavior="end"`, and missing final request transform fail.

- [ ] **Step 3: Implement constants, middleware and exact order**

Set:

```python
MAX_MODEL_STEPS = 64
MAX_TOOL_CALLS = 63
CONSULTANT_RECURSION_LIMIT = max(100, MAX_MODEL_STEPS * 3 + 6)
```

Do not change `MAX_OUTPUT_TOKENS=8192`, reasoning, timeout, model ID, provider route, hidden retry, strict tools or parallel-tool setting. Do not add an async wrapper.

- [ ] **Step 4: Run the focused tests to green**

Run the same command. Expected: all selected tests pass, and graph state contains no LangChain limit text.

- [ ] **Step 5: Commit the green unit**

```powershell
git add experiments/jd-relational-app/src/jd_relational/consultant_model.py experiments/jd-relational-app/src/jd_relational/consultant_context.py experiments/jd-relational-app/src/jd_relational/consultant_execution.py experiments/jd-relational-app/tests/test_consultant_execution.py experiments/jd-relational-app/tests/test_consultant_context.py experiments/jd-relational-app/tests/test_consultant_app.py
git commit -m "feat(agent): reserve a no-tools consultant final response"
```

---

### Task 3: Prove exact 63-tool／64-model lifecycle and counter persistence

**Files:**
- Modify: `experiments/jd-relational-app/tests/test_consultant_execution.py`
- Modify: `experiments/jd-relational-app/tests/test_consultant_context.py`
- Modify: `experiments/jd-relational-app/tests/test_ai_runtime.py`
- Modify: `experiments/jd-relational-app/src/jd_relational/ai_runtime.py`

- [ ] **Step 1: Write RED lifecycle tests using fixed local models**

Required scenarios:

1. A fixed model emits exactly 63 serial one-tool responses followed by one public answer. Assert 63 handlers ran, 64 model requests occurred, request 64 carried no tools／`tool_choice="none"`, and no request 65 exists.
2. A controlled native interrupt／resume in the same consultant child proves persisted thread counters continue rather than reset. Do not emulate resume by starting a new child.
3. A second employee input on the same document creates a new native child namespace and starts at zero counters.
4. A model that answers on request 1 ends normally with one request and no artificial finalization call.
5. A model that attempts a tool from the no-tools request fails closed without executing the tool or saving a fake ToolMessage.
6. Runtime config supplies `CONSULTANT_RECURSION_LIMIT == 198`; the 63／64 fixture reaches the product guard rather than `GraphRecursionError`.

- [ ] **Step 2: Run lifecycle tests and preserve RED evidence**

Run:

```powershell
uv run --frozen pytest tests/test_consultant_execution.py tests/test_consultant_context.py tests/test_ai_runtime.py -q
```

Expected before the runtime change: the literal recursion limit remains 96 and the longest synthetic loop cannot reliably reach its intended final boundary.

- [ ] **Step 3: Replace only the A runtime recursion literal**

In `AiRuntime._run`, import the A recursion constant and pass it through the existing root invocation config. Do not alter `max_concurrency=1`, callback cancellation, durability, thread ID or background behavior.

- [ ] **Step 4: Run lifecycle tests to green**

Run the same command. Expected: all selected tests pass without sleeps, network, key reads or hidden retries.

- [ ] **Step 5: Commit the green unit**

```powershell
git add experiments/jd-relational-app/src/jd_relational/ai_runtime.py experiments/jd-relational-app/tests/test_consultant_execution.py experiments/jd-relational-app/tests/test_consultant_context.py experiments/jd-relational-app/tests/test_ai_runtime.py
git commit -m "test(agent): prove consultant budget and resume boundaries"
```

---

### Task 4: Exercise correction policy through the real tool middleware

**Files:**
- Modify: `experiments/jd-relational-app/src/jd_relational/consultant_tools.py`
- Modify: `experiments/jd-relational-app/tests/test_consultant_tools.py`
- Reuse: `experiments/jd-relational-app/src/jd_relational/consultant_execution.py` and its pure decision tests
- Verify: `experiments/jd-relational-app/tests/test_memory_repair_session.py`
- Verify: `experiments/jd-relational-app/tests/test_consultant_memory_context.py`

- [x] **Step 1: Add RED graph-level correction cases**

Use the existing `AiToolSession`, generated tool shapes, fixed owner and native ToolMessages. Do not construct a second fake result format.

Cover:

- `test_invalid_input_can_be_corrected_twice_but_not_submitted_a_third_time`
- `test_relationship_conflict_uses_reads_without_resetting_the_episode`
- `test_stale_view_requires_current_read_before_replanned_submission`
- `test_committed_or_no_change_closes_the_active_episode`
- `test_save_read_operation_failure_and_unknown_outcome_do_not_replay`
- `test_recovered_intermediate_tool_errors_remain_private_tool_messages`

Also prove `dependent_items` cannot cause an automatic cascade／set-null command: only an explicit model submission that already passes existing read／source／business validation may run.

- [x] **Step 2: Run the graph-level cases and record RED**

Run:

```powershell
uv run --frozen pytest tests/test_consultant_tools.py tests/test_consultant_execution.py -q
```

Expected before integration: the third replacement and exact no-progress repeat are not yet stopped by a request guard.

- [x] **Step 3: Make only narrow integration corrections**

If the pure decision cannot consume an actual result, adapt its decoder to the existing ToolMessage schema. Do not change `tool_output`, generated schemas, receipt identity, operation keys, writer behavior or Memory repair outcomes.

- [x] **Step 4: Run JD and Memory-adjacent regressions**

Run:

```powershell
uv run --frozen pytest tests/test_consultant_tools.py tests/test_consultant_execution.py tests/test_consultant_memory_context.py tests/test_memory_repair_session.py -q
```

Expected: all selected tests pass; C's existing refresh／stale／publication behavior is byte-for-byte unaffected.

- [x] **Step 5: Commit the green unit**

```powershell
git add experiments/jd-relational-app/src/jd_relational/consultant_execution.py experiments/jd-relational-app/tests/test_consultant_execution.py experiments/jd-relational-app/tests/test_consultant_tools.py
git commit -m "test(agent): enforce bounded tool error correction"
```

---

### Task 5: Verify failed finalization preserves durable effects and public boundaries

**Files:**
- Modify only if a failing assertion proves a mismatch: `experiments/jd-relational-app/tests/test_chat_api_postgres.py`
- Verify: `experiments/jd-relational-app/tests/test_ai_runtime.py`
- Verify: `experiments/jd-relational-app/tests/test_chat_history.py`
- Verify: `experiments/jd-relational-app/tests/test_conversation_sources.py`
- Verify: `experiments/jd-relational-app/web/tests/chat-session.test.ts`
- Verify: `experiments/jd-relational-app/web/tests/chat-drafts.test.ts`
- Verify-only product code: `experiments/jd-relational-app/web/src/components/ChatPanel.tsx`

- [x] **Step 1: Extend the existing committed-JD／failed-final test only where needed**

Reuse `test_http_failed_final_model_keeps_saved_input_and_confirmed_committed_jd`. Make its synthetic failure occur on the guard's final no-tools request and assert:

- the original employee input remains saved;
- the committed JD receipt and revision remain unchanged;
- the run closes as `failed` with `response_message_id=None`;
- native canonical messages contain the real Human／AI tool call／ToolMessage only, with no LangChain English limit message and no fixed UI fallback AIMessage;
- chat history and conversation sources expose no assistant fallback text;
- exact lookup returns the same closed result and does not call the model or writer again.

Do not modify App closure code merely because the test is PostgreSQL-backed. First prove a real mismatch.

- [x] **Step 2: Run offline public-boundary tests**

Run:

```powershell
uv run --frozen pytest tests/test_ai_runtime.py tests/test_chat_history.py tests/test_conversation_sources.py -q
```

Expected: all pass. ToolMessages remain private, and no code path creates a fallback AIMessage.

- [x] **Step 3: Run the existing exact PostgreSQL regression when the approved test DB is available**

Run:

```powershell
uv run --frozen pytest tests/test_chat_api_postgres.py::test_http_failed_final_model_keeps_saved_input_and_confirmed_committed_jd -q
```

Expected with test PostgreSQL available: one pass. If the environment marks it skipped, record that as environment-skipped; do not claim PostgreSQL evidence and do not alter product code to remove the skip.

- [x] **Step 4: Verify the existing Web state without changing copy**

Run from `S:\caliburn\experiments\jd-relational-app\web`:

```powershell
node --experimental-strip-types --test tests/chat-session.test.ts tests/chat-drafts.test.ts
```

Inspect `ChatPanel.tsx` and retain the existing saved-input failure label. Expected: tests pass and no Web source change is required.

- [x] **Step 5: Commit only real test／code changes**

If Task 5 required only verification, make no empty commit. If a narrow mismatch was fixed, commit only the affected files:

```powershell
git commit -m "fix(agent): preserve public state after final response failure"
```

---

### Task 6: Run affected regression, independent review and durable closure

**Files:**
- Modify: `docs/current-decisions.md`
- Modify: `docs/specs/2026-09-18-consultant-execution-budget-and-safe-finalization.md`
- Modify: `experiments/jd-relational-app/README.md`
- Modify: this plan's completed checkboxes and evidence section

- [x] **Step 1: Run the affected App regression set**

Run from `S:\caliburn\experiments\jd-relational-app`:

```powershell
uv run --frozen pytest tests/test_consultant_execution.py tests/test_consultant_model.py tests/test_consultant_context.py tests/test_consultant_tools.py tests/test_consultant_app.py tests/test_ai_runtime.py tests/test_chat_history.py tests/test_conversation_sources.py tests/test_continuation_compaction.py tests/test_consultant_memory_context.py tests/test_memory_repair_session.py tests/test_chat_api.py -q
```

Expected: all selected tests pass. Do not expand to the entire 3,000+ suite unless these tests fail outside the edited seam or independent review identifies a concrete wider dependency.

- [x] **Step 2: Compile the affected Python tree**

Run:

```powershell
uv run --frozen python -m compileall -q src tests
```

Expected: exit 0.

- [x] **Step 3: Perform the second-pass scoped code review**

After the focused regression, perform a second-pass scoped review against the task commits. Check:

- middleware order against pinned LangChain source;
- no artificial AI／Tool messages from generic limits;
- no counter reset on same-child resume and a fresh counter on a new employee turn;
- correction parsing uses trusted schemas and does not reinterpret C outcomes;
- no replay of unknown effects;
- compaction／Prompt／Memory／B1／B2／C and provider profile remain unchanged.

No blocking finding remained; the only new code is test-fixture／regression coverage and production files are unchanged.

- [x] **Step 4: Update durable documents with actual evidence**

Change the stage only after tests and review complete. Record exact pass／skip counts, commit IDs, limitations and unchanged gates. Do not write that natural-model quality, browser journey, production authority or paid provider behavior passed.

- [x] **Step 5: Perform final mechanical checks**

Run from repo root:

```powershell
git diff --check
rg -n "TODO|TBD|FIXME|NotImplementedError|pass\\s*$|\\.\\.\\." experiments/jd-relational-app/src/jd_relational/consultant_execution.py experiments/jd-relational-app/tests/test_consultant_execution.py
git status --short
git diff --stat
```

Expected: no whitespace error, no unfinished implementation marker, and only the planned files changed.

- [x] **Step 6: Commit documentation and create the local delivery tag**

```powershell
git add docs/current-decisions.md docs/specs/2026-09-18-consultant-execution-budget-and-safe-finalization.md docs/superpowers/plans/2026-09-18-consultant-execution-budget-and-safe-finalization.md experiments/jd-relational-app/README.md
git commit -m "docs(agent): record consultant execution guardrail evidence"
git tag jd-a-execution-guardrails-reviewed-20260918
```

Do not push the branch or tag.

## Baseline and Completion Evidence

- Planning baseline on 2026-09-18: the existing focused files (`test_consultant_model`, `test_consultant_context`, `test_consultant_tools`, `test_ai_runtime`, `test_chat_history`, `test_conversation_sources`, `test_continuation_compaction`, `test_consultant_app`) passed **218 tests／0 failed** with one pytest cache-permission warning.
- Completion requires the exact Task 6 results, independent review closure and a clean scoped diff.
- A green offline suite means the App wiring satisfies this contract. It does not prove Luna will naturally use all available calls well, provider reliability, long-interview quality, or full browser acceptance.

Task 5–6 completion evidence: the final no-tools regression fixture passed collection and remains environment-skipped without the explicitly opted-in PostgreSQL database; the offline boundary set passed **314 tests**, the Web set passed **62 tests**, and compileall／diff check passed. No production source changed in this task; the test-only changes are the opt-in final no-tools transport assertion and canonical-message/public-boundary checks.

## Self-Review Checklist

- [x] Every requirement in spec §8 maps to at least one named test above.
- [x] No task changes a generated contract, database schema, Prompt, Skill, Memory or background workflow.
- [x] `64／63／2／198` each has one authoritative code owner and a direct test.
- [x] Finalization uses the already composed and compacted request; no canonical message is rewritten.
- [ ] `outcome_unknown` and unconfirmed receipts never create a replacement operation.
- [ ] Public history cannot contain framework limit text, fixed UI fallback text or recovered intermediate tool errors.
- [ ] No unfinished implementation marker, paid call, key read, push or production authority claim remains.
