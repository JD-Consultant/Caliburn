"""OPKS 的模型契約(§13)。

`result.py` 是 verifier 與下游吃的**內部**形狀;`wire.py` 的 `opks_result_v1` 才是
**送給模型**的形狀,兩者以 `opks_wire_to_result()` 相接;`prompt.py` 是固定的
Static Instructions。

Task Analysis 的 `prompt.py`／`result.py`／`wire.py` 屬於 `app.task_analysis.llm`
（ADR 0058);這裡只有 OPKS specialist 的 prompt、result 與 wire 形狀。
"""

from app.core.portable_schema import (
    ProviderSchemaPortabilityError,
    assert_portable_strict_output_schema,
    compact_strict_output_schema,
    expand_refs,
    schema_complexity,
)

from .prompt import OPKS_INSTRUCTIONS
from .result import (
    OpksDecision,
    OpksGenerationEntityKind,
    OpksResult,
    OpksResultItem,
)
from .wire import (
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
    "OPKS_INSTRUCTIONS",
    "OPKS_RESULT_WIRE_SCHEMA_NAME",
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
