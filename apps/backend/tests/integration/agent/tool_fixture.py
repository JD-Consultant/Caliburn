"""Checkpoint 整合測試共用的合成工具與可觀察外部效果。"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

from langchain_core.tools import StructuredTool, ToolException
from langgraph.prebuilt import ToolRuntime

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
)
from caliburn.modules.agent.plugins.services import ServiceKey


@dataclass
class ToolProbe:
    effects: list[str] = field(default_factory=list)
    after_effect: Callable[[str], Awaitable[None]] | None = None
    business_error: bool = False
    fail_before_effect: bool = False


PROBE = ServiceKey[ToolProbe]("checkpoint-tool-probe")


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def read_alpha(item: str, runtime: ToolRuntime[AgentContext]) -> str:
        probe = runtime.context.services.require(PROBE)
        if probe.fail_before_effect:
            raise RuntimeError("synthetic tool outage")
        probe.effects.append(item)
        if probe.after_effect is not None:
            await probe.after_effect(item)
        if probe.business_error and item == "alpha":
            raise ToolException("Synthetic business rejection")
        return "read " + item

    return AgentBundle(
        (
            AgentPlugin(
                "tools",
                required_services=(PROBE,),
                tools=(
                    StructuredTool.from_function(
                        coroutine=read_alpha,
                        description="Read.",
                        handle_tool_error=True,
                    ),
                ),
            ),
        )
    )
