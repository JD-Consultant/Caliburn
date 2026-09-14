"""The conversation consultant's own model, on the one provider this product uses.

This App talks to OpenAI. There is no second consultant path, no provider menu
and no automatic fallback: the framework can speak to more than one provider,
but this product does not, and a role that cannot reach its provider reports
that rather than quietly using another.

The role profile is the verified one -- reasoning effort high, an explicit
output ceiling rather than the adapter's default, inline compaction so a long
interview keeps its own window, no parallel tool calls, and no server-side
conversation storage: the durable record is this App's Saver, Store and JD
database, never the provider's.

An oversize input must fail loudly rather than arrive shortened, which is
already the behaviour: `truncation` is deprecated with `disabled` as its
default, under which an input past the context window returns a 400. No such
parameter is sent. Whether a reply actually finished is judged by
`openai_responses.accepted`, the same rule the background stages use.
"""

import math

from langchain_openai import ChatOpenAI

# The verified profile for this role. A and B2 are both bounded tool-calling
# agents with the same budgets; B1 is a structured extraction graph and has its
# own. These are this case's measured values, not provider defaults.
REASONING_EFFORT = "high"
MAX_OUTPUT_TOKENS = 8192
COMPACT_THRESHOLD = 12000
MAX_MODEL_STEPS = 16
MAX_TOOL_CALLS = 15


class ConsultantModelError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def create_consultant_model(
    *, model: str, api_key: str, http_client, base_url: str | None = None,
    request_timeout: float | None = None, reasoning_effort: str = REASONING_EFFORT,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    compact_threshold: int | None = COMPACT_THRESHOLD,
) -> ChatOpenAI:
    """Build from explicit caller inputs; no configuration or environment lookup.

    Scope, run ownership, request context and checkpoint persistence belong to
    the application runtime; they are not model parameters.
    """
    if (any(type(value) is not str or not value.strip() or "\0" in value
            for value in (model, api_key))
            or type(max_output_tokens) is not int or max_output_tokens <= 0
            or not isinstance(reasoning_effort, str) or not reasoning_effort.strip()
            or (compact_threshold is not None
                and (type(compact_threshold) is not int or compact_threshold <= 0))
            or (request_timeout is not None
                and (type(request_timeout) not in (int, float)
                     or not math.isfinite(request_timeout) or request_timeout <= 0))):
        raise ConsultantModelError("invalid_model_configuration")
    return ChatOpenAI(
        model=model, api_key=api_key, base_url=base_url, http_client=http_client,
        # LangChain passes this to the SDK explicitly; a timeout set only on the
        # HTTP client is overwritten by request_timeout=None during binding.
        timeout=request_timeout if request_timeout is not None else http_client.timeout,
        use_responses_api=True, output_version="responses/v1", store=False,
        max_tokens=max_output_tokens,
        reasoning={"effort": reasoning_effort, "context": "all_turns"},
        model_kwargs={"parallel_tool_calls": False},
        max_retries=0,
        context_management=([{"type": "compaction", "compact_threshold": compact_threshold}]
                            if compact_threshold is not None else None),
    )
