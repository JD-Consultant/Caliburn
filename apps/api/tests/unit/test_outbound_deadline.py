"""The execution deadline bounds network waiting without losing a terminal R."""

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.result_save_retries import ResultSaveCancelledError
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponseCancelledError,
    run_response_step,
)
from caliburn.features.executions.budget_models import BudgetExceededError, BudgetLimit
from caliburn.workflows import model_requests
from tests.fixtures.response_capacity import synthetic_response_runtime
from tests.unit.test_response_streaming import client_for, request, terminal, wire_events


class DeadlineStream(httpx2.AsyncByteStream):
    def __init__(self, *, terminal_first=False):
        self.terminal_first = terminal_first
        self.closed = False
        self.chunks = 0
        self.started = asyncio.Event()
        self.cleanup_started = asyncio.Event()

    async def __aiter__(self):
        if self.terminal_first:
            import json

            yield f"data: {json.dumps(wire_events(terminal())[-1])}\n\n".encode()
        while True:
            await asyncio.sleep(0.005)
            self.chunks += 1
            self.started.set()
            yield b": synthetic heartbeat\n\n"

    async def aclose(self):
        if self.closed:
            return
        self.closed = True
        if self.terminal_first:
            # Deadline races with cleanup after a complete envelope has arrived.
            self.cleanup_started.set()
            await asyncio.Event().wait()


@pytest.fixture
def network_timeouts(monkeypatch):
    timers = []

    def capture(deadline):
        timer = asyncio.timeout_at(deadline)
        timers.append(timer)
        return timer

    monkeypatch.setattr(model_requests, "timeout_at", capture)
    return timers


async def expire_after_network_ready(wire, timers):
    ready = wire.cleanup_started if wire.terminal_first else wire.started
    async with asyncio.timeout(5):
        await ready.wait()
    assert len(timers) == 1
    timers[0].reschedule(asyncio.get_running_loop().time())


@pytest.mark.parametrize("terminal_first", [False, True])
async def test_network_deadline_stops_drips_or_hands_back_the_terminal(
    monkeypatch, terminal_first, network_timeouts
):
    attempt_id = uuid4()

    async def admit(*_args, **_kwargs):
        return SimpleNamespace(
            attempt_id=attempt_id, deadline=asyncio.get_running_loop().time() + 60
        )

    reserve = AsyncMock(side_effect=admit)
    record = AsyncMock(side_effect=AssertionError("A deadline never authorizes provider retry"))
    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_reserve_request", reserve)
    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_record_failure", record)
    wire, captured = DeadlineStream(terminal_first=terminal_first), []
    async with client_for(wire, captured) as client:
        executor = model_requests.ModelRequestExecutor(
            Mock(), Mock(), client, Mock(model=None, reserve_response_cost=lambda *_: Decimal("1"))
        )
        error_type = ReceivedModelResponseCancelledError if terminal_first else BudgetExceededError
        task = asyncio.create_task(executor.request_model(request(stream=True), uuid4(), 100))
        try:
            await expire_after_network_ready(wire, network_timeouts)
            with pytest.raises(error_type) as caught:
                await asyncio.wait_for(task, 5)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    if terminal_first:
        assert caught.value.received.attempt_id == attempt_id
        assert caught.value.received.response.id == terminal()["id"]
    else:
        assert caught.value.limit == BudgetLimit.DEADLINE
        assert wire.chunks > 0
    assert wire.closed
    assert len(captured) == 1
    record.assert_not_awaited()


async def test_expired_admission_does_not_start_network(monkeypatch):
    reserve = AsyncMock(
        return_value=SimpleNamespace(
            attempt_id=uuid4(), deadline=asyncio.get_running_loop().time() - 1
        )
    )
    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_reserve_request", reserve)
    send = AsyncMock(side_effect=AssertionError("An expired execution cannot start HTTP"))
    executor = model_requests.ModelRequestExecutor(Mock(), Mock(), Mock(), Mock(model=None))
    with pytest.raises(BudgetExceededError):
        await executor._send(uuid4(), model_requests.OutboundKind.MODEL, {}, Decimal("1"), send)
    send.assert_not_awaited()


async def test_terminal_deadline_does_not_cancel_the_following_checkpoint_save(
    monkeypatch, network_timeouts
):
    save_started, save_release = asyncio.Event(), asyncio.Event()

    class SlowSave(InMemorySaver):
        async def aput(self, config, checkpoint, metadata, new_versions):
            if checkpoint["channel_values"].get("response_snapshot") is not None:
                save_started.set()
                await save_release.wait()
            return await super().aput(config, checkpoint, metadata, new_versions)

    attempt_id = uuid4()

    async def admit(*_args, **_kwargs):
        return model_requests._OutboundAdmission(attempt_id, asyncio.get_running_loop().time() + 60)

    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_reserve_request", admit)
    saver = SlowSave()
    wire, captured = DeadlineStream(terminal_first=True), []
    forbidden = AsyncMock(side_effect=AssertionError("A stopped stream cannot start side effects"))
    async with client_for(wire, captured) as client:
        executor = model_requests.ModelRequestExecutor(
            Mock(), Mock(), client, Mock(model=None, reserve_response_cost=lambda *_: Decimal("1"))
        )
        task = asyncio.create_task(
            run_response_step(
                saver,
                thread_id="deadline-original",
                request=request(stream=True),
                max_tool_calls=16,
                runtime=synthetic_response_runtime(
                    request_model=executor.request_model,
                    ensure_active=AsyncMock(),
                    account_response=forbidden,
                    prepare_tool=forbidden,
                    execute_tool=forbidden,
                ),
            )
        )
        try:
            await expire_after_network_ready(wire, network_timeouts)
            async with asyncio.timeout(5):
                await save_started.wait()
            assert network_timeouts[0].expired()
            assert not task.done()
            save_release.set()
            with pytest.raises(ResultSaveCancelledError) as stopped:
                await asyncio.wait_for(task, 5)
        finally:
            save_release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    saved = await saver.aget_tuple({"configurable": {"thread_id": "deadline-original"}})
    assert saved.checkpoint["channel_values"]["response_snapshot"] == terminal()
    assert stopped.value.save_error.recovery.update["response_attempt_id"] == attempt_id
    assert len(captured) == 1
    forbidden.assert_not_awaited()


async def test_external_cancellation_is_not_reclassified_as_deadline(monkeypatch):
    async def admit(*_args, **_kwargs):
        return model_requests._OutboundAdmission(uuid4(), asyncio.get_running_loop().time() + 60)

    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_reserve_request", admit)
    wire, captured = DeadlineStream(), []
    async with client_for(wire, captured) as client:
        executor = model_requests.ModelRequestExecutor(
            Mock(), Mock(), client, Mock(model=None, reserve_response_cost=lambda *_: Decimal("1"))
        )
        task = asyncio.create_task(executor.request_model(request(stream=True), uuid4(), 100))
        try:
            async with asyncio.timeout(2):
                await wire.started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert task.cancelled()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert wire.closed
    assert len(captured) == 1
