"""公開 Agent 入口的回合身分、模型步及正常流程接點。"""

import asyncio
from collections.abc import Mapping
from typing import TypedDict
from uuid import UUID

import httpx2
import pytest
from langgraph.runtime import Runtime

from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
    PluginHook,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    message,
    offline_client,
    open_test_agent,
    response_events,
    response_payload,
    sse_response,
)


def test_original_turn_input_remains_available_after_completion() -> None:
    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client:
            async with open_test_agent(client=client) as agent:
                async for _ in agent.astream(
                    workspace_id=UUID(int=1), turn_id=UUID(int=11), input="original"
                ):
                    pass
                saved = await agent.aget_state(workspace_id=UUID(int=1))
                assert saved.values.get("turn_input") == "original"

    asyncio.run(run())


class FlowState(TypedDict):
    phases: list[str]


class FlowView(AgentState):
    phases: list[str]


def test_each_model_step_runs_after_hook_before_turn_end() -> None:
    def record(phase: str) -> PluginHook[FlowView]:
        async def hook(
            state: FlowView, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            phases = [] if phase == "start" else state["phases"]
            return {"phases": [*phases, f"{phase}:{state['model_step']}"]}

        return hook

    plugin = AgentPlugin(
        "flow",
        state_schema=FlowState,
        on_turn_start=(PluginStep("start", record("start")),),
        before_model_step=(PluginStep("before", record("before")),),
        after_model_step=(PluginStep("after", record("after")),),
        on_turn_end=(PluginStep("end", record("end")),),
    )
    replies = iter([message("commentary"), message("final_answer")])

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(
                    EventStream(response_events(response_payload([next(replies)])))
                )
            )
        ) as client:
            async with open_test_agent(client=client, plugins=(plugin,)) as agent:
                async for _ in agent.astream(
                    workspace_id=UUID(int=1), turn_id=UUID(int=11), input="original"
                ):
                    pass
                saved = await agent.aget_state(workspace_id=UUID(int=1))
                assert saved.values["phases"] == [
                    "start:0",
                    "before:1",
                    "after:1",
                    "before:2",
                    "after:2",
                    "end:2",
                ]

    asyncio.run(run())


def test_failed_before_hook_resumes_same_model_step_in_a_new_run() -> None:
    attempts: list[tuple[UUID, int, str | None]] = []

    async def prepare(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        assert runtime.execution_info is not None
        attempts.append(
            (state["turn_id"], state["model_step"], runtime.execution_info.run_id)
        )
        assert state["model_response"] is None
        if len(attempts) == 1:
            raise RuntimeError("synthetic preparation failure")
        return {}

    plugin = AgentPlugin("prepare", before_model_step=(PluginStep("request", prepare),))

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client:
            async with open_test_agent(client=client, plugins=(plugin,)) as agent:
                with pytest.raises(RuntimeError, match="preparation failure"):
                    async for _ in agent.astream(
                        workspace_id=UUID(int=1), turn_id=UUID(int=11), input="original"
                    ):
                        pass
                pending = await agent.aget_state(workspace_id=UUID(int=1))
                assert pending.values["model_step"] == 1
                assert pending.values["model_response"] is None
                async for _ in agent.aresume(
                    workspace_id=UUID(int=1), turn_id=UUID(int=11)
                ):
                    pass
                done = await agent.aget_state(workspace_id=UUID(int=1))
                assert done.values["model_step"] == 1

    asyncio.run(run())
    assert [(turn, step) for turn, step, _ in attempts] == [
        (UUID(int=11), 1),
        (UUID(int=11), 1),
    ]
    assert attempts[0][2] is not None and attempts[1][2] is not None
    assert attempts[0][2] != attempts[1][2]
