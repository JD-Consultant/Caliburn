"""工具 gate 的原生人工回答沿同輪／模型步／call_id 冷恢復。"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx2
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command, interrupt

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import AgentPlugin
from tests.integration.agent.stream_support import consume
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


def test_tool_gate_answer_cold_resumes_same_step_without_repeating_model(
    checkpoint_conninfo: str,
) -> None:
    workspace, turn = UUID(int=81), UUID(int=801)
    sent: list[dict[str, Any]] = []
    effects: list[str] = []
    gates: list[tuple[UUID, int, str]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [call()] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    def plugin() -> AgentPlugin:
        async def read_alpha(item: str) -> str:
            effects.append(item)
            return f"read {item}"

        async def gate(
            request: ToolCallRequest,
            execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[str]]],
        ) -> ToolMessage | Command[str]:
            call_id = request.tool_call["id"]
            assert isinstance(call_id, str)
            gates.append(
                (
                    request.state["turn_id"],
                    request.state["model_step"],
                    call_id,
                )
            )
            answer = interrupt(
                {"call_id": request.tool_call["id"], "question": "Approve this read?"}
            )
            assert answer == {"approved": True}
            return await execute(request)

        return AgentPlugin(
            "approval",
            tools=(
                StructuredTool.from_function(
                    coroutine=read_alpha, description="Read synthetic data."
                ),
            ),
            wrap_tool_call=(gate,),
        )

    async def run() -> None:
        for first in (True, False):
            async with (
                open_postgres_checkpointer(
                    checkpoint_conninfo, initialize=first
                ) as saver,
                offline_client(httpx2.MockTransport(respond)) as client,
                open_agent(
                    agent_id="tool-gate",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        BundleConfig(
                            "tests.unit.modules.agent.offline_openai",
                            {"plugins": (plugin(),)},
                        ),
                    ),
                    checkpointer=saver,
                ) as agent,
            ):
                if first:
                    parts = [
                        part
                        async for part in agent.astream(
                            workspace_id=workspace, turn_id=turn, input="original"
                        )
                    ]
                    questions = [
                        item for part in parts for item in part.get("interrupts", ())
                    ]
                    assert len(questions) == 1
                    assert questions[0].value == {
                        "call_id": "call_alpha",
                        "question": "Approve this read?",
                    }
                    saved = await agent.aget_state(workspace_id=workspace)
                    assert saved.values["model_step"] == 1
                    assert len(sent) == 1 and effects == []
                else:
                    waiting = await agent.aget_state(workspace_id=workspace)
                    await consume(
                        agent.aresume(
                            workspace_id=workspace,
                            turn_id=turn,
                            resume_command=Command(
                                resume={waiting.interrupts[0].id: {"approved": True}}
                            ),
                        )
                    )
                    saved = await agent.aget_state(workspace_id=workspace)
                    assert not saved.next and not saved.interrupts
                    assert saved.values["model_step"] == 2
                    assert saved.values["turn_input"] == "original"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(sent) == 2
    assert effects == ["alpha"]
    assert gates == [(turn, 1, "call_alpha"), (turn, 1, "call_alpha")]
    assert sent[1]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call_alpha",
        "output": "read alpha",
    }
