"""正常完成輪的公開查讀沿原生保存點，取消與未完成不推進基準。"""

import asyncio
from collections.abc import Mapping
from typing import TypedDict, cast
from uuid import UUID

import httpx2
import pytest
from langgraph.runtime import Runtime

from caliburn.modules.agent.agent import Agent
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
    response_events,
    response_payload,
    sse_response,
)


class CompletedState(TypedDict):
    completed_version: int


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle(cast(tuple[AgentPlugin, ...], config["plugins"]))


def test_previous_completed_turn_survives_reopen_and_skips_cancelled_end_hook(
    checkpoint_conninfo: str,
) -> None:
    workspace = UUID(int=31)
    first, cancelled, current = UUID(int=319), UUID(int=312), UUID(int=315)
    agent: Agent
    captured: list[tuple[UUID, int | None]] = []
    requests: list[httpx2.Request] = []

    async def capture_previous(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        previous = await agent.aget_previous_completed_turn(
            workspace_id=state["workspace_id"], before_turn_id=state["turn_id"]
        )
        captured.append(
            (
                state["turn_id"],
                previous.values["completed_version"] if previous else None,
            )
        )
        return {}

    async def record_completion(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        return {"completed_version": int(cast(str, state["turn_input"]))}

    async def reject_second_end(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        if state["turn_id"] == cancelled:
            raise RuntimeError("synthetic failure after completion channel")
        return {}

    plugin = AgentPlugin(
        "completion_probe",
        state_schema=CompletedState,
        on_turn_start=(PluginStep("capture_previous", capture_previous),),
        on_turn_end=(
            PluginStep("record_completion", record_completion),
            PluginStep("reject_second_end", reject_second_end),
        ),
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        nonlocal agent
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
        ):
            async with open_agent(
                agent_id="previous-completed",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(BundleConfig(__name__, {"plugins": (plugin,)}),),
                checkpointer=saver,
            ) as agent:
                await consume(
                    agent.astream(workspace_id=workspace, turn_id=first, input="1")
                )
                with pytest.raises(RuntimeError, match="after completion channel"):
                    await consume(
                        agent.astream(
                            workspace_id=workspace, turn_id=cancelled, input="2"
                        )
                    )
                failed = await agent.aget_state(workspace_id=workspace)
                assert failed.values["completed_version"] == 2
                assert failed.values["model_response"] is not None
                assert failed.next
                await agent.acancel_turn(workspace_id=workspace, turn_id=cancelled)

        async with (
            open_postgres_checkpointer(checkpoint_conninfo) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
            open_agent(
                agent_id="previous-completed",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(BundleConfig(__name__, {"plugins": (plugin,)}),),
                checkpointer=saver,
            ) as agent,
        ):
            await consume(
                agent.astream(workspace_id=workspace, turn_id=current, input="3")
            )
            before = [
                item.config
                async for item in agent.aget_state_history(workspace_id=workspace)
            ]
            previous = await agent.aget_previous_completed_turn(
                workspace_id=workspace, before_turn_id=current
            )
            assert previous is not None
            assert previous.values["turn_id"] == first
            assert previous.values["completed_version"] == 1
            assert previous.values["model_response"].output_text == "Synthetic reply"
            assert (
                await agent.aget_previous_completed_turn(
                    workspace_id=workspace, before_turn_id=cancelled
                )
            ) == previous
            assert (
                await agent.aget_previous_completed_turn(
                    workspace_id=workspace, before_turn_id=first
                )
            ) is None
            assert (
                await agent.aget_previous_completed_turn(
                    workspace_id=workspace, before_turn_id=UUID(int=999)
                )
            ) is None
            assert (
                await agent.aget_previous_completed_turn(
                    workspace_id=UUID(int=32), before_turn_id=current
                )
            ) is None
            assert [
                item.config
                async for item in agent.aget_state_history(workspace_id=workspace)
            ] == before
            assert len(requests) == 3

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert captured == [(first, None), (cancelled, 1), (current, 1)]
