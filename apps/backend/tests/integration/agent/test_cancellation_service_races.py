"""取消服務的讀取、斷線與關閉競態，保留官方 Saver 與真 PostgreSQL。"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import aclosing, asynccontextmanager
from typing import Any, cast
from uuid import UUID, uuid4

import httpx2
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import CheckpointTuple
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.application.agent_service import AgentService
from caliburn.modules.agent.application.errors import (
    AgentUnavailable,
    TurnConflict,
    TurnNotFound,
)
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
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST, offline_client


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle((cast(AgentPlugin, config["plugin"]),))


@asynccontextmanager
async def open_service(
    conninfo: str, workspace: UUID, plugin: AgentPlugin
) -> AsyncIterator[tuple[AgentService, Agent, AsyncPostgresSaver]]:
    async def ensure_workspace(workspace_id: UUID) -> None:
        assert workspace_id == workspace

    def no_model(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("These cancellation scenarios must not call the model")

    async with (
        open_postgres_checkpointer(conninfo, initialize=True) as saver,
        offline_client(httpx2.MockTransport(no_model)) as sdk,
        open_agent(
            agent_id="cancellation-races",
            resume_version="v1",
            client=sdk,
            model_settings=MODEL_REQUEST,
            bundles=(BundleConfig(__name__, {"plugin": plugin}),),
            checkpointer=saver,
        ) as agent,
        aclosing(AgentService(agent, ensure_workspace=ensure_workspace)) as service,
    ):
        yield service, agent, saver


def test_disconnected_cancel_failure_is_owned_and_stream_has_no_cancelled_body(
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def run() -> None:
        workspace, turn = uuid4(), uuid4()
        writer_entered, writer_release = asyncio.Event(), asyncio.Event()
        cleanup_entered, cleanup_release = asyncio.Event(), asyncio.Event()
        duplicate_read = asyncio.Event()
        cleanup_attempts: list[UUID] = []
        loop_errors: list[dict[str, Any]] = []
        disconnected: asyncio.Task[None] | None = None
        duplicate: asyncio.Task[None] | None = None
        secret = "SYNTHETIC_PRIVATE_CANCELLED_BODY"

        async def wait_for_input(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            writer_entered.set()
            await writer_release.wait()
            interrupt(secret)
            return {}

        async def cleanup(
            state: AgentState | None,
            *,
            workspace_id: UUID,
            turn_id: UUID,
            context: AgentContext,
        ) -> None:
            cleanup_attempts.append(turn_id)
            cleanup_entered.set()
            await cleanup_release.wait()
            raise RuntimeError(secret)

        plugin = AgentPlugin(
            "waiting",
            on_turn_start=(PluginStep("wait", wait_for_input),),
            on_turn_cancel=cleanup,
        )
        loop = asyncio.get_running_loop()
        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(lambda _, context: loop_errors.append(context))
        try:
            async with open_service(checkpoint_conninfo, workspace, plugin) as (
                service,
                agent,
                saver,
            ):
                original_list = saver.alist

                async def observe_duplicate(
                    config: RunnableConfig | None,
                    *,
                    filter: dict[str, Any] | None = None,
                    before: RunnableConfig | None = None,
                    limit: int | None = None,
                ) -> AsyncIterator[CheckpointTuple]:
                    async for saved in original_list(
                        config, filter=filter, before=before, limit=limit
                    ):
                        yield saved
                    if asyncio.current_task() is duplicate:
                        duplicate_read.set()

                monkeypatch.setattr(saver, "alist", observe_duplicate)
                try:
                    await service.submit_turn(
                        workspace_id=workspace, turn_id=turn, input=secret
                    )
                    await writer_entered.wait()
                    async with aclosing(
                        service.stream_turn(workspace_id=workspace, turn_id=turn)
                    ) as stream:
                        first = await anext(stream)
                        assert first.event == "status"
                        disconnected = asyncio.create_task(
                            service.cancel_turn(workspace_id=workspace, turn_id=turn)
                        )
                        async with asyncio.timeout(5):
                            while True:
                                try:
                                    await service.submit_turn(
                                        workspace_id=workspace,
                                        turn_id=turn,
                                        input=secret,
                                    )
                                except TurnConflict:
                                    break
                            writer_release.set()
                            await cleanup_entered.wait()
                            duplicate = asyncio.create_task(
                                service.cancel_turn(
                                    workspace_id=workspace, turn_id=turn
                                )
                            )
                            await duplicate_read.wait()
                            disconnected.cancel()
                            with pytest.raises(asyncio.CancelledError):
                                await disconnected
                            assert not duplicate.done()
                            cleanup_release.set()
                            with pytest.raises(AgentUnavailable) as failure:
                                await duplicate
                            remaining = [event async for event in stream]
                        assert secret not in str(failure.value)
                        assert [
                            event.model_dump(mode="json") for event in remaining
                        ] == [
                            {
                                "event": "cancellation",
                                "data": {"turn_id": str(turn), "status": "pending"},
                            }
                        ]
                    await service.aclose()
                    assert cleanup_attempts == [turn]
                    saved = await agent.aget_state(workspace_id=workspace)
                    assert saved.values["cancel_status"] == "pending"
                    assert not loop_errors, (
                        "Disconnected cleanup failures must remain owned"
                    )
                    assert secret not in caplog.text
                finally:
                    writer_release.set()
                    cleanup_release.set()
                    await asyncio.gather(
                        *(
                            task
                            for task in (disconnected, duplicate)
                            if task is not None
                        ),
                        return_exceptions=True,
                    )
        finally:
            loop.set_exception_handler(previous_handler)

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_shutdown_awaits_cleanup_when_writer_finishes_during_cancel_admission(
    checkpoint_conninfo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run() -> None:
        workspace, turn = uuid4(), uuid4()
        writer_entered, writer_release = asyncio.Event(), asyncio.Event()
        history_entered, history_release = asyncio.Event(), asyncio.Event()
        cleanup_entered, cleanup_release = asyncio.Event(), asyncio.Event()
        close_entered = asyncio.Event()
        cancellation: asyncio.Task[None] | None = None
        closing: asyncio.Task[None] | None = None

        async def wait_for_input(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            writer_entered.set()
            await writer_release.wait()
            interrupt("Synthetic question")
            return {}

        async def cleanup(
            state: AgentState | None,
            *,
            workspace_id: UUID,
            turn_id: UUID,
            context: AgentContext,
        ) -> None:
            cleanup_entered.set()
            await cleanup_release.wait()

        plugin = AgentPlugin(
            "waiting",
            on_turn_start=(PluginStep("wait", wait_for_input),),
            on_turn_cancel=cleanup,
        )
        async with open_service(checkpoint_conninfo, workspace, plugin) as (
            service,
            agent,
            saver,
        ):
            original_list = saver.alist

            async def hold_cancel_history(
                config: RunnableConfig | None,
                *,
                filter: dict[str, Any] | None = None,
                before: RunnableConfig | None = None,
                limit: int | None = None,
            ) -> AsyncIterator[CheckpointTuple]:
                if asyncio.current_task() is cancellation:
                    history_entered.set()
                    await history_release.wait()
                async for saved in original_list(
                    config, filter=filter, before=before, limit=limit
                ):
                    yield saved

            monkeypatch.setattr(saver, "alist", hold_cancel_history)
            try:
                await service.submit_turn(
                    workspace_id=workspace, turn_id=turn, input="Synthetic input"
                )
                await writer_entered.wait()
                async with aclosing(
                    service.stream_turn(workspace_id=workspace, turn_id=turn)
                ) as stream:
                    await anext(stream)
                    cancellation = asyncio.create_task(
                        service.cancel_turn(workspace_id=workspace, turn_id=turn)
                    )
                    async with asyncio.timeout(5):
                        await history_entered.wait()
                        writer_release.set()
                        terminal = [event async for event in stream]
                        last = terminal[-1]
                        assert last.event == "status"
                        assert last.data.status == "waiting_for_input"
                        history_release.set()
                        await cleanup_entered.wait()

                        async def close_service() -> None:
                            close_entered.set()
                            await service.aclose()

                        closing = asyncio.create_task(close_service())
                        await close_entered.wait()
                        assert not closing.done(), (
                            "Shutdown must await admitted cleanup"
                        )
                        cleanup_release.set()
                        await cancellation
                        await closing
                saved = await agent.aget_state(workspace_id=workspace)
                assert saved.values["cancel_status"] == "completed"
            finally:
                writer_release.set()
                history_release.set()
                cleanup_release.set()
                await asyncio.gather(
                    *(task for task in (cancellation, closing) if task is not None),
                    return_exceptions=True,
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("start_next_turn", [False, True])
@pytest.mark.parametrize("read_list", [False, True], ids=["execution", "list"])
def test_read_crossing_cancel_does_not_return_cancelled_body(
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
    start_next_turn: bool,
    read_list: bool,
) -> None:
    async def run() -> None:
        workspace, turn = uuid4(), uuid4()
        live_read_entered, live_read_release = asyncio.Event(), asyncio.Event()
        reading: asyncio.Task[Any] | None = None
        next_turn: UUID | None = None

        async def wait_for_input(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            interrupt("Synthetic question")
            return {}

        plugin = AgentPlugin(
            "waiting", on_turn_start=(PluginStep("wait", wait_for_input),)
        )
        async with open_service(checkpoint_conninfo, workspace, plugin) as (
            service,
            _,
            saver,
        ):
            original_get = saver.aget_tuple

            async def hold_live_read(config: RunnableConfig) -> CheckpointTuple | None:
                if asyncio.current_task() is reading and not config["configurable"].get(
                    "checkpoint_id"
                ):
                    live_read_entered.set()
                    await live_read_release.wait()
                return await original_get(config)

            monkeypatch.setattr(saver, "aget_tuple", hold_live_read)
            try:
                await service.submit_turn(
                    workspace_id=workspace,
                    turn_id=turn,
                    input="SYNTHETIC_PRIVATE_CANCELLED_BODY",
                )
                async with aclosing(
                    service.stream_turn(workspace_id=workspace, turn_id=turn)
                ) as stream:
                    terminal = [event async for event in stream]
                    last = terminal[-1]
                    assert last.event == "status"
                    assert last.data.status == "waiting_for_input"
                reading = asyncio.create_task(
                    service.list_turns(workspace_id=workspace)
                    if read_list
                    else service.read_turn_execution(
                        workspace_id=workspace, turn_id=turn
                    )
                )
                async with asyncio.timeout(5):
                    await live_read_entered.wait()
                    await service.cancel_turn(workspace_id=workspace, turn_id=turn)
                    if start_next_turn:
                        next_turn = uuid4()
                        await service.submit_turn(
                            workspace_id=workspace,
                            turn_id=next_turn,
                            input="Fresh input",
                        )
                        async with aclosing(
                            service.stream_turn(
                                workspace_id=workspace, turn_id=next_turn
                            )
                        ) as stream:
                            terminal = [event async for event in stream]
                            last = terminal[-1]
                            assert last.event == "status"
                            assert last.data.status == "waiting_for_input"
                    live_read_release.set()
                    if read_list:
                        turns = await reading
                        expected = [] if next_turn is None else [next_turn]
                        assert [item.turn_id for item in turns] == expected
                    else:
                        with pytest.raises(TurnNotFound):
                            await reading
            finally:
                live_read_release.set()
                if reading is not None:
                    await asyncio.gather(reading, return_exceptions=True)

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
