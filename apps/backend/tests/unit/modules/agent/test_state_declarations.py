"""插件持久欄位與 Node 讀取視圖是兩個不同宣告。"""

import asyncio
import operator
from collections.abc import Mapping
from typing import Annotated, TypedDict

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST, offline_client


class PluginFields(TypedDict):
    count: Annotated[int, operator.add]


class UnknownView(AgentState, total=False):
    undeclared: str


class Reserved(TypedDict):
    messages: list[str]


class Conflict(TypedDict):
    count: str


async def hook(
    state: UnknownView, *, runtime: Runtime[AgentContext]
) -> Mapping[str, object]:
    return {}


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    kind = config["kind"]
    if kind == "reserved":
        return AgentBundle((AgentPlugin("reserved", state_schema=Reserved),))
    if kind == "conflict":
        return AgentBundle(
            (
                AgentPlugin("first", state_schema=PluginFields),
                AgentPlugin("second", state_schema=Conflict),
            )
        )
    return AgentBundle(
        (
            AgentPlugin(
                "view",
                state_schema=PluginFields,
                before_model_step=(
                    PluginStep("unknown", hook, input_schema=UnknownView),
                ),
            ),
        )
    )


@pytest.mark.parametrize("kind", ["reserved", "conflict", "undeclared_view"])
def test_invalid_state_declaration_is_rejected_before_agent_is_ready(kind: str) -> None:
    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("Model called"))
        ) as client:
            with pytest.raises(ValueError):
                async with open_agent(
                    agent_id="schema",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=[BundleConfig(__name__, {"kind": kind})],
                    checkpointer=InMemorySaver(),
                ):
                    pass

    asyncio.run(run())
