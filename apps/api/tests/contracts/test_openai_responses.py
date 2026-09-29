"""Real SDK HTTP mocks: request policy and call counts, not remote model acceptance."""

import json
from pathlib import Path

import httpx2
import pytest
from openai import APIStatusError, APITimeoutError, DefaultAsyncHttpxClient, InternalServerError

from caliburn.adapters import openai_responses
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    compact_context,
    count_response_input,
    create_response,
    create_responses_client,
)
from caliburn.adapters.response_serialization import snapshot_compaction, snapshot_response


def request_fixture() -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="合成指引",
        input_items=[{"role": "user", "content": "合成原話"}],
        tools=[],
        reasoning_effort="medium",
        max_output_tokens=1024,
    )


def test_saved_request_restores_exact_settings_without_sharing_mutable_context() -> None:
    original = request_fixture()
    saved = json.loads(json.dumps(original.create_payload()))
    restored = ResponseRequest.from_snapshot(saved)
    saved["input"].clear()
    saved["instructions"] = "later role instruction"
    assert restored.create_payload() == original.create_payload()
    assert restored.count_payload() == original.count_payload()


@pytest.mark.parametrize("field, value", [("stream", True), ("store", True)])
def test_saved_request_cannot_silently_change_the_direct_contract(field, value) -> None:
    saved = request_fixture().create_payload()
    saved[field] = value
    with pytest.raises(ValueError, match="direct SDK contract"):
        ResponseRequest.from_snapshot(saved)


@pytest.mark.asyncio
async def test_transient_failure_is_one_outbound_attempt_not_sdk_retries() -> None:
    attempts = 0

    def reject(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        return httpx2.Response(
            503,
            headers={"retry-after": "0", "x-should-retry": "true"},
            json={"error": {"message": "synthetic overload", "code": "server_is_overloaded"}},
        )

    async with create_responses_client(
        api_key="synthetic-only",
        timeout_seconds=5,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(reject)),
    ) as client:
        with pytest.raises(InternalServerError):
            await create_response(client, request_fixture())
    assert attempts == 1


@pytest.mark.asyncio
async def test_count_and_create_share_native_context_and_explicit_policy(monkeypatch) -> None:
    captured = []
    raw = json.loads(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(encoding="utf-8")
    )
    history = [{"role": "user", "content": "synthetic original"}, *raw["output"]]
    tools = [
        {
            "type": "function",
            "name": "read_synthetic",
            "strict": True,
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        }
    ]
    request = ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic role instruction",
        input_items=history,
        tools=tools,
        reasoning_effort="medium",
        max_output_tokens=1024,
    )
    expected = request.count_payload()
    history.clear()
    tools[0]["name"] = "do_not_change_prepared_request"
    discarded_projection = request.count_payload()
    discarded_projection["input"].clear()
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unapproved.invalid/v1")

    def respond(http_request: httpx2.Request) -> httpx2.Response:
        assert http_request.url.host == "api.openai.com"
        captured.append(json.loads(http_request.content))
        if http_request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 88}
            )
        return httpx2.Response(200, json=raw)

    async with create_responses_client(
        api_key="synthetic-only",
        timeout_seconds=5,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    ) as client:
        count = await count_response_input(client, request)
        response = await create_response(client, request)
    assert count.input_tokens == 88
    assert snapshot_response(response) == raw
    assert captured[0] == expected
    assert {key: captured[1][key] for key in expected} == expected
    assert captured[1] == {**request.create_payload(), "stream": False}
    assert captured[1]["store"] is False
    assert captured[1]["truncation"] == "disabled"
    assert captured[1]["reasoning"]["context"] == "all_turns"
    assert captured[1]["parallel_tool_calls"] is True
    assert not {"previous_response_id", "conversation", "context_management"} & captured[1].keys()
    assert "synthetic original" not in repr(request)


@pytest.mark.asyncio
async def test_compact_sends_complete_window_and_returns_original_without_adopting() -> None:
    captured = []
    window = [{"role": "user", "content": "synthetic previous history"}]
    raw = {
        "id": "cmp_test",
        "object": "response.compaction",
        "created_at": 1,
        "usage": {
            "input_tokens": 12,
            "output_tokens": 7,
            "total_tokens": 19,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
        "output": [
            {"type": "compaction", "id": "ci_test", "encrypted_content": "synthetic opaque"},
            window[0],
        ],
    }

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/responses/compact"
        captured.append(json.loads(request.content))
        return httpx2.Response(200, json=raw)

    async with create_responses_client(
        api_key="synthetic-only",
        timeout_seconds=5,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    ) as client:
        result = await compact_context(client, model="gpt-6-luna", input_items=window)
    assert captured == [{"model": "gpt-6-luna", "input": window}]
    assert snapshot_compaction(result) == raw
    assert window == [{"role": "user", "content": "synthetic previous history"}]


@pytest.mark.asyncio
async def test_timeout_propagates_once_and_adapter_does_not_requery_unknown_result() -> None:
    calls = 0

    def timeout(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        raise httpx2.ReadTimeout("synthetic timeout", request=request)

    async with create_responses_client(
        api_key="synthetic-only",
        timeout_seconds=5,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(timeout)),
    ) as client:
        with pytest.raises(APITimeoutError):
            await create_response(client, request_fixture())
    assert calls == 1


@pytest.mark.asyncio
async def test_changed_client_policy_is_rejected_before_any_outbound_call() -> None:
    def reject_outbound(request: httpx2.Request) -> httpx2.Response:
        pytest.fail("Invalid transport policy must not send")

    async with create_responses_client(
        api_key="synthetic-only",
        timeout_seconds=5,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(reject_outbound)),
    ) as client:
        client.max_retries = 2
        with pytest.raises(ValueError, match="retries disabled"):
            await create_response(client, request_fixture())
        client.max_retries = 0
        client.base_url = "https://unapproved.invalid/v1"
        with pytest.raises(ValueError, match="direct client"):
            await count_response_input(client, request_fixture())


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_client_cannot_have_unbounded_or_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="finite positive timeout"):
        create_responses_client(api_key="synthetic-only", timeout_seconds=timeout)


@pytest.mark.asyncio
async def test_injected_redirecting_client_is_rejected_before_dispatch() -> None:
    async with httpx2.AsyncClient(follow_redirects=True) as transport:
        with pytest.raises(ValueError, match="redirect"):
            async with create_responses_client(
                api_key="synthetic-only", timeout_seconds=5, http_client=transport
            ):
                pass


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [307, 308])
async def test_default_client_does_not_forward_post_body_to_redirect(monkeypatch, status) -> None:
    destinations = []

    def redirect(request: httpx2.Request) -> httpx2.Response:
        destinations.append(request.url.host)
        return httpx2.Response(status, headers={"location": "https://unapproved.invalid/target"})

    def default_transport(**options):
        return DefaultAsyncHttpxClient(transport=httpx2.MockTransport(redirect), **options)

    monkeypatch.setattr(openai_responses, "DefaultAsyncHttpxClient", default_transport)
    async with create_responses_client(api_key="synthetic-only", timeout_seconds=5) as client:
        with pytest.raises(APIStatusError):
            await create_response(client, request_fixture())
        with pytest.raises(APIStatusError):
            await count_response_input(client, request_fixture())
        with pytest.raises(APIStatusError):
            await compact_context(client, model="gpt-6-luna", input_items=[])
    assert destinations == ["api.openai.com"] * 3
