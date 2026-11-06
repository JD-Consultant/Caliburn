"""三個獨立程序沿公開 Agent 入口驗證回答、故障與後續人工等待。"""

import asyncio
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict
from uuid import UUID

import httpx2
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from caliburn.modules.agent.agent import Agent, AgentExecutionError
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
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

WORKSPACE = UUID(int=61)
TURN = UUID(int=601)


class Answers(TypedDict):
    first_answer: str
    second_answer: str


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    directory = Path(str(config["directory"]))

    async def read_alpha(item: str) -> str:
        with (directory / "effects.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item) + "\n")
        return "saved " + item

    async def ask(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        first = interrupt("First question")
        with (directory / "attempts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "turn_id": str(state["turn_id"]),
                        "model_step": state["model_step"],
                    }
                )
                + "\n"
            )
        if config["fail_after_answer"]:
            raise RuntimeError("synthetic failure after answer")
        second = interrupt("Second question")
        (directory / "answers.json").write_text(
            json.dumps([first, second]), encoding="utf-8"
        )
        return {"first_answer": first, "second_answer": second}

    return AgentBundle(
        (
            AgentPlugin(
                "approval",
                state_schema=Answers,
                tools=(
                    StructuredTool.from_function(
                        coroutine=read_alpha, description="Read synthetic data."
                    ),
                ),
                on_turn_end=(PluginStep("ask", ask),),
            ),
        )
    )


async def assert_unrelated_operations_preserve_waiting(agent: Agent) -> None:
    before = await agent.aget_state(workspace_id=WORKSPACE)
    history = [
        item.config async for item in agent.aget_state_history(workspace_id=WORKSPACE)
    ]
    answer = {before.interrupts[0].id: "injected"}
    for events in (
        agent.astream(workspace_id=WORKSPACE, turn_id=UUID(int=602), input="skip"),
        agent.aresume(
            workspace_id=WORKSPACE,
            turn_id=UUID(int=602),
            resume_command=Command(resume=answer),
        ),
        agent.aresume(
            workspace_id=WORKSPACE,
            turn_id=TURN,
            resume_command=Command(resume=answer, update={"first_answer": "injected"}),
        ),
        agent.aresume(
            workspace_id=WORKSPACE,
            turn_id=TURN,
            resume_command=Command(resume=answer, goto="call_model"),
        ),
    ):
        try:
            await consume(events)
        except AgentExecutionError:
            pass
        else:
            raise AssertionError("Waiting accepted an unrelated operation")
        after = await agent.aget_state(workspace_id=WORKSPACE)
        assert after.config == before.config
        assert after.values == before.values
        assert after.interrupts == before.interrupts
        assert [
            item.config
            async for item in agent.aget_state_history(workspace_id=WORKSPACE)
        ] == history


async def run(mode: str, conninfo: str, directory: Path) -> None:
    sent: list[dict[str, object]] = []
    replies = iter([response_payload([call()]), response_payload()])

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert mode == "writer", "Recovery repeated an already completed model call"
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(next(replies))))

    async with (
        open_postgres_checkpointer(conninfo, initialize=mode == "writer") as saver,
        offline_client(httpx2.MockTransport(respond)) as client,
        open_agent(
            agent_id="answered-interrupt-process",
            resume_version="v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=(
                BundleConfig(
                    __name__,
                    {
                        "directory": str(directory),
                        "fail_after_answer": mode == "writer",
                    },
                ),
            ),
            checkpointer=saver,
        ) as agent,
    ):
        if mode == "writer":
            await consume(
                agent.astream(
                    workspace_id=WORKSPACE, turn_id=TURN, input="original question"
                )
            )
            waiting = await agent.aget_state(workspace_id=WORKSPACE)
            assert [item.value for item in waiting.interrupts] == ["First question"]
            await assert_unrelated_operations_preserve_waiting(agent)
            try:
                await consume(
                    agent.aresume(
                        workspace_id=WORKSPACE,
                        turn_id=TURN,
                        resume_command=Command(
                            resume={waiting.interrupts[0].id: "first answer"}
                        ),
                    )
                )
            except RuntimeError as error:
                assert str(error) == "synthetic failure after answer"
            else:
                raise AssertionError("Expected a failure after the first answer")
            failed = await agent.aget_state(workspace_id=WORKSPACE)
            assert failed.interrupts and any(task.error for task in failed.tasks)
        elif mode == "recover":
            before = await agent.aget_state(workspace_id=WORKSPACE)
            assert [item.value for item in before.interrupts] == ["First question"]
            for _ in range(2):
                await consume(agent.aresume(workspace_id=WORKSPACE, turn_id=TURN))
                waiting = await agent.aget_state(workspace_id=WORKSPACE)
                assert [item.value for item in waiting.interrupts] == [
                    "Second question"
                ]
                assert waiting.values == before.values
                assert not (directory / "answers.json").exists()
                await assert_unrelated_operations_preserve_waiting(agent)
        elif mode == "reader":
            waiting = await agent.aget_state(workspace_id=WORKSPACE)
            assert [item.value for item in waiting.interrupts] == ["Second question"]
            await assert_unrelated_operations_preserve_waiting(agent)
            await consume(
                agent.aresume(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    resume_command=Command(
                        resume={waiting.interrupts[0].id: "second answer"}
                    ),
                )
            )
            done = await agent.aget_state(workspace_id=WORKSPACE)
            assert not done.next and not done.interrupts
            assert done.values["first_answer"] == "first answer"
            assert done.values["second_answer"] == "second answer"
        else:
            raise AssertionError(f"Unexpected process mode: {mode}")
        saved = await agent.aget_state(workspace_id=WORKSPACE)
        assert saved.values["turn_id"] == TURN
        assert saved.values["turn_input"] == "original question"
        assert saved.values["model_step"] == 2
        (directory / f"{mode}.json").write_text(json.dumps(sent), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(
        run(sys.argv[1], sys.argv[2], Path(sys.argv[3])),
        loop_factory=asyncio.SelectorEventLoop,
    )
