"""靜態插件、正常流程、圖外取消與啟動服務的公開契約。"""

from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.prebuilt.tool_node import AsyncToolCallWrapper
from langgraph.runtime import Runtime

from caliburn.modules.agent.plugins.services import (
    PluginServices,
    ServiceBinding,
    ServiceKey,
)


@dataclass(frozen=True)
class AgentContext:
    services: PluginServices


class PluginHook[StateT](Protocol):
    def __call__(
        self, state: StateT, *, runtime: Runtime[AgentContext]
    ) -> Awaitable[Mapping[str, object]]: ...


type PluginWrapper[StateT] = Callable[[PluginHook[StateT]], PluginHook[StateT]]


class PluginCancelHook[StateT](Protocol):
    def __call__(
        self,
        state: StateT | None,
        *,
        workspace_id: UUID,
        turn_id: UUID,
        context: AgentContext,
    ) -> Awaitable[None]: ...


@dataclass(frozen=True)
class PluginStep[StateT]:
    name: str
    node: PluginHook[StateT] | Runnable[StateT, Mapping[str, object]]
    input_schema: type[StateT] | None = None
    wrappers: tuple[PluginWrapper[StateT], ...] = ()
    run_last: bool = False


@dataclass(frozen=True)
class AgentPlugin:
    name: str
    prompt_sections: tuple[str, ...] = ()
    tools: tuple[StructuredTool, ...] = ()
    required_services: tuple[ServiceKey[Any], ...] = ()
    provided_services: tuple[ServiceKey[Any], ...] = ()
    open_services: (
        Callable[
            [PluginServices],
            AbstractAsyncContextManager[tuple[ServiceBinding[Any], ...]],
        ]
        | None
    ) = None
    state_schema: type[Any] | None = None
    on_turn_start: tuple[PluginStep[Any], ...] = ()
    before_model_step: tuple[PluginStep[Any], ...] = ()
    after_model_step: tuple[PluginStep[Any], ...] = ()
    on_turn_end: tuple[PluginStep[Any], ...] = ()
    on_turn_cancel: PluginCancelHook[Any] | None = None
    wrap_tool_call: tuple[AsyncToolCallWrapper, ...] = ()
    required_plugins: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentBundle:
    plugins: tuple[AgentPlugin, ...] = ()
