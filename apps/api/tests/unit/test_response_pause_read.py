"""The public pause reader observes the existing native graph, never executes it."""

from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.tool_steps import (
    PausedResponseLoop,
    read_response_pause,
    run_response_loop,
)
from tests.fixtures.response_capacity import CapacityProbe, request_fixture
from tests.unit.test_response_pause import PauseProbe


async def test_read_pause_is_side_effect_free_and_does_not_return_consumed_interrupt() -> None:
    saver = InMemorySaver()
    provider = CapacityProbe([100], final=True)
    control = PauseProbe()
    thread_id = "read-native-pause"
    assert await read_response_pause(saver, thread_id=thread_id) is None
    options = dict(
        thread_id=thread_id,
        runtime=provider.runtime(),
        max_tool_calls=2,
        max_model_steps=3,
        controls=control.controls(),
    )
    original = await run_response_loop(saver, request=request_fixture(), **options)
    assert isinstance(original, PausedResponseLoop)
    config = {"configurable": {"thread_id": thread_id}}
    before = await saver.aget_tuple(config)
    for _ in range(2):
        observed = await read_response_pause(saver, thread_id=thread_id)
        assert observed == original
    assert await saver.aget_tuple(config) == before
    assert control.paused == 1
    assert len(provider.model_requests) == len(provider.count_requests) == 1
    control.requested = False
    await run_response_loop(
        saver,
        request=None,
        resume_interrupt_id=original.interrupt_id,
        **options,
    )
    assert await read_response_pause(saver, thread_id=thread_id) is None
    assert len(provider.model_requests) == 1
