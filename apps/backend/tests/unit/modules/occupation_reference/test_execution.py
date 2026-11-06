"""Actual thread completion owns capacity, even when the async caller cancels."""

import asyncio
import threading
from collections.abc import Callable
from typing import Any

import anyio
import pytest

from caliburn.modules.occupation_reference.application.errors import (
    RetrievalBusy,
    RetrievalUnavailable,
)
from caliburn.modules.occupation_reference.infrastructure.execution import (
    RetrievalWorker,
)


class BlockingOperation:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def __call__(self) -> int:
        self.calls += 1
        self.started.set()
        assert self.release.wait(5), "test did not release worker"
        return 42


async def eventually(predicate: Callable[[], bool]) -> None:
    with anyio.fail_after(3):
        while not predicate():
            await anyio.sleep(0.001)


def test_running_cancel_keeps_lane_and_close_drains_physical_thread() -> None:
    async def scenario() -> None:
        worker = RetrievalWorker()
        operation = BlockingOperation()
        active = asyncio.create_task(worker.run(operation))
        pending: list[asyncio.Task[object]] = []
        try:
            await eventually(operation.started.is_set)
            queued = asyncio.create_task(worker.run(operation))
            pending.append(queued)
            active.cancel()
            await anyio.lowlevel.checkpoint()
            active.cancel()
            await anyio.sleep(0.02)
            assert not active.done()
            assert operation.calls == 1
            closing = asyncio.create_task(worker.aclose())
            pending.append(closing)
            await anyio.sleep(0.02)
            assert not closing.done()
            with pytest.raises(RetrievalUnavailable):
                await queued
            with pytest.raises(RetrievalUnavailable):
                await worker.run(operation)
            closing.cancel()
            await anyio.lowlevel.checkpoint()
            closing.cancel()
            assert not closing.done()
        finally:
            operation.release.set()
            results = await asyncio.gather(active, *pending, return_exceptions=True)
            await worker.aclose()
        assert isinstance(results[0], asyncio.CancelledError)
        assert isinstance(results[-1], asyncio.CancelledError)
        assert operation.calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("cancellation", ["scope", "raw"])
def test_cancellation_after_capacity_acquisition_prevents_dispatch(
    monkeypatch: pytest.MonkeyPatch, cancellation: str
) -> None:
    async def scenario() -> None:
        worker = RetrievalWorker()
        calls: list[str] = []
        limiter_type = type(anyio.CapacityLimiter(1))
        acquire_nowait = limiter_type.acquire_on_behalf_of_nowait
        try:
            with anyio.CancelScope() as scope:

                def acquire_and_cancel(limiter: Any, borrower: object) -> None:
                    acquire_nowait(limiter, borrower)
                    if cancellation == "scope":
                        scope.cancel()
                    else:
                        task = asyncio.current_task()
                        assert task is not None
                        asyncio.get_running_loop().call_soon(task.cancel)

                with monkeypatch.context() as patch:
                    # Keep native admission; inject at its shielded checkpoint.
                    patch.setattr(
                        limiter_type, "acquire_on_behalf_of_nowait", acquire_and_cancel
                    )
                    if cancellation == "raw":
                        with pytest.raises(asyncio.CancelledError):
                            await worker.run(lambda: calls.append("started"))
                    else:
                        await worker.run(lambda: calls.append("started"))
            assert calls == []
            if cancellation == "scope":
                assert scope.cancelled_caught
        finally:
            await worker.aclose()

    asyncio.run(scenario())


def test_running_anyio_cancellation_discards_late_result() -> None:
    async def scenario() -> None:
        worker = RetrievalWorker()
        operation = BlockingOperation()
        scope = anyio.CancelScope()
        results: list[int] = []

        async def request() -> None:
            with scope:
                results.append(await worker.run(operation))

        task = asyncio.create_task(request())
        try:
            await eventually(operation.started.is_set)
            scope.cancel()
            await anyio.sleep(0.02)
            assert not task.done()
        finally:
            operation.release.set()
            await task
            await worker.aclose()
        assert scope.cancelled_caught
        assert results == []

    asyncio.run(scenario())


def test_queue_cancel_timeout_and_failure_leave_worker_usable() -> None:
    async def scenario() -> None:
        worker = RetrievalWorker(admission_timeout=0.03)
        operation = BlockingOperation()
        active = asyncio.create_task(worker.run(operation))
        try:
            await eventually(operation.started.is_set)
            queued = asyncio.create_task(worker.run(operation))
            await anyio.sleep(0.01)
            queued.cancel()
            with pytest.raises(asyncio.CancelledError):
                await queued
            with pytest.raises(RetrievalBusy):
                await worker.run(operation)
            assert operation.calls == 1
        finally:
            operation.release.set()
            await active
        try:

            def broken() -> None:
                raise ValueError("broken")

            with pytest.raises(ValueError, match="broken"):
                await worker.run(broken)
            assert await worker.run(lambda: 42) == 42
        finally:
            await worker.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("cancellation", ["scope", "raw"])
def test_cancelled_before_dispatch_never_starts_worker(cancellation: str) -> None:
    async def scenario() -> None:
        worker = RetrievalWorker()
        calls: list[str] = []
        try:
            if cancellation == "scope":
                with anyio.CancelScope() as scope:
                    scope.cancel()
                    await worker.run(lambda: calls.append("started"))
                assert scope.cancelled_caught
            else:
                task = asyncio.current_task()
                assert task is not None
                asyncio.get_running_loop().call_soon(task.cancel)
                with pytest.raises(asyncio.CancelledError):
                    await worker.run(lambda: calls.append("started"))
            assert calls == []
        finally:
            await worker.aclose()

    asyncio.run(scenario())
