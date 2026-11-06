"""從公開 Graph 入口驗證原生 Responses 串流及完整工具往返。"""

import asyncio
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import cast
from uuid import UUID, uuid4

import httpx2
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime
from openai.types.responses import Response, ResponseReasoningItem
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState, OpenAIItems, request_items
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    TEST_WORKSPACE_ID,
    EventStream,
    call,
    message,
    offline_client,
    open_test_agent,
    reasoning,
    request_body,
    response_events,
    response_payload,
    run_turn,
    sse_response,
    stream_test_agent,
)


def test_public_agent_uses_streaming_and_returns_complete_response() -> None:
    payload = response_payload()
    streams: list[EventStream] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert request_body(request)["stream"] is True
        stream = EventStream(response_events(payload))
        streams.append(stream)
        return sse_response(stream)

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(client=client, tools=()) as graph:
                events = [
                    event
                    async for event in graph.astream(
                        turn_id=uuid4(),
                        input=cast(ResponseInputParam, INITIAL),
                        workspace_id=TEST_WORKSPACE_ID,
                    )
                ]
                custom = [
                    event["data"] for event in events if event["type"] == "custom"
                ]
                values = [
                    event["data"] for event in events if event["type"] == "values"
                ]
                assert [event["event"]["type"] for event in custom] == [
                    "response.created",
                    "response.completed",
                ]
                assert len({event["execution"]["run_id"] for event in custom}) == 1
                assert UUID(custom[0]["execution"]["run_id"]) != TEST_WORKSPACE_ID
                assert all(
                    set(value) <= {"turn_id", "model_response"} for value in values
                )
                result = cast(
                    AgentState,
                    (await graph.aget_state(workspace_id=TEST_WORKSPACE_ID)).values,
                )
                assert isinstance(result["model_response"], Response)
                assert result["model_response"] is not None
                assert result["model_response"].output_text == "Synthetic reply"
                assert result["model_response"].model_extra == {
                    "future_response_field": {"retained": True}
                }
                assert result["model_step"] == 1
                assert not client.is_closed()

    asyncio.run(run())
    assert len(streams) == 1 and streams[0].closed


def test_commentary_tools_and_final_replay_native_items_once_in_order() -> None:
    effects: list[str] = []
    sent = []
    original = deepcopy(INITIAL)
    payloads = [
        response_payload([reasoning(), message("commentary", "Looking up")]),
        response_payload(
            [call(), call(call_id="call_beta", arguments='{"item":"beta"}'), message()]
        ),
        response_payload(),
    ]

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return "read " + item

    tool = StructuredTool.from_function(
        coroutine=read_alpha, description="Read synthetic data."
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(payloads[len(sent) - 1])))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(client=client, tools=(tool,)) as graph:
                events = [
                    event
                    async for event in graph.astream(
                        turn_id=uuid4(),
                        input=cast(ResponseInputParam, INITIAL),
                        workspace_id=TEST_WORKSPACE_ID,
                    )
                ]
                completed = [
                    event["data"]
                    for event in events
                    if event["type"] == "custom"
                    and event["data"]["event"]["type"] == "response.completed"
                ]
                assert len({event["execution"]["task_id"] for event in completed}) == 3
                assert all(
                    event["execution"]["node_attempt"] == 1 for event in completed
                )
                result = cast(
                    AgentState,
                    (await graph.aget_state(workspace_id=TEST_WORKSPACE_ID)).values,
                )
                assert result["model_step"] == 3
                assert result["model_response"] is not None
                assert result["model_response"].output_text == "Synthetic reply"
                opaque = request_items(result["model_request"])[1]
                assert isinstance(opaque, ResponseReasoningItem)
                assert opaque.encrypted_content == "synthetic-opaque-content"

    asyncio.run(run())
    assert effects == ["alpha", "beta"]
    assert INITIAL == original
    assert [item["type"] for item in sent[2]["input"][1:]] == [
        "reasoning",
        "message",
        "function_call",
        "function_call",
        "message",
        "function_call_output",
        "function_call_output",
    ]
    assert sent[1]["input"][1]["encrypted_content"] == "synthetic-opaque-content"
    assert sent[1]["input"][2]["phase"] == "commentary"
    assert sent[2]["input"][3]["future_call_field"] == {"retained": True}
    assert "parsed_arguments" not in sent[2]["input"][3]
    assert "parsed" not in sent[2]["input"][5]["content"][0]
    assert [item["call_id"] for item in sent[2]["input"][-2:]] == [
        "call_alpha",
        "call_beta",
    ]
    assert all(body["tools"][0]["name"] == "read_alpha" for body in sent)


def test_history_plugin_selects_native_items_for_each_new_turn() -> None:
    """歷史由插件公開讀取能力選取，caller 每次只傳新增 input。"""
    sent = []
    history: OpenAIItems = []
    next_input: OpenAIItems = [{"role": "user", "content": "Next question"}]
    first_output = [reasoning(), message()]

    async def select_history(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        request = state["model_request"]
        return {
            "model_request": {
                **request,
                "input": cast(ResponseInputParam, [*history, *request_items(request)]),
            }
        }

    plugin = AgentPlugin(
        "history", on_turn_start=(PluginStep("select", select_history),)
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = first_output if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        nonlocal history
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(
                client=client, tools=(), plugins=(plugin,)
            ) as graph:
                first = await run_turn(graph, input=cast(ResponseInputParam, INITIAL))
                previous = deepcopy(request_items(first["model_request"]))
                history = previous
                continuation = [*request_items(first["model_request"]), *next_input]
                second = await run_turn(
                    graph, input=cast(ResponseInputParam, next_input)
                )
                history = []
                fresh = await run_turn(
                    graph, input=cast(ResponseInputParam, next_input)
                )
                assert request_items(first["model_request"]) == previous
                assert continuation == [*previous, *next_input]
                assert request_items(second["model_request"])[:-1] == continuation
                assert request_items(fresh["model_request"])[:-1] == next_input
                assert second["model_step"] == fresh["model_step"] == 1

    asyncio.run(run())
    assert sent[0]["input"] == INITIAL
    assert sent[1]["input"] == [*INITIAL, *first_output, *next_input]
    assert sent[1]["input"][1]["encrypted_content"] == "synthetic-opaque-content"
    assert sent[1]["input"][2]["phase"] == "final_answer"
    assert sent[2]["input"] == next_input


def test_arguments_delta_is_observed_before_any_tool_executes() -> None:
    effects: list[str] = []
    payload = response_payload([call()])
    events = response_events(payload)
    events[1:1] = [
        {
            "type": "response.output_item.added",
            "sequence_number": 1,
            "output_index": 0,
            "item": {**call(), "arguments": "", "status": "in_progress"},
        },
        {
            "type": "response.function_call_arguments.delta",
            "sequence_number": 2,
            "output_index": 0,
            "item_id": "fc_call_alpha",
            "delta": '{"item":"alpha"}',
        },
    ]
    events[-1]["sequence_number"] = 3

    class ObservedStream(EventStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            async for chunk in super().__aiter__():
                assert effects == []
                yield chunk

    first_stream = ObservedStream(events)
    requests = 0

    async def read_alpha(item: str) -> str:
        assert first_stream.closed
        effects.append(item)
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        return sse_response(
            first_stream
            if requests == 1
            else EventStream(response_events(response_payload()))
        )

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            observed = [
                part
                async for part in stream_test_agent(
                    client=client,
                    tools=(tool,),
                    input=cast(ResponseInputParam, INITIAL),
                )
            ]
            assert [
                part["data"]["event"]["type"]
                for part in observed
                if part["type"] == "custom"
            ][:4] == [
                "response.created",
                "response.output_item.added",
                "response.function_call_arguments.delta",
                "response.completed",
            ]

    asyncio.run(run())
    assert effects == ["alpha"] and requests == 2
