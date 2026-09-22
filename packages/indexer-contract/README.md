# indexer-contract

Single source of truth for the isolated **indexer query API** wire shapes. `apps/ocs-indexer`
imports these pydantic models as FastAPI request/`response_model`; there is currently no formal
JD App consumer. Historical consumer code and decisions remain in Git and the linked research.

Pure pydantic, distributed as an editable **path dependency** (like `ocs-contract`). The producer
keeps a single typed contract, so no codegen / JSON-Schema is needed — see
`docs/specs/2026-06-28-contract-2-indexer-query-api-research.md` and ADR 0010. Any future consumer
must adopt this contract through a new approved integration rather than importing retired code.
