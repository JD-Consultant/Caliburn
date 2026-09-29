"""A pause must stop a complete native Step, including a final pending delivery."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses import Response

from caliburn.agent_execution.tool_steps import (
    PausedResponseLoop,
    ReceivedModelResponse,
    ResponseLoopControls,
    run_response_loop,
)
from tests.fixtures.response_capacity import CapacityProbe, request_fixture


class PauseProbe:
    def __init__(self):
        self.requested = True
        self.paused = 0

    async def read_request(self):
        return self.requested

    async def mark_paused(self):
        self.paused += 1

    def controls(self):
        return ResponseLoopControls(self.read_request, self.mark_paused)


@pytest.mark.asyncio
@pytest.mark.parametrize("final", [False, True])
async def test_pause_precedes_next_count_compaction_and_final_delivery(final):
    provider = CapacityProbe([100, 100], final=final)
    control = PauseProbe()
    saver = InMemorySaver()
    compact_calls = []

    async def compact(*args):
        compact_calls.append(args)
        pytest.fail("A paused loop must not compact")

    options = dict(
        thread_id="pause-before-next-request",
        runtime=replace(provider.runtime(), compact_window=compact),
        max_tool_calls=2,
        max_model_steps=3,
        controls=control.controls(),
    )
    paused = await run_response_loop(saver, request=request_fixture(), **options)
    assert isinstance(paused, PausedResponseLoop)
    assert paused.state["completed_steps"] == 1
    assert len(provider.model_requests) == len(provider.count_requests) == 1
    assert compact_calls == []
    assert control.paused == 1

    # Ordinary crash/reopen recovery cannot silently consume an interrupt.
    again = await run_response_loop(saver, request=None, **options)
    assert again == paused
    assert len(provider.model_requests) == 1
    control.requested = False
    result = await run_response_loop(
        saver, request=None, resume_interrupt_id=paused.interrupt_id, **options
    )
    assert not isinstance(result, PausedResponseLoop)
    assert result["next_action"] == "deliver_answer"
    assert len(provider.model_requests) == (1 if final else 2)
    assert result["input_items"][: len(paused.state["input_items"])] == paused.state["input_items"]


@pytest.mark.asyncio
async def test_pause_waits_for_all_ordered_tool_results_even_after_tool_failure():
    provider = CapacityProbe([100])
    control = PauseProbe()
    control.requested = False
    saver = InMemorySaver()
    response = Response.model_validate_json(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text("utf-8")
    )
    original_call = response.output[-1].model_dump(mode="json")
    response = Response.model_validate(
        {
            **response.model_dump(mode="json"),
            "output": [
                *response.output,
                {**original_call, "id": "second_function", "call_id": "second_call"},
            ],
        }
    )
    effects = []
    failed = False
    model_calls = 0

    async def model(*args):
        nonlocal model_calls
        model_calls += 1
        return ReceivedModelResponse(response, uuid4())

    async def prepare(call, operation_id):
        return {"call_id": call.call_id, "operation_id": operation_id}

    async def execute(command):
        nonlocal failed
        control.requested = True
        if command["call_id"] == "second_call" and not failed:
            failed = True
            raise ConnectionError("synthetic unresolved second tool")
        effects.append(command["call_id"])
        return "synthetic saved observation"

    options = dict(
        thread_id="pause-with-tools",
        max_tool_calls=2,
        max_model_steps=2,
        controls=control.controls(),
        runtime=replace(
            provider.runtime(), request_model=model, prepare_tool=prepare, execute_tool=execute
        ),
    )
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=request_fixture(), **options)
    assert control.paused == 0
    assert effects == ["call_synthetic"]
    paused = await run_response_loop(saver, request=None, **options)
    assert isinstance(paused, PausedResponseLoop)
    assert effects == ["call_synthetic", "second_call"]
    assert model_calls == 1
    assert [result["call_id"] for result in paused.state["tool_results"]] == effects


class InterruptSaveFault(InMemorySaver):
    fail = True

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if self.fail and any(key == "__interrupt__" for key, _ in writes):
            raise ConnectionError("synthetic interrupt save failure")
        await super().aput_writes(config, writes, task_id, task_path)


class ContinueAcknowledgementFault(InMemorySaver):
    fail = True
    before_save = False

    async def aput(self, config, checkpoint, metadata, new_versions):
        if self.fail and checkpoint["channel_values"].get("control_action") == "continue":
            self.fail = False
            if self.before_save:
                raise ConnectionError("synthetic control checkpoint unavailable")
            await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic saved control acknowledgement lost")
        return await super().aput(config, checkpoint, metadata, new_versions)


class StepCheckpointFault(InMemorySaver):
    fail = True

    async def aput(self, config, checkpoint, metadata, new_versions):
        if self.fail and checkpoint["channel_values"].get("completed_steps") == 1:
            raise ConnectionError("synthetic complete Step checkpoint unavailable")
        return await super().aput(config, checkpoint, metadata, new_versions)


@pytest.mark.asyncio
@pytest.mark.parametrize("final", [False, True])
async def test_pending_step_result_is_not_overwritten_by_recovery_control_refresh(final):
    provider = CapacityProbe([100, 100], final=final)
    control = PauseProbe()
    control.requested = False
    saver = StepCheckpointFault()
    options = dict(
        thread_id="pending-step",
        runtime=provider.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
        controls=control.controls(),
    )
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=request_fixture(), **options)
    saver.fail = False
    control.requested = True
    paused = await run_response_loop(saver, request=None, **options)
    assert isinstance(paused, PausedResponseLoop)
    assert paused.state["completed_steps"] == 1
    assert paused.state["input_items"][:1] == request_fixture().create_payload()["input"]
    assert len(paused.state["input_items"]) > 1
    assert len(provider.model_requests) == len(provider.count_requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("final", [False, True])
@pytest.mark.parametrize("before_save", [False, True])
async def test_recovery_rechecks_pause_after_saved_continue_decision(final, before_save):
    provider = CapacityProbe([100, 100], final=final)
    control = PauseProbe()
    control.requested = False
    saver = ContinueAcknowledgementFault()
    saver.before_save = before_save
    options = dict(
        thread_id="stale-continue",
        runtime=provider.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
        controls=control.controls(),
    )
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=request_fixture(), **options)
    assert len(provider.model_requests) == len(provider.count_requests) == 1
    control.requested = True
    paused = await run_response_loop(saver, request=None, **options)
    assert isinstance(paused, PausedResponseLoop)
    assert paused.state["completed_steps"] == 1
    assert len(provider.model_requests) == len(provider.count_requests) == 1
    control.requested = False
    result = await run_response_loop(
        saver, request=None, resume_interrupt_id=paused.interrupt_id, **options
    )
    assert not isinstance(result, PausedResponseLoop)
    assert result["completed_steps"] == (1 if final else 2)


@pytest.mark.asyncio
async def test_unsaved_interrupt_does_not_acknowledge_pause_or_replay_complete_step():
    provider = CapacityProbe([100])
    control = PauseProbe()
    saver = InterruptSaveFault()
    options = dict(
        thread_id="pause-save",
        runtime=provider.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
        controls=control.controls(),
    )
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=request_fixture(), **options)
    assert control.paused == 0
    saver.fail = False
    paused = await run_response_loop(saver, request=None, **options)
    assert isinstance(paused, PausedResponseLoop)
    assert control.paused == 1
    assert len(provider.model_requests) == 1


@pytest.mark.asyncio
async def test_resume_requires_original_pause_identity_and_control_configuration():
    provider = CapacityProbe([100])
    control = PauseProbe()
    saver = InMemorySaver()
    options = dict(
        thread_id="pause-identity",
        runtime=provider.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
        controls=control.controls(),
    )
    with pytest.raises(ValueError):
        await run_response_loop(
            saver, request=request_fixture(), resume_interrupt_id="stale", **options
        )
    paused = await run_response_loop(saver, request=request_fixture(), **options)
    assert isinstance(paused, PausedResponseLoop)
    with pytest.raises(ValueError):
        await run_response_loop(saver, request=None, resume_interrupt_id="stale", **options)
    with pytest.raises(ValueError):
        await run_response_loop(saver, request=None, **{**options, "controls": None})
    assert len(provider.model_requests) == 1


@pytest.mark.asyncio
async def test_pause_ack_loss_recovers_original_interrupt_and_not_model_work():
    provider = CapacityProbe([100])
    control = PauseProbe()
    saver = InMemorySaver()
    first_ack = True

    async def mark_paused():
        nonlocal first_ack
        await control.mark_paused()
        if first_ack:
            first_ack = False
            raise ConnectionError("synthetic pause acknowledgement lost")

    options = dict(
        thread_id="pause-ack",
        runtime=provider.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
        controls=ResponseLoopControls(control.read_request, mark_paused),
    )
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=request_fixture(), **options)
    paused = await run_response_loop(saver, request=None, **options)
    assert isinstance(paused, PausedResponseLoop)
    assert control.paused == 2
    assert len(provider.model_requests) == 1
