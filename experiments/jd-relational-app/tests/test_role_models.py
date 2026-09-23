"""One OpenRouter/Luna factory for the App's A, B1 and B2 roles."""

import asyncio
from contextlib import contextmanager
import json

import httpx
import pytest
from openai.types.responses import Response

from jd_relational.openrouter_model import OPENROUTER_HEADERS, OpenRouterModelError
from jd_relational.role_models import create_role_models
from support.openai_replies import reply


KEY = "synthetic-openrouter-not-a-key"


def gpt6_reply(identity):
    payload = reply(identity)
    payload["model"] = "openai/gpt-6-luna"
    payload["reasoning"] = {"effort": "high"}
    return Response.model_validate(payload).model_dump(mode="json", exclude_none=True)


@contextmanager
def role_transport(*bodies):
    requests = []

    def receive(request):
        requests.append(request)
        return httpx.Response(200, json=bodies[len(requests) - 1], request=request)

    sync_client = httpx.Client(
        transport=httpx.MockTransport(receive),
        trust_env=False,
        headers=OPENROUTER_HEADERS,
    )
    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(receive),
        trust_env=False,
        headers=OPENROUTER_HEADERS,
    )
    try:
        yield sync_client, async_client, requests
    finally:
        sync_client.close()
        asyncio.run(async_client.aclose())


def test_factory_builds_all_roles_without_sending_a_request():
    with role_transport() as (sync_client, async_client, requests):
        roles = create_role_models(
            api_key=KEY,
            http_client=sync_client,
            async_http_client=async_client,
        )

        assert requests == []
        assert roles.consultant is not roles.case
        assert roles.case is not roles.understanding


def test_formal_roles_use_stateless_gpt6_responses_profile():
    with role_transport() as (sync_client, async_client, requests):
        roles = create_role_models(
            api_key=KEY, http_client=sync_client,
            async_http_client=async_client,
        )
        for role, limit in zip(
            (roles.consultant, roles.case, roles.understanding),
            (8192, 32768, 32768), strict=True,
        ):
            assert role.model_name == "openai/gpt-6-luna"
            assert role.use_responses_api is True
            assert role.output_version == "responses/v1"
            assert role.store is False
            assert role.reasoning == {"effort": "high"}
            assert role.include == ["reasoning.encrypted_content"]
            assert role.model_kwargs["max_output_tokens"] == limit
            assert role.max_retries == 0
            assert role.extra_body["provider"] == {
                "only": ["openai"], "order": ["openai"],
                "allow_fallbacks": False, "require_parameters": False,
            }
        assert requests == []


def test_every_role_uses_the_verified_luna_route_without_fallback_or_hidden_retry():
    bodies = (gpt6_reply("a-role"), gpt6_reply("b1-role"), gpt6_reply("b2-role"))
    with role_transport(*bodies) as (sync_client, async_client, requests):
        roles = create_role_models(
            api_key=KEY,
            http_client=sync_client,
            async_http_client=async_client,
        )
        for model in (roles.consultant, roles.case, roles.understanding):
            model.invoke("合成輸入")

    assert len(requests) == 3
    for request, expected_max_tokens in zip(requests, (8192, 32768, 32768), strict=True):
        payload = json.loads(request.content)
        assert request.url.path == "/api/v1/responses"
        assert payload["model"] == "openai/gpt-6-luna"
        assert payload["provider"] == {
            "only": ["openai"],
            "order": ["openai"],
            "allow_fallbacks": False,
            "require_parameters": False,
        }
        assert payload["reasoning"] == {"effort": "high"}
        assert payload["max_output_tokens"] == expected_max_tokens
        assert payload["parallel_tool_calls"] is False
        assert payload["store"] is False
        assert payload["include"] == ["reasoning.encrypted_content"]

    assert [model.max_retries for model in (
        roles.consultant, roles.case, roles.understanding,
    )] == [0, 0, 0]
    assert [model.request_timeout for model in (
        roles.consultant, roles.case, roles.understanding,
    )] == [300, 300, 300]


@pytest.mark.parametrize("api_key", ["", "   "])
def test_factory_rejects_a_missing_key_before_any_request(api_key):
    with role_transport() as (sync_client, async_client, requests):
        with pytest.raises(OpenRouterModelError) as error:
            create_role_models(
                api_key=api_key,
                http_client=sync_client,
                async_http_client=async_client,
            )

    assert error.value.code == "invalid_model_configuration"
    assert requests == []
