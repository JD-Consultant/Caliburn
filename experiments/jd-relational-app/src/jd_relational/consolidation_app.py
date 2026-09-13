"""B2 application wiring: the adopted consolidation workflow and its provider.

This is the background stage that turns one completed B1 batch of saved
detail into published understanding. The workflow, prompt, budgets, staged
files, stale->load and publication identity stay in
`caliburn_memory.consolidation`; nothing here re-implements them, adds a
scheduler, writes JD or exposes a user tool.

Like B1, only this stage is bound to OpenAI. The conversation consultant
keeps its pinned Anthropic runtime; there is no app-wide provider switch or
fallback. B2 is a bounded tool-calling agent, so it carries the verified
agent budgets, which are not B1's window budgets.
"""

from collections.abc import Callable
import math

from caliburn_memory import PublicationStore
from caliburn_memory.consolidation import ConsolidationWorkflow
from caliburn_memory.extraction import ExtractionWorkflow
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI


# This case's tested B2 profile, not a provider default: the agent budgets and
# the explicit visible output verified for this role. The class default of 4096
# is deliberately not used -- the verified entry configures 8192 -- and these
# sixteen model steps are B2's own, not B1's sixteen windows.
MAX_MODEL_STEPS = 16
MAX_TOOL_CALLS = 15
MAX_OUTPUT_TOKENS = 8192
REASONING_EFFORT = "high"
COMPACT_THRESHOLD = 12000


def server_compaction_view(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Copy a conversation from its latest inline server compaction item.

    Input is canonical conversation using ChatOpenAI ``responses/v1`` blocks.
    System instructions/Memory guide must be supplied separately by the caller.
    This is NOT for standalone ``/responses/compact`` output: that entire
    returned window must be passed as-is. No database messages are modified.

    https://developers.openai.com/api/docs/guides/compaction
    """
    for message_index in range(len(messages) - 1, -1, -1):
        message = messages[message_index]
        if not isinstance(message, AIMessage) or not isinstance(message.content, list):
            continue
        for block_index in range(len(message.content) - 1, -1, -1):
            block = message.content[block_index]
            if not isinstance(block, dict) or block.get("type") != "compaction":
                continue
            first = message.model_copy(deep=True)
            first.content = first.content[block_index:]
            remaining_call_ids = {
                item["call_id"]
                for item in first.content
                if isinstance(item, dict)
                and item.get("type") in ("function_call", "custom_tool_call")
                and "call_id" in item
            }
            # The adapter also replays calls from these separate convenience
            # fields. Leaving a pre-cut call here would reintroduce it on wire.
            first.tool_calls = [call for call in first.tool_calls if call["id"] in remaining_call_ids]
            first.invalid_tool_calls = [call for call in first.invalid_tool_calls if call["id"] in remaining_call_ids]
            return [first, *(item.model_copy(deep=True) for item in messages[message_index + 1:])]
    return [message.model_copy(deep=True) for message in messages]


@wrap_model_call
def native_context_view(request: ModelRequest,
                        handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    """Override the model request, never return a messages update to graph state.

    https://docs.langchain.com/oss/python/langchain/context-engineering
    System instructions stay in request.system_message outside the conversation.
    Only supports the responses/v1 inline-compaction contract of the builder below.
    """
    return handler(request.override(messages=server_compaction_view(request.messages)))


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


