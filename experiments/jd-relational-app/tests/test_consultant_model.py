"""Formal consultant Responses binding; all HTTP is synthetic."""

import asyncio
from contextlib import contextmanager
import json

import httpx
import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai.types.responses import Response

from jd_relational.consultant_model import (
    CONSULTANT_MODEL, MAX_OUTPUT_TOKENS, OPENROUTER_HEADERS,
    OPENROUTER_PROVIDER,
    ConsultantModelError, create_consultant_model,
)
from jd_relational.openai_responses import accepted
from support.openai_replies import reply, refused, truncated


KEY = "synthetic-openrouter-not-a-key"


def gpt6_body(payload):
    payload["model"] = CONSULTANT_MODEL
    payload["reasoning"] = {"effort": "high"}
    return Response.model_validate(payload).model_dump(mode="json", exclude_none=True)


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


def test_the_role_profile_and_route_are_the_verified_responses_binding():
    with answering(gpt6_body(reply("profile"))) as (model, requests):
        assert isinstance(model, ChatOpenAI)
        assert model.model_name == CONSULTANT_MODEL == "openai/gpt-6-luna"
        assert model.model_kwargs["max_output_tokens"] == MAX_OUTPUT_TOKENS == 8192
        assert model.reasoning == {"effort": "high"}
        assert model.model_kwargs["parallel_tool_calls"] is False
        assert model.max_retries == 0
        assert model.request_timeout == 300.0
        assert model.store is False
        assert model.include == ["reasoning.encrypted_content"]
        assert model.extra_body["provider"] == {
            "only": [OPENROUTER_PROVIDER], "order": [OPENROUTER_PROVIDER],
            "allow_fallbacks": False, "require_parameters": False,
        }
        assert requests == []
        assert KEY not in repr(model.metadata)


def test_a_completed_reply_and_request_route_are_preserved():
    with answering(gpt6_body(reply("a1", text="完整合成回覆"))) as (model, requests):
        message = model.invoke("合成輸入")
    assert accepted(message)
    assert message.text == "完整合成回覆"
    assert message.response_metadata["model_name"] == CONSULTANT_MODEL
    assert len(requests) == 1 and requests[0].url.path == "/api/v1/responses"
    assert requests[0].headers["X-OpenRouter-Metadata"] == "enabled"
    # LangChain's generic model_provider=OpenAI is not actual route evidence.
    assert "provider" not in message.response_metadata


def test_one_tool_call_arrives_as_one_completed_tool_call():
    with answering(gpt6_body(reply("a2", "jd_read", {"view": "current"}))) as (model, _):
        message = model.invoke("合成輸入")
    assert accepted(message)
    assert [call["name"] for call in message.tool_calls] == ["jd_read"]
    assert message.tool_calls[0]["args"] == {"view": "current"}


def test_the_wire_carries_the_pinned_route_and_no_parallel_calls():
    with answering(gpt6_body(reply("a3"))) as (model, requests):
        model.invoke("合成輸入")
    payload = json.loads(requests[0].content)
    assert payload["model"] == CONSULTANT_MODEL
    assert payload["provider"] == {
        "only": ["openai"], "order": ["openai"],
        "allow_fallbacks": False, "require_parameters": False,
    }
    assert payload["parallel_tool_calls"] is False
    assert payload["store"] is False
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["include"] == ["reasoning.encrypted_content"]
    assert payload["max_output_tokens"] == MAX_OUTPUT_TOKENS


def test_stable_system_guidance_is_not_mutated_or_marked_as_a_chat_cache_block():
    system = SystemMessage(content="固定的顧問方法與行為規則")
    original = system.model_copy(deep=True)
    with answering(gpt6_body(reply("cache-prefix"))) as (model, requests):
        model.invoke([system, HumanMessage(content="本輪員工原話")])
    payload = json.loads(requests[0].content)
    assert payload["input"][0]["role"] == "system"
    assert payload["input"][0]["content"] == "固定的顧問方法與行為規則"
    assert "cache_control" not in json.dumps(payload, ensure_ascii=False)
    assert system == original


@pytest.mark.parametrize("body", [truncated("a4"), refused("a5")])
def test_an_incomplete_or_refused_reply_is_not_an_answer(body):
    with answering(gpt6_body(body)) as (model, _):
        message = model.invoke("合成輸入")
    assert not accepted(message)


@pytest.mark.parametrize("options", [
    {"model": ""}, {"model": "openai/gpt-5.6-luna"}, {"api_key": ""},
    {"max_output_tokens": 0}, {"max_output_tokens": -1},
    {"reasoning_effort": "none"}, {"request_timeout": 0},
    {"request_timeout": float("inf")},
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
