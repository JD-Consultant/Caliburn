"""Own the serialized retrieval worker from admission through physical shutdown."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import TypeVar

import anyio

T = TypeVar("T")


class RetrievalBusy(RuntimeError):
    """The model lane did not become available before the admission deadline."""


class RetrievalUnavailable(RuntimeError):
    """The application is shutting down and cannot admit retrieval work."""


async def _join(future: asyncio.Future[T]) -> T:
    """Never forward caller cancellation to a submitted physical worker."""
    cancelled = None
    with anyio.CancelScope(shield=True):
        while not future.done():
            try:
                await asyncio.wait({future})
            except asyncio.CancelledError as exc:
                cancelled = exc
        # Observe failures even when cancellation wins over the late result.
        error = future.exception()
    if cancelled is not None:
        raise cancelled
    await anyio.lowlevel.checkpoint()
    if error is not None:
        raise error
    return future.result()


class RetrievalWorker:
    """One application-owned model lane; waiting requests consume no thread.

    Admission has a separate deadline. Once synchronously submitted, work must
    finish before the lane or its clients can be released. No hard thread timeout
    is implied; provider timeouts still bound their own I/O.
    """

    def __init__(self, *, admission_timeout: float = 5.0) -> None:
        self._lane = anyio.CapacityLimiter(1)
        self._admission_timeout = admission_timeout
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="ocs-retrieval"
        )
        self._waiting: set[anyio.CancelScope] = set()
        self._closing = False
        self._active: asyncio.Future[object] | None = None
        self._shutdown: asyncio.Task[None] | None = None

    async def run(self, operation: Callable[[], T]) -> T:
        await anyio.lowlevel.checkpoint()
        if self._closing:
            raise RetrievalUnavailable
        acquired = False
        try:
            with anyio.CancelScope() as admission:
                self._waiting.add(admission)
                try:
                    with anyio.fail_after(self._admission_timeout):
                        await self._lane.acquire()
                        acquired = True
                except TimeoutError as exc:
                    raise RetrievalBusy from exc
                finally:
                    self._waiting.discard(admission)
            # Limiter acquisition may use a shielded checkpoint. Deliver pending
            # cancellation before the synchronous, non-awaiting submit handoff.
            await anyio.lowlevel.checkpoint()
            if self._closing:
                raise RetrievalUnavailable
            future = asyncio.wrap_future(
                self._executor.submit(copy_context().run, operation)
            )
            self._active = future
            try:
                return await _join(future)
            finally:
                self._active = None
        finally:
            if acquired:
                self._lane.release()

    async def aclose(self) -> None:
        if self._shutdown is None:
            self._closing = True
            for admission in self._waiting:
                admission.cancel()
            self._shutdown = asyncio.create_task(self._drain_and_shutdown())
        await _join(self._shutdown)

    async def _drain_and_shutdown(self) -> None:
        if self._active is not None:
            # The request observes its result. Shutdown only owns completion.
            await asyncio.wait({self._active})
        await anyio.to_thread.run_sync(self._executor.shutdown)
