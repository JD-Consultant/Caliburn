# First database-session candidate audit — 2026-07-15

Status: `OWNER_CONFIRMED_TEST_DATA / DEVELOPMENT_FIXTURE_COMMITTED / REPLAY_BLOCKED`

> 2026-07-15 correction: the repository owner confirmed that all records in this database are test data.
> The earlier privacy hold is therefore not applicable to this candidate. The privacy scanner results remain
> useful as a tooling smoke test, but privacy is not the reason replay remains blocked.

This report contains aggregate metadata only. It does not contain transcript text, job title, profile/user
IDs, document claims, guard messages, customer names, or source UUIDs.

## 1. Scope and controls

- Database access was read-only; only the existing project PostgreSQL `db` container was started.
- Inventory output was limited to session UUID plus aggregate counts. The selected source UUID is not copied
  into repository artifacts; the private export uses a salted fingerprint.
- The first conservative export was written outside Git. After the owner confirmed that the data is
  synthetic, it was re-exported with `--test-data` and committed as
  `cases/development/TEST-SYNTHETIC-SESSION-001`.
- The test-data export retains the synthetic semantics so negative evidence, contradictions and workflow
  relations remain available to graders.
- Direct identifier scan found zero remaining email/UUID/URL/Taiwan-phone matches.
- Conservative privacy pre-screen found one `ORGANIZATION_CUE` in transcript line 17. Two
  `LONG_NUMBER` findings are the date component of the case id in `case.json` and `gold.json`, not source
  content. Because the source is owner-confirmed test data, this finding does not require a privacy hold.
- The committed case is `privacy.status=synthetic`, `manual_review_required=false`. This classification is
  specific to the current fixture and does not weaken the default controls for future production data.

Reproducible tooling:

- `inventory_sessions.py`: content-free DB inventory.
- `export_candidate.py`: read-only export outside Git with known-value replacements.
- `privacy_scan.py`: category/location-only residual scan.
- `candidate_metrics.py`: content-free quality and latency metrics.

## 2. Why this candidate was selected

The database contained one synthetic interview session, so no success/incident stratified sampling was possible. It
is useful as the first mixed candidate because it has both positive and failure signals:

| Signal | Observed value | Interpretation limit |
|---|---:|---|
| Employee turns | 10 | Enough material for a first claim annotation pass; not evidence of role coverage. |
| Consultant turns | 10 | Complete alternation in the stored transcript; adaptive-policy quality is ungraded. |
| Employee characters | 3,586 | Information volume only; semantic quality is unknown. |
| Accepted review events | 105 | Human/UI acceptance signal, not claim-level correctness or JD fidelity. |
| LLM calls | 30 | High call amplification relative to 10 employee answers. |
| Guard outcomes | 105 pending-add, 12 verify-reject, 3 drop | Shows productive writes and contract friction in the same session. |
| Session state | active/survey after 10 employee turns | Candidate `long_active_session` signal; stopping quality is ungraded. |

The case is therefore tagged `guard-alert`, `long-active-session`, `mixed-acceptance`, and
`missing-initial-fixtures`. It is a development incident candidate, not a held-out promotion case.

## 3. Call and latency evidence

All 30 recorded calls used the stored model label `openai/gpt-5.4-mini`. This is an observation about this
session, not a recommendation or a controlled model comparison.

| Call role | Calls | Total latency | p50 | p95 | Guard outcomes |
|---|---:|---:|---:|---:|---|
| `interview` | 10 | 22,316 ms | 1,438 ms | 5,221 ms | none recorded |
| `select` | 20 | 178,900 ms | 4,005 ms | 38,548 ms | all 105 pending-add, 12 verify-reject, 3 drop |
| Total | 30 | 201,216 ms | 2,941 ms | 38,548 ms | aggregate above |

The `select` role consumed 88.9% of recorded model latency. Migration 0009 preserves these historical rows
as `stage=select|interview` and `outcome=legacy_unknown`; it deliberately does not pretend they succeeded.
The historical audit role name is too coarse to prove
whether each call was pool selection, extraction, retry, or another sub-pass; the next trace version must
use distinct stage names and outcomes.

Two turn-level clusters must be retained as regression targets:

- Turn 13 had one `interview` and three `select` calls, totaling 61,337 ms; one select call reached
  38,548 ms. The extra select call suggests a retry/fallback, but current audit data does not persist an
  reliable outcome, so this remains an inference.
- Turn 19 had one `interview` and two `select` calls, totaling 50,942 ms; one call reached 47,314 ms. The
  same turn produced seven verify rejects: six `invariant`, one `hygiene`.

Prompt and completion token columns were null for all 30 calls. Metrics now report
`recorded_calls=0, total=null`; treating missing telemetry as zero would understate cost and hide prompt
growth.

## 4. Output-contract evidence

The 12 verifier rejects split into:

| Verify check | Count | Safe reason classification |
|---|---:|---|
| `hygiene` | 6 | all six classified `non_plain_single_line` |
| `invariant` | 6 | all six remain `other`; stored 80-character guard truncation is insufficient for a reliable subtype |

This evidence supports a narrow conclusion: the current selection/extraction path sometimes asks the LLM
to emit values or write instructions that the deterministic document contract rejects. It does **not**
show that the guard should be relaxed. The guard prevented invalid mutations; the architectural question is
how to avoid paying for and depending on invalid mutation proposals.

The C1 experiment should therefore test:

1. LLM emits evidence claims with source/subject/polarity/time/typicality, not mutable document paths.
2. A deterministic reducer owns correction, contradiction and supersession.
3. A separate projector maps only accepted/sufficient evidence to document operations.
4. The existing verifier remains the final mutation boundary.

This is consistent with the upstream experiment plan and does not yet prove C1 wins. Claim-level gold and
an isolated baseline are still required.

## 5. Observed document and acceptance limits

The export-time document has 213 objects, 119 arrays, 685 object fields, 171 array items, 496 strings and
4,576 string characters. These are shape metrics only.

The equality `105 pending-add == 105 accepted review events` is not a semantic score. Possible
explanations include correct suggestions, permissive review behavior, batch acceptance, or UI workflow
effects. Without claim labels and reviewer rationale, the audit must not use acceptance rate as a proxy for:

- evidence correctness;
- ownership/polarity/typicality correctness;
- task/output/indicator distinction;
- JD completeness;
- wording quality;
- absence of unsupported inferences.

## 6. Why C0 replay is blocked

All three required historical start fixtures are unavailable:

- turn-zero document;
- turn-zero interview state;
- immutable reference snapshot used by that historical run.

The production draft was updated in place, and the audit table lacks complete prompts, raw/parsed model
responses and state deltas. The export-time document and state are stored separately as observed artifacts;
they are not placed into replay start fixtures.

Therefore:

- `replay.ready=false` is mandatory;
- the current candidate can support failure localization and claim-level static evaluation;
- it cannot produce a trustworthy historical C0 score;
- reconstructing the missing reference from current knowledge would introduce temporal leakage;
- replaying from the final observed draft would test an easier, false task.

## 7. Required instrumentation before the next consented pilot

Persist the following immutable artifacts for each eval-enabled session:

| Stage | Required artifact |
|---|---|
| Session start | initial document, initial session state, reference snapshot id/content hash, guide/policy version |
| Each model call | stage role, provider, requested/resolved model, prompt hash, tool-schema hash, tokens, latency, outcome |
| Each employee turn | state-before revision and exact transcript sequence boundary |
| Extraction | parsed evidence candidates plus source turn/span; raw response in restricted storage |
| Verification | per-operation check and stable reason code, without destructive message truncation |
| Reduction/projection | deterministic input/output hash and state/document delta |
| Session end | final state/document snapshot, unresolved gaps, stop reason |

Migration `0009` and the opt-in runtime now implement the first capture slice: immutable turn-zero
document/state/reference artifacts, per-turn before/after snapshots, stage outputs, tool results, trajectory
hashes, session-final snapshots, stage/provider/requested-model/attempt/outcome/prompt/tool-schema audit fields,
and a PostgreSQL trigger that rejects artifact `UPDATE` while preserving cascade/privacy `DELETE`.

This implementation is not yet a complete provider replay trace. The current LLM port does not expose
resolved model, provider-internal retries, raw provider response or token usage; a failed request also rolls
back the same transaction, so failure traces need a separate transaction/outbox before promotion. Future
production data still requires explicit consent, retention, access control and deletion policy.

## 8. Decision and next actions

Decision: `CAPTURE_FOUNDATION_IMPLEMENTED / NEW_REPLAY_READY_PILOT_REQUIRED`; do not start C1 production
implementation from this historical case.

1. Completed: classify the owner-confirmed source as synthetic and commit the development fixture.
2. Completed: annotate 22 required evidence claims, allowed/confirmation/forbidden inferences, three
   episodes and four state expectations; retain `annotation.status=maintainer_checked` pending domain review.
3. Completed: implement migration 0009 and the opt-in immutable capture foundation, disabled by default.
4. Next: expose provider-resolved model, tokens, raw/parsed responses, per-attempt prompts/outcomes and
   failure traces through the LLM port.
5. Next: run a fresh captured synthetic pilot from turn zero and verify every artifact hash/transition before
   marking any case replay-ready.
6. Collect at least 3–5 incidents and 3–5 successes across role families; this database currently has only
   one mixed case.
7. Run C0 only on cases with genuine initial fixtures and frozen reference snapshots.

Methodology and external-source rationale are documented in:

- `docs/specs/2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md`, sections 22–24.
- `docs/specs/2026-07-15-c0-c1-interview-eval-experiment-plan.md`, especially layers/gates E2–E6.
- OpenAI evaluation best practices and Anthropic agent-eval guidance cited in those documents.
