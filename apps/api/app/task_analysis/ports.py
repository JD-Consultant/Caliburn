"""Structural port `task_analysis` needs from a model provider(T5)。

`task_analysis` 不 import 具體的 `OpenRouterAdapter`(那是 provider-specific,
在 ADR 0058 的 import 邊界之外;Task 7 才會把它搬進 `app.adapters.openrouter`)。
它只需要任何滿足這個呼叫形狀的物件——`OpenRouterAdapter.complete()` 已經結構相符,
adapter 端不需要任何改動就能滿足這個 Protocol。
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.model_outcome import ProviderOutcome


class TaskAnalysisModelPort(Protocol):
    async def complete(
        self,
        *,
        instructions: str,
        packet_text: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> ProviderOutcome: ...
