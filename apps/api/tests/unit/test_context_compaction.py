"""Canonical C is adopted only after persistence; failures retain the original W."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses.compacted_response import CompactedResponse

from tests.fixtures.response_capacity import (
    CapacityProbe,
    request_fixture,
    synthetic_capacity_limits,
)

COMPACTED = {
    "id": "cmp_synthetic",
    "object": "response.compaction",
    "created_at": 1,
    "output": [
        {"type": "compaction", "id": "cmp_item", "encrypted_content": "opaque-synthetic"},
        {"role": "user", "content": "retained input, not to be appended again"},
    ],
    "usage": {
        "input_tokens": 272000,
        "output_tokens": 100,
        "input_tokens_details": {"cached_tokens": 0},
        "total_tokens": 272100,
    },
}


class CompactionSaveFault(InMemorySaver):
    fail = True
    fail_after_save = False

    async def aput(self, config, checkpoint, metadata, new_versions):
        if self.fail and checkpoint["channel_values"].get("compaction_snapshot"):
            if self.fail_after_save:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic checkpoint unavailable")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if self.fail and any(name == "compaction_snapshot" for name, _ in writes):
            raise ConnectionError("synthetic pending writes unavailable")
        await super().aput_writes(config, writes, task_id, task_path)


def options(events):
    from caliburn.agent_execution.context_compaction import CompactionRuntime, ReceivedCompaction

    async def compact(request, request_id):
        events.append(("compact", request.create_payload()["input"]))
        return ReceivedCompaction(CompactedResponse.model_construct(**deepcopy(COMPACTED)), uuid4())

    async def account(received):
        events.append(("account", received.response.id))

    async def active():
        pass

    return dict(
        thread_id="synthetic-compact",
        request=request_fixture(),
        input_count={"input_tokens": 272000, "attempt_id": uuid4()},
        runtime=CompactionRuntime(compact, account, active, synthetic_capacity_limits()),
    )


@pytest.mark.parametrize("fail_after_save", [False, True])
async def test_compaction_save_failure_reuses_full_original_not_second_http(fail_after_save):
    from caliburn.agent_execution.context_compaction import (
        CompactionSaveError,
        run_context_compaction,
    )

    events = []
    args = options(events)
    saver = CompactionSaveFault()
    saver.fail_after_save = fail_after_save
    with pytest.raises(CompactionSaveError) as failed:
        await run_context_compaction(saver, **args)
    assert events == [("compact", [{"role": "user", "content": "synthetic pinned map"}])]
    saver.fail = False
    result = await run_context_compaction(saver, **args, recovery=failed.value.recovery)
    assert result == COMPACTED["output"]
    assert len([event for event in events if event[0] == "compact"]) == 1
    # Calling the same saved boundary again must reuse C, not append W or recompact.
    assert await run_context_compaction(saver, **args) == COMPACTED["output"]
    assert len(events) == 2


async def test_compaction_account_failure_retains_c_and_resumes_without_http():
    from caliburn.agent_execution.context_compaction import run_context_compaction

    events = []
    args = options(events)
    saver = InMemorySaver()

    async def unavailable(received):
        raise ConnectionError("synthetic accounting unavailable")

    original = args["runtime"]
    args["runtime"] = replace(original, account_compaction=unavailable)
    with pytest.raises(ConnectionError, match="accounting"):
        await run_context_compaction(saver, **args)
    args["runtime"] = original
    assert await run_context_compaction(saver, **args) == COMPACTED["output"]
    assert len(events) == 2


async def test_cancel_after_compact_accounts_but_never_adopts_or_returns_c():
    from caliburn.agent_execution.context_compaction import run_context_compaction

    events = []
    args = options(events)

    async def active():
        if events:
            raise PermissionError("synthetic cancelled")

    args["runtime"] = replace(args["runtime"], ensure_active=active)
    saver = InMemorySaver()
    with pytest.raises(PermissionError, match="cancelled"):
        await run_context_compaction(saver, **args)
    saved = await saver.aget_tuple({"configurable": {"thread_id": args["thread_id"]}})
    assert saved.checkpoint["channel_values"].get("adopted") is not True
    assert saved.checkpoint["channel_values"]["request_snapshot"]["input"] == [
        {"role": "user", "content": "synthetic pinned map"}
    ]
    assert events[-1] == ("account", "cmp_synthetic")


@pytest.mark.parametrize("after_tokens", [100, 272000])
async def test_loop_adopts_c_recounts_and_never_recompacts_an_unchanged_window(after_tokens):
    from caliburn.agent_execution.context_compaction import run_context_compaction
    from caliburn.agent_execution.request_capacity import RequestCapacityError
    from caliburn.agent_execution.tool_steps import run_response_loop

    saver = InMemorySaver()
    events = []
    args = options(events)
    probe = CapacityProbe([100, 272000, after_tokens], final=False)

    async def compact_window(request, count, request_id):
        return await run_context_compaction(
            saver,
            thread_id=f"compact:{request_id}",
            request=request,
            input_count=count,
            runtime=args["runtime"],
        )

    runtime = replace(probe.runtime(), compact_window=compact_window)
    kwargs = dict(thread_id="compact-loop", runtime=runtime, max_tool_calls=2, max_model_steps=3)
    if after_tokens >= 272000:
        for request in (request_fixture(), None):
            with pytest.raises(RequestCapacityError, match="compacted"):
                await run_response_loop(saver, request=request, **kwargs)
        assert len(probe.model_requests) == 1
    else:
        result = await run_response_loop(saver, request=request_fixture(), **kwargs)
        assert result["next_action"] == "deliver_answer"
        assert probe.model_requests[1]["input"] == COMPACTED["output"]
    assert probe.count_requests[2][1]["input"] == COMPACTED["output"]
    assert len(probe.count_requests) == 3
    assert [event[0] for event in events] == ["compact", "account"]
    # Full original W, including completed model output, reached compact.
    assert events[0][1][0] == {"role": "user", "content": "synthetic pinned map"}
    assert len(events[0][1]) == 3


async def test_saved_compaction_boundary_rejects_changed_request_or_capacity():
    from caliburn.agent_execution.context_compaction import run_context_compaction

    events = []
    args = options(events)
    saver = InMemorySaver()
    await run_context_compaction(saver, **args)
    original = args["request"].create_payload()
    args["request"] = args["request"].from_snapshot({**original, "input": []})
    with pytest.raises(ValueError, match="original"):
        await run_context_compaction(saver, **args)
    args["request"] = args["request"].from_snapshot(original)
    args["runtime"] = replace(
        args["runtime"],
        capacity_limits={
            **args["runtime"].capacity_limits,
            "max_input_tokens": 950000,
        },
    )
    with pytest.raises(ValueError, match="original"):
        await run_context_compaction(saver, **args)
    assert [event[0] for event in events] == ["compact", "account"]


async def test_empty_compaction_cannot_replace_nonempty_history():
    from caliburn.agent_execution.context_compaction import (
        ReceivedCompaction,
        run_context_compaction,
    )

    events = []
    args = options(events)

    async def compact(request, request_id):
        events.append(("compact", []))
        return ReceivedCompaction(
            CompactedResponse.construct(**{**COMPACTED, "output": []}), uuid4()
        )

    args["runtime"] = replace(args["runtime"], request_compaction=compact)
    saver = InMemorySaver()
    for _ in range(2):
        with pytest.raises(ValueError, match="empty"):
            await run_context_compaction(saver, **args)
    assert [event[0] for event in events] == ["compact", "account"]


async def test_grown_window_can_compact_again_after_another_complete_step():
    from caliburn.agent_execution.context_compaction import run_context_compaction
    from caliburn.agent_execution.tool_steps import run_response_loop

    probe = CapacityProbe([100, 272000, 100, 272000, 100], final=False)
    saver = InMemorySaver()
    events = []
    args = options(events)
    boundaries = []

    async def model(request, request_id, input_tokens: int):
        received = await probe.model(request, request_id, input_tokens)
        received.response.output[1].phase = (
            "final_answer" if len(probe.model_requests) == 3 else "commentary"
        )
        return received

    async def compact_window(request, count, request_id):
        boundaries.append(request_id)
        return await run_context_compaction(
            saver,
            thread_id=f"compact:{request_id}",
            request=request,
            input_count=count,
            runtime=args["runtime"],
        )

    result = await run_response_loop(
        saver,
        thread_id="growth",
        request=request_fixture(),
        runtime=replace(probe.runtime(), request_model=model, compact_window=compact_window),
        max_tool_calls=2,
        max_model_steps=3,
    )
    assert result["completed_steps"] == 3
    assert probe.model_input_tokens == [100, 100, 100]
    assert len(boundaries) == len(set(boundaries)) == 2
    assert [event[0] for event in events] == ["compact", "account", "compact", "account"]
    assert len(events[2][1]) == 4  # Previous C plus the newly completed Step.


async def test_inactive_work_after_count_never_sends_boundary_compaction():
    from caliburn.agent_execution.tool_steps import run_response_loop

    probe = CapacityProbe([100, 272000], final=False)

    async def guard():
        if len(probe.count_requests) == 2:
            raise PermissionError("synthetic work no longer active")

    async def compact_window(*args):
        pytest.fail("Ineligible work must not start paid compaction")

    with pytest.raises(PermissionError, match="no longer active"):
        await run_response_loop(
            InMemorySaver(),
            thread_id="no-more-work",
            request=request_fixture(),
            runtime=replace(probe.runtime(), ensure_active=guard, compact_window=compact_window),
            max_tool_calls=2,
            max_model_steps=3,
        )
    assert len(probe.model_requests) == 1


async def test_cancelled_parent_resume_can_account_its_saved_child_c_without_adopting():
    from caliburn.agent_execution.context_compaction import run_context_compaction
    from caliburn.agent_execution.tool_steps import run_response_loop

    saver = InMemorySaver()
    events = []
    args = options(events)
    probe = CapacityProbe([100, 272000], final=False)
    active = True
    settled = []

    async def guard():
        if not active:
            raise PermissionError("synthetic cancelled")

    async def account(received):
        if active:
            raise ConnectionError("synthetic cost DB unavailable")
        settled.append(received.attempt_id)

    async def compact_window(request, count, request_id):
        return await run_context_compaction(
            saver,
            thread_id=f"compact:{request_id}",
            request=request,
            input_count=count,
            runtime=replace(args["runtime"], ensure_active=guard, account_compaction=account),
        )

    runtime = replace(probe.runtime(), ensure_active=guard, compact_window=compact_window)
    kwargs = dict(thread_id="cancel-parent", runtime=runtime, max_tool_calls=2, max_model_steps=3)
    with pytest.raises(ConnectionError, match="cost DB"):
        await run_response_loop(saver, request=request_fixture(), **kwargs)
    active = False
    with pytest.raises(PermissionError, match="cancelled"):
        await run_response_loop(saver, request=None, **kwargs)
    assert len(settled) == 1
    assert len(probe.model_requests) == 1
    assert [event[0] for event in events] == ["compact"]


async def test_empty_response_does_not_make_unchanged_c_eligible_for_compaction_again():
    from caliburn.agent_execution.context_compaction import run_context_compaction
    from caliburn.agent_execution.request_capacity import RequestCapacityError
    from caliburn.agent_execution.tool_steps import run_response_loop

    saver = InMemorySaver()
    events = []
    args = options(events)
    # Even if the remote counter changes, a new request ID is not new information.
    probe = CapacityProbe([100, 272000, 100, 272000], final=False)

    async def model(request, request_id, input_tokens: int):
        received = await probe.model(request, request_id, input_tokens)
        if len(probe.model_requests) == 2:
            received.response.output = []
        return received

    async def compact_window(request, count, request_id):
        if len(events) > 1:
            pytest.fail("Unchanged C cannot be compacted twice")
        return await run_context_compaction(
            saver,
            thread_id=f"compact:{request_id}",
            request=request,
            input_count=count,
            runtime=args["runtime"],
        )

    with pytest.raises(RequestCapacityError, match="compacted"):
        await run_response_loop(
            saver,
            thread_id="no-growth",
            request=request_fixture(),
            runtime=replace(probe.runtime(), request_model=model, compact_window=compact_window),
            max_tool_calls=2,
            max_model_steps=3,
        )
    assert [event[0] for event in events] == ["compact", "account"]
