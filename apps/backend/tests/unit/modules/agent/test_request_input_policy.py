"""自管 input 的工具協定在正式 Agent 外送邊界維持完整配對。"""

import asyncio
from typing import cast

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime
from openai.types.responses.parsed_response import ParsedResponseFunctionToolCall
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_function_tool_call_output_item import (
    ResponseFunctionToolCallOutputItem,
)
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState, OpenAIItems, request_items
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    offline_client,
    open_test_agent,
    request_body,
    response_events,
    response_payload,
    run_turn,
    sse_response,
)


@pytest.mark.parametrize(
    "items",
    [
        [{"type": "function_call_output", "call_id": "call_alpha", "output": "ok"}],
        [call()],
        [
            call(),
            {"type": "function_call_output", "call_id": "call_alpha", "output": "ok"},
            {"type": "function_call_output", "call_id": "call_alpha", "output": "ok"},
        ],
        [call(), call()],
        [
            {"type": "function_call_output", "call_id": "call_alpha", "output": "ok"},
            call(),
        ],
        [
            call(),
            {"type": "function_call_output", "call_id": "call_unknown", "output": "ok"},
        ],
        [ResponseFunctionToolCall.model_validate(call())],
        [ParsedResponseFunctionToolCall.model_validate(call())],
    ],
    ids=[
        "orphan_output",
        "missing_output",
        "duplicate_output",
        "duplicate_pending_call",
        "output_before_call",
        "unknown_output",
        "native_sdk_call_without_output",
        "parsed_sdk_call_without_output",
    ],
)
def test_unpaired_tool_history_is_rejected_before_model_request(
    items: OpenAIItems,
) -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(client=client) as agent:
                with pytest.raises(ValueError, match="[Pp]air|[Oo]utput"):
                    await run_turn(agent, input=cast(ResponseInputParam, items))

    asyncio.run(run())
    assert sent == []


def test_mixed_native_history_allows_multiple_calls_and_preserves_arguments() -> None:
    sent = []
    items = [
        ResponseFunctionToolCall.model_validate(call(call_id="call_native")),
        ParsedResponseFunctionToolCall.model_validate(
            {**call(call_id="call_parsed"), "parsed_arguments": {"item": "alpha"}}
        ),
        call(call_id="call_dict", arguments="historical arguments remain opaque"),
        {"type": "function_call_output", "call_id": "call_dict", "output": "dict"},
        {"type": "function_call_output", "call_id": "call_parsed", "output": "parsed"},
        ResponseFunctionToolCallOutputItem(
            id="fco_native",
            type="function_call_output",
            call_id="call_native",
            status="completed",
            output="native",
        ),
    ]

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(client=client) as agent:
                await run_turn(agent, input=cast(ResponseInputParam, items))

    asyncio.run(run())
    assert [item["call_id"] for item in sent[0]["input"]] == [
        "call_native",
        "call_parsed",
        "call_dict",
        "call_dict",
        "call_parsed",
        "call_native",
    ]
    assert sent[0]["input"][2]["arguments"] == "historical arguments remain opaque"
    assert "parsed_arguments" not in sent[0]["input"][1]
    assert sent[0]["input"][0]["future_call_field"] == {"retained": True}


def test_completed_call_id_can_be_reused_in_a_later_model_step() -> None:
    sent = []
    effects = []

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [call()] if len(sent) < 3 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(client=client, tools=(tool,)) as agent:
                await run_turn(agent)

    asyncio.run(run())
    assert effects == ["alpha", "alpha"]
    assert [item["type"] for item in sent[2]["input"][1:]] == [
        "function_call",
        "function_call_output",
        "function_call",
        "function_call_output",
    ]
    assert {item["call_id"] for item in sent[2]["input"][1:]} == {"call_alpha"}


@pytest.mark.parametrize("compact", [False, True])
def test_plugin_can_remove_or_compress_complete_tool_pairs(compact: bool) -> None:
    sent = []

    async def read_alpha(item: str) -> str:
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    async def replace_history(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        if state["model_step"] == 1:
            return {}
        request = state["model_request"]
        replacement: ResponseInputParam = (
            [{"role": "developer", "content": "Summary: read alpha."}]
            if compact
            else []
        )
        return {"model_request": {**request, "input": replacement}}

    plugin = AgentPlugin(
        "context", before_model_step=(PluginStep("replace_history", replace_history),)
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [call()] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(
                client=client, tools=(tool,), plugins=(plugin,)
            ) as agent:
                await run_turn(agent)

    asyncio.run(run())
    assert sent[1]["input"] == (
        [{"role": "developer", "content": "Summary: read alpha."}] if compact else []
    )


@pytest.mark.parametrize("remove", ["function_call", "function_call_output"])
def test_plugin_cannot_leave_half_a_tool_pair_for_the_next_model_step(
    remove: str,
) -> None:
    sent = []

    async def read_alpha(item: str) -> str:
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    async def remove_item(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        request = state["model_request"]
        items = [
            item
            for item in request_items(request)
            if (item.get("type") if isinstance(item, dict) else item.type) != remove
        ]
        return {"model_request": {**request, "input": cast(ResponseInputParam, items)}}

    plugin = AgentPlugin(
        "context", before_model_step=(PluginStep("remove_item", remove_item),)
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [call()] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(
                client=client, tools=(tool,), plugins=(plugin,)
            ) as agent:
                with pytest.raises(ValueError, match="[Pp]air|[Oo]utput"):
                    await run_turn(agent)

    asyncio.run(run())
    assert len(sent) == 1
