"""正式 agent 保留原生協定，並以真正 async 工具驗證序列與保存屏障。"""

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import TypeAdapter, ValidationError

from caliburn.adapters.response_serialization import snapshot_response
from caliburn.agent_execution.native_agent import NativeToolBinding, native_tool
from caliburn.agent_execution.native_cleanup import await_native_cleanup
from caliburn.agent_execution.response_steps import IncompleteModelResponseError
from caliburn.transport.model_tools.context_compaction import ContextCompactionTools
from tests.fixtures.native_response_runtime import run_response_loop, synthetic_tool_definitions
from tests.fixtures.response_loop import LoopProbe, initial_request, response_at


@pytest.mark.parametrize("phase", ["prepare", "execute"])
async def test_internal_validation_stops_tools_and_model_at_the_first_call(phase):
    probe = LoopProbe([response_at(1, tools=2), response_at(2, final=True)])
    events = []
    owner = ContextCompactionTools(None)

    async def prepare(call, operation_id):
        events.append("prepare:" + call.call_id)
        if phase == "prepare" and call.call_id == "call_1_0":
            TypeAdapter(int).validate_python("synthetic invalid internal value")
        return await probe.prepare(call, operation_id)

    async def execute(command):
        events.append("execute:" + command["call_id"])
        if command["call_id"] == "call_1_0":
            await owner.execute({"kind": "context_compaction"})
        return await probe.execute(command)

    with pytest.raises(RuntimeError) as error:
        await run_response_loop(
            InMemorySaver(),
            thread_id="internal-validation-" + phase,
            request=initial_request(),
            runtime=replace(probe.runtime(), prepare_tool=prepare, execute_tool=execute),
            max_tool_calls=2,
            max_model_steps=2,
        )
    assert isinstance(error.value.__cause__, ValidationError)
    assert str(error.value) == "Internal tool validation failed"
    assert events == (
        ["prepare:call_1_0"]
        if phase == "prepare"
        else [
            "prepare:call_1_0",
            "execute:call_1_0",
        ]
    )
    assert len(probe.requests) == 1
    assert probe.effects == []


async def test_canonical_rejection_preserves_call_order_and_allows_the_next_step():
    first = response_at(1, tools=2)
    first.output[-2].arguments = '{"unexpected":true}'
    probe = LoopProbe([first, response_at(2, final=True)])
    owner = ContextCompactionTools(None)

    async def prepare(call, operation_id):
        if call.call_id == "call_1_0":
            return owner.prepare(call.arguments)
        return await probe.prepare(call, operation_id)

    result = await run_response_loop(
        InMemorySaver(),
        thread_id="canonical-rejection-order",
        request=initial_request(),
        runtime=replace(probe.runtime(), prepare_tool=prepare),
        max_tool_calls=2,
        max_model_steps=2,
    )
    outputs = [
        item for item in probe.requests[1]["input"] if item.get("type") == "function_call_output"
    ]
    assert [item["call_id"] for item in outputs] == ["call_1_0", "call_1_1"]
    assert json.loads(outputs[0]["output"])["code"] == "invalid_arguments"
    assert outputs[1]["output"] == "observation:call_1_1"
    assert probe.effects == ["call_1_1"]
    assert result["completed_steps"] == 2


async def test_tool_entry_translates_saved_response_validation_before_prepare():
    # 正常模型邊界會較早驗證；此處只隔離工具入口的原件還原。
    probe = LoopProbe([])
    entered = []

    async def unavailable(*args):
        entered.append("owner")
        raise AssertionError("不應進入 prepare 或 execute")

    tool = native_tool(
        synthetic_tool_definitions()[0],
        NativeToolBinding(unavailable, unavailable),
        probe.guard,
    )
    saved = snapshot_response(response_at(1, tools=1))
    saved["output"][-1]["arguments"] = None
    runtime = SimpleNamespace(state={"response_snapshot": saved}, tool_call_id="call_1_0")
    with pytest.raises(RuntimeError) as error:
        await tool.coroutine(runtime=runtime)
    assert isinstance(error.value.__cause__, ValidationError)
    assert str(error.value) == "Internal tool validation failed"
    assert entered == []
    assert probe.effects == []


@pytest.mark.parametrize("arguments", ["[]", "null", "1", "{"])
async def test_original_arguments_reach_canonical_admission_once_without_message_parsing(arguments):
    first = response_at(1, final=True, tools=1)
    first.output[-1].arguments = arguments
    probe = LoopProbe([first, response_at(2, final=True)])
    admitted = []

    async def prepare(call, operation_id):
        admitted.append((call.arguments, operation_id))
        return "synthetic canonical rejection"

    result = await run_response_loop(
        InMemorySaver(),
        thread_id="original-arguments",
        request=initial_request(),
        runtime=replace(probe.runtime(), prepare_tool=prepare),
        max_tool_calls=2,
        max_model_steps=2,
    )
    assert [value for value, _ in admitted] == [arguments]
    assert probe.effects == []
    assert probe.requests[1]["input"][-2]["arguments"] == arguments
    assert probe.requests[1]["input"][-1]["output"] == "synthetic canonical rejection"
    assert result["completed_steps"] == 2


async def test_unknown_name_is_one_named_observation_and_does_not_drop_the_native_call():
    first = response_at(1, tools=1)
    first.output[-1].name = "not_registered"
    probe = LoopProbe([first, response_at(2, final=True)])
    result = await run_response_loop(
        InMemorySaver(),
        thread_id="unknown-tool",
        request=initial_request(),
        runtime=probe.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
    )
    assert probe.effects == []
    assert probe.requests[1]["input"][-2]["name"] == "not_registered"
    assert probe.requests[1]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call_1_0",
        "output": "synthetic unknown tool",
    }
    assert result["completed_steps"] == 2


@pytest.mark.parametrize("status", ["failed", "incomplete"])
async def test_unusable_response_is_saved_before_protocol_rejection(status):
    response = response_at(1, final=True)
    response.status = status
    probe = LoopProbe([response])
    saver = InMemorySaver()
    with pytest.raises(IncompleteModelResponseError):
        await run_response_loop(
            saver,
            thread_id="unusable-response",
            request=initial_request(),
            runtime=probe.runtime(),
            max_tool_calls=2,
            max_model_steps=2,
        )
    original = await saver.aget_tuple({"configurable": {"thread_id": "unusable-response"}})
    assert original.checkpoint["channel_values"]["response_snapshot"] == snapshot_response(response)
    assert len(probe.requests) == 1
    assert probe.effects == []


async def test_async_first_failure_never_starts_second_and_reuses_fixed_prepare():
    probe = LoopProbe([response_at(1, final=True, tools=2), response_at(2, final=True)])
    events, fixed = [], []
    available = False

    async def prepare(call, operation_id):
        command = await probe.prepare(call, operation_id)
        events.append("prepare:" + call.call_id)
        fixed.append(command)
        return command

    async def execute(command):
        await asyncio.sleep(0)
        events.append("execute:" + command["call_id"])
        if not available:
            raise ConnectionError("synthetic first effect unavailable")
        assert command == next(value for value in fixed if value["call_id"] == command["call_id"])
        return await probe.execute(command)

    saver = InMemorySaver()
    options = dict(
        thread_id="async-first-failure",
        max_tool_calls=2,
        max_model_steps=2,
        runtime=replace(probe.runtime(), prepare_tool=prepare, execute_tool=execute),
    )
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=initial_request(), **options)
    assert events == ["prepare:call_1_0", "execute:call_1_0"]
    available = True
    await run_response_loop(saver, request=None, **options)
    assert events == [
        "prepare:call_1_0",
        "execute:call_1_0",
        "execute:call_1_0",
        "prepare:call_1_1",
        "execute:call_1_1",
    ]
    assert len(probe.requests) == 2


async def test_prepare_ack_must_finish_before_any_effect():
    entered, release = asyncio.Event(), asyncio.Event()

    class BlockPrepare(InMemorySaver):
        async def aput(self, config, checkpoint, metadata, new_versions):
            if checkpoint["channel_values"].get("prepared") is not None:
                entered.set()
                await release.wait()
            return await super().aput(config, checkpoint, metadata, new_versions)

    probe = LoopProbe([response_at(1, final=True, tools=2), response_at(2, final=True)])
    task = asyncio.create_task(
        run_response_loop(
            BlockPrepare(),
            thread_id="blocked-prepare",
            request=initial_request(),
            runtime=probe.runtime(),
            max_tool_calls=2,
            max_model_steps=2,
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await asyncio.sleep(0)
        assert probe.effects == []
        assert len(probe.requests) == 1
    finally:
        release.set()
        await task
    assert probe.effects == ["call_1_0", "call_1_1"]


async def test_tool_output_is_saved_before_the_next_prepare():
    entered, release = asyncio.Event(), asyncio.Event()
    events = []

    class BlockOutput(InMemorySaver):
        async def aput(self, config, checkpoint, metadata, new_versions):
            first = checkpoint["channel_values"].get("output") == "observation:call_1_0"
            if first:
                entered.set()
                await release.wait()
            result = await super().aput(config, checkpoint, metadata, new_versions)
            if first:
                events.append("first-output-saved")
            return result

    probe = LoopProbe([response_at(1, tools=2), response_at(2, final=True)])

    async def prepare(call, operation_id):
        if call.call_id == "call_1_1":
            assert "first-output-saved" in events
        events.append("prepare:" + call.call_id)
        return await probe.prepare(call, operation_id)

    task = asyncio.create_task(
        run_response_loop(
            BlockOutput(),
            thread_id="saved-output-before-prepare",
            request=initial_request(),
            runtime=replace(probe.runtime(), prepare_tool=prepare),
            max_tool_calls=2,
            max_model_steps=2,
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await asyncio.sleep(0)
        assert events == ["prepare:call_1_0"]
        assert probe.effects == ["call_1_0"]
    finally:
        release.set()
        await task
    assert events == ["prepare:call_1_0", "first-output-saved", "prepare:call_1_1"]


async def test_cancelling_running_tool_stops_waiters_and_resumes_original_prepare():
    entered = asyncio.Event()
    probe = LoopProbe([response_at(1, tools=2), response_at(2, final=True)])
    commands, events = [], []
    available = False

    async def prepare(call, operation_id):
        command = await probe.prepare(call, operation_id)
        commands.append(command)
        events.append("prepare:" + call.call_id)
        return command

    async def execute(command):
        events.append("execute:" + command["call_id"])
        if not available:
            entered.set()
            await asyncio.Event().wait()
        assert command == next(item for item in commands if item["call_id"] == command["call_id"])
        return await probe.execute(command)

    saver = InMemorySaver()
    options = dict(
        thread_id="cancel-waiting-tools",
        runtime=replace(probe.runtime(), prepare_tool=prepare, execute_tool=execute),
        max_tool_calls=2,
        max_model_steps=2,
    )
    task = asyncio.create_task(run_response_loop(saver, request=initial_request(), **options))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as stopped:
        await task
    await await_native_cleanup(stopped.value)
    assert events == ["prepare:call_1_0", "execute:call_1_0"]
    assert probe.effects == []
    available = True
    await run_response_loop(saver, request=None, **options)
    assert events == [
        "prepare:call_1_0",
        "execute:call_1_0",
        "execute:call_1_0",
        "prepare:call_1_1",
        "execute:call_1_1",
    ]
    assert probe.effects == ["call_1_0", "call_1_1"]
    assert len(probe.requests) == 2


async def test_reused_call_ids_cannot_skip_a_failed_predecessor_in_the_next_step():
    first, second = response_at(1, tools=2), response_at(2, tools=2)
    for previous, current in zip(first.output[-2:], second.output[-2:], strict=True):
        current.call_id = previous.call_id
    probe = LoopProbe([first, second, response_at(3, final=True)])
    events = []
    available = False

    async def prepare(call, operation_id):
        events.append((len(probe.requests), "prepare", call.call_id))
        return await probe.prepare(call, operation_id)

    async def execute(command):
        await asyncio.sleep(0)
        events.append((len(probe.requests), "execute", command["call_id"]))
        if len(probe.requests) == 2 and not available:
            raise ConnectionError("synthetic second Step first tool failure")
        return await probe.execute(command)

    saver = InMemorySaver()
    options = dict(
        thread_id="reused-tool-call-ids",
        runtime=replace(probe.runtime(), prepare_tool=prepare, execute_tool=execute),
        max_tool_calls=2,
        max_model_steps=3,
    )
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=initial_request(), **options)
    assert [event for event in events if event[0] == 2] == [
        (2, "prepare", "call_1_0"),
        (2, "execute", "call_1_0"),
    ]
    assert probe.effects == ["call_1_0", "call_1_1"]
    available = True
    result = await run_response_loop(saver, request=None, **options)
    assert result["completed_steps"] == 3
    assert probe.effects == ["call_1_0", "call_1_1", "call_1_0", "call_1_1"]
    assert [event for event in events if event[0] == 2] == [
        (2, "prepare", "call_1_0"),
        (2, "execute", "call_1_0"),
        (2, "execute", "call_1_0"),
        (2, "prepare", "call_1_1"),
        (2, "execute", "call_1_1"),
    ]
