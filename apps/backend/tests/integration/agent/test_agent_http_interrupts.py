"""已答故障與下一題原生證據不可辨識時的保守 HTTP 狀態。"""

import asyncio
from collections.abc import Mapping
from typing import cast
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from sqlalchemy import Engine

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
from tests.integration.agent.http_support import api_client
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    response_events,
    response_payload,
    sse_response,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle((cast(AgentPlugin, config["plugin"]),))


def test_answered_failure_and_identical_next_question_remain_safe_to_resume(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        fail = True
        answers: list[str] = []
        calls = 0

        async def ask(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            nonlocal fail
            first = interrupt("Same public question")
            if fail:
                fail = False
                raise RuntimeError("Synthetic failure after saved answer")
            second = interrupt("Same public question")
            answers.extend([first, second])
            return {}

        plugin = AgentPlugin("ask", on_turn_end=(PluginStep("ask", ask),))
        bundles = (BundleConfig(__name__, {"plugin": plugin}),)

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            return sse_response(EventStream(response_events(response_payload())))

        transport = httpx2.MockTransport(respond)
        turn = uuid4()
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=bundles
        ) as client:
            workspace = UUID(
                (
                    await client.post(
                        "/workspaces", json={"interviewee_name": "Synthetic"}
                    )
                ).json()["workspace_id"]
            )
            accepted = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(turn), "input": "original"},
            )
            location = accepted.headers["Location"]
            async with asyncio.timeout(5):
                while (await client.get(location)).json()["status"] == "running":
                    await asyncio.sleep(0.01)
            waiting = (await client.get(location)).json()
            assert waiting["status"] == "waiting_for_input"
            async with asyncio.timeout(5):
                events = await client.get(location + "/events")
            assert events.status_code == 200
            assert '"waiting_for_input"' in events.text
            assert (await client.post(location + "/resume")).status_code == 409
        # 這是非問答模組的自訂 interrupt，沿可信 Core 回答。
        async with (
            open_postgres_checkpointer(checkpoint_conninfo) as saver,
            offline_client(transport) as sdk,
            open_agent(
                agent_id="http-test",
                resume_version="v1",
                client=sdk,
                model_settings=MODEL_REQUEST,
                bundles=bundles,
                checkpointer=saver,
            ) as agent,
        ):
            with pytest.raises(RuntimeError, match="Synthetic failure"):
                await consume(
                    agent.aresume(
                        workspace_id=workspace,
                        turn_id=turn,
                        resume_command=Command(
                            resume={
                                waiting["interrupts"][0]["interrupt_id"]: "first answer"
                            }
                        ),
                    )
                )
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=bundles
        ) as client:
            fault = (await client.get(location)).json()
            assert fault["status"] == "interrupted"
            assert fault["interrupts"] == waiting["interrupts"]
            assert (await client.post(location + "/resume")).status_code == 202
            async with asyncio.timeout(5):
                while (await client.get(location)).json()["status"] == "running":
                    await asyncio.sleep(0.01)
            next_question = (await client.get(location)).json()
            assert next_question["status"] == "waiting_for_input"
            assert next_question["interrupts"] == fault["interrupts"]
            assert answers == []
            assert calls == 1
            assert (await client.post(location + "/resume")).status_code == 409
            assert answers == []
            assert calls == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
