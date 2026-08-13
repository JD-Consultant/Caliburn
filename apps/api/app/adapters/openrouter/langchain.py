"""Narrow LangChain OpenRouter binding for the versioned consultant profile."""

from __future__ import annotations

from typing import Any

from langchain_openrouter import ChatOpenRouter

from app.consultant.model_runtime import ResolvedExecution


class ReceiptChatOpenRouter(ChatOpenRouter):
    """Keep route facts that langchain-openrouter 0.2.7 otherwise discards."""

    def _create_chat_result(self, response: Any):
        payload = (
            response
            if isinstance(response, dict)
            else response.model_dump(by_alias=True)
        )
        result = super()._create_chat_result(response)
        provider = payload.get("provider")
        model = payload.get("model")
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
    parameters = execution.effective_parameters
    return ReceiptChatOpenRouter(
        model=execution.requested_model,
        api_key=api_key,
        base_url=base_url,
        timeout=int(execution.timeout_seconds),
        max_retries=0,
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
