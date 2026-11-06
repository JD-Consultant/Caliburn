"""原生工具包裝器經正式入口執行，保留 State 與配對結果。"""

import asyncio
import operator
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Annotated, TypedDict
from uuid import UUID

import httpx2
import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from langgraph.prebuilt.tool_node import AsyncToolCallWrapper, ToolCallRequest
from langgraph.types import Command, interrupt

from caliburn.modules.agent.plugins.contracts import AgentContext, AgentPlugin
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    offline_client,
    open_test_agent,
    request_body,
    response_events,
    response_payload,
    run_test_agent,
    sse_response,
)


class LedgerState(TypedDict):
    ledger: Annotated[list[str], operator.add]


class ToolStateView(TypedDict):
    workspace_id: UUID
    ledger: list[str]


def test_wrappers_nest_in_order_and_preserve_command_updates() -> None:
    trace: list[str] = []
    sent = []

    async def write(
        item: str, runtime: ToolRuntime[AgentContext, ToolStateView]
    ) -> Command[object]:
        trace.append("tool")
        assert runtime.state["workspace_id"] == UUID(int=2)
        return Command(
            update={
                "ledger": [item],
                "messages": [
                    ToolMessage(content=item, tool_call_id=runtime.tool_call_id)
                ],
            }
        )

    def wrapper(label: str) -> AsyncToolCallWrapper:
        async def around(
            request: ToolCallRequest,
            execute: Callable[
                [ToolCallRequest], Awaitable[ToolMessage | Command[object]]
            ],
        ) -> ToolMessage | Command[object]:
            trace.append(f"{label}:before")
            result = await execute(request)
            trace.append(f"{label}:after")
            assert isinstance(result, Command)
            assert isinstance(result.update, dict)
            message = result.update["messages"][0]
            return replace(
                result,
                update={
                    **result.update,
                    "messages": [
                        message.model_copy(
                            update={"content": f"{message.content}/{label}"}
                        )
                    ],
                },
            )

        return around

    tool = StructuredTool.from_function(coroutine=write, description="Write item.")

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [call("write", "a", '{"item":"alpha"}')] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            state = await run_test_agent(
                client=client,
                plugins=(
                    AgentPlugin(
                        "outer",
                        tools=(tool,),
                        state_schema=LedgerState,
                        wrap_tool_call=(wrapper("A"),),
                    ),
                    AgentPlugin("inner", wrap_tool_call=(wrapper("B"),)),
                ),
            )
            assert state.get("ledger") == ["alpha"]
            assert "messages" not in state

    asyncio.run(run())
    assert trace == ["A:before", "B:before", "tool", "B:after", "A:after"]
    assert sent[1]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "a",
        "output": "alpha/B/A",
    }


def test_wrapper_cannot_execute_tool_twice() -> None:
    effects: list[str] = []

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    async def retry(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[object]]],
    ) -> ToolMessage | Command[object]:
        await execute(request)
        return await execute(request)

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read item.")
    responses = iter([response_payload([call()]), response_payload()])

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(next(responses))))
            )
        ) as client:
            with pytest.raises(ValueError, match="at most once"):
                await run_test_agent(
                    client=client,
                    plugins=(
                        AgentPlugin("retry", tools=(tool,), wrap_tool_call=(retry,)),
                    ),
                )

    asyncio.run(run())
    assert effects == ["alpha"]


@pytest.mark.parametrize("decision", ["reject", "override"])
def test_wrapper_can_reject_or_replace_unvalidated_arguments(decision: str) -> None:
    effects: list[str] = []
    sent = []

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    async def gate(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[object]]],
    ) -> ToolMessage | Command[object]:
        assert request.tool_call["args"] == {"item": None}
        if decision == "reject":
            return ToolMessage(content="denied", tool_call_id=request.tool_call["id"])
        return await execute(
            request.override(tool_call={**request.tool_call, "args": {"item": "valid"}})
        )

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [call(arguments='{"item":null}')] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read item.")

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            await run_test_agent(
                client=client,
                plugins=(AgentPlugin("gate", tools=(tool,), wrap_tool_call=(gate,)),),
            )

    asyncio.run(run())
    assert effects == ([] if decision == "reject" else ["valid"])
    assert sent[1]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call_alpha",
        "output": "denied" if decision == "reject" else "valid",
    }


def test_wrapper_interrupt_executes_only_after_same_turn_answer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    effects: list[str] = []
    responses = iter([response_payload([call()]), response_payload()])

    async def read_alpha(item: str) -> str:
        effects.append(item)
        return item

    async def approve(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[object]]],
    ) -> ToolMessage | Command[object]:
        answer = interrupt({"approve": request.tool_call["args"]["item"]})
        assert answer == "yes"
        return await execute(request)

    tool = StructuredTool.from_function(coroutine=read_alpha, description="Read item.")
    workspace_id = UUID(int=2)
    turn_id = UUID(int=3)

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(next(responses))))
            )
        ) as client:
            async with open_test_agent(
                client=client,
                plugins=(
                    AgentPlugin("approve", tools=(tool,), wrap_tool_call=(approve,)),
                ),
            ) as agent:
                async for _ in agent.astream(
                    workspace_id=workspace_id, turn_id=turn_id, input="go"
                ):
                    pass
                waiting = await agent.aget_state(workspace_id=workspace_id)
                assert waiting.interrupts
                assert effects == []
                assert waiting.values["model_step"] == 1
                async for _ in agent.aresume(
                    workspace_id=workspace_id,
                    turn_id=turn_id,
                    resume_command=Command(resume={waiting.interrupts[0].id: "yes"}),
                ):
                    pass
                complete = await agent.aget_state(workspace_id=workspace_id)
                assert not complete.next and not complete.interrupts

    asyncio.run(run())
    assert effects == ["alpha"]
    assert not [
        record
        for record in caplog.records
        if "agent.tool.failed" == getattr(record, "event", None)
    ]
