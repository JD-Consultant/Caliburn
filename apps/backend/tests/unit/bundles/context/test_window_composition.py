"""Context 單獨組裝，只依賴原生歷史讀取與選用的 SDK client。"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import StateSnapshot

from caliburn.bundles.context.history import previous_completed_window
from caliburn.bundles.context.services import COMPACTION_CLIENT, PREVIOUS_WINDOW
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.agent.state import request_items
from tests.unit.bundles.context.support import compacted_payload
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    message,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("output_kind", ["text", "refusal", "multiple_finals"])
def test_context_window_needs_no_business_services(
    native: bool, output_kind: str
) -> None:
    requests: list[dict[str, Any]] = []
    counts: list[dict[str, Any]] = []
    workspace_id = uuid4()
    bundle = BundleConfig(
        "caliburn.bundles.context",
        plugins=("window", "native_compaction") if native else ("window",),
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        if request.url.path.endswith("input_tokens"):
            counts.append(body)
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 1}
            )
        assert request.url.path == "/v1/responses"
        requests.append(body)
        output = [message(text="bare reply")]
        if output_kind == "refusal":
            output[0]["content"] = [{"type": "refusal", "refusal": "bare refusal"}]
        elif output_kind == "multiple_finals":
            output.append({**message(text="second final"), "id": "msg_second_final"})
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async def previous(workspace: UUID, turn: UUID) -> StateSnapshot | None:
            return await previous_completed_window(
                agent, workspace_id=workspace, turn_id=turn
            )

        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="context-only",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(bundle,),
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
                external_services=(
                    PREVIOUS_WINDOW.bind(previous),
                    *((COMPACTION_CLIENT.bind(client),) if native else ()),
                ),
            ) as agent:
                first = await complete_turn(
                    agent, workspace_id=workspace_id, input="first input"
                )
                history = list(request_items(first["model_request"]))
                second = await complete_turn(
                    agent, workspace_id=workspace_id, input="second input"
                )
                assert request_items(second["model_request"])[: len(history)] == history

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(requests) == 2
    assert len(counts) == (3 if native else 0)
    assert requests[0]["input"] == [{"role": "user", "content": "first input"}]
    assert requests[1]["input"][-1] == {"role": "user", "content": "second input"}
    assert all(request["tools"] == [] for request in requests)


@pytest.mark.parametrize("input_tokens", [95999, 96000])
def test_default_window_threshold_compacts_history_before_adding_turn_input(
    input_tokens: int,
) -> None:
    sent: list[tuple[str, dict[str, Any]]] = []
    workspace_id = uuid4()
    payload = compacted_payload()

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append((request.url.path, request_body(request)))
        if request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200,
                json={"object": "response.input_tokens", "input_tokens": input_tokens},
            )
        if request.url.path.endswith("compact"):
            return httpx2.Response(200, json=payload)
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async def previous(workspace: UUID, turn: UUID) -> StateSnapshot | None:
            return await previous_completed_window(
                agent, workspace_id=workspace, turn_id=turn
            )

        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="context-threshold",
                resume_version="v1",
                client=client,
                model_settings={**MODEL_REQUEST, "instructions": "保留原始工作事實。"},
                bundles=(
                    BundleConfig(
                        "caliburn.bundles.context",
                        plugins=("window", "native_compaction"),
                    ),
                ),
                checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
                external_services=(
                    PREVIOUS_WINDOW.bind(previous),
                    COMPACTION_CLIENT.bind(client),
                ),
            ) as agent:
                await complete_turn(agent, workspace_id=workspace_id, input="old input")
                await complete_turn(agent, workspace_id=workspace_id, input="new input")
                history = [{"role": "user", "content": "old input"}, message()]
                assert sent[2][1]["input"] == history
                expected_history = (
                    payload["output"] if input_tokens == 96000 else history
                )
                assert sent[-1][1]["input"][:-1] == expected_history
                assert sent[-1][1]["input"][-1] == {
                    "role": "user",
                    "content": "new input",
                }

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert [path for path, _ in sent] == [
        "/v1/responses/input_tokens",
        "/v1/responses",
        "/v1/responses/input_tokens",
        *(["/v1/responses/compact"] if input_tokens == 96000 else []),
        "/v1/responses/input_tokens",
        "/v1/responses",
    ]
    for field in ("instructions", "tools"):
        assert sent[2][1][field] == sent[-1][1][field]
    if input_tokens == 96000:
        assert sent[3][1]["input"] == sent[2][1]["input"]
        assert sent[3][1]["instructions"] == sent[2][1]["instructions"]
