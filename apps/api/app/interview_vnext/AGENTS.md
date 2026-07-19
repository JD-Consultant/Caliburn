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
- Active implementation handoff: `docs/plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md`
- Active R3 corrective addendum: `docs/plans/2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md`

Until R3-C passes its no-network and real PostgreSQL gates, R4 and paid live are also blocked.
Until V3-5A passes its new live gate, V3-6, production routes, Web wiring, provider promotion,
direct-vendor adapters, and migration 0011 are blocked. The active turn contract target is
`turn.interpret/2.0.0`; do not patch or create new runs with `turn.interpret/1.0.0`.
