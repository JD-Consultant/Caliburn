"""Core 模型／工具上限與原生排程、合作取消的界線。"""

import asyncio
from typing import cast

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphRecursionError
from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentLimitError, AgentState
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    EventStream,
    call,
    offline_client,
    open_test_agent,
    response_events,
    response_payload,
    run_test_agent,
    run_turn,
    sse_response,
)


@pytest.mark.parametrize("terminal_at", [64, None])
def test_default_schedule_allows_64_model_steps_but_core_stops_the_next_prepare(
    terminal_at: int | None,
) -> None:
    requests = 0
    preparations = 0
    effects: list[str] = []

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    async def prepare(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        nonlocal preparations
        preparations += 1
        return {}

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        output = None if requests == terminal_at else [call(call_id=f"call_{requests}")]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(
                client=client,
                tools=(tool,),
                plugins=(
                    AgentPlugin(
                        "count", before_model_step=(PluginStep("prepare", prepare),)
                    ),
                ),
            ) as graph:
                if terminal_at is None:
                    with pytest.raises(AgentLimitError, match="Model"):
                        await run_turn(graph, input=cast(ResponseInputParam, INITIAL))
                else:
                    result = (
                        await run_turn(graph, input=cast(ResponseInputParam, INITIAL))
                    )["model_response"]
                    assert result is not None
                    assert result.output_text == "Synthetic reply"

    asyncio.run(run())
    assert requests == preparations == 64
    assert len(effects) == (64 if terminal_at is None else 63)


def test_caller_can_lower_native_recursion_limit() -> None:
    requests: list[bool] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(True)
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(GraphRecursionError):
                await run_test_agent(
                    client=client,
                    tools=(),
                    input=cast(ResponseInputParam, INITIAL),
                    recursion_limit=1,
                )

    asyncio.run(run())
    assert requests == []


def test_long_tool_batch_uses_native_schedule_without_consuming_model_steps() -> None:
    effects: list[str] = []
    requests = 0

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        payload = response_payload(
            [call(call_id=f"call_{index}") for index in range(32)]
            if requests == 1
            else None
        )
        return sse_response(EventStream(response_events(payload)))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(
                client=client, tools=(tool,), max_model_steps=2
            ) as graph:
                result = await run_turn(graph, input=cast(ResponseInputParam, INITIAL))
                assert result["model_step"] == 2
                assert result["model_response"] is not None
                assert result["model_response"].output_text == "Synthetic reply"
                outputs = [
                    item
                    for item in result["model_request"]["input"]
                    if isinstance(item, dict)
                    and item.get("type") == "function_call_output"
                ]
                assert [item.get("call_id") for item in outputs] == [
                    f"call_{index}" for index in range(32)
                ]

    asyncio.run(run())
    assert requests == 2 and effects == ["alpha"] * 32


def test_tool_batch_limit_is_checked_before_first_side_effect() -> None:
    effects: list[str] = []
    stream = EventStream(
        response_events(
            response_payload([call(call_id=f"call_{index}") for index in range(33)])
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
            with pytest.raises(AgentLimitError, match="Tool"):
                await run_test_agent(
                    client=client,
                    tools=(tool,),
                    input=cast(ResponseInputParam, INITIAL),
                )

    asyncio.run(run())
    assert effects == []


@pytest.mark.parametrize("stage", ["prepare", "tool"])
def test_cancellation_in_preparation_or_tool_stops_later_work(stage: str) -> None:

    async def run() -> None:
        started = asyncio.Event()
        stopped = asyncio.Event()
        never = asyncio.Event()
        requests: list[bool] = []
        effects: list[str] = []

        async def pause() -> None:
            started.set()
            try:
                await never.wait()
            finally:
                stopped.set()

        async def read_alpha(item: str) -> str:
            effects.append(item)
            await pause()
            return item

        tool = StructuredTool.from_function(coroutine=read_alpha, description="Read.")

        async def prepare(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> AgentState:
            if stage == "prepare":
                await pause()
            return {}

        def respond(request: httpx2.Request) -> httpx2.Response:
            requests.append(True)
            return sse_response(
                EventStream(
                    response_events(
                        response_payload([call(), call(call_id="call_beta")])
                    )
                )
            )

        async with offline_client(httpx2.MockTransport(respond)) as client:
            task = asyncio.create_task(
                run_test_agent(
                    client=client,
                    tools=(tool,),
                    plugins=(
                        AgentPlugin(
                            "pause", before_model_step=(PluginStep("prepare", prepare),)
                        ),
                    ),
                    input=cast(ResponseInputParam, INITIAL),
                )
            )
            try:
                await asyncio.wait_for(started.wait(), 5)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert stopped.is_set()
                assert len(requests) == (0 if stage == "prepare" else 1)
                assert effects == ([] if stage == "prepare" else ["alpha"])
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())


@pytest.mark.parametrize(
    "limits",
    [
        {"max_model_steps": 0},
        {"max_model_steps": -1},
        {"max_tool_calls_per_step": 0},
        {"max_tool_calls_per_step": -1},
    ],
)
def test_nonpositive_limits_fail_at_composition(limits: dict[str, int]) -> None:

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: sse_response(EventStream([])))
        ) as client:
            with pytest.raises(ValueError):
                await run_test_agent(
                    client=client,
                    tools=(),
                    max_model_steps=limits.get("max_model_steps", 64),
                    max_tool_calls_per_step=limits.get("max_tool_calls_per_step", 32),
                )

    asyncio.run(run())
