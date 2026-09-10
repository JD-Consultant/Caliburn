# Task 3 implementer report — FROZEN / ready for independent review

Scope: JD-R002/C03, isolated G7 Task3 on `codex/analysis-only-agent`, BASE `23bf0161d3d61dc8517ec1ecf4ee9ad5cb8e5a6d`. All changes confined to `S:/caliburn/.worktrees/analysis-only-agent`; no commits/tags, agents, model keys, paid requests, production/root lock or Memory owner changes.

## Implemented seams

- The two exact design §6.2 descriptions were added only to the SSOT. Existing codegen regenerated all three artifacts, and check-codegen passed. Shapes, strict constraints and enums remain unchanged.
- Original `JdToolSession` factories stay in ToolNode, with recursive full schema validation before references/source/base/Node. The model wrapper supplies exact raw Responses function schemas (`strict:false` only for JD). Composition rejects reserved names; the innermost public `JdExecutionIdentity` wrapper checks the final actual tool identity after other middleware overrides.
- Current/history/target/selection and pinned continuation reads; same-base current targets versus read-only historical/navigation references; full-revision outgoing/incoming K/S refs and set/unset mapping; initial insert→read→link; exact before/after revision or actual operation history, including empty no-change differences.
- Saved input→AI message→tool call→operation/digest/base/commands checkpoint precedes Node. Receipt-first replay does not allocate another insertion; unconfirmed reconcile_operation preserves pending binding and prevents another model call. Existing same-document stop Event is forwarded through edit/read-selection to the existing native cancel parameter. Full close/reconcile/process lifecycle is Task5.
- Original ConversationReader/Memory source factory acquisition, canonical scope/window validation and current input source handles; no source text in JD tables or fabricated verification. Source acquisition does not come from parseability, JD citations or arbitrary same-name tool results.
- Request-only untrusted App JD context after compaction, with response-backed manifest in the same model checkpoint and shared normal child/root return. It counts committed manual events, including reverts/metadata-only edits, distinguishes mixed origins and no-change, keeps the turn interval visible, and conservatively handles unknown/unpaired baselines. 16 KiB/four event details/2 KiB preview limits, exact pairs only if they fit; no new model/tool/token budget.
- Actual API generated selection capture shape, native admission/recheck, checkpointed per-run context and `jd_read` issuance. Pure API runs clear selection; stale/cross-scope/unsupported captures are refused.

## RED and debugging evidence

1. Initial three requested test files: **2 failed, 1 skipped**, missing `analysis_agent.jd_references`/source boundary. Missing PG DSN was explicitly a skip, not a PG pass. The actual PG test was subsequently run against the existing dedicated database.
2. Model-view helper RED: **1 failed, 1 skipped**, missing `analysis_agent.jd_context`.
3. API selection RED: **1 failed**, `MessageInput.jd_selection` rejected as extra input.
4. First actual graph characterization exposed fixture assumptions: Task8 body does not contain the literal 每月; corrected selection uses the returned fixture body target. Fixed SDK responses needed distinct response IDs across the actual loop. Runtime incomplete-response checks were retained.
5. First MV wire assertions incorrectly treated actual SDK string content as a list; changed test reading to the actual SDK representation. Compaction is after the system message, not necessarily item zero; official tool-limit errors are plain ToolMessages, not JD JSON. These test assumptions were corrected without weakening runtime state/limits.
6. Final logging harness attempt (`task-3-final-tests.txt`) failed in pytest initialization because its Tee lacked isatty; no tests executed. Retained unchanged. The same matrix is recorded using external Tee in `task-3-final-tests-r2.txt`.

Focused results before final snapshot: **8 passed** (actual JD tool graph); **3 passed** (SDK schema/API shape); **20 passed, 2 fixture-observation failures**; then **17 passed** (remaining model-view/provider/source matrix), and **6 passed** (dynamic replacement refusal plus original Memory reader). These overlap and are not summed as a final total.

## Verification and MV coverage

Final exact command/output: `task-3-final-tests-r2.txt`: **177 passed, 0 failed, 0 skipped, 1 existing Starlette deprecation warning, 169.04 seconds**. Matrix includes all six Task3 test files, affected `test_jd_store.py` selection classification, and existing service/publication/conversation lookup/lifecycle/API/live Memory/native continuity regressions. The dedicated PG is `q019_jd_app_20260910`, loopback with guarded connect timeout, unique document IDs, no reset/drop. Existing unrelated Memory PG fixtures are not run against the JD database.

- MV01–05: next pure interview request, repeated manual saves/revert, AI/manual ordering, exact marks plus no-change exclusion; original unchanged r2 content compared in full after monthly edit.
- MV06–08: long CJK/emoji preview, latest-four/omission counts, history creating-event navigation, pinned read/comparison pagination, current and history page authority; supplied results recorded only when visible in the next actual request.
- MV09–11: cross-document manifest/ref/source rejection, unknown/unconfirmed/no-change outcomes, canonical HumanMessage and original source projection, real Memory reader alongside JD.
- MV12–14: two distinct Python processes using official PG Saver, response-backed baseline; old unpaired manifest becomes unknown; native compaction precedes reinjected context and removes prior result coverage claims.
- MV15–17: DB/context capacity failure before handler, saved original input retained; navigation does not grant writes; stopped after-model snapshot contains response and matching manifest in the saved model state, normal child return shares it with root.
- MV19: existing tool limit stops a partially read history/document; continuation remains explicit and guidance requires reporting unread scope. No budget extension or extra background model.
- MV18/full cancellation deliberately deferred to Task5, as authorized; same stop parameter and unresolved-operation gate are the finite Task3 seam only.

## Self-review and limits

The official local LangChain factory deduplicates tools through ToolNode.tools_by_name, composes middleware wrappers in order, and supports ExtendedModelResponse state-only commands. The extra final identity guard contains no execution/retry logic. Source instrumentation remains outside the existing Memory tool replacement wrapper; the guard only validates JD capabilities, so original Memory reads remain intact.

Root-node read pages preserve whole native nodes rather than inventing a text codec/range or diff engine. Individual large nodes are not truncated; existing native document and request-budget limits still apply. Exact current/pairs are request-only; checkpoint manifests/bases store references and finite descriptors, not another current JD. Provider acceptance, natural tool choice, professional JD quality, browser/IME and paid latency/cost are not proved by MockTransport. No product/production authority adoption is claimed.

Changed files: SSOT and its three generated artifacts; `jd_tools.py`, `jd_references.py`, `jd_context.py`; api/conversation/jd_contract/jd_service/jd_engine/service; six Task3 test files, fresh-process worker, actual Plate selection fixture; README appended after prior content; tool contract §3.2 semantic note. All earlier dirty README/research/register files remain owned by their original work; controller should stage only this task's changes.


## Final freeze verification

- 2026-09-10: final 177-item matrix passed; no code changes after that successful run.
- Final `npm run check-codegen -w @caliburn/jd-editor-contract` passed (official generated outputs match SSOT).
- Root-scoped `git diff --check -- docs/specs/contracts/jd-editor-v2.schema.json experiments/analysis-agent experiments/jd-editor/contract` exit 0. Only Git CRLF/LF notices, no whitespace errors.
- The first same check was mistakenly run with root-relative paths from the isolated npm directory and matched nothing; it is not counted as evidence. It was then correctly executed from the checkout root.
- Exact changed paths are in `task-3-files.json`. The native selection fixture is `experiments/jd-editor/fixtures/task3-selection.mjs` (actual createJdEditor + editor.tf.select; no browser claim).
- README prior dirty first 11 lines are preserved; only the Task3 section was appended. The pre-existing untracked tool-contract design file receives only the §3.2 creating-event semantics paragraph.
- Task3 code is frozen for controller review; implementer did not commit/tag or spawn a reviewer. MV18 and full writer/process lifecycle remain Task5; zero paid model requests.
