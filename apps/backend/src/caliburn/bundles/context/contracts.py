"""業務 Plugin 向窗口提供的普通回呼；資料與版本在同一 capture 內固定。"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from langgraph.runtime import Runtime

from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import AgentState


class WindowHook(Protocol):
    async def __call__(
        self,
        state: AgentState,
        *,
        previous: Mapping[str, Any] | None,
        rebuilding: bool,
        runtime: Runtime[AgentContext],
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class WindowContribution:
    prepare: WindowHook
    should_renew: Callable[[AgentState, Mapping[str, Any]], bool] | None = None
    prepare_input: WindowHook | None = None
