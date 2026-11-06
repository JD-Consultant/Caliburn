"""公開入口的啟動及 Workspace 執行生命週期。"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import aclosing, asynccontextmanager
from uuid import UUID

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.modules.agent.agent import AgentExecutionError
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    open_test_agent,
    request_body,
    response_events,
    response_payload,
    run_turn,
    sse_response,
)

STARTED: list[str] = []


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    @asynccontextmanager
    async def acquire(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[object], ...]]:
        STARTED.append("ready")
        try:
            yield ()
        finally:
            STARTED.append("closed")

    return AgentBundle((AgentPlugin("startup", open_services=acquire),))


def test_agent_is_ready_before_any_workspace_is_selected() -> None:
    async def run() -> None:
        STARTED.clear()
        async with offline_client(
            httpx2.MockTransport(lambda _: httpx2.Response(500))
        ) as client:
            async with open_agent(
                agent_id="test",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__)],
                checkpointer=InMemorySaver(),
            ):
                assert STARTED == ["ready"]
            assert STARTED == ["ready", "closed"]
            assert not client.is_closed()

    asyncio.run(run())


def test_new_turn_starts_fresh_and_keeps_saved_history_read_only() -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="fresh",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[],
                checkpointer=InMemorySaver(),
            ) as agent:
                for turn, text in ((UUID(int=11), "first"), (UUID(int=12), "second")):
                    async for _ in agent.astream(
                        workspace_id=UUID(int=1), turn_id=turn, input=text
                    ):
                        pass
                snapshot = await agent.aget_state(workspace_id=UUID(int=1))
                assert snapshot.values["turn_input"] == "second"
                assert snapshot.values["turn_id"] == UUID(int=12)
                assert snapshot.values["model_step"] == 1
                assert snapshot.values["workspace_id"] == UUID(int=1)
                assert not snapshot.next
                history = [
                    item
                    async for item in agent.aget_state_history(workspace_id=UUID(int=1))
                ]
                assert any(
                    item.values.get("model_request", {}).get("input", [])[0:1]
                    == [{"role": "user", "content": "first"}]
                    for item in history
                )

    asyncio.run(run())
    assert [body["input"] for body in sent] == [
        [{"role": "user", "content": "first"}],
        [{"role": "user", "content": "second"}],
    ]


def test_active_thread_rejects_second_writer_and_close_releases_guard() -> None:
    async def run() -> None:
        streams: list[EventStream] = []

        def respond(request: httpx2.Request) -> httpx2.Response:
            stream = EventStream(response_events(response_payload()))
            streams.append(stream)
            return sse_response(stream)

        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_test_agent(client=client) as agent:
                async with aclosing(
                    agent.astream(
                        workspace_id=UUID(int=1), turn_id=UUID(int=11), input="first"
                    )
                ) as first:
                    async for event in first:
                        if event["type"] == "custom":
                            break
                    with pytest.raises(AgentExecutionError, match="active"):
                        await anext(
                            agent.astream(
                                workspace_id=UUID(int=1),
                                turn_id=UUID(int=12),
                                input="second",
                            )
                        )
                    # 另一 Workspace 可以在同一長存 Agent 上獨立完成。
                    other = await run_turn(
                        agent, workspace_id=UUID(int=2), input="other"
                    )
                    assert other["workspace_id"] == UUID(int=2)
                assert streams[0].closed
                saved = await agent.aget_state(workspace_id=UUID(int=1))
                if saved.next or saved.tasks:
                    async for _ in agent.aresume(
                        workspace_id=UUID(int=1), turn_id=UUID(int=11)
                    ):
                        pass
                else:
                    await run_turn(agent, workspace_id=UUID(int=1), input="next")
                assert not client.is_closed()

    asyncio.run(run())


def test_missing_completed_and_closed_agent_operations_are_rejected() -> None:
    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client:
            async with open_test_agent(client=client) as agent:
                with pytest.raises(AgentExecutionError, match="missing or completed"):
                    await anext(
                        agent.aresume(workspace_id=UUID(int=1), turn_id=UUID(int=11))
                    )
                await run_turn(agent, workspace_id=UUID(int=1))
                with pytest.raises(AgentExecutionError, match="missing or completed"):
                    await anext(
                        agent.aresume(workspace_id=UUID(int=1), turn_id=UUID(int=11))
                    )
            with pytest.raises(AgentExecutionError, match="closed"):
                await agent.aget_state(workspace_id=UUID(int=1))
            with pytest.raises(AgentExecutionError, match="closed"):
                await anext(
                    agent.astream(
                        workspace_id=UUID(int=1), turn_id=UUID(int=12), input="next"
                    )
                )

    asyncio.run(run())
