"""Offline SDK wire tests for public-only streaming and intact terminal handoff."""

import asyncio
import json
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.adapters import openai_responses as adapter
from caliburn.adapters.response_serialization import snapshot_response
from caliburn.adapters.response_streaming import (
    ResponseStreamCancelledError,
    ResponseStreamCleanupError,
)
from caliburn.agent_execution.result_save_retries import ResultSaveCancelledError
from caliburn.agent_execution.tool_steps import ResponseStepSaveError, run_response_step
from caliburn.workflows import model_requests
from tests.fixtures.response_capacity import synthetic_response_runtime


def request(*, stream=False):
    return adapter.ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic",
        input_items=[],
        tools=[],
        reasoning_effort="medium",
        max_output_tokens=1024,
        stream=stream,
    )


def terminal(status="completed"):
    raw = json.loads(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(encoding="utf-8")
    )
    raw["status"] = status
    # Invalid tool JSON must remain an original, not be eagerly parsed by a helper.
    raw["output"][2]["arguments"] = "{"
    return raw


def wire_events(raw):
    message = {
        "type": "message",
        "id": "msg_live",
        "role": "assistant",
        "phase": "commentary",
        "status": "in_progress",
        "content": [],
    }
    return [
        {"type": "response.created", "response": {**raw, "status": "in_progress", "output": []}},
        {"type": "response.output_item.added", "output_index": 0, "item": message},
        {
            "type": "response.output_text.delta",
            "item_id": "msg_live",
            "output_index": 0,
            "content_index": 0,
            "delta": "正在",
            "logprobs": [],
        },
        {
            "type": "response.reasoning_text.delta",
            "item_id": "rs_private",
            "output_index": 1,
            "content_index": 0,
            "delta": "PRIVATE_REASONING",
        },
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "fc_private",
            "output_index": 2,
            "delta": "PRIVATE_ARGUMENTS",
        },
        {
            "type": "response.output_text.delta",
            "item_id": "msg_live",
            "output_index": 0,
            "content_index": 0,
            "delta": "核對",
            "logprobs": [],
        },
        {
            "type": "response.output_item.added",
            "output_index": 3,
            "item": {**message, "id": "msg_final", "phase": "final_answer"},
        },
        {
            "type": "response.output_text.delta",
            "item_id": "msg_final",
            "output_index": 3,
            "content_index": 0,
            "delta": "FINAL_NOT_COMMENTARY",
            "logprobs": [],
        },
        {
            "type": "response.output_text.delta",
            "item_id": "unregistered",
            "output_index": 4,
            "content_index": 0,
            "delta": "UNKNOWN_PHASE",
            "logprobs": [],
        },
        {"type": "response." + raw["status"], "response": raw},
    ]


class WireStream(httpx2.AsyncByteStream):
    def __init__(self, events, *, close_error=None, read_error=None):
        self.events = events
        self.close_error = close_error
        self.closed = False
        self.read_error = read_error

    async def __aiter__(self):
        for number, event in enumerate(self.events):
            yield ("data: " + json.dumps({**event, "sequence_number": number}) + "\n\n").encode()
        if self.read_error is not None:
            raise self.read_error

    async def aclose(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def client_for(wire, captured):
    def respond(http_request):
        captured.append(json.loads(http_request.content))
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=wire)

    return adapter.create_responses_client(
        api_key="synthetic-only",
        timeout_seconds=1,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    )


@pytest.mark.parametrize("stream", [False, True])
def test_snapshot_restores_original_transport_without_changing_count_context(stream):
    original = request(stream=stream)
    restored = adapter.ResponseRequest.from_snapshot(original.create_payload())
    assert restored.create_payload()["stream"] is stream
    assert "stream" not in restored.count_payload()
    assert restored.count_payload() == request().count_payload()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "incomplete", "failed"])
async def test_native_terminal_is_preserved_and_only_commentary_is_projected(status):
    raw = terminal(status)
    captured, updates = [], []
    wire = WireStream(wire_events(raw))
    async with client_for(wire, captured) as client:
        result = await adapter.create_response(
            client, request(stream=True), on_commentary=updates.append
        )
    assert snapshot_response(result) == raw
    assert captured[0]["stream"] is True
    assert len(captured) == 1
    assert wire.closed
    assert [asdict(value) for value in updates] == [
        {"response_id": "resp_synthetic", "message_id": "msg_live", "text": "正在"},
        {"response_id": "resp_synthetic", "message_id": "msg_live", "text": "正在核對"},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("cancelled", [False, True])
async def test_terminal_cleanup_failure_hands_back_original_and_does_not_resend(cancelled):
    raw = terminal()
    captured = []
    failure = asyncio.CancelledError() if cancelled else OSError("synthetic close failure")
    wire = WireStream(wire_events(raw), close_error=failure)
    async with client_for(wire, captured) as client:
        error_type = ResponseStreamCancelledError if cancelled else ResponseStreamCleanupError
        with pytest.raises(error_type) as caught:
            await adapter.create_response(client, request(stream=True))
    assert snapshot_response(caught.value.response) == raw
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_commentary_observer_failure_does_not_discard_response(caplog):
    calls = []

    def broken(update):
        calls.append(update)
        raise RuntimeError("PRIVATE_OBSERVER_ERROR")

    raw = terminal()
    async with client_for(WireStream(wire_events(raw)), []) as client:
        result = await adapter.create_response(client, request(stream=True), on_commentary=broken)
    assert snapshot_response(result) == raw
    assert len(calls) == 1
    assert "PRIVATE_OBSERVER_ERROR" not in caplog.text


@pytest.mark.asyncio
async def test_eof_without_terminal_never_manufactures_a_response():
    async with client_for(WireStream(wire_events(terminal())[:-1]), []) as client:
        with pytest.raises(RuntimeError, match="terminal"):
            await adapter.create_response(client, request(stream=True))


@pytest.mark.asyncio
@pytest.mark.parametrize("cancelled", [False, True])
async def test_executor_handoff_attaches_original_attempt_without_failure_retry(
    monkeypatch, cancelled
):
    attempt_id = uuid4()
    captured, updates = [], []
    raw = terminal()
    failure = asyncio.CancelledError() if cancelled else OSError("synthetic close failure")
    reserve = AsyncMock(return_value=attempt_id)
    record = AsyncMock(side_effect=AssertionError("An intact R must not enter provider retry"))
    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_reserve_request", reserve)
    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_record_failure", record)
    accounting = Mock(model=None, reserved_cost_usd=1)
    async with client_for(WireStream(wire_events(raw), close_error=failure), captured) as client:
        executor = model_requests.ModelRequestExecutor(
            Mock(), Mock(), client, accounting, on_commentary=updates.append
        )
        error_type = (
            model_requests.ReceivedModelResponseCancelledError
            if cancelled
            else model_requests.ReceivedModelResponseError
        )
        with pytest.raises(error_type) as caught:
            await executor.request_model(request(stream=True), uuid4())
    assert caught.value.received.attempt_id == attempt_id
    assert snapshot_response(caught.value.received.response) == raw
    assert len(captured) == 1
    assert updates[-1].text == "正在核對"
    assert reserve.await_count == 1
    record.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "close_error",
    [OSError("cleanup failure"), httpx2.ReadError("transport cleanup failure")],
)
async def test_cancel_before_terminal_is_not_replaced_by_cleanup_error(close_error):
    wire = WireStream(
        wire_events(terminal())[:-1],
        read_error=asyncio.CancelledError(),
        close_error=close_error,
    )
    async with client_for(wire, []) as client:
        with pytest.raises(asyncio.CancelledError) as caught:
            await adapter.create_response(client, request(stream=True))
    assert not hasattr(caught.value, "response")


@pytest.mark.asyncio
async def test_done_replaces_parts_without_duplicates_and_updates_are_immutable():
    raw = terminal()
    events = wire_events(raw)
    events[-1:-1] = [
        {
            "type": "response.output_text.done",
            "item_id": "msg_live",
            "output_index": 0,
            "content_index": 0,
            "text": "正在核對",
            "logprobs": [],
        },
        {
            "type": "response.refusal.delta",
            "item_id": "msg_live",
            "output_index": 0,
            "content_index": 1,
            "delta": "不提供私有分析",
        },
        {
            "type": "response.refusal.done",
            "item_id": "msg_live",
            "output_index": 0,
            "content_index": 1,
            "refusal": "不提供私有分析",
        },
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "type": "message",
                "id": "msg_live",
                "role": "assistant",
                "phase": "commentary",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": "正在核對", "annotations": []},
                    {"type": "refusal", "refusal": "不提供私有分析"},
                ],
            },
        },
    ]
    updates = []
    async with client_for(WireStream(events), []) as client:
        await adapter.create_response(client, request(stream=True), on_commentary=updates.append)
    assert [update.text for update in updates] == ["正在", "正在核對", "正在核對\n\n不提供私有分析"]
    with pytest.raises(FrozenInstanceError):
        updates[-1].text = "changed"
    assert "正在" not in repr(updates[-1])


@pytest.mark.asyncio
async def test_terminal_does_not_wait_for_or_retry_a_broken_tail():
    raw = terminal()
    wire = WireStream(wire_events(raw), read_error=AssertionError("Do not read beyond terminal"))
    async with client_for(wire, []) as client:
        result = await adapter.create_response(client, request(stream=True))
    assert snapshot_response(result) == raw


@pytest.mark.asyncio
async def test_task_cancel_during_terminal_cleanup_hands_off_original_without_resume():
    raw = terminal()
    closing = asyncio.Event()
    captured = []

    class ClosingStream(WireStream):
        async def aclose(self):
            self.closed = True
            closing.set()
            await asyncio.Event().wait()

    async with client_for(ClosingStream(wire_events(raw)), captured) as client:
        task = asyncio.create_task(adapter.create_response(client, request(stream=True)))
        await asyncio.wait_for(closing.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
    assert snapshot_response(caught.value.response) == raw
    assert task.cancelled()
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_absent_commentary_and_unknown_phase_are_normal_not_synthesized():
    raw = terminal()
    events = wire_events(raw)
    events[1]["item"].pop("phase")
    updates = []
    async with client_for(WireStream(events), []) as client:
        result = await adapter.create_response(
            client, request(stream=True), on_commentary=updates.append
        )
    assert snapshot_response(result) == raw
    assert updates == []


@pytest.mark.asyncio
async def test_text_for_a_mismatched_output_index_is_not_public():
    raw = terminal()
    events = wire_events(raw)
    events.insert(3, {**events[2], "output_index": 2, "delta": "PRIVATE_WRONG_ITEM"})
    updates = []
    async with client_for(WireStream(events), []) as client:
        await adapter.create_response(client, request(stream=True), on_commentary=updates.append)
    assert [update.text for update in updates] == ["正在", "正在核對"]


@pytest.mark.asyncio
@pytest.mark.parametrize("cancelled", [False, True])
async def test_sdk_executor_shared_step_saves_terminal_before_surfacing_cleanup(
    monkeypatch, cancelled
):
    raw = terminal()
    attempt_id = uuid4()
    captured = []
    saver = InMemorySaver()
    reserve = AsyncMock(return_value=attempt_id)
    record = AsyncMock(side_effect=AssertionError("Never resend an intact R"))
    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_reserve_request", reserve)
    monkeypatch.setattr(model_requests.ModelRequestExecutor, "_record_failure", record)
    no_effects = AsyncMock(side_effect=AssertionError("Cleanup must stop before tools/accounting"))
    failure = asyncio.CancelledError() if cancelled else OSError("synthetic cleanup")
    async with client_for(WireStream(wire_events(raw), close_error=failure), captured) as client:
        executor = model_requests.ModelRequestExecutor(
            Mock(), Mock(), client, Mock(model=None, reserved_cost_usd=1)
        )
        runtime = synthetic_response_runtime(
            request_model=executor.request_model,
            prepare_tool=no_effects,
            execute_tool=no_effects,
            account_response=no_effects,
            ensure_active=AsyncMock(),
        )
        with pytest.raises(
            ResultSaveCancelledError if cancelled else ResponseStepSaveError
        ) as caught:
            await run_response_step(
                saver,
                thread_id="wire-to-original",
                request=request(stream=True),
                runtime=runtime,
                max_tool_calls=16,
            )
    stop = caught.value.save_error if cancelled else caught.value
    assert stop.recovery.update["response_snapshot"] == raw
    assert stop.recovery.update["response_attempt_id"] == attempt_id
    saved = await saver.aget_tuple({"configurable": {"thread_id": "wire-to-original"}})
    assert saved.checkpoint["channel_values"]["response_snapshot"] == raw
    assert saved.checkpoint["channel_values"]["response_attempt_id"] == attempt_id
    assert len(captured) == reserve.await_count == 1
    record.assert_not_awaited()
    no_effects.assert_not_awaited()
