"""Shared OpenRouter transport and response evidence for this App's LLM roles.

Role prompts, graph budgets and business behaviour remain with each role.  This
module owns only the common provider boundary: caller-owned clients, the pinned
OpenAI route, no provider fallback, and terminal/route evidence which the stock
adapter currently drops.
"""

from __future__ import annotations

import math
from typing import Any

from langchain_core.messages import AIMessage
from langchain_openrouter import ChatOpenRouter


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_PROVIDER = "OpenAI"
OPENROUTER_HEADERS = {"X-OpenRouter-Metadata": "enabled"}
REQUEST_TIMEOUT_SECONDS = 90.0


class OpenRouterModelError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _metadata_enabled(client) -> bool:
    try:
        return client.headers.get("X-OpenRouter-Metadata", "").casefold() == "enabled"
    except (AttributeError, TypeError):
        return False


def _payload(response: Any) -> dict[str, Any]:
    return response if isinstance(response, dict) else response.model_dump(by_alias=True)


def _selected_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("openrouter_metadata")
    endpoints = metadata.get("endpoints") if isinstance(metadata, dict) else None
    available = endpoints.get("available") if isinstance(endpoints, dict) else None
    if not isinstance(available, list):
        return {}
    return next((item for item in available
                 if isinstance(item, dict) and item.get("selected") is True), {})


class ReceiptChatOpenRouter(ChatOpenRouter):
    """Keep route and terminal facts discarded by the stock 0.2.7 adapter."""

    def _create_chat_result(self, response: Any):
        payload = _payload(response)
        result = super()._create_chat_result(response)
        selected = _selected_endpoint(payload)
        provider = payload.get("provider") or selected.get("provider")
        actual_model = selected.get("model") or payload.get("model")
        choices = payload.get("choices") if isinstance(payload.get("choices"), list) else ()
        for generation, choice in zip(result.generations, choices, strict=False):
            message = generation.message
            if not isinstance(message, AIMessage) or not isinstance(choice, dict):
                continue
            finish_reason = choice.get("finish_reason")
            message.response_metadata["finish_reason"] = finish_reason
            if finish_reason in {"stop", "tool_calls"}:
                message.response_metadata["status"] = "completed"
            elif finish_reason is not None:
                message.response_metadata["status"] = "incomplete"
            raw_message = choice.get("message")
            refusal = raw_message.get("refusal") if isinstance(raw_message, dict) else None
            if refusal:
                message.additional_kwargs["refusal"] = refusal
            if provider is not None:
                message.response_metadata["provider"] = provider
            if actual_model is not None:
                message.response_metadata["model_name"] = actual_model
        return result


def create_openrouter_model(
    *,
    component: str,
    model: str,
    api_key: str,
    http_client,
    async_http_client,
    base_url: str = OPENROUTER_BASE_URL,
    request_timeout: float = REQUEST_TIMEOUT_SECONDS,
    reasoning_effort: str,
    max_output_tokens: int,
    max_retries: int = 0,
) -> ReceiptChatOpenRouter:
    """Bind one role to explicit transports and one non-fallback provider route."""
    if (any(type(value) is not str or not value.strip() or "\0" in value
            for value in (component, model, api_key, base_url, reasoning_effort))
            or type(max_output_tokens) is not int or max_output_tokens <= 0
            or type(max_retries) is not int or not 0 <= max_retries <= 10
            or type(request_timeout) not in (int, float)
            or not math.isfinite(request_timeout) or request_timeout <= 0
            or not _metadata_enabled(http_client)
            or not _metadata_enabled(async_http_client)):
        raise OpenRouterModelError("invalid_model_configuration")
    import openrouter

    timeout_ms = int(request_timeout * 1000)
    client_options = {
        "api_key": api_key,
        "server_url": base_url,
        "client": http_client,
        "async_client": async_http_client,
        "timeout_ms": timeout_ms,
    }
    if max_retries:
        from openrouter.utils import BackoffStrategy, RetryConfig
        client_options["retry_config"] = RetryConfig(
            strategy="backoff",
            backoff=BackoffStrategy(initial_interval=500, max_interval=60000,
                                    exponent=1.5, max_elapsed_time=max_retries * 150_000),
            retry_connection_errors=True,
        )
    else:
        client_options["retry_config"] = None
    sdk_client = openrouter.OpenRouter(**client_options)
    return ReceiptChatOpenRouter(
        client=sdk_client,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout_ms,
        max_retries=max_retries,
        default_headers=OPENROUTER_HEADERS,
        max_tokens=max_output_tokens,
        reasoning={"effort": reasoning_effort, "exclude": True},
        openrouter_provider={
            "only": [OPENROUTER_PROVIDER],
            "order": [OPENROUTER_PROVIDER],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
        model_kwargs={"parallel_tool_calls": False},
        metadata={"caliburn_component": component, "requested_model": model},
        tags=[f"caliburn-{component}"],
        stream_usage=True,
    )
