# B1／B2 Background Agent Compaction Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the completed non-destructive continuation-compaction middleware to B1 and B2 so B1 may compact only previously processed source windows, B2 keeps its fixed task verbatim, and both preserve canonical messages and attempt isolation.

**Architecture:** Keep compaction App-owned and inject one `AgentMiddleware` through the existing package workflows; the package owns graph state and lifecycle but never imports the App implementation or selects a provider. B1 uses a role-specific profile with the same latest-human protection as A, so a normal single source window is never compacted and only a prior completed window becomes eligible after Runtime advances to the next one. B2 preserves its first task message and may compact completed model/tool waves inside one attempt; every new stale attempt starts with empty compaction state.

**Tech Stack:** Python 3.12, LangChain 1.4.0, LangGraph 1.2.11, Pydantic 2.13.5, pytest 9.1.1.

**Spec:** `docs/specs/2026-09-16-openrouter-continuation-compaction-design.md`

**Execution status (2026-09-17):** Tasks 1–4 are committed as `3017dccd`, `8a7fb965`, `5064d315`, `0d0829d6`, `5ae63c0e`, and review tightening `792f20d9`. Task 5 is documentation-only: it records fresh offline regression evidence and commits the seven owned documents. Independent review, broad whole-branch review, and the local tag are controller responsibilities after this task; this worker does not run or mark them complete.

## Global Constraints

- Canonical interview messages, signed source references, the evidence registry, staged cases, staged understandings, Memory publications, and JD state remain unchanged by compaction.
- A continuity summary is non-authoritative request Context. It is never employee evidence, a case citation, Memory, a JD basis, or a substitute for exact source reads.
- B1 normally receives one complete source batch and must not add a fixed summary call. With multiple source windows, the latest not-yet-processed `HumanMessage` remains verbatim; only a previous window whose model/tool wave completed and whose `window_position` checkpoint advanced may enter compaction.
- B1 processing eligibility comes from the existing Runtime graph boundary, not an LLM-authored `processed` flag and not citation presence alone.
- B2 keeps the first task `HumanMessage` verbatim for the whole attempt. Same-attempt recovery restores compaction; a new stale attempt starts empty.
- Summary calls use the exact injected role model boundary, no business tools, no fallback, and no hidden retry added by this slice. The later formal OpenRouter/Luna role-model factory remains a separate unit.
- Reuse the existing middleware, safe tool-wave boundary, prefix digest, `ExtendedModelResponse`/`Command`, Saver, role limits, and source readers. Add no dependency, database table, migration, scheduler, registry, source copy, new Agent, or new summary schema.
- Use fixed offline models only. Do not read credentials, call a provider, run a paid smoke, change Prompt/Skills/Memory semantics, implement C, or change managed App/production authority.
- Preserve the current branch. Do not create another worktree, merge, or push.

## File and Responsibility Map

- `experiments/jd-relational-app/src/jd_relational/continuation_compaction.py`: shared request-only middleware and explicit A/B1/B2 role profiles.
- `packages/consultant-memory/src/caliburn_memory/case_maintenance.py`: B1 graph state, attempt lifecycle, and optional App-owned context-middleware seam.
- `packages/consultant-memory/src/caliburn_memory/understanding_workflow.py`: B2 graph state, attempt lifecycle, and optional App-owned context-middleware seam.
- `experiments/jd-relational-app/src/jd_relational/background_memory_app.py`: constructs B1/B2 compaction middleware from the exact injected role model and explicit output reserve.
- `experiments/jd-relational-app/tests/test_continuation_compaction.py`: pure role-profile and request-view contracts.
- `packages/consultant-memory/tests/test_case_maintenance_workflow.py`: B1 middleware placement and attempt-state forwarding.
- `packages/consultant-memory/tests/test_understanding_workflow.py`: B2 middleware placement and attempt-state forwarding.
- `experiments/jd-relational-app/tests/test_background_memory_app.py`: App assembly identity, role profile, reserve, and no-I/O construction.
- `experiments/jd-relational-app/tests/test_background_agent_compaction.py`: real `create_agent`/Saver integration for B1 multi-window and B2 attempt isolation with synthetic models.
- Existing decision/spec/README files already modified in the working tree: final status and evidence only after tests pass.

---

### Task 1: Lock the B1 role profile and processed-window boundary

**Files:**
- Modify: `experiments/jd-relational-app/src/jd_relational/continuation_compaction.py`
- Modify: `experiments/jd-relational-app/tests/test_continuation_compaction.py`

**Interfaces:**
- Consumes: existing `CompactionProfile`, `select_safe_boundary()`, `build_request_view()`, and `ContinuationCompactionMiddleware`.
- Produces: `B1_COMPACTION_PROFILE: CompactionProfile` with `preserve_initial_messages=0` and `protect_latest_human_turn=True`.

- [ ] **Step 1: Write failing B1 role tests**

  Import `B1_COMPACTION_PROFILE` and add these exact behavioral tests:

  ```python
  def test_b1_single_current_window_is_never_a_compaction_boundary():
      messages = [
          HumanMessage(id="window-1", content="尚在處理的完整訪談窗口"),
          AIMessage(
              id="b1-call",
              content="讀取案例",
              tool_calls=[{"name": "read_case", "args": {"id": "A"}, "id": "call-a"}],
          ),
          ToolMessage(id="b1-tool", name="read_case", tool_call_id="call-a", content="A result"),
          AIMessage(id="b1-done", content="完成目前工具 wave"),
      ]
      profile = B1_COMPACTION_PROFILE.model_copy(update={"keep_messages": 1})
      assert select_safe_boundary(messages, profile) is None


  def test_b1_previous_processed_window_becomes_compactable_only_after_next_window_arrives():
      messages = [
          HumanMessage(id="window-1", content="已完整處理的第一段訪談"),
          AIMessage(id="window-1-done", content="第一段處理完成"),
          HumanMessage(id="window-2", content="目前尚未完整處理的第二段訪談"),
          AIMessage(id="window-2-work", content="正在處理第二段"),
      ]
      profile = B1_COMPACTION_PROFILE.model_copy(update={"keep_messages": 1})
      boundary = select_safe_boundary(messages, profile)
      assert boundary == 2
      state = ContinuationCompaction(
          format_version=1,
          summary_text="第一段訪談與處理進度的非權威延續摘要。",
          covered_through_message_id="window-1-done",
          covered_prefix_digest=canonical_prefix_digest(messages[:boundary]),
      )
      view = build_request_view(messages, state, profile)
      assert view[0].id.startswith("continuation-summary:")
      assert [message.id for message in view[1:]] == ["window-2", "window-2-work"]
      assert messages[0].id == "window-1" and messages[2].content.endswith("第二段訪談")
  ```

- [ ] **Step 2: Run the focused tests and verify RED**

  From `experiments/jd-relational-app`:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_continuation_compaction.py -q -p no:cacheprovider
  ```

  Expected: collection fails because `B1_COMPACTION_PROFILE` does not exist.

- [ ] **Step 3: Add only the explicit B1 profile**

  Add beside the existing A/B2 profiles:

  ```python
  B1_COMPACTION_PROFILE = CompactionProfile(
      preserve_initial_messages=0,
      protect_latest_human_turn=True,
  )
  ```

  Do not change `select_safe_boundary()`, digest semantics, summary prompt, or A/B2 profiles unless the new tests reproduce a concrete defect.

- [ ] **Step 4: Run the focused tests and verify GREEN**

  Use the Step 2 command. Expected: all continuation-compaction tests pass.

---

### Task 2: Add one optional package middleware seam and durable state field

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/case_maintenance.py`
- Modify: `packages/consultant-memory/src/caliburn_memory/understanding_workflow.py`
- Modify: `packages/consultant-memory/tests/test_case_maintenance_workflow.py`
- Modify: `packages/consultant-memory/tests/test_understanding_workflow.py`

**Interfaces:**
- Consumes: one App-created `AgentMiddleware` instance or `None`.
- Produces: a keyword-only `context_middleware: AgentMiddleware | None = None` parameter on both `CaseMaintenanceWorkflow` and `UnderstandingMaintenanceWorkflow`.
- Produces state key: `continuation_compaction: dict[str, Any] | None`, owned by the injected middleware but carried by the outer package graph and Saver.

- [ ] **Step 1: Write failing middleware-placement tests**

  Add this test helper in each workflow test module:

  ```python
  class RequestProbe(AgentMiddleware):
      def __init__(self):
          self.requests = []

      def wrap_model_call(self, request, handler):
          self.requests.append(deepcopy(request.messages))
          return handler(request)
  ```

  Extend each local workflow helper to pass `context_middleware` through its existing `**options`. Add one B1 test:

  ```python
  probe = RequestProbe()
  source, _session, _model, workflow = _workflow(
      [
          _call("finish_case_maintenance", {}, "finish"),
          _done("done"),
      ],
      context_middleware=probe,
  )
  batch, _window, _context = _one_window(source)
  result = workflow.start(batch, base_publication_revision=0, base_version=None)
  assert probe.requests
  payload = json.loads(next(
      message.content for message in probe.requests[0]
      if isinstance(message, HumanMessage)
  ))
  assert "NEW_SOURCE" in payload
  assert result["continuation_compaction"] is None
  ```

  Add one B2 test using the existing harness:

  ```python
  probe = RequestProbe()
  _source, _session, model, workflow, case_stage, ids = _harness(
      [], context_middleware=probe,
  )
  model.replies.extend(_no_op_replies(ids, "probe"))
  result = workflow.run_attempt(case_stage, case_attempt_id=str(uuid4()))
  task = next(message for message in probe.requests[0] if isinstance(message, HumanMessage))
  assert "B1_CHANGES" in json.loads(task.content)
  assert result["continuation_compaction"] is None
  ```

- [ ] **Step 2: Run package workflow tests and verify RED**

  From `packages/consultant-memory`:

  ```powershell
  ..\..\experiments\jd-relational-app\.venv\Scripts\python.exe -m pytest tests\test_case_maintenance_workflow.py tests\test_understanding_workflow.py -q -p no:cacheprovider
  ```

  Expected: constructor failures because neither workflow accepts `context_middleware`, and results do not carry the compaction state field.

- [ ] **Step 3: Implement the narrow package seam**

  Add to both state schemas:

  ```python
  continuation_compaction: NotRequired[dict[str, Any] | None]
  ```

  Add the optional constructor parameter, validate it, retain it for configuration inspection, and append it last in the `create_agent` middleware list. In B1 use:

  ```python
  if context_middleware is not None and not isinstance(context_middleware, AgentMiddleware):
      raise ValueError("context_middleware must be an AgentMiddleware")
  self.context_middleware = context_middleware
  middleware = [
      CaseMaintenanceResponseGuard(),
      ModelCallLimitMiddleware(thread_limit=max_model_steps, exit_behavior="error"),
      ToolCallLimitMiddleware(thread_limit=max_tool_calls, exit_behavior="error"),
  ]
  if context_middleware is not None:
      middleware.append(context_middleware)
  ```

  B2 uses the same shape with `UnderstandingMaintenanceResponseGuard()`. Initialize `continuation_compaction` to `None` for a fresh `run_attempt()` and `start()`. When legacy `start()` replaces a previous completed job on the same thread, clear it together with `RemoveMessage(REMOVE_ALL_MESSAGES)`. Do not clear it on `resume()` or on lookup of the same attempt.

- [ ] **Step 4: Run package workflow tests and verify GREEN**

  Use the Step 2 command. Expected: both workflow suites pass, with existing no-middleware behavior unchanged.

- [ ] **Step 5: Commit the package seam**

  ```powershell
  git add packages/consultant-memory/src/caliburn_memory/case_maintenance.py packages/consultant-memory/src/caliburn_memory/understanding_workflow.py packages/consultant-memory/tests/test_case_maintenance_workflow.py packages/consultant-memory/tests/test_understanding_workflow.py
  git commit -m "feat(memory): accept background context middleware"
  ```

---

### Task 3: Assemble B1/B2 compaction from each exact role model

**Files:**
- Modify: `experiments/jd-relational-app/src/jd_relational/background_memory_app.py`
- Modify: `experiments/jd-relational-app/tests/test_background_memory_app.py`
- Modify: `experiments/jd-relational-app/tests/support/layered_background_support.py`

**Interfaces:**
- Consumes: injected `case_model`, injected `understanding_model`, explicit `case_max_output_tokens`, and explicit `understanding_max_output_tokens`.
- Produces: one `ContinuationCompactionMiddleware` per role, using `B1_COMPACTION_PROFILE` or `B2_COMPACTION_PROFILE` with the matching main-output reserve.

- [ ] **Step 1: Write failing composition assertions**

  Extend the existing `build()` helper and factory calls with:

  ```python
  case_max_output_tokens=8192,
  understanding_max_output_tokens=8192,
  ```

  In `test_build_binds_one_authority_per_document_without_io_or_model_calls`, assert:

  ```python
  assert isinstance(first.case_workflow.context_middleware, ContinuationCompactionMiddleware)
  assert first.case_workflow.context_middleware.summary_model is case_model
  assert first.case_workflow.context_middleware.profile.protect_latest_human_turn is True
  assert first.case_workflow.context_middleware.profile.preserve_initial_messages == 0
  assert first.case_workflow.context_middleware.profile.main_output_reserve_tokens == 8192

  assert isinstance(
      first.understanding_workflow.context_middleware,
      ContinuationCompactionMiddleware,
  )
  assert first.understanding_workflow.context_middleware.summary_model is understanding_model
  assert first.understanding_workflow.context_middleware.profile.preserve_initial_messages == 1
  assert first.understanding_workflow.context_middleware.profile.protect_latest_human_turn is False
  assert first.understanding_workflow.context_middleware.profile.main_output_reserve_tokens == 8192
  ```

  Keep the existing assertions that construction performs no SQL and no model call.

- [ ] **Step 2: Run the composition test and verify RED**

  From `experiments/jd-relational-app`:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_background_memory_app.py -q -p no:cacheprovider
  ```

  Expected: factory-signature and `context_middleware` assertion failures because the App does not yet construct these middlewares.

- [ ] **Step 3: Implement App-owned role assembly**

  Import the shared middleware and profiles, require the two output-token values, and construct:

  ```python
  case_compaction = ContinuationCompactionMiddleware(
      summary_model=case_model,
      profile=B1_COMPACTION_PROFILE.model_copy(update={
          "main_output_reserve_tokens": case_max_output_tokens,
      }),
  )
  understanding_compaction = ContinuationCompactionMiddleware(
      summary_model=understanding_model,
      profile=B2_COMPACTION_PROFILE.model_copy(update={
          "main_output_reserve_tokens": understanding_max_output_tokens,
      }),
  )
  ```

  Pass each middleware and its matching `max_output_tokens` into the corresponding package workflow. Do not bind tools to the summary model, clone a provider client, inspect credentials, or add fallback. Update the two known test/support callers with explicit `8192` values.

- [ ] **Step 4: Run composition and adjacent assembly tests and verify GREEN**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_background_memory_app.py tests\test_layered_background_dispatch.py tests\test_background_host.py -q -p no:cacheprovider
  ```

  Expected: all selected tests pass; construction still has zero SQL setup and zero model calls.

- [ ] **Step 5: Commit App assembly**

  ```powershell
  git add experiments/jd-relational-app/src/jd_relational/background_memory_app.py experiments/jd-relational-app/tests/test_background_memory_app.py experiments/jd-relational-app/tests/support/layered_background_support.py experiments/jd-relational-app/src/jd_relational/continuation_compaction.py experiments/jd-relational-app/tests/test_continuation_compaction.py
  git commit -m "feat(memory): assemble background compaction profiles"
  ```

---

### Task 4: Prove real B1/B2 graph lifecycle without provider calls

**Files:**
- Create: `experiments/jd-relational-app/tests/test_background_agent_compaction.py`

**Interfaces:**
- Consumes: Tasks 1–3, actual `CaseMaintenanceWorkflow`/`UnderstandingMaintenanceWorkflow`, `InMemorySaver`, canonical source readers, and one role-aware synthetic chat model used for both summary and main calls.
- Produces: end-to-end evidence for B1 processed-window eligibility, canonical preservation, same-attempt recovery, and stale/new-attempt isolation.

- [ ] **Step 1: Add a role-aware synthetic model**

  Implement one `BaseChatModel` whose `_generate()` identifies a summary call only from `SUMMARY_SYSTEM_PROMPT`, records separate `summary_requests` and `main_requests`, and returns queued completed `AIMessage` values. Use the same model object as both the workflow model and middleware `summary_model`; this proves boundary reuse without a provider call.

  ```python
  class RoleAwareModel(BaseChatModel):
      main_replies: list[AIMessage]
      summary_replies: list[AIMessage]
      main_requests: list = Field(default_factory=list)
      summary_requests: list = Field(default_factory=list)

      @property
      def _llm_type(self):
          return "background-compaction-offline-test"

      def bind_tools(self, tools, **kwargs):
          return self

      def _generate(self, messages, stop=None, run_manager=None, **kwargs):
          target = self.summary_requests if (
              messages and isinstance(messages[0], SystemMessage)
              and messages[0].content == SUMMARY_SYSTEM_PROMPT
          ) else self.main_requests
          target.append(deepcopy(messages))
          replies = self.summary_replies if target is self.summary_requests else self.main_replies
          return ChatResult(generations=[ChatGeneration(message=replies.pop(0))])
  ```

- [ ] **Step 2: Write the B1 multi-window contract test**

  Use the existing native conversation-source fixtures to create at least two safe interview exchanges and force source delivery into two windows. Inject a B1 profile copied with `trigger_input_tokens=1`, `keep_messages=1`, and a deterministic test token counter returning `100`.

  Assert all of the following in one test:

  ```python
  assert len(model.summary_requests) == 1
  assert "第一段" in model.summary_requests[0][-1].content
  assert "第二段" not in model.summary_requests[0][-1].content
  assert "對話延續摘要" in model.main_requests[1][0].content
  assert any("第二段" in str(message.content) for message in model.main_requests[1])
  assert not any("第一段" in str(message.content) for message in model.main_requests[1][1:])
  assert any("第一段" in str(message.content) for message in result["messages"])
  assert any("第二段" in str(message.content) for message in result["messages"])
  assert result["continuation_compaction"] is not None
  ```

  Retain both window source references from the Runtime payload and assert the existing source reader can still return their exact text after compaction. This proves the summary changed only the model request view.

  Add a separate single-window test with the same low trigger and multiple tool calls; assert `summary_requests == []`. The latest source message protects the whole current-window interaction, so this is a behavior assertion, not a token-count assumption.

- [ ] **Step 3: Write the B2 attempt-lifecycle contract test**

  Build one completed B1 stage with an in-memory bundle, then run B2 with a low-trigger `B2_COMPACTION_PROFILE`. Force one successful read tool wave, one later synthetic transport failure, and resume the same attempt.

  Assert:

  ```python
  saved = workflow.graph.get_state(workflow._attempt_config(first_attempt)).values
  assert saved["continuation_compaction"] is not None
  assert sum(isinstance(message, HumanMessage) for message in saved["messages"]) == 1
  resumed = workflow.run_attempt(case_stage, case_attempt_id=first_attempt)
  assert resumed["case_attempt_id"] == first_attempt
  assert model.main_requests[-1][0].model_dump() == saved["messages"][0].model_dump()
  ```

  Run the identical completed B1 stage under a different `case_attempt_id`. Assert its first main request contains the complete task `HumanMessage`, contains no `continuation-summary:` message, and does not contain the first attempt's summary text. Do not inspect private provider payloads.

- [ ] **Step 4: Run the new integration tests and verify RED, then GREEN after Tasks 1–3**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_background_agent_compaction.py -q -p no:cacheprovider
  ```

  Before Tasks 1–3: expected constructor/state/assembly failures. After Tasks 1–3: expected all tests pass with zero network calls.

- [ ] **Step 5: Commit lifecycle evidence**

  ```powershell
  git add experiments/jd-relational-app/tests/test_background_agent_compaction.py
  git commit -m "test(memory): prove background compaction lifecycle"
  ```

---

### Task 5: Regression, documentation closure, review, and local delivery

**Files:**
- Modify: `docs/current-decisions.md`
- Modify: `docs/specs/2026-09-16-openrouter-continuation-compaction-design.md`
- Modify: `docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md`
- Modify: `docs/specs/2026-09-17-layered-memory-background-workflow-design.md`
- Modify: `docs/plans/2026-09-16-b1-case-maintainer.md`
- Modify: `packages/consultant-memory/README.md`
- Modify: `docs/superpowers/plans/2026-09-17-background-agent-compaction-wiring.md`

**Interfaces:**
- Consumes: all prior tasks and already-approved documentation corrections in the working tree.
- Produces: one evidence-backed status update, one local documentation commit, and the Task 5 report; no tag, merge, push, independent review, or broad whole-branch review.

- [x] **Step 1: Run all directly affected offline suites**

  From `experiments/jd-relational-app`:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_continuation_compaction.py tests\test_background_agent_compaction.py tests\test_background_memory_app.py tests\test_consultant_context.py tests\test_consultant_app.py tests\test_layered_background_dispatch.py -q -p no:cacheprovider
  ```

  From `packages/consultant-memory`:

  ```powershell
  ..\..\experiments\jd-relational-app\.venv\Scripts\python.exe -m pytest tests\test_case_maintenance_workflow.py tests\test_understanding_workflow.py tests\test_background_workflow.py -q -p no:cacheprovider
  ```

  Observed: App **52 passed, 0 skipped**; package **50 passed, 0 skipped**.

- [x] **Step 2: Run compile and repository checks**

  From `experiments/jd-relational-app`:

  ```powershell
  .\.venv\Scripts\python.exe -m compileall -q src tests
  ```

  From `packages/consultant-memory`:

  ```powershell
  ..\..\experiments\jd-relational-app\.venv\Scripts\python.exe -m compileall -q src tests
  ```

  From the repository root:

  ```powershell
  git diff --check
  git status --short
  ```

  Observed: both `compileall` commands exited 0 with no output; `git diff --check` exited 0 with only line-ending conversion warnings and no whitespace errors; status contained exactly the seven task-owned documents.

- [x] **Step 3: Update status only with observed evidence**

  Mark B1/B2 App-side request-only compaction complete only if the exact integration and affected suites pass. Record actual pass/skip counts. Keep formal OpenRouter/Luna role-model factory, layered C repair, managed App callback, paid/natural-model validation, and complete App journey explicitly incomplete. Do not claim that normal B1 always calls compaction or that a summary is evidence.

- [x] **Step 4: Self-review the plan/spec mapping and stale wording**

  Verify every binding rule in spec sections 4–6 and 8–10 has a test or an explicitly unchanged existing test. Run:

  ```powershell
  rg -n "整批 canonical 訪談永遠不得摘要|canonical 訪談 batch 是受保護來源|固定 canonical batch 永不被 summary 取代" docs packages\consultant-memory\README.md
  ```

  Any remaining hit in a live decision or current responsibility document must be removed or explicitly marked superseded; historical evidence may remain only when its successor is linked.

  Observed: two hits remain—the command above and the B1 historical sentence that explicitly says the wording is superseded and links its successor boundary. No live unsuperseded hit remains.

- [ ] **Step 5: Controller requests independent review and closes concrete findings**

  Controller-owned after Task 5. It must review the exact diff against `CTX-C001` and `MEM-L001`. Required checks: no unprocessed B1 source can enter a boundary; same B1/B2 model object supplies summary; summary has no business tools; new attempts clear derived state; canonical Saver messages remain equivalent within the integration test's observed scope; no provider/credential/DB/schema/Prompt/Memory/C scope entered. Task 5 does not mark independent or broad branch review complete and does not upgrade the integration test into publication／JD byte-for-byte evidence.

- [x] **Step 6: Commit remaining documentation after fresh verification**

  ```powershell
  git add docs/current-decisions.md docs/specs/2026-09-16-openrouter-continuation-compaction-design.md docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md docs/specs/2026-09-17-layered-memory-background-workflow-design.md docs/plans/2026-09-16-b1-case-maintainer.md docs/superpowers/plans/2026-09-17-background-agent-compaction-wiring.md packages/consultant-memory/README.md
  git commit -m "docs(memory): close background compaction wiring"
  ```

  Do not tag, merge, or push. The controller creates the local tag only after final review and fresh verification.
