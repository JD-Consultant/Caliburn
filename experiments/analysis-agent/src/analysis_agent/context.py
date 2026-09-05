"""Request-only view; canonical conversation is never trimmed here."""

from langchain_core.messages import AIMessage, BaseMessage


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
