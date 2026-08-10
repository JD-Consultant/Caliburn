"""OPKS 的模型契約(§13)。

Task Analysis 的 `prompt.py`／`result.py`／`wire.py` 搬到 `app.task_analysis.llm`
（ADR 0058）；這裡只剩 OPKS specialist 的 prompt、result 與 wire 形狀，直到
`app.opks`（Task 5）把它們接手為止。
"""

from app.core.portable_schema import (
    ProviderSchemaPortabilityError,
    assert_portable_strict_output_schema,
    compact_strict_output_schema,
    expand_refs,
    schema_complexity,
)

from .opks_result import (
    OpksDecision,
    OpksGenerationEntityKind,
    OpksResult,
    OpksResultItem,
)
from .opks_prompt import OPKS_INSTRUCTIONS
from .opks_wire import (
    OPKS_RESULT_WIRE_SCHEMA_NAME,
    OPKS_WIRE_SCHEMA_PATH,
    OpksResultWire,
    OpksWireItem,
    committed_opks_wire_schema,
    opks_result_wire_provider_schema,
    opks_wire_to_result,
    render_opks_wire_schema_file,
)

__all__ = [
    "OPKS_RESULT_WIRE_SCHEMA_NAME",
    "OPKS_INSTRUCTIONS",
    "OPKS_WIRE_SCHEMA_PATH",
    "OpksDecision",
    "OpksGenerationEntityKind",
    "OpksResult",
    "OpksResultItem",
    "OpksResultWire",
    "OpksWireItem",
    "ProviderSchemaPortabilityError",
    "assert_portable_strict_output_schema",
    "committed_opks_wire_schema",
    "compact_strict_output_schema",
    "expand_refs",
    "opks_result_wire_provider_schema",
    "opks_wire_to_result",
    "render_opks_wire_schema_file",
    "schema_complexity",
]
