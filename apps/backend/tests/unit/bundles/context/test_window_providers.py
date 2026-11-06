"""另一個 Bundle 透過公開集合提供窗口，不修改中央模組清單。"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, TypedDict, cast
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from langgraph.types import StateSnapshot

from caliburn.bundles.context.contracts import WindowContribution
from caliburn.bundles.context.history import previous_completed_window
from caliburn.bundles.context.services import PREVIOUS_WINDOW, WINDOW_CONTRIBUTIONS
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding
from caliburn.modules.agent.state import AgentState, request_items
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


class CandidateFields(TypedDict):
    candidate_ready: bool


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def initialize(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        return {"candidate_ready": True}

    async def prepare(
        state: AgentState,
        *,
        previous: Mapping[str, Any] | None,
        rebuilding: bool,
        runtime: Runtime[AgentContext],
    ) -> Mapping[str, object]:
        assert cast(CandidateFields, state)["candidate_ready"]
        if not rebuilding:
            return {}
        request = state["model_request"]
        return {
            "model_request": {
                **request,
                "input": [
                    *request_items(request),
                    {"role": "user", "content": "alternative context"},
                ],
            }
        }

    async def prepare_input(
        state: AgentState,
        *,
        previous: Mapping[str, Any] | None,
        rebuilding: bool,
        runtime: Runtime[AgentContext],
    ) -> Mapping[str, object]:
        request = state["model_request"]
        return {
            "model_request": {
                **request,
                "input": [
                    *request_items(request),
                    {"role": "user", "content": "alternative input reference"},
                ],
            }
        }

    @asynccontextmanager
    async def open_services(
        services: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        yield (
            WINDOW_CONTRIBUTIONS.bind(
                (WindowContribution(prepare, prepare_input=prepare_input),)
            ),
        )

    return AgentBundle(
        (
            AgentPlugin(
                name=str(config.get("name", "alternative_context")),
                state_schema=CandidateFields,
                on_turn_start=(PluginStep("initialize", initialize),),
                provided_services=(WINDOW_CONTRIBUTIONS,),
                open_services=open_services,
            ),
        )
    )


@pytest.mark.parametrize("context_first", [False, True])
def test_new_bundle_provides_window_after_its_turn_preparation(
    context_first: bool,
) -> None:
    requests: list[dict[str, Any]] = []
    workspace_id = uuid4()
    bundles = (
        BundleConfig(__name__),
        BundleConfig("caliburn.bundles.context", plugins=("window",)),
    )
    if context_first:
        bundles = (bundles[1], bundles[0])

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/responses"
        requests.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async def previous(workspace: UUID, turn: UUID) -> StateSnapshot | None:
            return await previous_completed_window(
                agent, workspace_id=workspace, turn_id=turn
            )

        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="alternative-window",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=bundles,
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
                external_services=(PREVIOUS_WINDOW.bind(previous),),
            ) as agent:
                await complete_turn(agent, workspace_id=workspace_id, input="first")
                await complete_turn(agent, workspace_id=workspace_id, input="second")

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert requests[0]["input"] == [
        {"role": "user", "content": "alternative context"},
        {"role": "user", "content": "first"},
        {"role": "user", "content": "alternative input reference"},
    ]
    assert requests[1]["input"][:3] == requests[0]["input"]
    assert requests[1]["input"][-2:] == [
        {"role": "user", "content": "second"},
        {"role": "user", "content": "alternative input reference"},
    ]


def test_multiple_input_providers_are_rejected_before_model_calls() -> None:
    async def previous(workspace: UUID, turn: UUID) -> StateSnapshot | None:
        return None

    def respond(request: httpx2.Request) -> httpx2.Response:
        pytest.fail("Invalid composition must fail before any model request")

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(ValueError, match="at most one input projection"):
                async with open_agent(
                    agent_id="conflicting-window",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        BundleConfig(__name__, {"name": "first_provider"}),
                        BundleConfig(__name__, {"name": "second_provider"}),
                        BundleConfig(
                            "caliburn.bundles.context",
                            plugins=("window",),
                        ),
                    ),
                    checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
                    external_services=(PREVIOUS_WINDOW.bind(previous),),
                ):
                    pytest.fail("Conflicting input providers were accepted")

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
