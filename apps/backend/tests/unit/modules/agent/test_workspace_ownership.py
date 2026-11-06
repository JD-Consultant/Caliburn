"""Workspace 歸屬在 State 更新保存前即維持不變。"""

import asyncio
from collections.abc import Mapping
from typing import Literal
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import ServiceKey
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    response_events,
    response_payload,
    run_turn,
    sse_response,
)

OBSERVED = ServiceKey[list[UUID]]("observed-workspaces")


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def update(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        return {
            "workspace_id": state["workspace_id"]
            if config["same_workspace"]
            else UUID(int=99)
        }

    async def downstream(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        runtime.context.services.require(OBSERVED).append(state["workspace_id"])
        return {}

    if config["node_kind"] == "subgraph":
        graph = StateGraph(AgentState, context_schema=AgentContext)
        graph.add_node("update", update)
        graph.add_edge(START, "update")
        graph.add_edge("update", END)
        first = PluginStep("update", graph.compile(), input_schema=AgentState)
    else:
        first = PluginStep("update", update)
    return AgentBundle(
        (
            AgentPlugin(
                "ownership",
                required_services=(OBSERVED,),
                on_turn_start=(first, PluginStep("downstream", downstream)),
            ),
        )
    )


@pytest.mark.parametrize("node_kind", ["hook", "subgraph"])
@pytest.mark.parametrize("same_workspace", [False, True])
def test_workspace_update_is_checked_before_downstream_work(
    node_kind: Literal["hook", "subgraph"], same_workspace: bool
) -> None:
    observed: list[UUID] = []
    model_calls: list[bool] = []
    workspace_id = UUID(int=1)

    def respond(request: httpx2.Request) -> httpx2.Response:
        model_calls.append(True)
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="ownership",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                checkpointer=InMemorySaver(),
                external_services=(OBSERVED.bind(observed),),
                bundles=[
                    BundleConfig(
                        __name__,
                        {"node_kind": node_kind, "same_workspace": same_workspace},
                    )
                ],
            ) as agent:
                if same_workspace:
                    await run_turn(agent, workspace_id=workspace_id)
                    await run_turn(agent, workspace_id=workspace_id)
                    assert observed == [workspace_id, workspace_id]
                    assert model_calls == [True, True]
                else:
                    with pytest.raises(ValueError, match="Workspace ownership"):
                        async for _ in agent.astream(
                            turn_id=uuid4(), workspace_id=workspace_id, input="go"
                        ):
                            pass
                    assert observed == []
                    assert model_calls == []
                    history = [
                        snapshot
                        async for snapshot in agent.aget_state_history(
                            workspace_id=workspace_id
                        )
                    ]
                    saved = await agent.aget_state(
                        workspace_id=workspace_id,
                        checkpoint_id=history[0].config["configurable"][
                            "checkpoint_id"
                        ],
                    )
                    assert saved.values["workspace_id"] == workspace_id
                    assert saved.next
                    if node_kind == "hook":
                        # 最新讀取會重套原生 pending writes，不能隱藏壞更新。
                        with pytest.raises(ValueError, match="Workspace ownership"):
                            await agent.aget_state(workspace_id=workspace_id)

    asyncio.run(run())
