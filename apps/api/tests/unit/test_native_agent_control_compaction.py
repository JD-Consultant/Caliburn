"""控制查詢失敗不授權啟動原本未外送的 compact。"""

from dataclasses import replace
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.context_compaction import bind_window_compaction
from caliburn.agent_execution.native_agent import run_native_agent
from caliburn.agent_execution.response_runtime import ResponseLoopControls
from tests.fixtures.response_loop import LoopProbe, initial_request, response_at
from tests.unit.test_context_compaction import options as compaction_options


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_guard", [False, True])
async def test_failed_control_lookup_does_not_resume_unpaid_compact(failed_guard):
    probe = LoopProbe([response_at(1), response_at(2, final=True)])
    counts = 0
    compact_entries = 0
    control_broken = False
    compaction_events = []
    saver = InMemorySaver()
    bound_compact = bind_window_compaction(
        saver,
        response_thread_id="review-control-compact",
        runtime=compaction_options(compaction_events)["runtime"],
        recovery=None,
    )

    async def count(request, request_id):
        nonlocal counts
        counts += 1
        return {"input_tokens": 160000 if counts == 2 else 100, "attempt_id": uuid4()}

    async def compact(request, count, request_id):
        nonlocal compact_entries
        compact_entries += 1
        if compact_entries == 1:
            raise ConnectionError("synthetic failure before compact admission")
        return await bound_compact(request, count, request_id)

    async def active_guard():
        if control_broken and failed_guard:
            raise ConnectionError("synthetic active database lookup failed")

    async def pause_requested():
        if control_broken:
            raise ConnectionError("synthetic pause database lookup failed")
        return False

    async def paused():
        raise AssertionError("not requested")

    runtime = replace(
        probe.runtime(), count_input=count, compact_window=compact, ensure_active=active_guard
    )
    options = dict(
        thread_id="review-control-compact",
        runtime=runtime,
        tools=[],
        max_tool_calls=2,
        max_model_steps=3,
        unknown_tool_output="unknown",
        controls=ResponseLoopControls(pause_requested, paused),
    )
    with pytest.raises(ConnectionError, match="before compact admission"):
        await run_native_agent(saver, request=initial_request(), **options)
    assert compact_entries == 1
    control_broken = True
    with pytest.raises(ConnectionError, match="database lookup failed"):
        await run_native_agent(saver, request=None, **options)
    assert not compaction_events, (
        f"control failed but real compaction graph performed {compaction_events!r}"
    )
    assert compact_entries == 1, "failed control lookup must not re-enter a compact callback"
