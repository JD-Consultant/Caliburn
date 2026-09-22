"""One OpenRouter/Luna factory for the App's A, B1 and B2 roles."""

import asyncio
from contextlib import contextmanager
import json

import httpx
import pytest

from jd_relational.openrouter_model import OPENROUTER_HEADERS, OpenRouterModelError
from jd_relational.role_models import create_role_models
from support.openrouter_replies import reply


KEY = "synthetic-openrouter-not-a-key"


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


def test_every_role_uses_the_verified_luna_route_without_fallback_or_hidden_retry():
    bodies = (reply("a-role"), reply("b1-role"), reply("b2-role"))
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
        assert payload["model"] == "openai/gpt-5.6-luna"
        assert payload["provider"] == {
            "only": ["openai"],
            "order": ["openai"],
            "allow_fallbacks": False,
            "require_parameters": False,
        }
        assert payload["reasoning"] == {"effort": "high"}
        assert payload["max_tokens"] == expected_max_tokens
        assert payload["parallel_tool_calls"] is False

    assert [model.max_retries for model in (
        roles.consultant, roles.case, roles.understanding,
    )] == [0, 0, 0]
    assert [model.request_timeout for model in (
        roles.consultant, roles.case, roles.understanding,
    )] == [90_000, 300_000, 300_000]


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
