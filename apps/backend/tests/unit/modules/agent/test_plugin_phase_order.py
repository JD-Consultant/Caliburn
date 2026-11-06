"""插件選取不改宣告序；階段收尾沿原生節點保存。"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime

from caliburn.modules.agent.bootstrap import open_agent
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginHook,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

type Phase = Literal[
    "on_turn_start", "before_model_step", "after_model_step", "on_turn_end"
]


@pytest.mark.parametrize(
    "phase", ["on_turn_start", "before_model_step", "after_model_step", "on_turn_end"]
)
def test_phase_tail_runs_after_all_normal_steps_without_reordering_prompts(
    phase: Phase,
) -> None:
    events: list[str] = []
    requests: list[dict[str, Any]] = []

    def record(label: str) -> PluginHook[AgentState]:
        async def run(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> AgentState:
            events.append(label)
            return {}

        return run

    def configured(name: str, steps: tuple[PluginStep[AgentState], ...]) -> AgentPlugin:
        return AgentPlugin(
            name,
            prompt_sections=(name,),
            on_turn_start=steps if phase == "on_turn_start" else (),
            before_model_step=steps if phase == "before_model_step" else (),
            after_model_step=steps if phase == "after_model_step" else (),
            on_turn_end=steps if phase == "on_turn_end" else (),
        )

    plugins = (
        configured(
            "tail",
            (
                PluginStep("prepare", record("prepare_tail")),
                PluginStep("compact", record("compact"), run_last=True),
                PluginStep("recount", record("recount"), run_last=True),
            ),
        ),
        configured("writer", (PluginStep("write", record("writer")),)),
        configured(
            "third_party",
            (PluginStep("write", record("third_party")),),
        ),
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="phase-order",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(AgentBundle(plugins),),
                checkpointer=InMemorySaver(),
            ) as agent:
                await complete_turn(agent, workspace_id=uuid4(), input="input")

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert events == ["prepare_tail", "writer", "third_party", "compact", "recount"]
    assert requests[0]["instructions"].endswith("tail\n\nwriter\n\nthird_party")


async def empty_step(
    state: AgentState, *, runtime: Runtime[AgentContext]
) -> AgentState:
    return {}


def test_required_plugins_check_presence_without_reordering() -> None:
    events: list[str] = []

    def plugin(name: str, required: str) -> AgentPlugin:
        @asynccontextmanager
        async def acquire(
            dependencies: PluginServices,
        ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
            events.append(f"open:{name}")
            try:
                yield ()
            finally:
                events.append(f"close:{name}")

        async def run(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> AgentState:
            events.append(f"hook:{name}")
            return {}

        return AgentPlugin(
            name,
            required_plugins=(required,),
            open_services=acquire,
            on_turn_start=(PluginStep("prepare", run),),
        )

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client:
            async with open_agent(
                agent_id="required-presence",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(
                    AgentBundle((plugin("first", "second"), plugin("second", "first"))),
                ),
                checkpointer=InMemorySaver(),
            ) as agent:
                await complete_turn(agent, workspace_id=uuid4(), input="input")

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert events == [
        "open:first",
        "open:second",
        "hook:first",
        "hook:second",
        "close:second",
        "close:first",
    ]


@pytest.mark.parametrize("invalid", ["missing", "two_tail_owners", "normal_after_tail"])
def test_invalid_plugin_composition_is_rejected_before_opening_resources(
    invalid: str,
) -> None:
    acquired: list[str] = []

    @asynccontextmanager
    async def acquire(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        acquired.append("opened")
        yield ()

    tail = PluginStep("tail", empty_step, run_last=True)
    plugins: tuple[AgentPlugin, ...]
    if invalid == "missing":
        plugins = (AgentPlugin("consumer", required_plugins=("absent",)),)
        match = "consumer.*absent"
    elif invalid == "two_tail_owners":
        plugins = (
            AgentPlugin("one", before_model_step=(tail,)),
            AgentPlugin("two", before_model_step=(tail,)),
        )
        match = "before_model_step.*one.*two"
    else:
        plugins = (
            AgentPlugin(
                "invalid",
                on_turn_start=(tail, PluginStep("normal", empty_step)),
            ),
        )
        match = "on_turn_start.*invalid"

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            with pytest.raises(ValueError, match=match):
                async with open_agent(
                    agent_id="invalid-order",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        AgentBundle(
                            (AgentPlugin("resource", open_services=acquire), *plugins)
                        ),
                    ),
                    checkpointer=InMemorySaver(),
                ):
                    pass

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert acquired == []
