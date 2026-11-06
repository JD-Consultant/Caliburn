"""原生工具宣告、同一步選用與私有解析資料的配對。"""

import asyncio
from collections.abc import Mapping
from typing import TypedDict, cast

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolRuntime
from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    MODEL_REQUEST,
    TEST_WORKSPACE_ID,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


class SelectionFields(TypedDict, total=False):
    selection_label: str


class SelectionState(AgentState, SelectionFields):
    pass


def create_bundle(config: Mapping[str, object]) -> AgentBundle:

    async def read_alpha(item: str, runtime: ToolRuntime[AgentContext]) -> str:
        state = cast(SelectionState, runtime.state)
        return f"{state['selection_label']}/{item}"

    async def read_blocks(item: str) -> list[dict[str, str]]:
        return [{"type": "text", "text": item}]

    tool = StructuredTool.from_function(
        coroutine=read_blocks if config.get("nontext") else read_alpha,
        name="read_alpha",
        description="Read.",
    )

    async def select(
        state: SelectionState, *, runtime: Runtime[AgentContext]
    ) -> SelectionState:
        request = state["model_request"]
        tools = list(request.get("tools", ()))
        if config.get("disabled") or (
            config.get("disable_next") and state["model_step"] > 1
        ):
            tools = []
        if config.get("unknown_declaration"):
            tools = [
                {
                    "type": "function",
                    "name": "missing",
                    "description": "missing",
                    "parameters": {},
                    "strict": True,
                }
            ]
        if config.get("modified_declaration"):
            assert tools[0]["type"] == "function"
            tools = [{**tools[0], "strict": False}]
        return {
            "model_request": {**request, "tools": tools},
            "selection_label": f"step={state.get('model_step', 0)}",
        }

    return AgentBundle(
        (
            AgentPlugin(
                "static",
                tools=(tool,),
                state_schema=SelectionFields,
                before_model_step=(
                    PluginStep("select", select, input_schema=SelectionState),
                ),
            ),
        )
    )


def test_strict_schema_built_once_and_current_step_context_used_before_next_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    converted = []

    def convert(tool: StructuredTool, *, strict: bool) -> object:
        result = convert_to_openai_function(tool, strict=strict)
        converted.append(result)
        return result

    monkeypatch.setattr(
        "caliburn.modules.agent.infrastructure.openai.request_initialization.convert_to_openai_function",
        convert,
    )
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(
            EventStream(
                response_events(response_payload([call()] if len(sent) == 1 else None))
            )
        )

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"disable_next": True})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                result = await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, INITIAL),
                )
                assert result["model_response"].output_text == "Synthetic reply"

    asyncio.run(run())
    assert len(converted) == 1
    declaration = sent[0]["tools"][0]
    assert declaration["strict"] is True
    assert declaration["parameters"]["additionalProperties"] is False
    assert set(declaration["parameters"]["properties"]) == {"item"}
    assert sent[1]["tools"] == []
    assert sent[1]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call_alpha",
        "output": "step=1/alpha",
    }
    assert "agent_tool_context" not in str(sent)


def test_disabled_tool_is_neither_declared_nor_executable() -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload([call()]))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"disabled": True})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                with pytest.raises(ValueError, match="Unknown function"):
                    await complete_turn(
                        agent,
                        workspace_id=TEST_WORKSPACE_ID,
                        input=cast(ResponseInputParam, INITIAL),
                    )

    asyncio.run(run())
    assert sent[0]["tools"] == []


@pytest.mark.parametrize("option", ["unknown_declaration", "modified_declaration"])
def test_invalid_selection_is_rejected_before_model_call(option: str) -> None:

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {option: True})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                with pytest.raises(ValueError, match="tool"):
                    await complete_turn(
                        agent,
                        workspace_id=TEST_WORKSPACE_ID,
                        input=cast(ResponseInputParam, INITIAL),
                    )

    asyncio.run(run())


def test_non_text_tool_output_is_rejected_at_the_adapter_boundary() -> None:
    requests = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        return sse_response(EventStream(response_events(response_payload([call()]))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"nontext": True})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                with pytest.raises(ValueError, match="requires text output"):
                    await complete_turn(
                        agent,
                        workspace_id=TEST_WORKSPACE_ID,
                        input=cast(ResponseInputParam, INITIAL),
                    )

    asyncio.run(run())
    assert requests == 1
