"""Zero-paid contract for the installed Responses client, not provider support."""

import json

import httpx
import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ProviderToolSearchMiddleware
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses import Response

from jd_relational.openrouter_model import (
    OPENROUTER_BASE_URL, OPENROUTER_HEADERS, OpenRouterModelError,
    create_responses_openrouter_model,
)
from support.openai_replies import body, refused, reply, truncated


def _reply(output, identity):
    candidate = body(output, identity=identity)
    candidate["model"] = "openai/gpt-6-luna"
    candidate["reasoning"] = {"effort": "high"}
    return Response.model_validate(candidate).model_dump(mode="json", exclude_none=True)


def test_locked_client_can_send_and_resume_gpt6_reasoning_tool_loop():
    requests = []
    effects = []
    replies = [
        _reply([
            {"type": "reasoning", "id": "rs_1", "summary": [],
             "encrypted_content": "opaque-test-reasoning"},
            {"type": "function_call", "id": "fc_1", "call_id": "call_1",
             "name": "read_case", "arguments": '{"case_id":"case-1"}',
             "status": "completed"},
        ], "first"),
        _reply([
            {"type": "message", "id": "msg_2", "role": "assistant",
             "status": "completed", "phase": "final_answer",
             "content": [{"type": "output_text", "text": "已讀取案例。",
                          "annotations": []}]},
        ], "second"),
    ]

    @tool
    def read_case(case_id: str) -> str:
        """Read one synthetic case."""
        effects.append(case_id)
        return "合成案例內容"

    def receive(request):
        requests.append(request)
        return httpx.Response(200, json=replies[len(requests) - 1], request=request)

    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "gpt6-offline"}}
    with httpx.Client(
        transport=httpx.MockTransport(receive), trust_env=False,
        headers=OPENROUTER_HEADERS,
    ) as client:
        model = ChatOpenAI(
            model="openai/gpt-6-luna", api_key="synthetic-not-a-key",
            base_url=OPENROUTER_BASE_URL, http_client=client,
            timeout=90, max_retries=0, use_responses_api=True,
            output_version="responses/v1", store=False,
            reasoning={"effort": "high"},
            include=["reasoning.encrypted_content"],
            max_tokens=8192,
            model_kwargs={"parallel_tool_calls": False},
            extra_body={"provider": {"only": ["openai"], "order": ["openai"],
                                     "allow_fallbacks": False,
                                     "require_parameters": False}},
        )
        agent = create_agent(model=model, tools=[read_case], checkpointer=saver)
        result = agent.invoke(
            {"messages": [HumanMessage("請讀案例", id="employee-1")]}, config,
            durability="sync",
        )
        canonical = agent.get_state(config).values["messages"]

    assert effects == ["case-1"]
    assert len(requests) == 2
    assert all(request.url.path == "/api/v1/responses" for request in requests)
    payloads = [json.loads(request.content) for request in requests]
    assert all(payload["model"] == "openai/gpt-6-luna" for payload in payloads)
    assert all(payload["reasoning"] == {"effort": "high"} for payload in payloads)
    assert all(payload["store"] is False for payload in payloads)
    assert all(payload["include"] == ["reasoning.encrypted_content"] for payload in payloads)
    assert all(payload["parallel_tool_calls"] is False for payload in payloads)
    assert all(payload["max_output_tokens"] == 8192 for payload in payloads)
    assert all(payload["provider"] == {
        "only": ["openai"], "order": ["openai"], "allow_fallbacks": False,
        "require_parameters": False,
    } for payload in payloads)
    assert [item["type"] for item in payloads[1]["input"] if isinstance(item, dict)] == [
        "message", "reasoning", "function_call", "function_call_output",
    ]
    assert payloads[1]["input"][1]["encrypted_content"] == "opaque-test-reasoning"
    assert payloads[1]["input"][2]["call_id"] == "call_1"
    assert payloads[1]["input"][3]["call_id"] == "call_1"
    assert any(getattr(message, "response_metadata", {}).get("id") == "resp_first"
               for message in canonical)
    assert result["messages"][-1].text == "已讀取案例。"


def test_locked_provider_search_defers_a_function_on_actual_responses_wire():
    """Candidate-only boundary: no App switch and no provider-support claim."""
    requests = []

    @tool
    def read_case(case_id: str) -> str:
        """Read a synthetic case by its identifier."""
        return "合成案例內容"

    def receive(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=reply("deferred-probe"), request=request)

    with httpx.Client(
        transport=httpx.MockTransport(receive), trust_env=False,
        headers=OPENROUTER_HEADERS,
    ) as client:
        async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(receive), trust_env=False,
            headers=OPENROUTER_HEADERS,
        )
        try:
            model = create_responses_openrouter_model(
                component="consultant", model="openai/gpt-6-luna",
                api_key="synthetic-not-a-key", http_client=client,
                async_http_client=async_client, reasoning_effort="high",
                max_output_tokens=8192,
            )
            agent = create_agent(
                model=model, tools=[read_case],
                middleware=[ProviderToolSearchMiddleware(searchable_tools=["read_case"])],
            )
            agent.invoke({"messages": [HumanMessage("合成輸入")]})
        finally:
            import asyncio
            asyncio.run(async_client.aclose())

    assert len(requests) == 1
    tools = requests[0]["tools"]
    assert any(item["type"] == "tool_search" for item in tools)
    deferred = next(item for item in tools if item.get("name") == "read_case")
    assert deferred["defer_loading"] is True
    assert requests[0]["provider"]["only"] == ["openai"]


def test_role_factory_binds_the_verified_responses_profile_without_network():
    from jd_relational.openrouter_model import create_responses_openrouter_model

    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("unexpected HTTP")),
        trust_env=False, headers=OPENROUTER_HEADERS,
    ) as sync_client:
        async_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: pytest.fail("unexpected HTTP")),
            trust_env=False, headers=OPENROUTER_HEADERS,
        )
        try:
            model = create_responses_openrouter_model(
                component="consultant", model="openai/gpt-6-luna",
                api_key="synthetic-not-a-key", http_client=sync_client,
                async_http_client=async_client, reasoning_effort="high",
                max_output_tokens=8192,
            )
            assert isinstance(model, ChatOpenAI)
            assert model.use_responses_api is True
            assert model.output_version == "responses/v1"
            assert model.store is False
            assert model.include == ["reasoning.encrypted_content"]
            assert model.max_retries == 0
            assert model.model_kwargs["max_output_tokens"] == 8192
            assert model.metadata["caliburn_component"] == "consultant"
            assert model.model_kwargs["parallel_tool_calls"] is False
            assert model.extra_body["provider"]["allow_fallbacks"] is False
            with pytest.raises(OpenRouterModelError):
                create_responses_openrouter_model(
                    component="consultant", model="openai/gpt-6-luna",
                    api_key="", http_client=sync_client,
                    async_http_client=async_client, reasoning_effort="high",
                    max_output_tokens=8192,
                )
        finally:
            import asyncio
            asyncio.run(async_client.aclose())


@pytest.mark.parametrize("fixture,expected_status", [
    (truncated, "incomplete"), (refused, "completed"),
])
def test_responses_terminal_or_refusal_is_not_accepted_as_a_normal_answer(
    fixture, expected_status,
):
    from jd_relational.openai_responses import accepted
    from jd_relational.openrouter_model import create_responses_openrouter_model

    def receive(request):
        answer = fixture("terminal-check")
        answer["model"] = "openai/gpt-6-luna"
        return httpx.Response(200, json=answer, request=request)

    with httpx.Client(transport=httpx.MockTransport(receive), trust_env=False,
                      headers=OPENROUTER_HEADERS) as client:
        async_client = httpx.AsyncClient(transport=httpx.MockTransport(receive),
                                         trust_env=False, headers=OPENROUTER_HEADERS)
        try:
            model = create_responses_openrouter_model(
                component="consultant", model="openai/gpt-6-luna",
                api_key="synthetic-not-a-key", http_client=client,
                async_http_client=async_client, reasoning_effort="high",
                max_output_tokens=8192,
            )
            message = model.invoke("合成輸入")
            assert message.response_metadata["status"] == expected_status
            assert accepted(message) is False
        finally:
            import asyncio
            asyncio.run(async_client.aclose())
