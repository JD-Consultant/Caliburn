"""普通方法使用真 SDK 的離線 HTTP 邊界，完整保留壓縮窗口。"""

import asyncio
from copy import deepcopy
from typing import cast

import httpx2
import pytest
from openai.types.responses import CompactedResponse
from openai.types.responses.response_create_params import ResponseCreateParamsBase
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.bundles.context.request_compaction import compact_request
from tests.unit.bundles.context.support import compacted_payload
from tests.unit.modules.agent.offline_openai import (
    call,
    offline_client,
    reasoning,
    request_body,
)


def request_with_tools() -> ResponseCreateParamsBase:
    return {
        "model": "offline-model",
        "input": cast(
            ResponseInputParam,
            [
                {"role": "user", "content": "原始工作內容"},
                reasoning(),
                call(),
                {
                    "type": "function_call_output",
                    "call_id": "call_alpha",
                    "output": "結果",
                },
            ],
        ),
        "instructions": "以原話為依據。",
        "tools": [
            {"type": "function", "name": "read_alpha", "parameters": {}, "strict": True}
        ],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
        "reasoning": {"effort": "low", "context": "all_turns"},
        "text": {"format": {"type": "text"}},
        "truncation": "disabled",
        "service_tier": "default",
        "store": False,
        "max_output_tokens": 100,
    }


@pytest.mark.parametrize("input_tokens", [127999, 128000])
def test_threshold_counts_complete_request_and_preserves_native_window(
    input_tokens: int,
) -> None:
    sent: list[tuple[str, dict[str, object]]] = []
    request = request_with_tools()
    original = deepcopy(request)
    payload = compacted_payload()

    def respond(http_request: httpx2.Request) -> httpx2.Response:
        sent.append((http_request.url.path, request_body(http_request)))
        if http_request.url.path.endswith("input_tokens"):
            return httpx2.Response(
                200,
                json={"object": "response.input_tokens", "input_tokens": input_tokens},
            )
        return httpx2.Response(200, json=payload)

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            response = await compact_request(client, request, threshold_tokens=128000)
        if input_tokens < 128000:
            assert response is None
        else:
            assert isinstance(response, CompactedResponse)
            assert (
                response.model_dump(mode="json", exclude_unset=True, warnings=False)
                == payload
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert request == original
    assert sent[0] == (
        "/v1/responses/input_tokens",
        {
            key: value
            for key, value in original.items()
            if key not in {"service_tier", "store", "max_output_tokens"}
        },
    )
    if input_tokens < 128000:
        assert len(sent) == 1
    else:
        assert sent[1] == (
            "/v1/responses/compact",
            {
                key: original[key]
                for key in ("model", "input", "instructions", "service_tier")
            },
        )


@pytest.mark.parametrize("failure", ["count", "compact", "empty_output"])
def test_failure_does_not_modify_or_implicitly_retry_the_working_request(
    failure: str,
) -> None:
    request = request_with_tools()
    original = deepcopy(request)
    paths: list[str] = []

    def respond(http_request: httpx2.Request) -> httpx2.Response:
        paths.append(http_request.url.path)
        counting = http_request.url.path.endswith("input_tokens")
        if failure == ("count" if counting else "compact"):
            return httpx2.Response(
                500,
                json={
                    "error": {
                        "message": "synthetic rejection",
                        "type": "invalid_request_error",
                    }
                },
            )
        if counting:
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 128000}
            )
        return httpx2.Response(200, json={**compacted_payload(), "output": []})

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(
                ValueError if failure == "empty_output" else RuntimeError
            ):
                await compact_request(client, request, threshold_tokens=128000)

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert request == original
    assert len(paths) == (1 if failure == "count" else 2)
