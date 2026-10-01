# Task5 fix1 — root takeover, independent closure pending

2026-09-10; isolated `codex/analysis-only-agent`, BASE `8eec072d51e97735b22c5f0df598b67101fe570b`. Original implementer hit quota twice; root alone continued its preserved partial changes. No other code writer, production change, new authority, paid/model request, key read, dependency change or push.

## Findings addressed

- R01: final same-lock admission repeats original-key/input, archive, pending, foreground/owner and selection version checks; selection active reservation is released only inside that final lock, no intervening admission window. Actual archive interleaving test rejects before run/Human/model.
- R02: exact original recovery key is read on later refresh, while no-key discovery owns the current gate. Clearing the server descriptor no longer erases cachelost committed/no_change/failure. Late generation/identity checks and dirty/candidate protections remain. Three new actual-session cases pass.
- R03: finite actual Pydantic `restart_required` field projects retained native cleanup blockage without a fabricated run/manual descriptor. A failed head read still fetches that independent owner gate. Actual workspace renders a restart diagnostic even with null request_key/no run; tells employee to retain page/dirty/question, controlled stop and same original startup, then explicit status re-read. This isolated slice adds no generic cancel route or daily startup UI; P5 still owns that entry. API native-owner fixture, actual session and rendered workspace counterexample pass; no new headed browser claim.
- R04: recovery reconciliation and stop/abandon closure wait outside shared admission RLock, using same document reservation/generation. RLock still protects shared state; startup has not opened admission and drain waits release the Condition lock. Real PG head lock held for A while B is admitted passes. Both stop/abandon actual graph closure barrier cases also admit B. No SQL authority changes, striped-lock engine, throughput benchmark or 10–100x claim.
- R05: full manual payload first reads exact original receipt/digest. Optional matching descriptor cleanup failure or sibling owner cannot mask terminal. Actual full POST clear-fail with/without sibling returns committed and retains gate.
- R06: explicit recovery/stop stop admission at shutdown; close_entries joins the existing drain. Response projection is inside the final same-lock release while entry still counted, preventing a late old finally from releasing a newer reservation. Barrier test proves close waits for admitted recovery, rejects new recovery and joins both threads with captured exceptions. A transient intermediate projection regression was caught and corrected.
- R07: existing Starlette TestClient/AnyIO deprecation remains visible; no silent suppression or unrelated upgrade.

## Verification (do not sum overlapping rounds)

- Original author's RED preserved: `task5-fix1-service-red.log` 4 FAIL/1 PASS, `task5-fix1-r06-red.log` 1 FAIL, `task5-fix1-r02-red2.log` 3 FAIL. Tiny original r02-red/green logs were execution errors, not PASS evidence.
- Root partial code check: `task5-root-fix1-service-check2.log` 5 PASS,23.68s. First `service-check.log` failed before tests due launcher-relative executable.
- Added R03 RED: `task5-root-fix1-r03-web-red.log` 1 FAIL. `task5-root-fix1-r03-api-red.log` 3 FAIL/8 PASS: missing R03 diagnostic plus two existing recovery projections still seeing closing=True (one clear-failure assertion then fixture cleanup error). Root fixed atomic projection/release; raw retained. Wrapper exit0 in that red run does not override pytest's FAIL output.
- Final `task5-root-fix1-api-green.log`: **54 PASS**,77.55s across fix1/manual recovery/admission/close reconcile/native lifecycle/original service. Real dedicated JD PG plus actual graph/mock provider; all calls to paid providers zero.
- Final `task5-root-fix1-memory2-green.log`: **63 PASS**,33.85s, original five planned API/conversation/PG conversation/publication/PG publication groups. Existing separate q019_agent_test only. First memory-green failed to import analysis_agent before tests; explicit source paths fixed the harness, no source change.
- Final `task5-root-fix1-web-green.log`: **35 PASS**,7 files,5.46s; actual session/rendered workspace, same native UI test suite. No live model.
- `task5-root-fix1-codegen.log`, `task5-root-fix1-check-codegen.log`, `task5-root-fix1-types.log`, `task5-root-fix1-lint.log`: exit0. Fresh generated schema/DTO match, Web TypeScript and eslint pass. Authored scoped diff check passes; Git LF/CRLF notices only.

Original Task5 first failures and NL08 suspended-child/NL10 manual-A+selection-B/NL11 nested provenance limits remain exactly as initial report; no repeat broad crash matrix without source changes to those mechanisms. HTTP worker previously launched predates these changes; it is not evidence for final source. Task5 remains unaccepted/uncommitted until independent narrow closure. Task6/P3/P6/production remain incomplete.

## Review package

Exact current raw source hashes and delta against initial reviewed snapshot: `.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-5-fix1-review-manifest.json`, `task-5-fix1-review.diff` and `task-5-fix1-snapshot/`. All unlisted original31 source hashes checked unchanged. Source shape SSOT and three model tools unchanged; only App recovery output generated from actual DTO.

Limited official lock evidence: `scratch/task-5-lock-evidence.md` (reviewer authored separately without seeing fix1). Root does not call short shared-state locks non-mainstream or label PG advisory locks a substitute for native ownership.
