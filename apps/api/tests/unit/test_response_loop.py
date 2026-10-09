"""Native multi-Step execution must advance without losing history or replaying effects."""

from copy import deepcopy
from dataclasses import replace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.tool_steps import (
    ModelStepLimitError,
    ResponseStepSaveError,
    _build_response_step,
    run_response_loop,
    run_response_step,
)
from tests.fixtures.response_loop import LoopProbe, initial_request, response_at


@pytest.mark.asyncio
async def test_loop_preserves_native_history_and_orders_calls_until_final() -> None:
    # A final message beside calls is not completion; commentary alone must also continue.
    probe = LoopProbe(
        [response_at(1, final=True, tools=2), response_at(2), response_at(3, final=True)]
    )
    saver = InMemorySaver()
    options = {
        "thread_id": "three-steps",
        "runtime": probe.runtime(),
        "max_tool_calls": 4,
        "max_model_steps": 3,
    }
    result = await run_response_loop(saver, request=initial_request(), **options)
    assert len(probe.requests) == 3
    assert len(set(probe.request_ids)) == 3
    assert probe.effects == ["call_1_0", "call_1_1"]
    assert probe.accounted == ["response_1", "response_2", "response_3"]
    assert result["next_action"] == "deliver_answer"
    assert result["completed_steps"] == 3
    assert len(result["input_items"]) == 12
    assert [item["type"] for item in probe.requests[1]["input"][2:]] == [
        "reasoning",
        "message",
        "function_call",
        "function_call",
        "function_call_output",
        "function_call_output",
    ]
    assert probe.requests[1]["input"][2]["encrypted_content"] == "synthetic-opaque-1"
    assert probe.requests[1]["input"][3]["phase"] == "final_answer"
    assert probe.requests[2]["input"][:8] == probe.requests[1]["input"]
    for request in probe.requests:
        assert {key: value for key, value in request.items() if key != "input"} == {
            key: value
            for key, value in initial_request().create_payload().items()
            if key != "input"
        }
    completed = deepcopy(result)
    assert await run_response_loop(saver, request=None, **options) == completed
    assert len(probe.requests) == 3
    assert probe.effects == ["call_1_0", "call_1_1"]


@pytest.mark.asyncio
async def test_exhausted_loop_keeps_last_step_and_cannot_reset_limits_on_resume() -> None:
    probe = LoopProbe([response_at(1, tools=1), response_at(2)])
    saver = InMemorySaver()
    options = {
        "thread_id": "bounded",
        "runtime": probe.runtime(),
        "max_tool_calls": 4,
        "max_model_steps": 2,
    }
    for request in (initial_request(), None):
        with pytest.raises(ModelStepLimitError):
            await run_response_loop(saver, request=request, **options)
    saved = await _build_response_step(saver, max_tool_calls=4, max_model_steps=2).aget_state(
        {"configurable": {"thread_id": "bounded"}}
    )
    assert saved.values["completed_steps"] == 2
    assert saved.next == ("prepare_next_request",)
    assert len(saved.values["input_items"]) == 8
    assert len(probe.requests) == 2
    assert probe.effects == ["call_1_0"]
    for changed in ({"max_model_steps": 3}, {"max_tool_calls": 8}):
        with pytest.raises(ValueError, match="original execution mode and limits"):
            await run_response_loop(saver, request=None, **{**options, **changed})
    with pytest.raises(ValueError, match="original execution mode and limits"):
        await run_response_step(
            saver, thread_id="bounded", request=None, runtime=probe.runtime(), max_tool_calls=4
        )
    with pytest.raises(ValueError, match="already exists"):
        await run_response_loop(saver, request=initial_request(), **options)
    assert len(probe.requests) == 2


@pytest.mark.asyncio
async def test_second_step_tool_failure_resumes_only_pending_tool_then_continues() -> None:
    probe = LoopProbe(
        [response_at(1, tools=1), response_at(2, tools=2), response_at(3, final=True)]
    )
    failed_command = None

    async def fail_last_tool(command: object) -> str:
        nonlocal failed_command
        assert isinstance(command, dict)
        if command["call_id"] == "call_2_1":
            failed_command = deepcopy(command)
            raise ConnectionError("synthetic before effect")
        return await probe.execute(command)

    saver = InMemorySaver()
    options = {"thread_id": "tool-recovery", "max_tool_calls": 4, "max_model_steps": 3}
    with pytest.raises(ConnectionError):
        await run_response_loop(
            saver,
            request=initial_request(),
            runtime=replace(probe.runtime(), execute_tool=fail_last_tool),
            **options,
        )
    assert len(probe.requests) == 2
    assert probe.effects == ["call_1_0", "call_2_0"]

    async def resume_tool(command: object) -> str:
        assert command == failed_command
        return await probe.execute(command)

    result = await run_response_loop(
        saver, request=None, runtime=replace(probe.runtime(), execute_tool=resume_tool), **options
    )
    assert result["completed_steps"] == 3
    assert len(probe.requests) == 3
    assert probe.effects == ["call_1_0", "call_2_0", "call_2_1"]
    assert len(result["input_items"]) == 14


class SecondResponseSaveFault(InMemorySaver):
    fail = True

    async def aput(self, config, checkpoint, metadata, new_versions):
        response = checkpoint["channel_values"].get("response_snapshot", {})
        if self.fail and response.get("id") == "response_2":
            raise ConnectionError("synthetic second response checkpoint unavailable")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if self.fail and any(
            name == "response_snapshot" and value.get("id") == "response_2"
            for name, value in writes
        ):
            raise ConnectionError("synthetic second response pending writes unavailable")
        await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.asyncio
async def test_second_response_held_recovery_does_not_confuse_previous_response() -> None:
    saver = SecondResponseSaveFault()
    probe = LoopProbe(
        [response_at(1, tools=1), response_at(2, tools=1), response_at(3, final=True)]
    )
    options = {
        "thread_id": "held-second",
        "runtime": probe.runtime(),
        "max_tool_calls": 4,
        "max_model_steps": 3,
    }
    with pytest.raises(ResponseStepSaveError) as failure:
        await run_response_loop(saver, request=initial_request(), **options)
    held = failure.value.recovery
    assert held.request_id == probe.request_ids[1]
    assert held.update["response_snapshot"]["id"] == "response_2"
    assert probe.effects == ["call_1_0"]
    saver.fail = False
    result = await run_response_loop(saver, request=None, recovery=held, **options)
    assert result["completed_steps"] == 3
    assert probe.effects == ["call_1_0", "call_2_0"]
    assert len(probe.requests) == 3
    # A later Step cannot adopt an older held result and rewind the loop.
    with pytest.raises(ValueError, match="saved request boundary"):
        await run_response_loop(saver, request=None, recovery=held, **options)


class NextRequestSaveFault(InMemorySaver):
    fail = True
    fail_after_commit = False

    async def aput(self, config, checkpoint, metadata, new_versions):
        state = checkpoint["channel_values"]
        if self.fail and state.get("completed_steps") == 1 and state.get("response_snapshot") == {}:
            if self.fail_after_commit:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic next request save confirmation failure")
        return await super().aput(config, checkpoint, metadata, new_versions)


@pytest.mark.asyncio
async def test_initial_input_checkpoint_resumes_without_resetting_saved_limits() -> None:
    class InitialExpansionFault(InMemorySaver):
        fail = True

        async def aput(self, config, checkpoint, metadata, new_versions):
            if self.fail and metadata["source"] != "input":
                raise ConnectionError("synthetic start checkpoint unavailable")
            return await super().aput(config, checkpoint, metadata, new_versions)

        async def aput_writes(self, config, writes, task_id, task_path=""):
            if self.fail:
                raise ConnectionError("synthetic start pending writes unavailable")
            await super().aput_writes(config, writes, task_id, task_path)

    saver = InitialExpansionFault()
    probe = LoopProbe([response_at(1), response_at(2, final=True)])
    options = {
        "thread_id": "initial-input",
        "runtime": probe.runtime(),
        "max_tool_calls": 4,
        "max_model_steps": 2,
    }
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=initial_request(), **options)
    saved = await _build_response_step(saver, max_tool_calls=4, max_model_steps=2).aget_state(
        {"configurable": {"thread_id": "initial-input"}}
    )
    assert not saved.values
    assert saved.next == ("__start__",)
    assert not probe.requests
    saver.fail = False
    with pytest.raises(ValueError, match="original execution mode and limits"):
        await run_response_loop(saver, request=None, **{**options, "max_model_steps": 3})
    assert not probe.requests
    result = await run_response_loop(saver, request=None, **options)
    assert result["completed_steps"] == 2
    assert len(probe.requests) == 2


@pytest.mark.parametrize("fail_after_commit", [False, True])
@pytest.mark.asyncio
async def test_next_request_is_saved_before_http_and_restored_without_duplicate_items(
    fail_after_commit: bool,
) -> None:
    saver = NextRequestSaveFault()
    saver.fail_after_commit = fail_after_commit
    probe = LoopProbe([response_at(1, tools=1), response_at(2, final=True)])
    options = {
        "thread_id": "next-request",
        "runtime": probe.runtime(),
        "max_tool_calls": 4,
        "max_model_steps": 2,
    }
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=initial_request(), **options)
    assert len(probe.requests) == 1
    assert probe.effects == ["call_1_0"]
    saved = await _build_response_step(saver, max_tool_calls=4, max_model_steps=2).aget_state(
        {"configurable": {"thread_id": "next-request"}}
    )
    original_id = saved.values["request_id"]
    saver.fail = False
    result = await run_response_loop(saver, request=None, **options)
    assert probe.request_ids[1] == original_id
    assert len(probe.requests) == 2
    assert probe.effects == ["call_1_0"]
    assert len(result["input_items"]) == 8


@pytest.mark.asyncio
async def test_cancel_between_steps_does_not_issue_next_model_request() -> None:
    probe = LoopProbe([response_at(1, tools=1)])

    class CancelAtBoundary(InMemorySaver):
        async def aput(self, config, checkpoint, metadata, new_versions):
            result = await super().aput(config, checkpoint, metadata, new_versions)
            if checkpoint["channel_values"].get("completed_steps") == 1:
                probe.active = False
            return result

    with pytest.raises(PermissionError):
        await run_response_loop(
            CancelAtBoundary(),
            thread_id="cancel-between",
            request=initial_request(),
            runtime=probe.runtime(),
            max_tool_calls=4,
            max_model_steps=3,
        )
    assert len(probe.requests) == 1
    assert probe.effects == ["call_1_0"]
