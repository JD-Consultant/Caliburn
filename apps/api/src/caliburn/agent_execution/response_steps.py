"""Inspect complete Responses items without equating API completion with product completion."""

from dataclasses import dataclass
from enum import StrEnum

from openai.types.responses import Response, ResponseFunctionToolCall, ResponseOutputMessage
from openai.types.responses.response_reasoning_item import ResponseReasoningItem


class ResponseAction(StrEnum):
    EXECUTE_TOOLS = "execute_tools"
    CONTINUE = "continue"
    DELIVER_ANSWER = "deliver_answer"


class IncompleteModelResponseError(ValueError):
    """The original response must be retained, but cannot yet drive tool effects."""


class UnsupportedModelResponseError(ValueError):
    """The returned operation is not supported by this application's execution contract."""


@dataclass(frozen=True, slots=True)
class ResponseStep:
    action: ResponseAction
    calls: tuple[ResponseFunctionToolCall, ...]
    messages: tuple[ResponseOutputMessage, ...]


def inspect_response_step(response: Response) -> ResponseStep:
    """Derive routing only; callers must save the original response before any effects.

    Commentary is not final. Calls take priority even if a final-phase message coexists.
    Unknown item/phase protocols stop explicitly instead of silently dropping output.
    """
    if response.status != "completed" or response.error is not None:
        raise IncompleteModelResponseError("The model response is not successfully completed")
    if response.incomplete_details is not None:
        raise IncompleteModelResponseError("The model response reports incomplete output")
    calls: list[ResponseFunctionToolCall] = []
    messages: list[ResponseOutputMessage] = []
    seen_calls: set[str] = set()
    for item in response.output:
        if isinstance(item, ResponseReasoningItem):
            if item.status not in (None, "completed"):
                raise IncompleteModelResponseError("A reasoning item is not complete")
        elif isinstance(item, ResponseFunctionToolCall):
            if item.status not in (None, "completed"):
                raise IncompleteModelResponseError("A function call is not complete")
            if not item.call_id or not item.name or item.call_id in seen_calls:
                raise UnsupportedModelResponseError(
                    "Function identities must be nonempty and unique"
                )
            if (
                item.async_
                or item.namespace is not None
                or (item.caller is not None and item.caller.type != "direct")
            ):
                raise UnsupportedModelResponseError(
                    "Only direct local function calls are supported"
                )
            seen_calls.add(item.call_id)
            calls.append(item)
        elif isinstance(item, ResponseOutputMessage):
            if item.status != "completed":
                raise IncompleteModelResponseError("An assistant message is not complete")
            if item.phase not in ("commentary", "final_answer"):
                raise UnsupportedModelResponseError(
                    "An assistant message requires an explicit phase"
                )
            messages.append(item)
        else:
            raise UnsupportedModelResponseError("The response contains an unsupported output item")
    if calls:
        action = ResponseAction.EXECUTE_TOOLS
    elif any(
        message.phase == "final_answer"
        and any(
            (part.text if part.type == "output_text" else part.refusal).strip()
            for part in message.content
        )
        for message in messages
    ):
        action = ResponseAction.DELIVER_ANSWER
    else:
        action = ResponseAction.CONTINUE
    return ResponseStep(action, tuple(calls), tuple(messages))
