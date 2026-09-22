"""B2 application wiring: the adopted consolidation workflow and its provider.

This is the background stage that turns one completed B1 batch of saved
detail into published understanding. The workflow, prompt, budgets, staged
files, stale->load and publication identity stay in
`caliburn_memory.consolidation`; nothing here re-implements them, adds a
scheduler, writes JD or exposes a user tool.

Unlike B1, this older B2 adapter is still directly bound to OpenAI and is not yet
part of the formal OpenRouter host composition. The conversation consultant
now uses its pinned OpenRouter/OpenAI Luna route. B2 is a bounded tool-calling
agent, so it carries the verified agent budgets, which are not B1's window
budgets; its provider convergence belongs to the background slice.
"""

import math

from caliburn_memory import PublicationStore
from caliburn_memory.consolidation import ConsolidationWorkflow
from caliburn_memory.extraction import ExtractionWorkflow
from langchain_openai import ChatOpenAI

from .response_context import native_context_view, server_compaction_view


# This case's tested B2 profile, not a provider default: the agent budgets and
# the explicit visible output verified for this role. The class default of 4096
# is deliberately not used -- the verified entry configures 8192 -- and these
# sixteen model steps are B2's own, not B1's sixteen windows.
MAX_MODEL_STEPS = 16
MAX_TOOL_CALLS = 15
MAX_OUTPUT_TOKENS = 8192
REASONING_EFFORT = "high"
COMPACT_THRESHOLD = 12000


def build_consolidation_model(*, model: str, api_key: str, http_client,
                              base_url: str | None = None,
                              request_timeout: float | None = None,
                              reasoning_effort: str = REASONING_EFFORT,
                              compact_threshold: int | None = COMPACT_THRESHOLD) -> ChatOpenAI:
    """Bind B2's own model to the supplied transport; no server-side storage.

    Inline compaction is configured here and read back by the context view
    above, so a long attempt keeps its own window without this App trimming a
    saved conversation. An oversize input must still fail loudly rather than
    arrive shortened: as for B1, `truncation` is deprecated with `disabled` as
    its default, under which an input past the context window returns a 400,
    so no such parameter is sent. Server storage stays off: the canonical
    record is this App's Saver, Store and publication, never the provider's.
    """
    if request_timeout is not None and (not math.isfinite(request_timeout) or request_timeout <= 0):
        raise ValueError("request_timeout must be positive and finite")
    if compact_threshold is not None and compact_threshold <= 0:
        raise ValueError("compact_threshold must be positive when configured")
    return ChatOpenAI(
        model=model, api_key=api_key, base_url=base_url, http_client=http_client,
        # LangChain passes this to the SDK explicitly; a timeout set only on the
        # HTTP client is overwritten by request_timeout=None during binding.
        timeout=request_timeout if request_timeout is not None else http_client.timeout,
        use_responses_api=True, output_version="responses/v1", store=False,
        reasoning={"effort": reasoning_effort, "context": "all_turns"},
        model_kwargs={"parallel_tool_calls": False},
        context_management=([{"type": "compaction", "compact_threshold": compact_threshold}]
                            if compact_threshold is not None else None),
    )


def build_consolidation_workflow(*, extraction: ExtractionWorkflow, publication: PublicationStore,
                                 model: ChatOpenAI, checkpointer,
                                 max_output_tokens: int = MAX_OUTPUT_TOKENS,
                                 **options) -> ConsolidationWorkflow:
    """Assemble B2 for one document, over the B1 workflow that produced its input.

    The artifacts and the source reader come from that B1 workflow, so both
    stages read one document through one owner. The provider's context view is
    supplied here because the package binds no provider.
    """
    return ConsolidationWorkflow(extraction, publication, model, checkpointer,
                                 context_middleware=(native_context_view,),
                                 max_model_steps=options.pop("max_model_steps", MAX_MODEL_STEPS),
                                 max_tool_calls=options.pop("max_tool_calls", MAX_TOOL_CALLS),
                                 max_output_tokens=max_output_tokens, **options)
