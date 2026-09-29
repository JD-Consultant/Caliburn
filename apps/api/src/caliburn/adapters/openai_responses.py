"""Direct SDK transport only; execution admission, persistence and retry belong to callers."""

from copy import deepcopy
from math import isfinite
from typing import Any

import httpx2
from openai import AsyncOpenAI, DefaultAsyncHttpxClient
from openai.types.responses import Response
from openai.types.responses.compacted_response import CompactedResponse
from openai.types.responses.function_tool_param import FunctionToolParam
from openai.types.responses.input_token_count_response import InputTokenCountResponse
from openai.types.shared.reasoning_effort import ReasoningEffort

from caliburn.adapters.response_serialization import NativeItems


class ResponseRequest:
    """Own a copied SDK payload so count and create see the same context, not live maps."""

    def __init__(
        self,
        *,
        model: str,
        instructions: str,
        input_items: NativeItems,
        tools: list[FunctionToolParam],
        reasoning_effort: ReasoningEffort,
        max_output_tokens: int,
    ) -> None:
        if not model.strip() or type(max_output_tokens) is not int or max_output_tokens < 1:
            raise ValueError("A model and positive output limit are required")
        self._max_output_tokens = max_output_tokens
        self._context: dict[str, Any] = deepcopy(
            {
                "model": model,
                "instructions": instructions,
                "input": input_items,
                "tools": tools,
                "reasoning": {"context": "all_turns", "effort": reasoning_effort},
                # Allow multiple returned calls; the App still executes them in output order.
                "parallel_tool_calls": True,
                "tool_choice": "auto",
                "truncation": "disabled",
            }
        )

    def count_payload(self) -> dict[str, Any]:
        return deepcopy(self._context)

    def create_payload(self) -> dict[str, Any]:
        return {
            **self.count_payload(),
            "max_output_tokens": self._max_output_tokens,
            "store": False,
            "background": False,
            "service_tier": "default",
            "include": ["reasoning.encrypted_content"],
        }


def create_responses_client(
    *, api_key: str, timeout_seconds: float, http_client: httpx2.AsyncClient | None = None
) -> AsyncOpenAI:
    """Caller owns this long-lived SDK client; construction does not make a request."""
    if not api_key.strip() or not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("Explicit credentials and a finite positive timeout are required")
    if http_client is not None and http_client.follow_redirects:
        raise ValueError("Direct requests cannot follow redirects")
    return AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.openai.com/v1",
        max_retries=0,
        timeout=timeout_seconds,
        http_client=http_client or DefaultAsyncHttpxClient(follow_redirects=False),
    )


async def create_response(client: AsyncOpenAI, request: ResponseRequest) -> Response:
    """Return the original SDK response; no routing, model fallback or business completion."""
    _require_direct_client(client)
    response = await client.responses.create(stream=False, **request.create_payload())
    if not isinstance(response, Response):
        raise TypeError("The non-streaming SDK call did not return a Response")
    return response


async def count_response_input(
    client: AsyncOpenAI, request: ResponseRequest
) -> InputTokenCountResponse:
    """A remote call requiring admission too; do not replace failure with a guessed count."""
    _require_direct_client(client)
    return await client.responses.input_tokens.count(**request.count_payload())


async def compact_context(
    client: AsyncOpenAI, *, model: str, input_items: NativeItems
) -> CompactedResponse:
    """Return full C without adopting it; the caller supplies the eligible complete window."""
    _require_direct_client(client)
    payload: dict[str, Any] = {"model": model, "input": deepcopy(input_items)}
    return await client.responses.compact(**payload)


def _require_direct_client(client: AsyncOpenAI) -> None:
    if str(client.base_url) != "https://api.openai.com/v1/" or client.max_retries != 0:
        raise ValueError("Use the direct client with SDK retries disabled")
