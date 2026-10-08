"""One bounded delivery mechanism for public text projections; no persistence."""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID


class PublicStreamCapacityError(RuntimeError):
    """The bounded hub cannot admit another transient subscriber."""


class BoundedPublicTextHub[T]:
    def __init__(
        self,
        *,
        queue_capacity: int = 8,
        max_subscribers: int = 64,
        max_update_chars: int = 32768,
    ) -> None:
        if min(queue_capacity, max_subscribers, max_update_chars) < 1:
            raise ValueError("Public text hub limits must be positive")
        self._queue_capacity = queue_capacity
        self._max_subscribers = max_subscribers
        self._max_update_chars = max_update_chars
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: dict[tuple[UUID, UUID], set[asyncio.Queue[T]]] = {}

    @contextmanager
    def subscribe(self, job_file_id: UUID, execution_id: UUID) -> Iterator[asyncio.Queue[T]]:
        self._check_loop()
        if sum(map(len, self._subscribers.values())) >= self._max_subscribers:
            raise PublicStreamCapacityError("Public text subscriber capacity reached")
        key = (job_file_id, execution_id)
        queue: asyncio.Queue[T] = asyncio.Queue(self._queue_capacity)
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

    def _publish(self, job_file_id: UUID, execution_id: UUID, update: T, chars: int) -> None:
        """Never await readers; overflow drops oldest, oversize drops whole updates.

        Callers supply only allowlisted accumulated text, not raw provider events.
        Durable history is read separately from native saved results.
        """
        subscribers = self._subscribers.get((job_file_id, execution_id))
        if not subscribers:
            return
        self._check_loop()
        if chars > self._max_update_chars:
            return
        for queue in subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(update)

    def _check_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError("Public text hub must be used on one event loop")
