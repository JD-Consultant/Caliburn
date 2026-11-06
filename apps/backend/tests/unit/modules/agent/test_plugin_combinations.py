"""同一 Loop 上，以配置替換 Memory 與選配換窗；驗真正出站與工具閉包。"""

import asyncio
from typing import cast
from uuid import UUID

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.state import OpenAIItems
from tests.unit.modules.agent.execution import complete_turn
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

PREFIX = "tests.unit.modules.agent.bundle_fixtures."
INITIAL: OpenAIItems = [
    {"role": "user", "content": "old prefix"},
    {"role": "user", "content": "current question"},
]


@pytest.mark.parametrize(
    "memory, window",
    [
        ("a", None),
        ("b", None),
        ("a", "before"),
        ("b", "recollect"),
        (None, "recollect"),
    ],
)
def test_configuration_replaces_memory_and_disables_optional_window(
    memory: str | None, window: str | None
) -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [call()] if memory is not None and len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        bundles = [BundleConfig(PREFIX + "memory_" + memory)] if memory else []
        if window:
            bundles.insert(0, BundleConfig(PREFIX + "window", {"strategy": window}))
        bundles.append(BundleConfig(PREFIX + "interview"))
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=bundles,
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                await complete_turn(
                    agent,
                    workspace_id=UUID(int=1),
                    input=cast(ResponseInputParam, INITIAL),
                )
            if memory:
                count = 1 if window else 2
                stamp = f"{memory.upper()}:workspace=1:items={count}"
                assert sent[0]["instructions"] == f"Memory {stamp}; short id alpha."
                assert sent[0]["tools"][0]["description"] == "Read item."
                assert sent[1]["input"][-1]["output"] == f"{stamp}/alpha"
            else:
                assert sent[0]["tools"] == [] and "instructions" not in sent[0]

    asyncio.run(run())
    assert INITIAL == [
        {"role": "user", "content": "old prefix"},
        {"role": "user", "content": "current question"},
    ]
    if window:
        assert sent[0]["input"][-1] == {"role": "user", "content": "current question"}
        assert all(item.get("content") != "old prefix" for item in sent[0]["input"])


def test_memory_can_import_public_interview_query_without_service_binding() -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="memory-only",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(PREFIX + "memory_a")],
                checkpointer=InMemorySaver(),
            ) as agent:
                await complete_turn(agent, workspace_id=UUID(int=1), input="question")

    asyncio.run(run())
    assert sent[0]["instructions"] == "Memory A:workspace=1:items=1; short id alpha."


def test_shared_agent_keeps_overlapping_workspace_data_and_tools_private() -> None:

    async def run() -> None:
        ready = asyncio.Event()
        sent = []

        async def respond(request: httpx2.Request) -> httpx2.Response:
            body = request_body(request)
            sent.append(body)
            if len(body["input"]) == 3:
                if len(sent) == 2:
                    ready.set()
                await asyncio.wait_for(ready.wait(), timeout=5)
                output = [call()]
            else:
                output = None
            return sse_response(EventStream(response_events(response_payload(output))))

        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(PREFIX + "memory_a")],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:

                async def invoke(number: int) -> None:
                    await complete_turn(
                        agent,
                        workspace_id=UUID(int=number),
                        input=cast(ResponseInputParam, INITIAL),
                    )

                await asyncio.gather(invoke(1), invoke(2))
        final = [body for body in sent if len(body["input"]) == 5]
        assert {
            (body["instructions"], body["input"][-1]["output"]) for body in final
        } == {
            (
                "Memory A:workspace=1:items=4; short id alpha.",
                "A:workspace=1:items=2/alpha",
            ),
            (
                "Memory A:workspace=2:items=4; short id alpha.",
                "A:workspace=2:items=2/alpha",
            ),
        }

    asyncio.run(run())
