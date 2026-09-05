"""Native Responses binding; no product or legacy application imports."""

import httpx
from langchain_openai import ChatOpenAI


def build_model(
    *, model: str, api_key: str, http_client: httpx.Client,
    compact_threshold: int | None = None,
) -> ChatOpenAI:
    """Bind the configured model to the supplied HTTP transport."""
    if compact_threshold is not None and compact_threshold <= 0:
        raise ValueError("compact_threshold must be positive when configured")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        http_client=http_client,
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
