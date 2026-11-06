"""訂閱與明確恢復交錯時，running 觀察值仍須帶出終局。"""

import asyncio
from contextlib import aclosing
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.types import StateSnapshot

from caliburn.modules.agent.application.agent_service import AgentService
from caliburn.modules.agent.application.events import TurnEvent
from caliburn.modules.agent.application.views import TurnView
from caliburn.modules.agent.bootstrap import open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.test_agent_http_streaming import GatedModelStream
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    response_events,
    response_payload,
    sse_response,
)


def test_subscription_started_during_resume_keeps_terminal_status(
    checkpoint_conninfo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run() -> None:
        workspace = uuid4()
        turn = uuid4()
        model = GatedModelStream()
        calls = 0
        resume_read_entered = asyncio.Event()
        resume_read_release = asyncio.Event()
        stream_attempted = asyncio.Event()
        resume_task: asyncio.Task[TurnView] | None = None
        first_event_task: asyncio.Task[TurnEvent] | None = None

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return sse_response(EventStream(response_events(response_payload([]))))
            return sse_response(model)

        async def ensure_workspace(workspace_id: UUID) -> None:
            assert workspace_id == workspace
            if asyncio.current_task() is first_event_task:
                await model.entered.wait()

        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(httpx2.MockTransport(respond)) as sdk,
            open_agent(
                agent_id="subscription-race",
                resume_version="v1",
                client=sdk,
                model_settings=MODEL_REQUEST,
                bundles=(),
                checkpointer=saver,
            ) as agent,
            aclosing(AgentService(agent, ensure_workspace=ensure_workspace)) as service,
        ):
            try:
                await service.submit_turn(
                    workspace_id=workspace, turn_id=turn, input="original"
                )
                initial = [
                    event
                    async for event in service.stream_turn(
                        workspace_id=workspace, turn_id=turn
                    )
                ]
                interrupted = initial[-1]
                assert interrupted.event == "status"
                assert interrupted.data.status == "interrupted"
                original_read = agent.aget_state

                async def gated_read(
                    *,
                    workspace_id: UUID,
                    checkpoint_id: str | None = None,
                    subgraphs: bool = False,
                ) -> StateSnapshot:
                    # 保留真 PG 查讀，只暫停持有准入權的 resume。
                    if asyncio.current_task() is resume_task:
                        resume_read_entered.set()
                        await resume_read_release.wait()
                    return await original_read(
                        workspace_id=workspace_id,
                        checkpoint_id=checkpoint_id,
                        subgraphs=subgraphs,
                    )

                monkeypatch.setattr(agent, "aget_state", gated_read)
                resume_task = asyncio.create_task(
                    service.resume_turn(workspace_id=workspace, turn_id=turn)
                )
                await asyncio.wait_for(resume_read_entered.wait(), timeout=5)
                async with aclosing(
                    service.stream_turn(workspace_id=workspace, turn_id=turn)
                ) as stream:

                    async def read_first_event() -> TurnEvent:
                        stream_attempted.set()
                        return await anext(stream)

                    first_event_task = asyncio.create_task(read_first_event())
                    await stream_attempted.wait()
                    resume_read_release.set()
                    async with asyncio.timeout(5):
                        resumed = await resume_task
                        first = await first_event_task
                    assert resumed.status == "running"
                    assert first.event == "status"
                    assert first.data.status == "running"
                    model.release.set()
                    async with asyncio.timeout(5):
                        remaining = [event async for event in stream]
                    assert remaining, "running 訂閱不可在恢復工作完成前直接關閉"
                    last = remaining[-1]
                    assert last.event == "status"
                    assert last.data.status == "completed"
                    assert last.data.output == "Synthetic reply"
                assert calls == 2
            finally:
                resume_read_release.set()
                model.release.set()
                tasks = [
                    task for task in (resume_task, first_event_task) if task is not None
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
