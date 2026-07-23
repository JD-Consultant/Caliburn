# Interview vNext implementation rules

This package implements ADR 0034 and the 2026-07-16 greenfield architecture.

## Non-negotiable boundaries

- Do not import or wrap `app.interview.consultant`, `scribe`, `harvest`, `select`, their prompts, or their intermediate state.
- `domain/` may import only the Python standard library, Pydantic, and other `interview_vnext.domain` modules.
- Provider SDK objects, ORM rows, FastAPI request models, and Web DTOs must stop at adapters.
- LLM output is a proposal. Only a deterministic reducer may mutate domain state.
- Employee evidence and reference knowledge are separate source channels.
- Every projected job claim must close over existing evidence IDs.
- Domain objects are immutable; changes return a new state and versioned domain events.
- A repeated command ID is idempotent. A different command with a stale state version is a conflict.
- Do not add an agent framework, graph, vector store, multi-agent handoff, or fine-tuning path without the eval entry conditions in the architecture spec.

## Source of truth

- Architecture: `docs/specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md`
- Decision: `docs/adr/0034-interview-ai-vnext-greenfield-evidence-workflow.md`
- Build order: `docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md`
- V2-B persistence reference: `docs/specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md`
- V2-B implementation handoff: `docs/plans/2026-07-16-interview-vnext-v2b-durable-persistence-plan.md`
- Runtime contract decision: `docs/adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md`
- Grounded short-answer decision: `docs/adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md`
- V3-5A runtime mother handoff: `docs/plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md`
- R5 exact implementation handoff: `docs/plans/2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md`
- Post-R5 product decision: `docs/adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md`
- Completed question selection handoff: `docs/plans/2026-07-23-interview-vnext-question-select-context-loop-plan.md`
- Completed production OpenRouter/consultant loop handoff: `docs/plans/2026-07-23-interview-vnext-production-openrouter-consultant-loop-plan.md`
- Completed R4 provider evidence/conformance evidence: `docs/plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md`
- Completed R3 corrective evidence: `docs/plans/2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md`

R5 grounded short-answer, R5-D bounded correctness closure, the UI-independent minimal Authoring Core, and the
provider-neutral `question.select/1.0.0` Context/Agenda/QuestionFrame slice are complete. Authoring lives in the independent `app/job_authoring/` module; do not retrofit the old
`DocumentVersion/_pending` tree or make Authoring domain import the legacy editor/OCS/indexer contracts.

Product work is standalone/single-user first. Unless the owner explicitly changes scope, do not add organizations,
memberships, ACLs, quotas, billing, tenant administration, or a SaaS test matrix; retained `tenant_id` fields are
storage compatibility only. The employee launches a local Web app; its startup may open a localhost UI, but there is
no remote product URL, registration, login, account, or password flow, and host/port setup must remain an implementation detail. The next slice should compose the existing durable executor/OpenRouter boundary with
`question.select`, then expose the smallest local Web conversation + JD canvas; `episode.code` and grounded task/output
proposals follow. Do not rebuild Agenda as a planner agent, add a graph framework, or start K/S/SaaS before that
vertical path works. The production OpenRouter adapter, exact GPT-5.4 mini flex profile, durable
`question.select` executor, deterministic STOP/explicit-shift control and one paid live smoke are now complete.
The next slice is the smallest localhost conversation + JD canvas route/UI; direct-vendor adapters remain optional.
Do not rebuild the completed provider/loop seam before that visible vertical. Migration `0011_job_authoring_core.py` is
limited to the three exact Authoring tables in the A1 plan. The active turn contract remains
`turn.interpret/2.0.0`; do not patch or create new runs with `turn.interpret/1.0.0`.
