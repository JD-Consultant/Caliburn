"""Around 是具名 hook 的普通組合，局部更新與清理明示。"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, cast

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from openai.types.responses.response_create_params import ResponseCreateParamsBase
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginHook,
    PluginStep,
    PluginWrapper,
)
from caliburn.modules.agent.plugins.services import (
    PluginServices,
    ServiceBinding,
    ServiceKey,
)
from caliburn.modules.agent.state import AgentState, request_items
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    MODEL_REQUEST,
    TEST_WORKSPACE_ID,
    EventStream,
    message,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@dataclass
class Trace:
    events: list[str] = field(default_factory=list)
    started: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)
    failure: RuntimeError = field(default_factory=lambda: RuntimeError("hook failed"))


TRACE = ServiceKey[Trace]("around-trace")
FACTORIES: list[str] = []


def create_bundle(config: Mapping[str, object]) -> AgentBundle:

    def wrapper(label: str) -> PluginWrapper[AgentState]:

        def wrap(next_hook: PluginHook[AgentState]) -> PluginHook[AgentState]:
            FACTORIES.append(label)

            async def call(
                state: AgentState, *, runtime: Runtime[AgentContext]
            ) -> Mapping[str, object]:
                trace = runtime.context.services.require(TRACE)
                trace.events.append(f"{label}:before")
                request = state["model_request"]
                before: AgentState = {
                    "model_request": {
                        **request,
                        "input": cast(
                            ResponseInputParam,
                            [
                                *request_items(request),
                                {"role": "user", "content": f"{label}:before"},
                            ],
                        ),
                    }
                }
                try:
                    update = await next_hook({**state, **before}, runtime=runtime)
                    current = {**state, **before, **update}
                    request = cast(ResponseCreateParamsBase, current["model_request"])
                    trace.events.append(f"{label}:after")
                    return {
                        **update,
                        "model_request": {
                            **request,
                            "input": cast(
                                ResponseInputParam,
                                [
                                    *request_items(request),
                                    {"role": "user", "content": f"{label}:after"},
                                ],
                            ),
                        },
                    }
                finally:
                    trace.events.append(f"{label}:finally")

            return call

        return wrap

    async def callback(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        trace = runtime.context.services.require(TRACE)
        trace.events.append("callback")
        try:
            if config.get("failure"):
                raise trace.failure
            if config.get("wait"):
                trace.started.set()
                await trace.release.wait()
            if config.get("empty"):
                return {}
            request = state["model_request"]
            return {
                "model_request": {
                    **request,
                    "input": cast(
                        ResponseInputParam,
                        [
                            *request_items(request),
                            {"role": "user", "content": "callback"},
                        ],
                    ),
                }
            }
        finally:
            trace.events.append("callback:finally")

    @asynccontextmanager
    async def open_services(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        trace = dependencies.require(TRACE)
        trace.events.append("enter")
        try:
            yield ()
        finally:
            trace.events.append("exit")

    return AgentBundle(
        (
            AgentPlugin(
                "around",
                required_services=(TRACE,),
                open_services=open_services,
                before_model_step=(
                    PluginStep(
                        "callback", callback, wrappers=(wrapper("A"), wrapper("B"))
                    ),
                ),
            ),
        )
    )


@pytest.mark.parametrize("empty", [True, False])
def test_nested_around_preserves_next_and_post_updates_through_model(
    empty: bool,
) -> None:
    trace = Trace()
    FACTORIES.clear()
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(
            EventStream(
                response_events(
                    response_payload(
                        [message("commentary")] if len(sent) == 1 else None
                    )
                )
            )
        )

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"empty": empty})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                external_services=(TRACE.bind(trace),),
            ) as agent:
                await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, INITIAL),
                )

    asyncio.run(run())
    assert FACTORIES == ["B", "A"]
    one_step = [
        "A:before",
        "B:before",
        "callback",
        "callback:finally",
        "B:after",
        "B:finally",
        "A:after",
        "A:finally",
    ]
    assert trace.events == ["enter", *one_step, *one_step, "exit"]
    expected = [
        "Synthetic input",
        "A:before",
        "B:before",
        *([] if empty else ["callback"]),
        "B:after",
        "A:after",
    ]
    assert [item["content"] for item in sent[0]["input"]] == expected
    assert sent[1]["input"][: len(expected)] == sent[0]["input"]


@pytest.mark.parametrize("failure", [True, False])
def test_around_propagates_error_or_cancellation_and_cleans_inside_scope(
    failure: bool,
) -> None:

    async def run() -> None:
        trace = Trace()
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:

            async def invoke() -> None:
                async with open_agent(
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=[
                        BundleConfig(
                            __name__, {"failure": failure, "wait": not failure}
                        )
                    ],
                    agent_id="test-agent",
                    resume_version="v1",
                    checkpointer=InMemorySaver(),
                    external_services=(TRACE.bind(trace),),
                ) as agent:
                    await complete_turn(
                        agent,
                        workspace_id=TEST_WORKSPACE_ID,
                        input=cast(ResponseInputParam, INITIAL),
                    )

            if failure:
                with pytest.raises(RuntimeError) as caught:
                    await invoke()
                assert caught.value is trace.failure
            else:
                task = asyncio.create_task(invoke())
                try:
                    await asyncio.wait_for(trace.started.wait(), 5)
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        assert trace.events == [
            "enter",
            "A:before",
            "B:before",
            "callback",
            "callback:finally",
            "B:finally",
            "A:finally",
            "exit",
        ]

    asyncio.run(run())


def test_waiting_hook_cannot_send_a_partial_request() -> None:

    async def run() -> None:
        trace = Trace()
        sent = []

        def respond(request: httpx2.Request) -> httpx2.Response:
            sent.append(request_body(request))
            return sse_response(EventStream(response_events(response_payload())))

        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"wait": True})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                external_services=(TRACE.bind(trace),),
            ) as agent:
                task = asyncio.create_task(
                    complete_turn(
                        agent,
                        workspace_id=TEST_WORKSPACE_ID,
                        input=cast(ResponseInputParam, INITIAL),
                    )
                )
                try:
                    await asyncio.wait_for(trace.started.wait(), 5)
                    assert sent == []
                    trace.release.set()
                    await task
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        assert len(sent) == 1

    asyncio.run(run())
