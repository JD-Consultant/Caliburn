"""A complete terminal carrier reaches the native save boundary before any effects."""

import asyncio
from dataclasses import replace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.result_save_retries import ResultSaveCancelledError
from caliburn.agent_execution.tool_steps import ResponseStepSaveError, run_response_step
from caliburn.workflows.model_requests import (
    ReceivedModelResponseCancelledError,
    ReceivedModelResponseError,
)
from tests.fixtures.response_capacity import CapacityProbe, request_fixture
from tests.unit.test_response_recovery import EntireResponseSaveFault
from tests.unit.test_result_save_retries import TransientResultFault


@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("save_fails", [False, True])
async def test_terminal_carrier_saves_or_holds_original_without_effects(cancelled, save_fails):
    saver = EntireResponseSaveFault() if save_fails else InMemorySaver()
    probe = CapacityProbe([100])
    accounted = []
    received = None

    async def model(request, request_id):
        nonlocal received
        received = await probe.model(request, request_id)
        kind = ReceivedModelResponseCancelledError if cancelled else ReceivedModelResponseError
        raise kind(received)

    async def account(response):
        accounted.append(response.attempt_id)

    args = dict(
        thread_id="terminal-carrier",
        max_tool_calls=2,
        runtime=replace(probe.runtime(), request_model=model, account_response=account),
    )
    task = asyncio.create_task(run_response_step(saver, request=request_fixture(), **args))
    with pytest.raises(asyncio.CancelledError if cancelled else Exception) as stopped:
        await task
    assert task.cancelled() is cancelled
    failure = (
        stopped.value.save_error
        if isinstance(stopped.value, ResultSaveCancelledError)
        else stopped.value
    )
    assert isinstance(failure, ResponseStepSaveError)
    assert failure.recovery.update["response_attempt_id"] == received.attempt_id
    assert failure.recovery.update["response_snapshot"] == received.response.model_dump(
        mode="json", exclude_unset=True
    )
    assert accounted == []
    if not save_fails:
        saved = await saver.aget_tuple({"configurable": {"thread_id": "terminal-carrier"}})
        assert saved.checkpoint["channel_values"]["response_snapshot"]
    else:
        saver.fail_response_saves = False
    result = await run_response_step(saver, request=None, recovery=failure.recovery, **args)
    assert result["response_attempt_id"] == received.attempt_id
    assert len(probe.model_requests) == len(probe.count_requests) == 1
    assert accounted == [received.attempt_id]


async def test_real_task_cancellation_after_terminal_retains_original_without_effects():
    saver = InMemorySaver()
    probe = CapacityProbe([100])
    closing = asyncio.Event()
    accounted = []

    async def model(request, request_id):
        original = await probe.model(request, request_id)
        closing.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            raise ReceivedModelResponseCancelledError(original) from None

    async def account(response):
        accounted.append(response.attempt_id)

    args = dict(
        thread_id="actual-terminal-cancel",
        max_tool_calls=2,
        runtime=replace(probe.runtime(), request_model=model, account_response=account),
    )
    task = asyncio.create_task(run_response_step(saver, request=request_fixture(), **args))
    await asyncio.wait_for(closing.wait(), timeout=5)
    task.cancel()
    with pytest.raises(ResultSaveCancelledError) as stopped:
        await task
    assert task.cancelled()
    failure = stopped.value.save_error
    assert isinstance(failure, ResponseStepSaveError)
    assert accounted == []
    # A real task cancellation can interrupt native cleanup: retain, then join its
    # exact native task references before explicitly reentering this test workflow.
    error = stopped.value
    while error is not None:
        tasks = [arg for arg in error.args if isinstance(arg, asyncio.Task)]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        error = error.__cause__
    result = await run_response_step(saver, request=None, recovery=failure.recovery, **args)
    assert result["response_attempt_id"] == failure.recovery.update["response_attempt_id"]
    assert len(probe.model_requests) == 1
    assert len(accounted) == 1


async def test_terminal_cancel_plus_transient_save_fault_never_becomes_automatic_resume():
    saver = TransientResultFault("response_snapshot")
    probe = CapacityProbe([100])

    async def model(request, request_id):
        raise ReceivedModelResponseCancelledError(await probe.model(request, request_id))

    with pytest.raises(ResultSaveCancelledError) as stopped:
        await run_response_step(
            saver,
            thread_id="cancel-not-resave-retry",
            request=request_fixture(),
            runtime=replace(probe.runtime(), request_model=model),
            max_tool_calls=2,
        )
    assert isinstance(stopped.value.save_error, ResponseStepSaveError)
    assert saver.reconciliations == 0
    assert len(probe.count_requests) == len(probe.model_requests) == 1
