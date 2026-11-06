"""工具本身帶完整說明，不另加 Prompt。"""

from collections.abc import Mapping

from langchain_core.tools import StructuredTool

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentPlugin,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def echo(item: str) -> str:
        return item

    return AgentBundle(
        (
            AgentPlugin(
                str(config.get("name", "tools")),
                tools=(
                    StructuredTool.from_function(coroutine=echo, description="Echo."),
                ),
            ),
        )
    )
