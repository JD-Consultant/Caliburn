"""工具 Task 成功後 wrapper 失敗；跨程序復用原生 Command 回值。"""

import asyncio
import json
import operator
import sys
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Annotated, TypedDict
from uuid import UUID

import httpx2
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.func import task
from langgraph.prebuilt import ToolRuntime
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
)
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

WORKSPACE = UUID(int=71)
TURN = UUID(int=701)


class TaskChannels(TypedDict, total=False):
    journal: Annotated[list[str], operator.add]


class ToolState(TaskChannels):
    workspace_id: UUID
    turn_id: UUID
    model_step: int


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    effects = Path(str(config["effects"]))

    async def read_alpha(
        item: str, runtime: ToolRuntime[AgentContext, ToolState]
    ) -> Command[str]:
        assert runtime.state["workspace_id"] == WORKSPACE
        assert runtime.state["turn_id"] == TURN
        assert runtime.state["model_step"] == 1
        with effects.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item) + "\n")
        return Command(
            update={
                "journal": [item],
                "messages": [
                    ToolMessage(
                        content=f"read {item}", tool_call_id=runtime.tool_call_id
                    )
                ],
            }
        )

    async def save_then_postprocess(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[str]]],
    ) -> ToolMessage | Command[str]:
        # request/runtime 保持閉包；只有執行結果需要由原生 Task 保存。
        @task
        async def execute_once() -> ToolMessage | Command[str]:
            return await execute(request)

        result = await execute_once()
        if config["fail"]:
            raise RuntimeError("synthetic postprocess outage")
        assert isinstance(result, Command) and isinstance(result.update, dict)
        messages = result.update["messages"]
        assert len(messages) == 1 and isinstance(messages[0], ToolMessage)
        message = messages[0]
        return Command(
            update={
                **result.update,
                "messages": [
                    ToolMessage(
                        content=f"{message.content}; approved",
                        tool_call_id=message.tool_call_id,
                    )
                ],
            }
        )

    return AgentBundle(
        (
            AgentPlugin(
                "task-tool",
                tools=(
                    StructuredTool.from_function(
                        coroutine=read_alpha, description="Read synthetic data."
                    ),
                ),
                state_schema=TaskChannels,
                wrap_tool_call=(save_then_postprocess,),
            ),
        )
    )


async def run(mode: str, conninfo: str, directory: Path) -> None:
    sent: list[dict[str, object]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [call()] if mode == "writer" else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async with (
        open_postgres_checkpointer(conninfo, initialize=mode == "writer") as saver,
        offline_client(httpx2.MockTransport(respond)) as client,
        open_agent(
            agent_id="task-process",
            resume_version="v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=(
                BundleConfig(
                    __name__,
                    {
                        "fail": mode == "writer",
                        "effects": str(directory / "effects.jsonl"),
                    },
                ),
            ),
            checkpointer=saver,
        ) as agent,
    ):
        if mode == "writer":
            try:
                await consume(
                    agent.astream(
                        workspace_id=WORKSPACE, turn_id=TURN, input="original"
                    )
                )
            except RuntimeError as error:
                assert str(error) == "synthetic postprocess outage"
            else:
                raise AssertionError("postprocess failure was swallowed")
            saved = await agent.aget_state(workspace_id=WORKSPACE)
            assert saved.next
            assert saved.values.get("journal", []) == []
            assert saved.values["model_step"] == 1
        else:
            before = await agent.aget_state(workspace_id=WORKSPACE)
            assert before.values.get("journal", []) == []
            await consume(agent.aresume(workspace_id=WORKSPACE, turn_id=TURN))
            saved = await agent.aget_state(workspace_id=WORKSPACE)
            assert not saved.next
            assert saved.values["journal"] == ["alpha"]
            assert saved.values["model_step"] == 2
            assert "messages" not in saved.values
        (directory / f"{mode}.json").write_text(json.dumps(sent), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(
        run(sys.argv[1], sys.argv[2], Path(sys.argv[3])),
        loop_factory=asyncio.SelectorEventLoop,
    )
