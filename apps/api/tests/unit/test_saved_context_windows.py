"""A reusable window must name a fully saved boundary, never a moving latest value."""

from dataclasses import replace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.context_compaction import (
    prepare_context_history,
    read_prepared_history,
)
from caliburn.agent_execution.tool_steps import (
    PausedResponseLoop,
    ResponseLoopControls,
    read_completed_response_history,
    run_response_loop,
)
from tests.fixtures.response_loop import LoopProbe, initial_request, response_at
from tests.unit.test_context_preparation import PreparationProbe
from tests.unit.test_response_pause import PauseProbe


async def test_prepared_reference_keeps_entire_window_without_replaying_compaction():
    saver = InMemorySaver()
    probe = PreparationProbe(128_000)
    options = probe.options()
    await prepare_context_history(saver, **options)
    original = await read_prepared_history(saver, thread_id=options["thread_id"])
    assert original.items == probe.window
    original.items.append({"role": "user", "content": "abandoned input"})
    restored = await read_prepared_history(
        saver, thread_id=options["thread_id"], checkpoint_id=original.checkpoint_id
    )
    assert restored.items == probe.window
    assert len(probe.compact_requests) == 1
    with pytest.raises(ValueError, match="unavailable"):
        await read_prepared_history(
            saver, thread_id=options["thread_id"], checkpoint_id="missing-checkpoint"
        )


async def test_count_or_compaction_result_without_adoption_is_not_a_prepared_base():
    saver = InMemorySaver()
    probe = PreparationProbe(128_000)
    options = probe.options()

    async def unavailable(_):
        raise ConnectionError("synthetic accounting outage")

    options["runtime"] = replace(options["runtime"], account_compaction=unavailable)
    with pytest.raises(ConnectionError):
        await prepare_context_history(saver, **options)
    with pytest.raises(ValueError, match="prepared"):
        await read_prepared_history(saver, thread_id=options["thread_id"])


async def test_completed_response_exports_exact_native_history_and_does_not_execute():
    saver = InMemorySaver()
    probe = LoopProbe([response_at(1, tools=2), response_at(2, final=True)])
    state = await run_response_loop(
        saver,
        thread_id="finished",
        request=initial_request(),
        runtime=probe.runtime(),
        max_tool_calls=4,
        max_model_steps=3,
    )
    original = await read_completed_response_history(saver, thread_id="finished")
    assert original.items == state["input_items"]
    assert original.items[2]["encrypted_content"] == "synthetic-opaque-1"
    assert [
        item["call_id"] for item in original.items if item.get("type") == "function_call_output"
    ] == ["call_1_0", "call_1_1"]
    restored = await read_completed_response_history(
        saver, thread_id="finished", checkpoint_id=original.checkpoint_id
    )
    assert restored == original
    assert len(probe.requests) == 2
    assert probe.effects == ["call_1_0", "call_1_1"]


async def test_paused_final_is_not_a_completed_work_history():
    saver = InMemorySaver()
    probe = LoopProbe([response_at(1, final=True)])

    async def pause():
        return True

    async def acknowledged():
        pass

    result = await run_response_loop(
        saver,
        thread_id="paused",
        request=initial_request(),
        runtime=probe.runtime(),
        max_tool_calls=4,
        max_model_steps=3,
        controls=ResponseLoopControls(pause, acknowledged),
    )
    assert isinstance(result, PausedResponseLoop)
    with pytest.raises(ValueError, match="completed"):
        await read_completed_response_history(saver, thread_id="paused")


async def test_exact_saved_position_does_not_follow_a_later_control_checkpoint():
    saver = InMemorySaver()
    probe = LoopProbe([response_at(1, final=True)])
    control = PauseProbe()
    control.requested = False
    options = dict(
        thread_id="changing-latest",
        runtime=probe.runtime(),
        max_tool_calls=4,
        max_model_steps=3,
        controls=control.controls(),
    )
    await run_response_loop(saver, request=initial_request(), **options)
    original = await read_completed_response_history(saver, thread_id=options["thread_id"])
    control.requested = True
    paused = await run_response_loop(saver, request=None, **options)
    assert isinstance(paused, PausedResponseLoop)
    with pytest.raises(ValueError, match="completed"):
        await read_completed_response_history(saver, thread_id=options["thread_id"])
    assert (
        await read_completed_response_history(
            saver, thread_id=options["thread_id"], checkpoint_id=original.checkpoint_id
        )
        == original
    )
    control.requested = False
    await run_response_loop(saver, request=None, resume_interrupt_id=paused.interrupt_id, **options)
    assert (
        await read_completed_response_history(saver, thread_id=options["thread_id"])
    ).items == original.items
    assert len(probe.requests) == 1
