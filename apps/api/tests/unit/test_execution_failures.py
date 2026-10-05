"""An unavailable settlement is not a successful rollback."""

import asyncio
from uuid import uuid4

import pytest

from caliburn.agent_execution.result_save_retries import ResultSaveCancelledError
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.workflows.execution_failures import run_with_failure_boundary


async def test_settlement_failure_propagates_without_retrying_work():
    writer = ExecutionWriter(
        ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN), uuid4()
    )
    calls = []

    async def failed_work(current):
        calls.append(current)
        raise ValueError("invalid work")

    async def unavailable_owner(current, error):
        assert current == writer
        raise ConnectionError("database unavailable")

    with pytest.raises(ConnectionError, match="database unavailable"):
        await run_with_failure_boundary(writer, run=failed_work, settle_failure=unavailable_owner)
    assert calls == [writer]


@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("cancel_again", [False, True])
async def test_native_cleanup_finishes_before_failure_or_cancellation_leaves_the_boundary(
    cancelled, cancel_again
):
    writer = ExecutionWriter(
        ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN), uuid4()
    )
    release = asyncio.Event()
    exiting = asyncio.Event()
    saved = asyncio.Event()
    settlements = []
    native = None
    error = (
        ResultSaveCancelledError(ValueError("held original"))
        if cancelled
        else ValueError("work failed")
    )

    async def cleanup():
        await release.wait()
        saved.set()

    async def failed_work(current):
        nonlocal native
        native = asyncio.create_task(cleanup())
        exiting.set()
        # Same exact task handoff used by the pinned LangGraph exit boundary.
        raise error from asyncio.CancelledError(native)

    async def settle(current, original):
        assert saved.is_set()
        settlements.append(original)

    invocation = asyncio.create_task(
        run_with_failure_boundary(writer, run=failed_work, settle_failure=settle)
    )
    try:
        await exiting.wait()
        assert not invocation.done(), "The invocation must retain ownership of native cleanup"
        if cancel_again:
            invocation.cancel()
            await asyncio.sleep(0)
            assert not invocation.done()
        release.set()
        if cancelled or cancel_again:
            with pytest.raises(asyncio.CancelledError) as stopped:
                await invocation
            if cancelled:
                assert stopped.value is error
            assert not settlements
        else:
            await invocation
            assert settlements == [error]
        assert saved.is_set()
    finally:
        release.set()
        await asyncio.gather(invocation, return_exceptions=True)
        if native is not None:
            await asyncio.gather(native, return_exceptions=True)
