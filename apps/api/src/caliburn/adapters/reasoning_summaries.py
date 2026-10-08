"""Allowlisted readable summaries, never raw reasoning or encrypted continuation state."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from openai.types.responses import Response, ResponseReasoningItem, ResponseStreamEvent

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PublicReasoningSummary:
    response_id: str
    item_id: str
    output_index: int
    summary_index: int
    text: str = field(repr=False)


def project_reasoning_summaries(response: Response) -> tuple[PublicReasoningSummary, ...]:
    if response.status != "completed" or response.error is not None:
        return ()
    return tuple(
        PublicReasoningSummary(response.id, item.id, output_index, summary_index, part.text)
        for output_index, item in enumerate(response.output)
        if isinstance(item, ResponseReasoningItem) and item.status in (None, "completed")
        for summary_index, part in enumerate(item.summary)
        if part.type == "summary_text" and part.text.strip()
    )


class ReasoningSummaryProjection:
    """Accumulate text per native part; done events replace deltas rather than append."""

    def __init__(self, callback: Callable[[PublicReasoningSummary], None] | None) -> None:
        self.callback = callback
        self.response_id: str | None = None
        self.items: dict[str, int] = {}
        self.parts: dict[tuple[str, int], str] = {}
        self.emitted: dict[tuple[str, int], str] = {}

    def accept(self, event: ResponseStreamEvent) -> None:
        if self.callback is None:
            return
        if event.type == "response.created":
            self.response_id = event.response.id
        elif event.type in ("response.output_item.added", "response.output_item.done"):
            item = event.item
            if not isinstance(item, ResponseReasoningItem):
                return
            self.items[item.id] = event.output_index
            for index, part in enumerate(item.summary):
                if part.type == "summary_text":
                    self._replace(item.id, index, part.text)
        elif event.type in (
            "response.reasoning_summary_text.delta",
            "response.reasoning_summary_text.done",
            "response.reasoning_summary_part.added",
            "response.reasoning_summary_part.done",
        ):
            if self.items.get(event.item_id) != event.output_index:
                return
            key = (event.item_id, event.summary_index)
            if event.type == "response.reasoning_summary_text.delta":
                text = self.parts.get(key, "") + event.delta
            elif event.type == "response.reasoning_summary_text.done":
                text = event.text
            else:
                if event.part.type != "summary_text":
                    return
                text = event.part.text
            self._replace(event.item_id, event.summary_index, text)

    def _replace(self, item_id: str, summary_index: int, text: str) -> None:
        key = (item_id, summary_index)
        self.parts[key] = text
        if (
            self.response_id is None
            or self.callback is None
            or not text
            or self.emitted.get(key) == text
        ):
            return
        self.emitted[key] = text
        try:
            self.callback(
                PublicReasoningSummary(
                    self.response_id, item_id, self.items[item_id], summary_index, text
                )
            )
        except Exception:
            self.callback = None
            _LOG.warning("reasoning_summary.observer_disabled")
