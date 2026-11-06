"""只有 Tool 與持久欄位的合成插件，使用官方 Command 回傳更新。"""

import operator
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Annotated, TypedDict
from uuid import UUID

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
)
from caliburn.modules.agent.plugins.services import ServiceKey


class CommandChannels(TypedDict, total=False):
    journal: Annotated[list[str], operator.add]
    aliases: dict[str, str]


@dataclass
class CommandProbe:
    observed: list[tuple[UUID, str, list[str], str | None]] = field(
        default_factory=list
    )


COMMAND_PROBE = ServiceKey[CommandProbe]("checkpoint-command-probe")


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def advance(label: str, runtime: ToolRuntime[AgentContext]) -> Command[str]:
        previous = list(runtime.state.get("journal", []))
        previous_alias = runtime.state.get("aliases", {}).get("k1")
        runtime.context.services.require(COMMAND_PROBE).observed.append(
            (runtime.state["workspace_id"], label, previous, previous_alias)
        )
        if config.get("fail") and label == "beta":
            raise RuntimeError("synthetic command outage")
        return Command(
            update={
                "journal": [label],
                "aliases": {"k1": label},
                "messages": [
                    ToolMessage(
                        content=f"{label} after {','.join(previous) or 'none'}",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    return AgentBundle(
        (
            AgentPlugin(
                "command-state",
                tools=(
                    StructuredTool.from_function(
                        coroutine=advance,
                        description="Advance a synthetic saved value.",
                    ),
                ),
                state_schema=CommandChannels,
                required_services=(COMMAND_PROBE,),
            ),
        )
    )
