"""Context 的插件選擇只啟用所需依賴與請求步驟。"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import StateSnapshot
from openai.types.responses import CompactedResponse
from openai.types.responses.response_create_params import ResponseCreateParamsBase

from caliburn.bundles.context.history import previous_completed_window
from caliburn.bundles.context.services import (
    COMPACTION_CLIENT,
    HISTORY_COMPACTION,
    PREVIOUS_WINDOW,
)
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
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


@pytest.mark.parametrize(
    ("plugins", "expected_counts", "keeps_history"),
    [
        (("window",), 0, True),
        (("native_compaction",), 2, False),
        (("window", "native_compaction"), 3, True),
        ((), 0, False),
    ],
    ids=["window-only", "native-only", "both", "disabled"],
)
def test_selected_plugins_only_require_and_run_their_capabilities(
    plugins: tuple[str, ...], expected_counts: int, keeps_history: bool
) -> None:
    requests: list[dict[str, Any]] = []
    paths: list[str] = []
    workspace_id = uuid4()

    def respond(request: httpx2.Request) -> httpx2.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 1}
            )
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
                agent_id="context-selection",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(BundleConfig("caliburn.bundles.context", plugins=plugins),),
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
                external_services=(
                    *((PREVIOUS_WINDOW.bind(previous),) if "window" in plugins else ()),
                    *(
                        (COMPACTION_CLIENT.bind(client),)
                        if "native_compaction" in plugins
                        else ()
                    ),
                ),
            ) as agent:
                await complete_turn(agent, workspace_id=workspace_id, input="first")
                await complete_turn(agent, workspace_id=workspace_id, input="second")

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert paths.count("/v1/responses/input_tokens") == expected_counts
    assert len(requests) == 2
    assert requests[1]["input"][-1] == {"role": "user", "content": "second"}
    assert len(requests[1]["input"]) == (3 if keeps_history else 1)


def test_multiple_history_compactors_are_rejected_before_model_calls() -> None:
    async def previous(workspace: UUID, turn: UUID) -> StateSnapshot | None:
        return None

    async def compact(request: ResponseCreateParamsBase) -> CompactedResponse | None:
        pytest.fail("Conflicting history compactors must not be invoked")

    def respond(request: httpx2.Request) -> httpx2.Response:
        pytest.fail("Invalid composition must fail before model requests")

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(ValueError, match="at most one history compaction"):
                async with open_agent(
                    agent_id="conflicting-history-compaction",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        BundleConfig("caliburn.bundles.context", plugins=("window",)),
                    ),
                    checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
                    external_services=(
                        PREVIOUS_WINDOW.bind(previous),
                        HISTORY_COMPACTION.bind((compact, compact)),
                    ),
                ):
                    pytest.fail("Conflicting history compactors were accepted")

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
