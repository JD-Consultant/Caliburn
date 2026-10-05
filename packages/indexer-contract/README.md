# indexer-contract

Single source of truth for the independent **indexer query API** wire shapes. `apps/ocs-indexer`
uses these Pydantic models for FastAPI requests and `response_model` responses. The occupation-reference
shapes are maintained in [references.py](src/indexer_contract/references.py); employee state and JD
completion remain outside this contract.

The formal JD App can opt into the reference API over HTTP under
[ADR0080](../../docs/adr/0080-opt-in-public-reference-agent-tools.md). It validates the HTTP boundary
in its own adapter and does not import this Python package. Older profile/task consumer designs
remain historical; the optional reference integration does not restore retired consumer code.

This is a pure Pydantic package, used by the producer as an editable **path dependency**
(like `ocs-contract`). The producer keeps one typed contract, without a separate codegen or
JSON-Schema workflow; the original design is recorded in
[`docs/specs/2026-06-28-contract-2-indexer-query-api-research.md`](../../docs/research/retrieval/2026-06-28-contract-2-indexer-query-api-research.md)
and [ADR0010](../../docs/adr/0010-indexer-contract-shared-package.md).
