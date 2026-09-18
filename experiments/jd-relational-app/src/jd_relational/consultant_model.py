"""The completed consultant's model route through OpenRouter.

The consultant stays a LangChain/LangGraph agent. This adapter only binds its
verified Luna profile to OpenRouter, keeps the route on OpenAI with fallback
disabled, and translates OpenRouter's terminal evidence into the App's existing
``completed``/``incomplete`` boundary. It does not own prompts, tools, document
scope, checkpoints, retries, or background work.
"""

from .openrouter_model import (
    OPENROUTER_BASE_URL, OPENROUTER_HEADERS, OPENROUTER_PROVIDER,
    REQUEST_TIMEOUT_SECONDS, OpenRouterModelError, ReceiptChatOpenRouter,
    create_openrouter_model,
)


CONSULTANT_MODEL = "openai/gpt-5.6-luna"
# The verified profile for this role. The agent loop budgets stay where the
# consultant graph is assembled; these values are model request parameters.
REASONING_EFFORT = "high"
MAX_OUTPUT_TOKENS = 8192
MAX_MODEL_STEPS = 64
MAX_TOOL_CALLS = 63


ConsultantModelError = OpenRouterModelError


def create_consultant_model(
    *,
    api_key: str,
    http_client,
    async_http_client,
    model: str = CONSULTANT_MODEL,
    base_url: str = OPENROUTER_BASE_URL,
    request_timeout: float = REQUEST_TIMEOUT_SECONDS,
    reasoning_effort: str = REASONING_EFFORT,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
) -> ReceiptChatOpenRouter:
    """Bind the consultant profile to the App's common OpenRouter boundary."""
    return create_openrouter_model(
        component="consultant",
        model=model,
        api_key=api_key,
        http_client=http_client,
        async_http_client=async_http_client,
        base_url=base_url,
        request_timeout=request_timeout,
        reasoning_effort=reasoning_effort,
        max_output_tokens=max_output_tokens,
        max_retries=0,
    )
