"""Responses request-only continuity shared by the A and B2 agent loops.

This module preserves the completed consultant's inline-compaction behavior:
the Saver keeps the canonical messages, while a model request starts at the
latest opaque compaction item.  It does not choose a provider, grant raw
conversation access, summarize Memory, or make an unsupported transport
capable of producing compaction items.
"""

from collections.abc import Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain_core.messages import AIMessage, BaseMessage


def server_compaction_view(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Copy a Responses conversation from its latest inline compaction item.

    System instructions and Memory context remain separate model inputs.  This
    view only applies to the inline Responses contract; standalone
    ``/responses/compact`` returns a complete replacement window and must not
    use this cutter.  No checkpointed message is modified.

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
            # Responses adapters can replay calls from these convenience
            # fields.  Calls cut from content must not reappear on the wire.
            first.tool_calls = [
                call for call in first.tool_calls if call["id"] in remaining_call_ids
            ]
            first.invalid_tool_calls = [
                call for call in first.invalid_tool_calls
                if call["id"] in remaining_call_ids
            ]
            return [
                first,
                *(item.model_copy(deep=True) for item in messages[message_index + 1:]),
            ]
    return [message.model_copy(deep=True) for message in messages]


@wrap_model_call
def native_context_view(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    """Apply the Responses view to one request, never to canonical state."""
    return handler(request.override(messages=server_compaction_view(request.messages)))
