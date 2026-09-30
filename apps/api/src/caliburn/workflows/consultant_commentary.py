"""Bounded, non-durable public commentary delivery within one event loop."""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PublicCommentaryUpdate:
    job_file_id: UUID
    execution_id: UUID
    response_id: str
    message_id: str
    text: str


class CommentaryCapacityError(RuntimeError):
    """The bounded hub cannot admit another transient subscriber."""


class ConsultantCommentaryHub:
    def __init__(
        self,
        *,
        queue_capacity: int = 8,
        max_subscribers: int = 64,
        max_update_chars: int = 32768,
    ) -> None:
        if min(queue_capacity, max_subscribers, max_update_chars) < 1:
            raise ValueError("Commentary hub limits must be positive")
        self._queue_capacity = queue_capacity
        self._max_subscribers = max_subscribers
        self._max_update_chars = max_update_chars
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: dict[tuple[UUID, UUID], set[asyncio.Queue[PublicCommentaryUpdate]]] = {}

    @contextmanager
    def subscribe(
        self,
        job_file_id: UUID,
        execution_id: UUID,
    ) -> Iterator[asyncio.Queue[PublicCommentaryUpdate]]:
        self._check_loop()
        if sum(map(len, self._subscribers.values())) >= self._max_subscribers:
            raise CommentaryCapacityError("Commentary subscriber capacity reached")
        key = (job_file_id, execution_id)
        queue: asyncio.Queue[PublicCommentaryUpdate] = asyncio.Queue(self._queue_capacity)
        self._subscribers.setdefault(key, set()).add(queue)
        try:
            yield queue
        finally:
            subscribers = self._subscribers[key]
            subscribers.remove(queue)
            if not subscribers:
                del self._subscribers[key]
            while not queue.empty():
                queue.get_nowait()

    def publish(
        self,
        job_file_id: UUID,
        execution_id: UUID,
        response_id: str,
        message_id: str,
        text: str,
    ) -> None:
        """Publish accumulated *public* text on the subscribers' event loop.

        No I/O, task creation, replay, or wait for consumers. Overflow drops the
        oldest update; oversized updates are dropped whole, never truncated.
        The caller alone selects public commentary (never raw SDK events).
        """
        subscribers = self._subscribers.get((job_file_id, execution_id))
        if not subscribers:
            return
        self._check_loop()
        if len(response_id) + len(message_id) + len(text) > self._max_update_chars:
            return
        update = PublicCommentaryUpdate(
            job_file_id,
            execution_id,
            response_id,
            message_id,
            text,
        )
        for queue in subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(update)

    def _check_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError("Commentary hub must be used on one event loop")
