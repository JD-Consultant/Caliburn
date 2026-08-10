"""Structural port `opks` needs from a model provider(T5)。

`opks` 不 import 具體的 `OpenRouterAdapter`(那是 provider-specific,在 ADR 0058
的 import 邊界之外;Task 7 才會把它搬進 `app.adapters.openrouter`)。它只需要任何
滿足這個呼叫形狀的物件——`OpenRouterAdapter.complete()` 已經結構相符,adapter 端
不需要任何改動就能滿足這個 Protocol。

同形、但由 `app.opks` 擁有——與 `app.task_analysis.ports.TaskAnalysisModelPort`
刻意不共用同一個定義,因為兩個 feature module 互不 import 對方(ADR 0058 rule 2)。
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.model_outcome import ProviderOutcome


class OpksModelPort(Protocol):
    async def complete(
        self,
        *,
        instructions: str,
        packet_text: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> ProviderOutcome: ...
