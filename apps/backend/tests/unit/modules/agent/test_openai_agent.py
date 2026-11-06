"""完整工具批次的預檢、套件驗證及順序副作用。"""

import asyncio
from typing import cast

import httpx2
import pytest
from langchain_core.tools import StructuredTool, ToolException
from langgraph.prebuilt.tool_node import ToolInvocationError
from openai.types.responses.response_input_param import ResponseInputParam
from pydantic import ValidationError

from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    run_test_agent,
    sse_response,
)


@pytest.mark.parametrize(
    "invalid",
    [
        {"name": "missing"},
        {"arguments": "{"},
        {"call_id": ""},
        {"call_id": "call_alpha"},
        {"status": "in_progress"},
        pytest.param(
            {"call_id": 123},
            id="numeric_call_id",
            marks=pytest.mark.filterwarnings(
                "ignore:Pydantic serializer warnings:UserWarning"
            ),
        ),
    ],
)
def test_invalid_second_call_prevents_all_tool_side_effects(
    invalid: dict[str, object],
) -> None:
    effects: list[str] = []
    stream = EventStream(
        response_events(
            response_payload([call(), {**call(call_id="call_beta"), **invalid}])
        )
    )

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(stream))
        ) as client:
            with pytest.raises(ValueError):
                await run_test_agent(
                    client=client,
                    tools=(tool,),
                    input=cast(ResponseInputParam, INITIAL),
                )

    asyncio.run(run())
    assert effects == [] and stream.closed


def test_expected_tool_rejection_returns_to_model_and_later_calls_continue() -> None:
    effects: list[str] = []
    sent = []

    async def read_alpha(item: str) -> str:
        effects.append(item)
        if item == "alpha":
            raise ToolException("Choose a different item.")
        return "read " + item

    tool = StructuredTool.from_function(
        coroutine=read_alpha, description="Read.", handle_tool_error=True
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = (
            [call(), call(call_id="call_beta", arguments='{"item":"beta"}')]
            if len(sent) == 1
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            result = (
                await run_test_agent(
                    client=client,
                    tools=(tool,),
                    input=cast(ResponseInputParam, INITIAL),
                )
            )["model_response"]
            assert result is not None
            assert result.output_text == "Synthetic reply"

    asyncio.run(run())
    assert effects == ["alpha", "beta"]
    assert [item["output"] for item in sent[1]["input"][-2:]] == [
        "Choose a different item.",
        "read beta",
    ]


def test_unhandled_tool_failure_stops_later_calls_and_preserves_prior_effects() -> None:
    effects: list[str] = []
    failure = RuntimeError("Synthetic storage failure")
    requests = 0

    async def read_alpha(item: str) -> str:
        effects.append(item)
        if item == "beta":
            raise failure
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        return sse_response(
            EventStream(
                response_events(
                    response_payload(
                        [
                            call(arguments='{"item":"alpha"}'),
                            call(call_id="call_beta", arguments='{"item":"beta"}'),
                            call(call_id="call_gamma", arguments='{"item":"gamma"}'),
                        ]
                    )
                )
            )
        )

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(RuntimeError) as caught:
                await run_test_agent(
                    client=client,
                    tools=(tool,),
                    input=cast(ResponseInputParam, INITIAL),
                )
            assert caught.value is failure

    asyncio.run(run())
    assert effects == ["alpha", "beta"] and requests == 1


@pytest.mark.parametrize("arguments", ['{"item":123}', "[]"])
def test_pydantic_argument_validation_remains_at_structured_tool_boundary(
    arguments: str,
) -> None:
    effects: list[str] = []
    stream = EventStream(response_events(response_payload([call(arguments=arguments)])))

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(stream))
        ) as client:
            with pytest.raises(
                ToolInvocationError if arguments != "[]" else ValidationError
            ):
                await run_test_agent(
                    client=client,
                    tools=(tool,),
                    input=cast(ResponseInputParam, INITIAL),
                )

    asyncio.run(run())
    assert effects == []


def test_sync_handler_argument_named_type_does_not_collide_with_tool_envelope() -> None:
    effects: list[str] = []
    requests = 0

    def read_alpha(type: str) -> str:
        effects.append(type)
        return type

    tool = StructuredTool.from_function(func=read_alpha, description="Read.")

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        output = [call(arguments='{"type":"tool_call"}')] if requests == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            result = (
                await run_test_agent(
                    client=client,
                    tools=(tool,),
                    input=cast(ResponseInputParam, INITIAL),
                )
            )["model_response"]
            assert result is not None
            assert result.output_text == "Synthetic reply"

    asyncio.run(run())
    assert effects == ["tool_call"] and requests == 2
