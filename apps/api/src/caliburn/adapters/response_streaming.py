"""Transient public text projection; native terminal responses remain the only originals."""

import logging
from asyncio import CancelledError
from collections.abc import Callable
from dataclasses import dataclass, field

from openai import APIConnectionError, AsyncStream
from openai.types.responses import Response, ResponseOutputMessage, ResponseStreamEvent

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PublicCommentaryUpdate:
    response_id: str
    message_id: str
    text: str = field(repr=False)


class ResponseStreamCleanupError(RuntimeError):
    """A terminal original exists; reconcile it instead of repeating the provider call."""

    def __init__(self, response: Response) -> None:
        self.response = response
        super().__init__("Stream cleanup failed after receiving the original response")


class ResponseStreamCancelledError(CancelledError):
    """Propagate cancellation while handing the terminal original to the immediate caller."""

    def __init__(self, response: Response) -> None:
        self.response = response
        super().__init__("Stream cancelled after receiving the original response")


class ResponseStreamProtocolError(RuntimeError):
    """No terminal original was received; public text cannot substitute for one."""


class _CommentaryProjection:
    def __init__(self, callback: Callable[[PublicCommentaryUpdate], None] | None) -> None:
        self.callback = callback
        self.response_id: str | None = None
        self.messages: dict[str, int] = {}
        self.parts: dict[str, dict[int, str]] = {}
        self.emitted: dict[str, str] = {}

    def accept(self, event: ResponseStreamEvent) -> None:
        if self.callback is None:
            return
        if event.type == "response.created":
            self.response_id = event.response.id
        elif event.type in ("response.output_item.added", "response.output_item.done"):
            item = event.item
            if not (
                isinstance(item, ResponseOutputMessage)
                and item.role == "assistant"
                and item.phase == "commentary"
            ):
                return
            self.messages[item.id] = event.output_index
            self.parts[item.id] = {
                index: part.text if part.type == "output_text" else part.refusal
                for index, part in enumerate(item.content)
            }
            self._emit(item.id)
        elif event.type in (
            "response.output_text.delta",
            "response.output_text.done",
            "response.refusal.delta",
            "response.refusal.done",
        ):
            if self.messages.get(event.item_id) != event.output_index:
                return
            parts = self.parts[event.item_id]
            if event.type in ("response.output_text.delta", "response.refusal.delta"):
                parts[event.content_index] = parts.get(event.content_index, "") + event.delta
            elif event.type == "response.output_text.done":
                parts[event.content_index] = event.text
            elif event.type == "response.refusal.done":
                parts[event.content_index] = event.refusal
            self._emit(event.item_id)

    def _emit(self, message_id: str) -> None:
        if self.response_id is None or self.callback is None:
            return
        parts = self.parts[message_id]
        text = "\n\n".join(parts[index] for index in sorted(parts))
        if not text or self.emitted.get(message_id) == text:
            return
        self.emitted[message_id] = text
        try:
            self.callback(PublicCommentaryUpdate(self.response_id, message_id, text))
        except Exception:
            # Presentation is best effort. Never log observer text or exception payloads,
            # never await a slow reader, and never catch task cancellation here.
            self.callback = None
            _LOG.warning("Public commentary observer disabled after failure")


async def consume_response_stream(
    stream: AsyncStream[ResponseStreamEvent],
    *,
    on_commentary: Callable[[PublicCommentaryUpdate], None] | None = None,
) -> Response:
    """Consume one SDK stream, preserving terminal R before any subsequent cleanup await.

    No delta assembly, automatic argument parsing, retry or durable storage. The caller
    must retain typed terminal handoffs, including cancellation, before propagating them.
    """
    terminal: Response | None = None
    projection = _CommentaryProjection(on_commentary)
    try:
        try:
            async for event in stream:
                if event.type in ("response.completed", "response.failed", "response.incomplete"):
                    terminal = event.response
                    break  # Do not wait for EOF after an intact terminal envelope.
                projection.accept(event)
        finally:
            await stream.close()
    except CancelledError:
        if terminal is not None:
            raise ResponseStreamCancelledError(terminal) from None
        raise
    except Exception as error:
        # The pinned HTTP stream closes in its own finally block. A close error can
        # mask a read cancellation; preserve that immediate Python exception context.
        # The SDK wraps HTTP transport errors once; unwrap only that known boundary.
        # Do not scan arbitrary chains or turn normal transport failures into cancels.
        masked = error
        if isinstance(error, APIConnectionError) and isinstance(error.__cause__, Exception):
            masked = error.__cause__
        if isinstance(masked.__context__, CancelledError):
            if terminal is not None:
                raise ResponseStreamCancelledError(terminal) from None
            raise masked.__context__ from None
        if terminal is not None:
            raise ResponseStreamCleanupError(terminal) from None
        raise
    if terminal is None:
        raise ResponseStreamProtocolError("The stream ended without a terminal response")
    return terminal
