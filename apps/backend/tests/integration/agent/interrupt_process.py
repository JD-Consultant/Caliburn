"""人工等待 writer／reader：只以公開入口核對跨程序准入。"""

import asyncio
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import httpx2
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
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

WORKSPACE = UUID(int=51)
TURN = UUID(int=501)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    answers = Path(str(config["answers"]))

    async def ask(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        answer = interrupt({"question": "Which source is approved?"})
        answers.write_text(json.dumps(answer), encoding="utf-8")
        return {}

    return AgentBundle(
        (AgentPlugin("approval", on_turn_start=(PluginStep("ask", ask),)),)
    )


async def assert_waiting_is_unchanged(agent: Agent) -> None:
    before = await agent.aget_state(workspace_id=WORKSPACE)
    history = [
        item.config async for item in agent.aget_state_history(workspace_id=WORKSPACE)
    ]
    assert before.interrupts
    for events in (
        agent.astream(workspace_id=WORKSPACE, turn_id=UUID(int=502), input="skip"),
        agent.aresume(workspace_id=WORKSPACE, turn_id=TURN),
        agent.aresume(
            workspace_id=WORKSPACE,
            turn_id=UUID(int=502),
            resume_command=Command(resume="wrong turn"),
        ),
    ):
        try:
            await consume(events)
        except AgentExecutionError:
            pass
        else:
            raise AssertionError("Waiting accepted an operation without its answer")
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

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async with (
        open_postgres_checkpointer(conninfo, initialize=mode == "writer") as saver,
        offline_client(httpx2.MockTransport(respond)) as client,
        open_agent(
            agent_id="waiting-process",
            resume_version="v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=(
                BundleConfig(__name__, {"answers": str(directory / "answer.json")}),
            ),
            checkpointer=saver,
        ) as agent,
    ):
        if mode == "writer":
            chunks = [
                chunk
                async for chunk in agent.astream(
                    workspace_id=WORKSPACE, turn_id=TURN, input="original question"
                )
            ]
            questions = [
                item for chunk in chunks for item in chunk.get("interrupts", ())
            ]
            assert len(questions) == 1
            assert questions[0].value == {"question": "Which source is approved?"}
        await assert_waiting_is_unchanged(agent)
        assert sent == []
        assert not (directory / "answer.json").exists()
        if mode == "reader":
            waiting = await agent.aget_state(workspace_id=WORKSPACE)
            await consume(
                agent.aresume(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    resume_command=Command(
                        resume={waiting.interrupts[0].id: {"source": "approved"}}
                    ),
                )
            )
            saved = await agent.aget_state(workspace_id=WORKSPACE)
            assert not saved.next and not saved.interrupts
            assert saved.values["turn_id"] == TURN
            assert saved.values["turn_input"] == "original question"
            assert saved.values["model_step"] == 1
            assert json.loads((directory / "answer.json").read_text()) == {
                "source": "approved"
            }
        (directory / f"{mode}.json").write_text(json.dumps(sent), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(
        run(sys.argv[1], sys.argv[2], Path(sys.argv[3])),
        loop_factory=asyncio.SelectorEventLoop,
    )
