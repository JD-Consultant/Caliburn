"""Owned CPU work must outlive cancellation of the borrowing coroutine."""

import asyncio
import threading

import pytest

from caliburn.adapters.memory_cpu import MemoryCpu


@pytest.mark.asyncio
async def test_cancelled_worker_keeps_capacity_until_physical_completion():
    cpu = MemoryCpu()
    started = threading.Event()
    release = threading.Event()
    second_started = threading.Event()

    def first():
        started.set()
        assert release.wait(5)
        return "late"

    task = asyncio.create_task(cpu.run(first))
    await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(0.02)
    task.cancel()
    second = asyncio.create_task(cpu.run(second_started.set))
    await asyncio.sleep(0.02)
    assert not task.done() and not second_started.is_set()
    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second
    closing = asyncio.create_task(cpu.aclose())
    await asyncio.sleep(0.02)
    closing.cancel()
    await asyncio.sleep(0.02)
    closing.cancel()
    assert not closing.done()
    with pytest.raises(RuntimeError, match="closed"):
        await cpu.run(lambda: None)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(asyncio.CancelledError):
        await closing
    await cpu.aclose()
    assert not second_started.is_set()


@pytest.mark.asyncio
async def test_error_is_observed_and_next_work_can_run():
    cpu = MemoryCpu()

    def fail():
        raise ValueError("worker failure")

    try:
        with pytest.raises(ValueError, match="worker failure"):
            await cpu.run(fail)
        assert await cpu.run(lambda: 42) == 42
    finally:
        await cpu.aclose()


@pytest.mark.asyncio
async def test_anyio_cancel_scope_does_not_adopt_late_result():
    import anyio

    cpu = MemoryCpu()
    started, release = threading.Event(), threading.Event()
    completed = []

    def work():
        started.set()
        assert release.wait(5)
        return "late"

    scope = anyio.CancelScope()

    async def borrower():
        with scope:
            completed.append(await cpu.run(work))

    task = asyncio.create_task(borrower())
    assert await asyncio.to_thread(started.wait, 2)
    scope.cancel()
    await asyncio.sleep(0.02)
    assert not task.done()
    release.set()
    await task
    await cpu.aclose()
    assert completed == []


@pytest.mark.asyncio
async def test_pre_cancelled_scope_does_not_dispatch_on_idle_lane():
    import anyio

    cpu = MemoryCpu()
    effects = []
    try:
        with anyio.CancelScope() as scope:
            scope.cancel()
            await cpu.run(lambda: effects.append("dispatched"))
        assert scope.cancelled_caught
        assert effects == []
    finally:
        await cpu.aclose()


@pytest.mark.asyncio
async def test_raw_cancel_before_owned_task_runs_does_not_dispatch():
    cpu = MemoryCpu()
    effects = []

    async def borrower():
        task = asyncio.current_task()
        asyncio.get_running_loop().call_soon(task.cancel)
        await cpu.run(lambda: effects.append("dispatched"))

    task = asyncio.create_task(borrower())
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
        assert effects == []
    finally:
        await cpu.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellation", ["raw", "scope"])
async def test_cancel_waiting_for_native_admission_does_not_dispatch(cancellation):
    import anyio

    cpu = MemoryCpu()
    effects = []
    scope = anyio.CancelScope()

    async def borrower():
        with scope:
            await cpu.run(lambda: effects.append("dispatched"))

    # Hold the real native admission limiter to expose its pre-dispatch wait. No thread,
    # cancellation or run_sync replacement is used in this race regression.
    async with cpu._admission:
        task = asyncio.create_task(borrower())
        for _ in range(100):
            if cpu._admission.statistics().tasks_waiting:
                break
            await asyncio.sleep(0)
        assert cpu._admission.statistics().tasks_waiting == 1
        if cancellation == "raw":
            task.cancel()
        else:
            scope.cancel()
        for _ in range(100):
            if task.done():
                break
            await asyncio.sleep(0)
        cancelled_before_capacity_release = task.done()
    try:
        if cancellation == "raw":
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task
            assert scope.cancelled_caught
        assert cancelled_before_capacity_release, (
            "Cancelled pending dispatch still holds its borrower"
        )
        assert effects == []
    finally:
        await cpu.aclose()


@pytest.mark.asyncio
async def test_close_during_admission_checkpoint_rejects_dispatch():
    cpu = MemoryCpu()
    effects = []
    task = asyncio.create_task(cpu.run(lambda: effects.append("dispatched")))
    # Let the borrower enter its pre-dispatch checkpoint, then close before it resumes.
    await asyncio.sleep(0)
    await cpu.aclose()
    with pytest.raises(RuntimeError, match="closed"):
        await task
    assert effects == []


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellation", ["raw", "scope"])
async def test_cancel_after_native_token_acquired_does_not_start_callback(cancellation):
    import anyio

    cpu = MemoryCpu()
    effects = []
    scope = anyio.CancelScope()

    async def borrower():
        with scope:
            await cpu.run(lambda: effects.append("dispatched"))

    task = asyncio.create_task(borrower())
    for _ in range(100):
        if cpu._admission.borrowed_tokens:
            break
        await asyncio.sleep(0)
    # Native acquire has taken its token, then yields its shielded checkpoint.
    assert cpu._admission.borrowed_tokens == 1 and effects == []
    if cancellation == "raw":
        task.cancel()
    else:
        scope.cancel()
    try:
        if cancellation == "raw":
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task
        assert effects == []
    finally:
        await cpu.aclose()


@pytest.mark.asyncio
async def test_close_joins_the_owned_executor_thread_and_is_idempotent():
    cpu = MemoryCpu()
    worker_thread = await cpu.run(threading.current_thread)
    assert worker_thread.is_alive()
    await cpu.aclose()
    await cpu.aclose()
    assert not worker_thread.is_alive()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellation", ["raw", "scope"])
async def test_late_worker_error_does_not_replace_borrower_cancellation(cancellation):
    import anyio

    cpu = MemoryCpu()
    started, release = threading.Event(), threading.Event()
    scope = anyio.CancelScope()

    def failing():
        started.set()
        assert release.wait(5)
        raise ValueError("late worker failure")

    async def borrow():
        with scope:
            await cpu.run(failing)

    task = asyncio.create_task(borrow())
    try:
        for _ in range(1000):
            if started.is_set():
                break
            await asyncio.sleep(0.001)
        assert started.is_set()
        if cancellation == "raw":
            task.cancel()
        else:
            scope.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        if cancellation == "raw":
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task
            assert scope.cancelled_caught
        assert await cpu.run(lambda: "next borrower") == "next borrower"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await cpu.aclose()
