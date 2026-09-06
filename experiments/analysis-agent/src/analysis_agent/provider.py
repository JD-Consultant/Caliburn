"""Native Responses binding; no product or legacy application imports."""

import httpx
import math
from langchain_openai import ChatOpenAI
from openai import APIStatusError


def is_billing_error(error: Exception) -> bool:
    """Public SDK fields, not provider-message substring matching.

    https://developers.openai.com/api/docs/guides/error-codes#api-errors
    This only governs the application's manual-resume classification, not SDK
    transport retry or a claim that we can inspect/fix account balances.
    """
    return isinstance(error, APIStatusError) and error.status_code == 429 and (
        error.code in {'credit_balance_exhausted', 'organization_spend_limit_exceeded',
                       'project_spend_limit_exceeded', 'organization_usage_limit_exceeded',
                       'insufficient_quota'} or error.type == 'insufficient_quota')


def build_model(
    *, model: str, api_key: str, http_client: httpx.Client,
    compact_threshold: int | None = None,
    request_timeout: float | None = None,
) -> ChatOpenAI:
    """Bind the configured model to the supplied HTTP transport."""
    if compact_threshold is not None and compact_threshold <= 0:
        raise ValueError("compact_threshold must be positive when configured")
    if request_timeout is not None and (not math.isfinite(request_timeout) or request_timeout <= 0):
        raise ValueError("request_timeout must be positive and finite")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        http_client=http_client,
        # LangChain passes this explicitly to the SDK. A timeout on the HTTP
        # client alone is overwritten by request_timeout=None during binding.
        timeout=request_timeout if request_timeout is not None else http_client.timeout,
        use_responses_api=True,
        output_version="responses/v1",
        store=False,
        reasoning={"effort": "medium", "context": "all_turns"},
        model_kwargs={"parallel_tool_calls": False},
        context_management=(
            [{"type": "compaction", "compact_threshold": compact_threshold}]
            if compact_threshold is not None else None
        ),
    )
