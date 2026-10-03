"""Task cancellation inside a saver must hand back the intact original, not retry it."""

import asyncio
from dataclasses import replace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.context_compaction import (
    CompactionSaveError,
    PreparationCountSaveError,
    prepare_context_history,
    run_context_compaction,
)
from caliburn.agent_execution.result_save_retries import ResultSaveCancelledError
from caliburn.agent_execution.tool_steps import (
    InputCountSaveError,
    ResponseStepSaveError,
    run_response_loop,
)
from tests.fixtures.response_capacity import CapacityProbe, request_fixture
from tests.unit.test_context_compaction import COMPACTED, options


class CancelDuringSave(InMemorySaver):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.available = False

    async def block(self):
        self.entered.set()
        await self.release.wait()
        raise ConnectionError("synthetic original result save unavailable")

    async def aput(self, config, checkpoint, metadata, new_versions):
        if not self.available and checkpoint["channel_values"].get(self.channel) is not None:
            await self.block()
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if not self.available and any(key == self.channel for key, _ in writes):
            await self.block()
        await super().aput_writes(config, writes, task_id, task_path)


async def cancel_saving(task, saver):
    await asyncio.wait_for(saver.entered.wait(), timeout=5)
    task.cancel()
    saver.release.set()
    with pytest.raises(asyncio.CancelledError) as stopped:
        await task
    # Drain native LangGraph cleanup references; task cancellation is not cleanup proof.
    error = stopped.value
    while error is not None:
        pending = [arg for arg in error.args if isinstance(arg, asyncio.Task)]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        error = error.__cause__
    assert task.cancelled()
    assert isinstance(stopped.value, ResultSaveCancelledError)
    return stopped.value.save_error


@pytest.mark.parametrize("channel", ["response_snapshot", "input_count"])
@pytest.mark.parametrize("cancel_repair", [False, True])
async def test_cancel_inside_response_save_keeps_original_for_explicit_reentry(
    channel, cancel_repair
):
    saver = CancelDuringSave(channel)
    probe = CapacityProbe([100])
    args = dict(
        thread_id="cancel-inside-response-save",
        runtime=probe.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
    )
    failure = await cancel_saving(
        asyncio.create_task(run_response_loop(saver, request=request_fixture(), **args)), saver
    )
    expected = ResponseStepSaveError if channel == "response_snapshot" else InputCountSaveError
    assert isinstance(failure, expected)
    assert len(probe.count_requests) == 1
    assert len(probe.model_requests) == (1 if channel == "response_snapshot" else 0)
    if cancel_repair:
        saver.entered.clear()
        saver.release.clear()
        original = failure.recovery
        failure = await cancel_saving(
            asyncio.create_task(run_response_loop(saver, request=None, recovery=original, **args)),
            saver,
        )
        assert failure.recovery == original
    saver.available = True
    result = await run_response_loop(saver, request=None, recovery=failure.recovery, **args)
    assert result["completed_steps"] == 1
    assert len(probe.count_requests) == len(probe.model_requests) == 1


@pytest.mark.parametrize("channel", ["compaction_snapshot", "input_count"])
@pytest.mark.parametrize("cancel_repair", [False, True])
async def test_cancel_inside_preparation_save_keeps_original_without_recount_or_recompact(
    channel,
    cancel_repair,
):
    saver = CancelDuringSave(channel)
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
    )
    failure = await cancel_saving(
        asyncio.create_task(prepare_context_history(saver, **args)), saver
    )
    expected = (
        CompactionSaveError if channel == "compaction_snapshot" else PreparationCountSaveError
    )
    assert isinstance(failure, expected)
    assert len(counts) == 1
    assert [event[0] for event in events] == (
        ["compact"] if channel == "compaction_snapshot" else []
    )
    if cancel_repair:
        saver.entered.clear()
        saver.release.clear()
        held = failure.recovery
        failure = await cancel_saving(
            asyncio.create_task(prepare_context_history(saver, recovery=held, **args)), saver
        )
        assert failure.recovery == held
    saver.available = True
    assert (
        await prepare_context_history(saver, recovery=failure.recovery, **args)
        == COMPACTED["output"]
    )
    assert len(counts) == 1
    assert [event[0] for event in events] == ["compact", "account"]


async def test_cancel_inside_direct_compaction_save_keeps_complete_original_window():
    saver = CancelDuringSave("compaction_snapshot")
    events = []
    args = options(events)
    failure = await cancel_saving(asyncio.create_task(run_context_compaction(saver, **args)), saver)
    assert isinstance(failure, CompactionSaveError)
    saver.available = True
    assert (
        await run_context_compaction(saver, recovery=failure.recovery, **args)
        == COMPACTED["output"]
    )
    assert [event[0] for event in events] == ["compact", "account"]


async def test_parent_loop_preserves_cancelled_child_compaction_handoff():
    saver = CancelDuringSave("compaction_snapshot")
    events = []
    original = options(events)
    probe = CapacityProbe([100, 272_000, 100], final=False)
    held = None

    async def compact(request, count, request_id):
        return await run_context_compaction(
            saver,
            thread_id=f"nested-compact:{request_id}",
            request=request,
            input_count=count,
            runtime=original["runtime"],
            recovery=held,
        )

    args = dict(
        thread_id="cancel-nested-compact",
        runtime=replace(probe.runtime(), compact_window=compact),
        max_tool_calls=2,
        max_model_steps=3,
    )
    failure = await cancel_saving(
        asyncio.create_task(run_response_loop(saver, request=request_fixture(), **args)), saver
    )
    assert isinstance(failure, CompactionSaveError)
    held = failure.recovery
    saver.available = True
    result = await run_response_loop(saver, request=None, **args)
    assert result["next_action"] == "deliver_answer"
    assert len(probe.count_requests) == 3
    assert len(probe.model_requests) == 2
    assert [event[0] for event in events] == ["compact", "account"]
