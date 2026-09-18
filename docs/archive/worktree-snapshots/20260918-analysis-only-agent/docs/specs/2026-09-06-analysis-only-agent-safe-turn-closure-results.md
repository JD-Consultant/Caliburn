# Q019-APP-01 Task2 — safe closure and extractable sources

2026-09-06. **Checkpoint A passed: 209 passed / 0 skipped; independent R01 re-review CLOSED, no remaining Important findings.** This is the isolated implementation record, not production authority. Latest decisions/design/history are in [main decision register](S:/caliburn/docs/current-decisions.md), [approved Task2 plan](S:/caliburn/docs/plans/2026-09-06-analysis-only-agent-application-wiring.md), and [detailed research/results](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-safe-turn-closure-results.md).

## Scope

Worktree `S:/caliburn/.worktrees/analysis-only-agent`, branch `codex/analysis-only-agent`, Task1 base `3118e8a1`. Only the synchronous conversation/Memory repair/source seam changed. No production, API, scheduler, UI, JD editing, dependency upgrade, migration, new Memory store or model call.

## What changed

- Public middleware saves a runtime-only association between the canonical model/tool call and the existing C publication operation before tool execution. C reuses that operation. Model tool arguments still contain only edits.
- `close_turn` requires a genuinely quiescent worker and serialized document. Known not-started calls receive paired not-executed results; committed C is reconciled using its exact receipt. Missing/unknown results stay pending, block B1 and prevent replacement input. Cancellation never invokes C, publishes new Memory, or rolls back committed Memory.
- Public state updates first seal the child at its final owned node, then merge canonical messages/outcome into the root. These are two checkpoints, not one transaction. A root write failure can be closed again without re-running a model/tool, relabelling the outcome or adding another notice. Historical/provider items remain unchanged.
- `send_input` requires explicit safe abandonment before a replacement input and does not append an already-saved Human ID. It is not concurrent API admission/idempotency.
- Runtime terminal boundaries make successful and safely closed unsuccessful turns extractable without pretending the model answered successfully. Reader pagination preserves roles and full selected text; B1 receives actual terminal metadata and cannot skip unresolved middle turns. Runtime notices remain canonical but do not become employee facts.
- Required prior context preserves the latest visible consultant message and intervening answers, including across consecutive safely closed failures. It uses canonical ranges, not another summary/source copy. If the entire required context cannot fit its configured context/total budget, planning fails before a B1 call rather than silently dropping it.

## Framework mechanisms and limits

[LangChain middleware hooks/state](https://docs.langchain.com/oss/python/langchain/middleware/custom) provide the checkpointed technical binding; [LangGraph update_state](https://docs.langchain.com/oss/python/langgraph/checkpointers#update-state) provides reducer-aware checkpoint updates and public `as_node` routing. [Subgraph inspection](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#view-subgraph-state) does not expose a graph hidden inside a tool; the binding avoids private namespace discovery or replacing the Agent loop.

The operation association, closure policy and source-window selection are approved application wiring, not claims that OpenAI/Anthropic prescribe this exact recipe. Worker stopping/joining belongs to Task3. Unknown tool outcomes remain pending; cancellation is not forced publication. No compatibility promise for old-version pending checkpoints. Native reasoning/compaction and Memory analysis policies are unchanged.

## Verification and review history

- Initial Task2 missing-feature RED: 4 failed / 2 passed; operation/source RED: 12 failed. These were implemented, not skipped.
- Initial integrated PG snapshots: 196 passed / 0 skipped (23.44s), then 198 passed / 0 skipped (23.31s). Not final evidence after later edits.
- Independent review found T2-R01: long previous employee text caused omission of a short consultant question. First fix: 6 RED, 83 focused GREEN; full PG 204 passed / 0 skipped (25.08s). Re-review found the same issue across consecutive unsuccessful turns.
- Second focused repair: 5 RED, 88 focused GREEN. Preserve the question plus intervening employee correction/qualification in actual B1 payloads; exact and insufficient context/total budgets tested. Final independent re-review closed R01 with no newly introduced Important findings. This is a Task2-scoped gate, not whole-branch merge approval.
- Controller latest complete suite: **209 passed / 0 skipped in 25.83s**, including real dedicated PostgreSQL Saver/Store/publication and client reconstruction. Models use fake HTTP transport through the real SDK/framework; **paid calls: 0**. This does not test live-model interview quality.
- `compileall`, `uv lock --check --offline` (73 packages), `git diff --check`: pass. Git LF-to-CRLF notices are not test warnings. No dependency/lock changes.
- Existing dedicated `caliburn-q019-postgres`, loopback55433/q019_agent_test, ownership label checked. Only test-owned records touched. Docker was not restarted/reset; previous startup diagnosis is not declared fixed.

## Next gate

Save Task2 commit/local tag and stop at Checkpoint A to report. Task3–5 are not implemented. No merge/push. Reopen only if a reproducible failure violates these boundaries, the public framework contract changes, or Owner changes scope; do not restart the broad Memory research.
