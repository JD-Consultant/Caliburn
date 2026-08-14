"""Narrow LangChain OpenRouter binding for the versioned consultant profile."""

from __future__ import annotations

from typing import Any

from langchain_openrouter import ChatOpenRouter

from app.consultant.model_runtime import ResolvedExecution


def _selected_router_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("openrouter_metadata")
    if not isinstance(metadata, dict):
        return {}
    endpoints = metadata.get("endpoints")
    available = endpoints.get("available") if isinstance(endpoints, dict) else None
    if not isinstance(available, list):
        return {}
    return next(
        (
            endpoint
            for endpoint in available
            if isinstance(endpoint, dict) and endpoint.get("selected") is True
        ),
        {},
    )


class ReceiptChatOpenRouter(ChatOpenRouter):
    """Keep route facts that langchain-openrouter 0.2.7 otherwise discards."""

    def _create_chat_result(self, response: Any):
        payload = (
            response
            if isinstance(response, dict)
            else response.model_dump(by_alias=True)
        )
        result = super()._create_chat_result(response)
        selected = _selected_router_endpoint(payload)
        provider = payload.get("provider") or selected.get("provider")
        model = selected.get("model") or payload.get("model")
        for generation in result.generations:
            message = generation.message
            if provider is not None:
                message.response_metadata["provider"] = provider
            if model is not None:
                message.response_metadata["model_name"] = model
        return result


def build_openrouter_chat_model(
    execution: ResolvedExecution,
    *,
    api_key: str,
    base_url: str,
) -> ReceiptChatOpenRouter:
    if not api_key.strip():
        raise ValueError("OpenRouter API key is required")
    import httpx
    import openrouter

    parameters = execution.effective_parameters
    timeout_ms = int(execution.timeout_seconds * 1_000)
    router_headers = {"X-OpenRouter-Metadata": "enabled"}
    sdk_client = openrouter.OpenRouter(
        api_key=api_key,
        server_url=base_url,
        client=httpx.Client(headers=router_headers, follow_redirects=True),
        async_client=httpx.AsyncClient(
            headers=router_headers,
            follow_redirects=True,
        ),
        timeout_ms=timeout_ms,
        retry_config=None,
    )
    return ReceiptChatOpenRouter(
        client=sdk_client,
        model=execution.requested_model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout_ms,
        max_retries=0,
        default_headers=router_headers,
        temperature=parameters.temperature,
        top_p=parameters.top_p,
        frequency_penalty=parameters.frequency_penalty,
        presence_penalty=parameters.presence_penalty,
        seed=parameters.seed,
        max_tokens=parameters.max_tokens,
        max_completion_tokens=parameters.max_completion_tokens,
        reasoning=(
            parameters.reasoning.model_dump(mode="json")
            if parameters.reasoning is not None
            else None
        ),
        openrouter_provider={
            "only": list(execution.provider_allowlist),
            "order": list(execution.provider_allowlist),
            "allow_fallbacks": execution.allow_fallbacks,
            "require_parameters": True,
        },
        metadata={
            "caliburn_component": "consultant",
            "profile_id": execution.profile_id,
            "profile_revision": execution.profile_revision,
            "policy_id": execution.policy_id,
            "policy_revision": execution.policy_revision,
            "requested_model": execution.requested_model,
        },
        tags=["caliburn-consultant", execution.run_kind],
        stream_usage=True,
    )
