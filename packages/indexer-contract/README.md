# indexer-contract

Single source of truth for the **indexer query API** wire shapes — the HTTP seam between
`apps/ocs-indexer` (producer) and `apps/api` (consumer). Both ends import these pydantic
models (producer as FastAPI request/`response_model`; consumer as `KnowledgePort` return types +
`HttpIndexerClient` parsing), so the request/response contract cannot drift.

Pure pydantic, distributed as a per-app editable **path dependency** (like `ocs-contract`).
This seam is Python↔Python with a single consumer, so no codegen / JSON-Schema is needed — see
`docs/specs/2026-06-28-contract-2-indexer-query-api-research.md` and ADR 0010.
