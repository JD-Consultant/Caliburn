"""選配換窗只改工作 request，不依賴 Memory 實作。"""

from collections.abc import Mapping
from typing import cast

from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState, request_items


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def window(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        request = state["model_request"]
        items = [
            item
            for item in request_items(request)
            if not (isinstance(item, dict) and item.get("content") == "old prefix")
        ]
        return {"model_request": {**request, "input": cast(ResponseInputParam, items)}}

    return AgentBundle(
        (AgentPlugin("window", before_model_step=(PluginStep("compact", window),)),)
    )
