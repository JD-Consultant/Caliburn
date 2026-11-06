"""合作留在 Bundle 普通函式，不要求 Core 的 registry 或 cache。"""

import asyncio
from typing import cast

import httpx2
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from tests.unit.modules.agent.bundle_fixtures.cooperation import (
    COOPERATION_TRACE,
    CooperationTrace,
)
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    TEST_WORKSPACE_ID,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_one_projection_feeds_independent_consumers_and_step_private_tool() -> None:
    trace = CooperationTrace()
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [call()] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings={
                    "model": "offline-model",
                    "max_output_tokens": 100,
                    "reasoning": {"effort": "low"},
                },
                bundles=[
                    BundleConfig("tests.unit.modules.agent.bundle_fixtures.cooperation")
                ],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                external_services=(COOPERATION_TRACE.bind(trace),),
            ) as agent:
                result = await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, INITIAL),
                )
                assert result["model_response"].output_text == "Synthetic reply"

    asyncio.run(run())
    assert trace.projection_counts == [1, 3]
    assert [body["instructions"] for body in sent] == [
        "Use projection items=1.",
        "Use projection items=3.",
    ]
    assert [body["tools"][0]["description"] for body in sent] == [
        "Read item.",
        "Read item.",
    ]
    assert sent[1]["input"][-1]["output"] == "items=1/alpha"
