"""Active provider-neutral LLM contract schema IDs(R3-C1;修正計畫 §6.1.1)。

executor、provider gate validator 與 eval probes 只 import 這一份常數,不各自
複製字串。`provider.config` artifact 刻意沒有 generic schema ID(composition-owned
provider-specific snapshot,以 content hash 對 binding;§5.2),不得加入本清單。
本 module 只含字串常數:不 import application/evals,也不是第二份 schema catalog
(檔名→schema 內容的 authority 仍是 `schema_exports.SCHEMA_EXPORTS`)。
"""

from __future__ import annotations


MODEL_REQUEST_SCHEMA_ID = (
    "https://caliburn.local/schemas/model-call-request.v2.schema.json"
)
MODEL_RESULT_SCHEMA_ID = (
    "https://caliburn.local/schemas/model-call-result.v2.schema.json"
)
PROVIDER_BINDING_SCHEMA_ID = (
    "https://caliburn.local/schemas/provider-binding.v1.schema.json"
)
SCHEMA_PROJECTION_SCHEMA_ID = (
    "https://caliburn.local/schemas/schema-projection-report.v1.schema.json"
)
EXECUTION_EVIDENCE_SCHEMA_ID = (
    "https://caliburn.local/schemas/provider-execution-evidence.v1.schema.json"
)
CONFORMANCE_SCHEMA_ID = (
    "https://caliburn.local/schemas/provider-conformance-report.v1.schema.json"
)
