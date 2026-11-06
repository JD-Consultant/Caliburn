# indexer-contract

Single source of truth for the **occupation reference HTTP API** wire shapes. The rebuilt backend's
[occupation_reference module](../../apps/backend/src/caliburn/modules/occupation_reference/README.md)
uses these Pydantic models for FastAPI requests and `response_model` responses. The module runs inside
the main API process. The occupation-reference shapes are maintained in
[references.py](src/indexer_contract/references.py); employee state and JD completion remain outside
this contract.

The model-facing [Job Reference Bundle](../../apps/backend/src/caliburn/bundles/job_reference/README.md)
calls the module directly and owns its cleaned tool projections and Workspace short-code parameters.
Those tool outputs are separate from this HTTP contract.

This is a pure Pydantic package, used by the producer as an editable **path dependency**
(like `ocs-contract`). The producer keeps one typed contract without a separate codegen or JSON-Schema workflow.
