# Task 3 fix round 2 — frozen narrow handoff

R02 remaining actual-supply integrity finding is fixed. R01/R03/R04 code is unchanged. No new durable field, state owner, model chain, schema or DTO.

## Change

The existing request-local model preparation now deep-copies complete supplied JD ToolMessage projections (including content, ID, name and tool_call_id) plus visible matching AI tool-call records and AI message IDs. The same final public model wrapper compares the actual final request projection before invoking the existing provider handler. Keeping a ToolMessage ID while changing its body or pairing no longer preserves the view claim. Non-JD messages/System customization remain outside this exact JD projection. Compaction still occurs on its existing path before preparation. No projection/hash is persisted; the existing ContextVar is reset in finally.

The new actual graph/SDK test has a same-ID body mutation negative and a normal jd_read-to-next-request positive. The negative performs the initial read-producing model call, then refuses the changed next request with zero provider entries for that request (one total for the completed initial call), retains the prior manifest across saved checkpoint views, and keeps canonical ToolMessage text unchanged. The positive sends the original text on the next SDK request and pairs its updated manifest with the returned response.

## Evidence

- task-3-fix2-red.txt: 1 expected failure (same ID body mutation was accepted), 1 passing normal path; 6.71 seconds.
- task-3-fix2-green.txt: 6 passed, 8 deselected, 8.21 seconds. New two cases plus the four directly affected R02 schema/notice/System/Command cases from fix1. The -k filter also deselected the provider-binding file; those cases are explicitly run in the next log rather than claimed here.
- task-3-fix2-boundary.txt: 4 passed, 6.37 seconds. Three existing provider schema/factory checks plus the actual compaction/notice/result-coverage case.
- Total: 10 distinct directly affected cases passed, no failure/skip. No 77/177 matrix rerun. Local dedicated PostgreSQL and SDK MockTransport only; no keys or paid calls.
- git diff --check -- experiments/analysis-agent passed; README original first 11 lines remain equal to original task-3 snapshot.

Exact three changed paths relative to fix1 are task-3-fix2-files.json. Existing native selection fixture unchanged. Prior reports and raw RED/GREEN evidence preserved. No git mutation/subagents or changes to root-owned durable evidence/.gitattributes. FROZEN for root narrow review; no outstanding context needed.
