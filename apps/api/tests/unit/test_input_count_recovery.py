"""An intact remote count must survive saver failure without another remote request."""

from dataclasses import replace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.tool_steps import (
    InputCountSaveError,
    PausedResponseLoop,
    ResponseLoopControls,
    run_response_loop,
)
from tests.fixtures.response_capacity import CapacityProbe, request_fixture


class InputCountSaveFault(InMemorySaver):
    fail_count_saves = True
    fail_after_commit = False
    fail_pending_writes = True
    fail_control_confirmation = False

    async def aput(self, config, checkpoint, metadata, new_versions):
        if (
            self.fail_control_confirmation
            and checkpoint["channel_values"].get("control_action") == "continue"
        ):
            self.fail_control_confirmation = False
            await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic saved control acknowledgement lost")
        if self.fail_count_saves and checkpoint["channel_values"].get("input_count"):
            if self.fail_after_commit:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic count checkpoint unavailable")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if (
            self.fail_count_saves
            and self.fail_pending_writes
            and any(name == "input_count" for name, _ in writes)
        ):
            raise ConnectionError("synthetic count pending writes unavailable")
        await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.parametrize("save_mode", ["before_save", "after_save", "pending_only"])
async def test_count_save_failure_returns_original_and_recovery_does_not_recount(
    save_mode,
):
    saver = InputCountSaveFault()
    saver.fail_after_commit = save_mode == "after_save"
    saver.fail_pending_writes = save_mode != "pending_only"
    probe = CapacityProbe([100])
    options = dict(
        thread_id="held-count", runtime=probe.runtime(), max_tool_calls=2, max_model_steps=2
    )
    with pytest.raises(InputCountSaveError) as failure:
        await run_response_loop(saver, request=request_fixture(), **options)
    assert len(probe.count_requests) == 1
    assert not probe.model_requests
    assert hasattr(failure.value, "recovery"), "The intact count must reach the recovery caller"
    original = failure.value.recovery
    assert "synthetic pinned map" not in repr(original)
    if save_mode == "before_save":
        with pytest.raises(InputCountSaveError) as again:
            await run_response_loop(saver, request=None, recovery=original, **options)
        assert again.value.recovery is original
    saver.fail_count_saves = False
    result = await run_response_loop(saver, request=None, recovery=original, **options)
    assert result["input_count"]["input_tokens"] == 100
    assert result["completed_steps"] == 1
    assert len(probe.count_requests) == len(probe.model_requests) == 1
    assert await run_response_loop(saver, request=None, recovery=original, **options) == result
    assert len(probe.count_requests) == len(probe.model_requests) == 1


async def test_count_handoff_cannot_change_request_or_thread():
    saver = InputCountSaveFault()
    probe = CapacityProbe([100])
    options = dict(
        thread_id="count-identity", runtime=probe.runtime(), max_tool_calls=2, max_model_steps=2
    )
    with pytest.raises(InputCountSaveError) as failure:
        await run_response_loop(saver, request=request_fixture(), **options)
    original = failure.value.recovery
    saver.fail_count_saves = False
    with pytest.raises(ValueError, match="original Step"):
        await run_response_loop(
            saver, request=None, recovery=replace(original, thread_id="elsewhere"), **options
        )
    with pytest.raises(ValueError, match="saved request boundary"):
        await run_response_loop(
            saver, request=None, recovery=replace(original, request_snapshot={}), **options
        )
    assert not probe.model_requests
    assert len(probe.count_requests) == 1


@pytest.mark.parametrize("fail_after_commit", [False, True])
async def test_cancelled_work_cannot_adopt_held_count_or_generate(fail_after_commit):
    saver = InputCountSaveFault()
    saver.fail_after_commit = fail_after_commit
    probe = CapacityProbe([100])
    options = dict(thread_id="cancel-count", max_tool_calls=2, max_model_steps=2)
    with pytest.raises(InputCountSaveError) as failure:
        await run_response_loop(
            saver, request=request_fixture(), runtime=probe.runtime(), **options
        )
    saver.fail_count_saves = False

    async def cancelled():
        raise PermissionError("synthetic cancelled writer")

    with pytest.raises(PermissionError, match="cancelled writer"):
        await run_response_loop(
            saver,
            request=None,
            recovery=failure.value.recovery,
            runtime=replace(probe.runtime(), ensure_active=cancelled),
            **options,
        )
    assert not probe.model_requests
    assert len(probe.count_requests) == 1


async def test_adopted_count_still_enforces_capacity_and_is_not_a_save_failure():
    saver = InputCountSaveFault()
    probe = CapacityProbe([901])
    options = dict(
        thread_id="too-large-count",
        runtime=probe.runtime(max_input_tokens=900),
        max_tool_calls=2,
        max_model_steps=2,
    )
    with pytest.raises(InputCountSaveError) as failure:
        await run_response_loop(saver, request=request_fixture(), **options)
    saver.fail_count_saves = False
    for recovery in (failure.value.recovery, None):
        with pytest.raises(ValueError, match="capacity"):
            await run_response_loop(saver, request=None, recovery=recovery, **options)
    assert not probe.model_requests
    assert len(probe.count_requests) == 1


@pytest.mark.parametrize("final", [False, True])
async def test_repeated_count_handoff_does_not_bypass_new_pause_at_completed_step(final):
    saver = InputCountSaveFault()
    probe = CapacityProbe([100, 100], final=final)
    requested = False

    async def read_pause():
        return requested

    async def mark_paused():
        pass

    options = dict(
        thread_id="count-then-pause",
        runtime=probe.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
        controls=ResponseLoopControls(read_pause, mark_paused),
    )
    with pytest.raises(InputCountSaveError) as failure:
        await run_response_loop(saver, request=request_fixture(), **options)
    original = failure.value.recovery
    saver.fail_count_saves = False
    saver.fail_control_confirmation = True
    with pytest.raises(ConnectionError, match="control acknowledgement"):
        await run_response_loop(saver, request=None, recovery=original, **options)
    requested = True
    result = await run_response_loop(saver, request=None, recovery=original, **options)
    assert isinstance(result, PausedResponseLoop)
    assert result.state["completed_steps"] == 1
    assert len(probe.count_requests) == len(probe.model_requests) == 1
