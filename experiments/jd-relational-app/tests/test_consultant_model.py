"""The completed consultant's OpenRouter model binding; zero provider calls."""

import asyncio
from contextlib import contextmanager
import json

import httpx
import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from jd_relational.consultant_model import (
    CONSULTANT_MODEL, MAX_OUTPUT_TOKENS, OPENROUTER_HEADERS, OPENROUTER_PROVIDER,
    REQUEST_TIMEOUT_SECONDS, ConsultantModelError, ReceiptChatOpenRouter,
    create_consultant_model,
)
from jd_relational.openai_responses import accepted
from support.openrouter_replies import refused, reply, truncated


KEY = "synthetic-openrouter-not-a-key"


@contextmanager
def answering(*bodies):
    requests = []

    def receive(request):
        requests.append(request)
        return httpx.Response(200, json=bodies[len(requests) - 1], request=request)

    sync_client = httpx.Client(transport=httpx.MockTransport(receive), trust_env=False,
                               headers=OPENROUTER_HEADERS)
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(receive), trust_env=False,
                                     headers=OPENROUTER_HEADERS)
    try:
        yield create_consultant_model(
            api_key=KEY, http_client=sync_client, async_http_client=async_client,
        ), requests
    finally:
        sync_client.close()
        asyncio.run(async_client.aclose())


def test_the_role_profile_and_route_are_the_verified_openrouter_binding():
    with answering(reply("a1")) as (model, _):
        assert isinstance(model, ReceiptChatOpenRouter)
        assert model.model_name == CONSULTANT_MODEL == "openai/gpt-5.6-luna"
        assert model.max_tokens == MAX_OUTPUT_TOKENS == 8192
        assert model.reasoning == {"effort": "high", "exclude": True}
        assert model.model_kwargs["parallel_tool_calls"] is False
        assert model.max_retries == 0
        assert model.request_timeout == int(REQUEST_TIMEOUT_SECONDS * 1000)
        assert model.openrouter_provider == {
            "only": [OPENROUTER_PROVIDER], "order": [OPENROUTER_PROVIDER],
            "allow_fallbacks": False, "require_parameters": False,
        }
        assert KEY not in repr(model.metadata)


def test_a_completed_reply_and_actual_route_are_preserved():
    with answering(reply("a1", text="完整合成回覆")) as (model, requests):
        message = model.invoke("合成輸入")
    assert accepted(message)
    assert message.content == "完整合成回覆"
    assert message.response_metadata["provider"] == "OpenAI"
    assert message.response_metadata["model_name"] == CONSULTANT_MODEL
    assert len(requests) == 1 and requests[0].url.host == "openrouter.ai"
    assert requests[0].headers["X-OpenRouter-Metadata"] == "enabled"


def test_one_tool_call_arrives_as_one_completed_tool_call():
    with answering(reply("a2", "jd_read", {"view": "current"})) as (model, _):
        message = model.invoke("合成輸入")
    assert accepted(message)
    assert [call["name"] for call in message.tool_calls] == ["jd_read"]
    assert message.tool_calls[0]["args"] == {"view": "current"}


def test_the_wire_carries_the_pinned_route_and_no_parallel_calls():
    with answering(reply("a3")) as (model, requests):
        model.invoke("合成輸入")
    payload = json.loads(requests[0].content)
    assert payload["model"] == CONSULTANT_MODEL
    assert payload["provider"] == {
        "only": ["openai"], "order": ["openai"],
        "allow_fallbacks": False, "require_parameters": False,
    }
    assert payload["parallel_tool_calls"] is False


def test_the_wire_marks_only_the_stable_system_prefix_without_mutating_messages():
    system = SystemMessage(content=[
        {"type": "text", "text": "固定的顧問方法與行為規則"},
        {"type": "text", "text": "每次請求會改變的 App context"},
    ])
    original = system.model_copy(deep=True)

    with answering(reply("cache-prefix")) as (model, requests):
        model.invoke([system, HumanMessage(content="本輪員工原話")])

    payload = json.loads(requests[0].content)
    blocks = payload["messages"][0]["content"]
    assert blocks[0] == {
        "type": "text",
        "text": "固定的顧問方法與行為規則",
        "cache_control": {"type": "ephemeral"},
    }
    assert blocks[1] == {"type": "text", "text": "每次請求會改變的 App context"}
    assert payload["messages"][1] == {"role": "user", "content": "本輪員工原話"}
    assert system == original


@pytest.mark.parametrize("body", [truncated("a4"), refused("a5")])
def test_an_incomplete_or_refused_reply_is_not_an_answer(body):
    with answering(body) as (model, _):
        message = model.invoke("合成輸入")
    assert not accepted(message)


@pytest.mark.parametrize("options", [
    {"model": ""}, {"model": "   "}, {"api_key": ""}, {"model": "with\0null"},
    {"max_output_tokens": 0}, {"max_output_tokens": -1}, {"reasoning_effort": " "},
    {"request_timeout": 0}, {"request_timeout": float("inf")},
])
def test_an_unusable_configuration_is_refused_before_binding(options):
    sync_client = httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("No request")))
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: pytest.fail("No request")))
    try:
        arguments = {"api_key": KEY, "http_client": sync_client,
                     "async_http_client": async_client, **options}
        with pytest.raises(ConsultantModelError) as error:
            create_consultant_model(**arguments)
    finally:
        sync_client.close()
        asyncio.run(async_client.aclose())
    assert error.value.code == "invalid_model_configuration"
