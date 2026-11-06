"""四個公開 Hook 在模型步邊界保存，後置故障不重做已完成模型或工具。"""

import asyncio
from collections.abc import Mapping
from uuid import UUID

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from langgraph.runtime import Runtime

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import (
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


@pytest.mark.parametrize("with_tools", [False, True])
def test_failed_after_step_cold_resume_preserves_completed_model_and_tools(
    checkpoint_conninfo: str, with_tools: bool
) -> None:
    workspace, turn = UUID(int=61), UUID(int=601)
    trace: list[str] = []
    sent: list[dict[str, object]] = []

    async def read_alpha(item: str) -> str:
        trace.append(f"tool:{item}")
        return f"read {item}"

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        trace.append(f"model:{len(sent)}")
        output = (
            [call(), call(call_id="call_beta", arguments='{"item":"beta"}')]
            if with_tools and len(sent) == 1
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    def plugin(*, fail: bool) -> AgentPlugin:
        async def start(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            trace.append(f"start:{state['model_step']}")
            assert state["turn_input"] == "original"
            return {}

        async def before(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            trace.append(f"before:{state['model_step']}")
            assert state["model_response"] is None
            return {}

        async def after(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            trace.append(f"after:{state['model_step']}:{'fail' if fail else 'ok'}")
            assert state["model_response"] is not None
            if fail:
                raise RuntimeError("synthetic after-step outage")
            return {}

        async def end(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            trace.append(f"end:{state['model_step']}")
            return {}

        return AgentPlugin(
            "lifecycle",
            tools=(
                StructuredTool.from_function(
                    coroutine=read_alpha, description="Read synthetic data."
                ),
            )
            if with_tools
            else (),
            on_turn_start=(PluginStep("start", start),),
            before_model_step=(PluginStep("before", before),),
            after_model_step=(PluginStep("after", after),),
            on_turn_end=(PluginStep("end", end),),
        )

    async def run() -> None:
        for fail in (True, False):
            async with (
                open_postgres_checkpointer(
                    checkpoint_conninfo, initialize=fail
                ) as saver,
                offline_client(httpx2.MockTransport(respond)) as client,
                open_agent(
                    agent_id="lifecycle",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        BundleConfig(
                            "tests.unit.modules.agent.offline_openai",
                            {"plugins": (plugin(fail=fail),)},
                        ),
                    ),
                    checkpointer=saver,
                ) as agent,
            ):
                if fail:
                    with pytest.raises(RuntimeError, match="after-step outage"):
                        await consume(
                            agent.astream(
                                workspace_id=workspace, turn_id=turn, input="original"
                            )
                        )
                    saved = await agent.aget_state(workspace_id=workspace)
                    assert saved.values["model_step"] == 1
                    assert saved.next and not saved.interrupts
                    assert not any(item.startswith("end:") for item in trace)
                else:
                    await consume(agent.aresume(workspace_id=workspace, turn_id=turn))
                    saved = await agent.aget_state(workspace_id=workspace)
                    assert not saved.next and not saved.interrupts
                    assert saved.values["model_step"] == (2 if with_tools else 1)
                    assert saved.values["turn_input"] == "original"
                    assert saved.values["turn_id"] == turn

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert trace == (
        [
            "start:0",
            "before:1",
            "model:1",
            "tool:alpha",
            "tool:beta",
            "after:1:fail",
            "after:1:ok",
            "before:2",
            "model:2",
            "after:2:ok",
            "end:2",
        ]
        if with_tools
        else ["start:0", "before:1", "model:1", "after:1:fail", "after:1:ok", "end:1"]
    )
    assert len(sent) == (2 if with_tools else 1)
