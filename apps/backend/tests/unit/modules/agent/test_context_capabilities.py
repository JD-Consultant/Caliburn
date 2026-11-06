"""工作 request 的輸入所有權、接續與固定 Prompt 初始化。"""

import asyncio
from collections.abc import Mapping
from copy import deepcopy
from typing import cast

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
    PluginStep,
)
from caliburn.modules.agent.state import AgentState, request_items
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
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


def create_bundle(config: Mapping[str, object]) -> AgentBundle:

    async def update(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        if config.get("empty"):
            return {}
        if config.get("string_input"):
            return {"model_request": {**state["model_request"], "input": "hello"}}
        if "request_override" in config:
            override = cast(ResponseCreateParamsBase, config["request_override"])
            updated_request = {**state["model_request"], **override}
            removed_key = config.get("request_remove")
            if isinstance(removed_key, str):
                updated_request.pop(removed_key)
            return {"model_request": cast(ResponseCreateParamsBase, updated_request)}
        request = state["model_request"]
        items = request_items(request)
        return {
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    [*items, {"role": "developer", "content": "shared update"}],
                ),
            }
        }

    return AgentBundle(
        (
            AgentPlugin(
                "first",
                prompt_sections=("First",),
                before_model_step=(PluginStep("update", update),),
            ),
            AgentPlugin("second", prompt_sections=("Second",)),
        )
    )


def test_continuation_reuses_final_input_without_doubling_static_prompt() -> None:
    sent = []
    initial = [{"role": "user", "content": "question"}]

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [message("commentary")] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings={**MODEL_REQUEST, "instructions": "Base"},
                bundles=[BundleConfig(__name__, {"empty": True})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                first = await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, initial),
                )
                previous = deepcopy(first["model_request"])
                continuation = [
                    *request_items(first["model_request"]),
                    {"role": "user", "content": "next"},
                ]
                second = await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, continuation),
                )
                assert first["model_request"] == previous
                assert second["model_step"] == 1 and first["model_step"] == 2
                assert request_items(second["model_request"])[:-1] == continuation

    asyncio.run(run())
    assert initial == [{"role": "user", "content": "question"}]
    assert [body["instructions"] for body in sent] == ["Base\n\nFirst\n\nSecond"] * 3
    assert sent[2]["input"][-1] == {"role": "user", "content": "next"}
    assert [item["type"] for item in sent[2]["input"][1:3]] == ["message", "message"]


@pytest.mark.parametrize("empty", [True, False])
def test_graph_owns_nested_initial_input_and_no_update_preserves_request(
    empty: bool,
) -> None:
    initial = [{"role": "user", "content": [{"type": "input_text", "text": "nested"}]}]
    original = deepcopy(initial)

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"empty": empty})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                final = await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, initial),
                )
                items = request_items(final["model_request"])
                assert items[0] == initial[0] and items[0] is not initial[0]
                assert isinstance(items[0], dict)
                content = items[0].get("content")
                assert isinstance(content, list)
                content[0].update(text="caller must remain unchanged")
                assert len(items) == (2 if empty else 3)

    asyncio.run(run())
    assert initial == original


def test_hook_cannot_replace_working_items_with_a_bare_string() -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"string_input": True})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                with pytest.raises(ValueError, match="items list"):
                    await complete_turn(agent, workspace_id=TEST_WORKSPACE_ID, input=[])

    asyncio.run(run())
    assert sent == []


@pytest.mark.parametrize(
    "settings, override, removed_key",
    [
        ({}, {"store": True}, None),
        ({}, {"extra_body": {"store": True}}, None),
        ({}, {"metadata": {"step": "one"}}, None),
        ({}, {"temperature": 0.37}, None),
        ({}, {"temperature": None}, None),
        ({}, {}, "max_output_tokens"),
        ({"metadata": None}, {}, "metadata"),
    ],
    ids=[
        "changed_policy",
        "extra_body",
        "added_metadata",
        "added_model_setting",
        "added_explicit_null",
        "removed_model_setting",
        "removed_explicit_null",
    ],
)
def test_request_hook_cannot_change_fixed_policy_before_sending_to_model(
    settings: ResponseCreateParamsBase,
    override: dict[str, object],
    removed_key: str | None,
) -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings={**MODEL_REQUEST, **settings},
                bundles=[
                    BundleConfig(
                        __name__,
                        {"request_override": override, "request_remove": removed_key},
                    )
                ],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                with pytest.raises(ValueError, match="policy"):
                    await complete_turn(agent, workspace_id=TEST_WORKSPACE_ID, input=[])

    asyncio.run(run())
    assert sent == []
