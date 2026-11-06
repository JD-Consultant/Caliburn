"""固定 SDK 政策在公開組裝時核對，當步材料不能繞過政策。"""

import asyncio
from copy import deepcopy
from typing import Any, cast

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import open_agent
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    MODEL_REQUEST,
    TEST_WORKSPACE_ID,
    EventStream,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize(
    "override",
    [
        {"tools": []},
        {"conversation": "conv_remote"},
        {"previous_response_id": "resp_remote"},
        {"context_management": []},
        {"prompt": {"id": "remote"}},
        {"stream": False},
        {"extra_body": {"store": True}},
        {"store": True},
        {"background": True},
        {"parallel_tool_calls": False},
        {"tool_choice": "none"},
        {"truncation": "auto"},
        {"service_tier": "priority"},
        {"include": []},
        {"reasoning": {"effort": "low", "context": "none"}},
        {"model": ""},
        {"max_output_tokens": 0},
        {"input": "bare string"},
    ],
)
def test_fixed_configuration_cannot_bypass_core_request_policy(
    override: dict[str, object],
) -> None:
    source = deepcopy(MODEL_REQUEST)
    cast(dict[str, Any], source).update(override)

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            with pytest.raises(ValueError):
                async with open_agent(
                    client=client,
                    model_settings=source,
                    bundles=[],
                    agent_id="test-agent",
                    resume_version="v1",
                    checkpointer=InMemorySaver(),
                ):
                    pass

    asyncio.run(run())


@pytest.mark.parametrize(
    "override",
    [
        {},
        {
            "tools": None,
            "conversation": None,
            "previous_response_id": None,
            "context_management": None,
            "prompt": None,
            "stream": None,
            "response_id": None,
            "starting_after": None,
            "extra_body": None,
            "extra_headers": None,
            "extra_query": None,
        },
        {
            "store": None,
            "background": None,
            "parallel_tool_calls": None,
            "tool_choice": None,
            "truncation": None,
            "service_tier": None,
        },
        {"include": None},
        {"reasoning": {"effort": "low", "context": None}},
    ],
)
def test_unset_options_send_same_local_policy_without_mutating_configuration(
    override: dict[str, object],
) -> None:
    sent = []
    source = deepcopy(MODEL_REQUEST)
    cast(dict[str, Any], source).update(override)
    original = deepcopy(source)

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=source,
                bundles=[],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, INITIAL),
                )

    asyncio.run(run())
    assert source == original
    assert sent == [
        {
            **MODEL_REQUEST,
            "input": cast(ResponseInputParam, INITIAL),
            "reasoning": {"effort": "low", "context": "all_turns"},
            "store": False,
            "background": False,
            "include": ["reasoning.encrypted_content"],
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "truncation": "disabled",
            "service_tier": "default",
            "tools": [],
            "stream": True,
        }
    ]
