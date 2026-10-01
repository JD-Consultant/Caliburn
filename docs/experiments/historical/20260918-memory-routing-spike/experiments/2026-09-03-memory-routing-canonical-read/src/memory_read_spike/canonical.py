"""Canonical conversation append and scoped deep-read operations."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from memory_read_spike.contracts import ConversationItem, ReadConversationContextResult
from memory_read_spike.scope import (
    TrustedReadScope,
    classify_message_ref,
    issue_message_ref,
)


class ReferenceUnavailableError(RuntimeError):
    def __init__(self, internal_reason: str) -> None:
        super().__init__("reference_unavailable")
        self.internal_reason = internal_reason
        self.public_payload = {"error": {"code": "reference_unavailable"}}


async def latest_canonical_messages(
    runtime: Any,
    scope: TrustedReadScope,
) -> tuple[BaseMessage, ...]:
    snapshot = await runtime.graph.aget_state(scope.checkpoint_config)
    return tuple(snapshot.values.get("messages", ()))


async def append_canonical_round(
    runtime: Any,
    scope: TrustedReadScope,
    human: HumanMessage,
    assistant: AIMessage,
) -> None:
    if not isinstance(human, HumanMessage) or not isinstance(assistant, AIMessage):
        raise TypeError("canonical round requires HumanMessage then AIMessage")
    if not human.id or not assistant.id:
        raise ValueError("canonical messages require stable IDs")

    await runtime.graph.ainvoke(
        {"messages": [human, assistant]},
        scope.checkpoint_config,
    )


async def read_canonical_context(
    runtime: Any,
    scope: TrustedReadScope,
    message_ref: str,
) -> ReadConversationContextResult:
    classification = classify_message_ref(scope, message_ref)
    if classification == "malformed":
        raise ReferenceUnavailableError("malformed")
    if classification == "cross_scope":
        raise ReferenceUnavailableError("cross_scope")

    messages = await latest_canonical_messages(runtime, scope)
    target_index = next(
        (
            index
            for index, message in enumerate(messages)
            if message.id is not None
            and issue_message_ref(scope, message.id) == message_ref
        ),
        None,
    )
    if target_index is None:
        raise ReferenceUnavailableError("missing")
    target = messages[target_index]
    if not isinstance(target, HumanMessage):
        raise ReferenceUnavailableError("missing")

    context: list[ConversationItem] = []
    if target_index > 0 and isinstance(messages[target_index - 1], AIMessage):
        context.append(
            ConversationItem(
                speaker="consultant",
                text=str(messages[target_index - 1].content),
            )
        )
    context.append(ConversationItem(speaker="employee", text=str(target.content)))
    return ReadConversationContextResult(context=tuple(context))
