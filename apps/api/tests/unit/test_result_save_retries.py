"""Only intact result handoffs may be automatically reconciled after saver faults."""

import asyncio
from dataclasses import replace

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from psycopg.errors import ConnectionFailure, UndefinedTable

from caliburn.agent_execution import result_save_retries
from caliburn.agent_execution.context_compaction import (
    CompactionSaveError,
    PreparationCountSaveError,
    prepare_context_history,
    run_context_compaction,
)
from caliburn.agent_execution.result_save_retries import ResultSaveRetryPolicy, retry_result_save
from caliburn.agent_execution.tool_steps import (
    InputCountSaveError,
    PausedResponseLoop,
    ResponseStepSaveError,
    run_response_loop,
    run_response_step,
)
from tests.fixtures.response_capacity import CapacityProbe, request_fixture
from tests.unit.test_context_compaction import COMPACTED, options
from tests.unit.test_response_pause import PauseProbe
from tests.unit.test_response_recovery import recording_runtime

NO_WAIT = ResultSaveRetryPolicy(max_attempts=3, initial_delay_seconds=0, max_delay_seconds=0)


class TransientResultFault(InMemorySaver):
    """Fail checkpoint and pending writes, then recover on the next inspection."""

    def __init__(self, channel, *, after_save=False, error_type=ConnectionFailure):
        super().__init__()
        self.channel = channel
        self.after_save = after_save
        self.error_type = error_type
        self.failed = False
        self.available = False
        self.reconciliations = 0

    async def aget_tuple(self, config):
        if self.failed and not self.available:
            self.available = True
            self.reconciliations += 1
        return await super().aget_tuple(config)

    async def aput(self, config, checkpoint, metadata, new_versions):
        if not self.available and checkpoint["channel_values"].get(self.channel) is not None:
            self.failed = True
            if self.after_save:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise self.error_type("synthetic saver failure")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if not self.available and any(key == self.channel for key, _ in writes):
            self.failed = True
            raise self.error_type("synthetic pending write failure")
        await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.parametrize("after_save", [False, True])
@pytest.mark.parametrize("loop", [False, True])
async def test_original_response_is_automatically_saved_without_second_model(loop, after_save):
    events = []
    saver = TransientResultFault("response_snapshot", after_save=after_save)
    args = dict(
        thread_id="automatic-response-save",
        request=request_fixture(),
        runtime=recording_runtime(events),
        max_tool_calls=2,
        save_retry_policy=NO_WAIT,
    )
    if loop:
        # The fixture requests a tool; stop after one Step to inspect original recovery.
        from caliburn.agent_execution.tool_steps import ModelStepLimitError

        with pytest.raises(ModelStepLimitError):
            await run_response_loop(saver, **args, max_model_steps=1)
    else:
        result = await run_response_step(saver, **args)
        assert len(result["tool_results"]) == 1
    assert events == ["model", "read"]
    assert saver.reconciliations == 1


async def test_original_input_count_is_saved_without_recounting():
    probe = CapacityProbe([100])
    result = await run_response_loop(
        TransientResultFault("input_count"),
        thread_id="automatic-count-save",
        request=request_fixture(),
        runtime=probe.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
        save_retry_policy=NO_WAIT,
    )
    assert result["completed_steps"] == 1
    assert len(probe.count_requests) == len(probe.model_requests) == 1


@pytest.mark.parametrize("channel", ["compaction_snapshot", "input_count"])
async def test_preparation_reuses_original_count_and_complete_compaction(channel):
    events = []
    args = options(events)
    counts = []

    async def count(request, request_id):
        counts.append(request_id)
        return args["input_count"]

    result = await prepare_context_history(
        TransientResultFault(channel),
        thread_id=args["thread_id"],
        history_request=args["request"],
        threshold_tokens=128_000,
        compact_requested=False,
        count_input=count,
        runtime=args["runtime"],
        save_retry_policy=NO_WAIT,
    )
    assert result == COMPACTED["output"]
    assert len(counts) == 1
    assert [event[0] for event in events] == ["compact", "account"]


@pytest.mark.parametrize("after_save", [False, True])
async def test_explicit_compaction_reuses_original_full_window(after_save):
    events = []
    result = await run_context_compaction(
        TransientResultFault("compaction_snapshot", after_save=after_save),
        **options(events),
        save_retry_policy=NO_WAIT,
    )
    assert result == COMPACTED["output"]
    assert [event[0] for event in events] == ["compact", "account"]


async def test_permanent_saver_error_returns_original_handoff_without_retry():
    saver = TransientResultFault("response_snapshot", error_type=UndefinedTable)
    events = []
    with pytest.raises(ResponseStepSaveError) as stopped:
        await run_response_step(
            saver,
            thread_id="permanent-save-error",
            request=request_fixture(),
            runtime=recording_runtime(events),
            max_tool_calls=2,
            save_retry_policy=NO_WAIT,
        )
    assert stopped.value.recovery.update["response_snapshot"]
    assert saver.reconciliations == 0
    assert events == ["model"]


async def test_cancelled_work_cannot_dispatch_tools_after_save_retry():
    saver = TransientResultFault("response_snapshot")
    events = []

    async def active():
        if saver.failed:
            raise PermissionError("synthetic cancelled writer")

    with pytest.raises(PermissionError, match="cancelled writer"):
        await run_response_step(
            saver,
            thread_id="cancel-during-save-retry",
            request=request_fixture(),
            runtime=replace(recording_runtime(events), ensure_active=active),
            max_tool_calls=2,
            save_retry_policy=NO_WAIT,
        )
    assert events == ["model"]


@pytest.fixture
def cancel_at_retry_wait(monkeypatch):
    def cancel_on_wait(retry_state):
        # The actual task cancellation arrives at the next suspension (backoff).
        task = asyncio.current_task()
        asyncio.get_running_loop().call_soon(task.cancel)
        return 0

    monkeypatch.setattr(
        result_save_retries, "wait_random_exponential", lambda **kwargs: cancel_on_wait
    )


@pytest.mark.parametrize("channel", ["response_snapshot", "input_count"])
async def test_cancelled_response_backoff_exposes_original_handoff(cancel_at_retry_wait, channel):
    saver = TransientResultFault(channel)
    probe = CapacityProbe([100])
    args = dict(
        thread_id="cancel-response-backoff",
        runtime=probe.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
        save_retry_policy=NO_WAIT,
    )
    task = asyncio.create_task(run_response_loop(saver, request=request_fixture(), **args))
    with pytest.raises(asyncio.CancelledError) as stopped:
        await task
    assert task.cancelled()
    assert saver.reconciliations == 0
    failure = getattr(stopped.value, "save_error", None)
    expected_error = (
        ResponseStepSaveError if channel == "response_snapshot" else InputCountSaveError
    )
    assert isinstance(failure, expected_error)
    assert failure.recovery.update[channel] is not None

    # The supervisor explicitly resumes the original work; cancellation itself does not retry.
    result = await run_response_loop(saver, request=None, recovery=failure.recovery, **args)
    assert result["completed_steps"] == 1
    assert len(probe.count_requests) == len(probe.model_requests) == 1


@pytest.mark.parametrize("channel", ["compaction_snapshot", "input_count"])
async def test_cancelled_preparation_backoff_exposes_original_handoff(
    cancel_at_retry_wait, channel
):
    saver = TransientResultFault(channel)
    events = []
    original = options(events)
    counts = []

    async def count(request, request_id):
        counts.append(request_id)
        return original["input_count"]

    args = dict(
        thread_id=original["thread_id"],
        history_request=original["request"],
        threshold_tokens=128_000,
        compact_requested=False,
        count_input=count,
        runtime=original["runtime"],
        save_retry_policy=NO_WAIT,
    )
    task = asyncio.create_task(prepare_context_history(saver, **args))
    with pytest.raises(asyncio.CancelledError) as stopped:
        await task
    assert task.cancelled()
    assert saver.reconciliations == 0
    failure = getattr(stopped.value, "save_error", None)
    expected_error = (
        CompactionSaveError if channel == "compaction_snapshot" else PreparationCountSaveError
    )
    assert isinstance(failure, expected_error)
    assert failure.recovery.update[channel] is not None

    result = await prepare_context_history(saver, recovery=failure.recovery, **args)
    assert result == COMPACTED["output"]
    assert len(counts) == 1
    assert [event[0] for event in events] == ["compact", "account"]


async def test_resumed_interrupt_is_not_replayed_when_next_response_needs_resaving():
    saver = TransientResultFault("response_snapshot")
    saver.available = True
    provider = CapacityProbe([100, 100], final=False)
    control = PauseProbe()

    async def model(request, request_id, input_tokens: int):
        if provider.model_requests:
            saver.available = False
        return await provider.model(request, request_id, input_tokens)

    args = dict(
        thread_id="resume-then-save-retry",
        runtime=replace(provider.runtime(), request_model=model),
        controls=control.controls(),
        max_tool_calls=2,
        max_model_steps=2,
        save_retry_policy=NO_WAIT,
    )
    paused = await run_response_loop(saver, request=request_fixture(), **args)
    assert isinstance(paused, PausedResponseLoop)
    control.requested = False
    result = await run_response_loop(
        saver, request=None, resume_interrupt_id=paused.interrupt_id, **args
    )
    assert result["completed_steps"] == 2
    assert len(provider.model_requests) == len(provider.count_requests) == 2
    assert saver.reconciliations == 1
    assert control.paused == 1


async def test_later_tool_driver_failure_is_not_a_result_save_retry():
    events = []

    async def prepare(call, operation_id):
        events.append("prepare")
        return {"operation_id": operation_id}

    async def execute(prepared):
        events.append("execute")
        raise ConnectionFailure("synthetic tool commit result unknown")

    with pytest.raises(ConnectionFailure):
        await run_response_step(
            TransientResultFault("response_snapshot"),
            thread_id="save-recovered-tool-unresolved",
            request=request_fixture(),
            runtime=replace(recording_runtime(events), prepare_tool=prepare, execute_tool=execute),
            max_tool_calls=2,
            save_retry_policy=NO_WAIT,
        )
    assert events == ["model", "prepare", "execute"]


async def test_later_tool_cancellation_does_not_expose_a_stale_save_handoff():
    events = []
    executing = asyncio.Event()

    async def prepare(call, operation_id):
        events.append("prepare")
        return {"operation_id": operation_id}

    async def execute(prepared):
        events.append("execute")
        executing.set()
        await asyncio.Future()

    task = asyncio.create_task(
        run_response_step(
            TransientResultFault("response_snapshot"),
            thread_id="cancel-after-result-save-recovery",
            request=request_fixture(),
            runtime=replace(recording_runtime(events), prepare_tool=prepare, execute_tool=execute),
            max_tool_calls=2,
            save_retry_policy=NO_WAIT,
        )
    )
    await asyncio.wait_for(executing.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as stopped:
        await task
    assert task.cancelled()
    assert getattr(stopped.value, "save_error", None) is None
    assert events == ["model", "prepare", "execute"]


@pytest.mark.parametrize("fault", [ConnectionFailure("not a held save"), asyncio.CancelledError()])
async def test_unwrapped_failure_and_cancellation_are_never_retried(fault):
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        raise fault

    with pytest.raises(type(fault)):
        await retry_result_save(operation, errors=(ResponseStepSaveError,), policy=NO_WAIT)
    assert calls == 1


async def test_retry_exhaustion_preserves_last_handoff_and_does_not_reset_budget():
    calls = 0
    failure = InputCountSaveError(None)  # Policy-only probe; no graph consumes this sentinel.

    async def operation():
        nonlocal calls
        calls += 1
        raise failure from ConnectionFailure("synthetic save unavailable")

    with pytest.raises(InputCountSaveError) as stopped:
        await retry_result_save(operation, errors=(InputCountSaveError,), policy=NO_WAIT)
    assert stopped.value is failure
    assert calls == 3


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"max_attempts": True},
        {"initial_delay_seconds": -1},
        {"max_delay_seconds": float("inf")},
        {"initial_delay_seconds": float("nan")},
        {"initial_delay_seconds": 2, "max_delay_seconds": 1},
    ],
)
def test_save_retry_policy_requires_finite_bounded_configuration(kwargs):
    with pytest.raises(ValueError):
        ResultSaveRetryPolicy(**kwargs)
