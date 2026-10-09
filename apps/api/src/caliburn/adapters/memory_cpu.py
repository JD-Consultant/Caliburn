"""One application-owned executor lane for pure Memory CPU work."""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from functools import partial
from typing import cast

import anyio

from caliburn.adapters.owned_tasks import join_owned


class MemoryCpu:
    """Submit only after cancellable admission, then own the physical future.

    There is at most one submitted job, with no executor queue of waiting work.
    Thread cancellation cannot stop CPU code: a borrower joins its submitted job
    before releasing the lane. This is not a hard CPU deadline or GIL parallelism.
    """

    def __init__(self) -> None:
        self._admission = anyio.CapacityLimiter(1)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="caliburn-memory-cpu")
        self._active: asyncio.Future[object] | None = None
        self._closing = False
        self._shutdown: asyncio.Task[None] | None = None

    async def run[T, **P](self, function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        if self._closing:
            raise RuntimeError("Memory CPU resource is closed")
        async with self._admission:
            # Native limiter acquisition can finish with a shielded checkpoint.
            # Deliver cancellation before the synchronous executor handoff below.
            await anyio.lowlevel.checkpoint()
            if self._closing:
                raise RuntimeError("Memory CPU resource is closed")
            job = self._executor.submit(copy_context().run, partial(function, *args, **kwargs))
            future = asyncio.wrap_future(job)
            # Close only observes completion; the borrower retains the typed result.
            self._active = cast(asyncio.Future[object], future)
            try:
                return await join_owned(future)
            finally:
                self._active = None

    async def aclose(self) -> None:
        self._closing = True
        if self._shutdown is None:
            self._shutdown = asyncio.create_task(self._close(), name="memory-cpu-shutdown")
        await join_owned(self._shutdown)

    async def _close(self) -> None:
        if self._active is not None:
            # Only the borrower adopts the result/error; close observes completion.
            await asyncio.wait((self._active,))
        # Even idle executor threads belong to this owner. Join them off-loop;
        # aclose keeps this cleanup task alive through raw/repeated cancellation.
        await asyncio.to_thread(self._executor.shutdown, wait=True, cancel_futures=True)
