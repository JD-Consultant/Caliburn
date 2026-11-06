"""工具原生 State 注入、Command 與順序保存。"""

import asyncio
import operator
from collections.abc import Mapping
from typing import Annotated, TypedDict
from uuid import UUID

import httpx2
import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
)
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


class ToolState(TypedDict, total=False):
    ledger: Annotated[list[str], operator.add]


class ToolStateView(TypedDict):
    workspace_id: UUID
    ledger: list[str]


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def write(
        item: str, runtime: ToolRuntime[AgentContext, ToolStateView]
    ) -> Command[object]:
        state = runtime.state
        assert state["workspace_id"] == UUID(int=11)
        invalid = config.get("invalid")
        message = ToolMessage(content="accepted", tool_call_id=runtime.tool_call_id)
        if invalid == "core":
            return Command(update={"messages": [message], "workspace_id": UUID(int=99)})
        if invalid == "unknown":
            return Command(update={"messages": [message], "unowned": "value"})
        if invalid == "route":
            return Command(update={"messages": [message]}, goto="call_model")
        if invalid == "resume":
            return Command(update={"messages": [message]}, resume="answer")
        if invalid == "parent":
            return Command(update={"messages": [message]}, graph=Command.PARENT)
        if invalid == "multiple_messages":
            return Command(update={"messages": [message, message]})
        if invalid == "call_id":
            return Command(
                update={"messages": [ToolMessage(content="bad", tool_call_id="other")]}
            )
        if invalid == "nontext":
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=[{"type": "text", "text": "body"}],
                            tool_call_id=runtime.tool_call_id,
                        )
                    ]
                }
            )
        return Command(
            update={
                "ledger": [item],
                "messages": [
                    ToolMessage(
                        content=",".join([*state.get("ledger", []), item]),
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    tool = StructuredTool.from_function(coroutine=write, description="Append item.")
    return AgentBundle((AgentPlugin("state", tools=(tool,), state_schema=ToolState),))


def test_pure_stateful_tool_reads_prior_tool_update_and_hides_runtime() -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = (
            [
                call("write", "a", '{"item":"alpha"}'),
                call("write", "b", '{"item":"beta"}'),
            ]
            if len(sent) == 1
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="tools",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__)],
                checkpointer=InMemorySaver(),
            ) as agent:
                async for _ in agent.astream(
                    workspace_id=UUID(int=11), turn_id=UUID(int=101), input="go"
                ):
                    pass
                saved = await agent.aget_state(workspace_id=UUID(int=11))
                assert saved.values["ledger"] == ["alpha", "beta"]
                assert "messages" not in saved.values
                checkpoints = [
                    snapshot
                    async for snapshot in agent.aget_state_history(
                        workspace_id=UUID(int=11)
                    )
                ]
                first = next(
                    snapshot
                    for snapshot in checkpoints
                    if snapshot.values.get("ledger") == ["alpha"]
                )
                assert first.values["model_request"]["input"][-1] == {
                    "type": "function_call_output",
                    "call_id": "a",
                    "output": "alpha",
                }

    asyncio.run(run())
    assert sent[0]["tools"][0]["parameters"]["properties"] == {
        "item": {"type": "string"}
    }
    assert [item["output"] for item in sent[1]["input"][-2:]] == ["alpha", "alpha,beta"]


@pytest.mark.parametrize(
    "invalid",
    [
        "core",
        "unknown",
        "route",
        "resume",
        "parent",
        "multiple_messages",
        "nontext",
        "call_id",
    ],
)
def test_invalid_command_cannot_commit_plugin_state_or_tool_output(
    invalid: str,
) -> None:
    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(
                    EventStream(
                        response_events(
                            response_payload([call("write", "a", '{"item":"alpha"}')])
                        )
                    )
                )
            )
        ) as client:
            async with open_agent(
                agent_id="invalid",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"invalid": invalid})],
                checkpointer=InMemorySaver(),
            ) as agent:
                with pytest.raises(ValueError):
                    async for _ in agent.astream(
                        workspace_id=UUID(int=11), turn_id=UUID(int=101), input="go"
                    ):
                        pass
                saved = await agent.aget_state(workspace_id=UUID(int=11))
                assert saved.values["ledger"] == []
                assert saved.values["workspace_id"] == UUID(int=11)
                assert (
                    saved.values["model_request"]["input"][-1].type == "function_call"
                )
                assert saved.next == ("execute_tool",)

    asyncio.run(run())
