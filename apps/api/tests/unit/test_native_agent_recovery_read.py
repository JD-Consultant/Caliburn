"""持有原件的初次讀取故障沿同一保存責任恢復。"""

import pytest
from psycopg.errors import ConnectionFailure, UndefinedTable

from caliburn.agent_execution.native_agent import NativeToolBinding, native_tool, run_native_agent
from caliburn.agent_execution.response_runtime import (
    InputCountSaveError,
    ModelStepLimitError,
    ResponseStepSaveError,
)
from tests.fixtures.native_response_runtime import run_response_step, synthetic_tool_definitions
from tests.fixtures.response_capacity import request_fixture
from tests.unit.test_response_recovery import recording_runtime
from tests.unit.test_result_save_retries import NO_WAIT, TransientResultFault


@pytest.mark.parametrize("channel", ["response_snapshot", "input_count"])
@pytest.mark.parametrize("persistent", [False, True])
async def test_initial_recovery_read_preserves_original_without_repeating_outbound(
    monkeypatch, channel, persistent
):
    events = []
    saver = TransientResultFault(channel, error_type=UndefinedTable)
    runtime = recording_runtime(events)
    failure_type = ResponseStepSaveError if channel == "response_snapshot" else InputCountSaveError
    with pytest.raises(failure_type) as stopped:
        await run_response_step(
            saver,
            thread_id="initial-read",
            request=request_fixture(),
            runtime=runtime,
            max_tool_calls=2,
            save_retry_policy=NO_WAIT,
        )
    original = stopped.value.recovery
    original_get = saver.aget_tuple
    reads = 0

    async def read(config):
        nonlocal reads
        reads += 1
        if persistent or reads == 1:
            raise ConnectionFailure("synthetic original snapshot read unavailable")
        return await original_get(config)

    monkeypatch.setattr(saver, "aget_tuple", read)
    tools = [
        native_tool(
            definition,
            NativeToolBinding(runtime.prepare_tool, runtime.execute_tool),
            runtime.ensure_active,
        )
        for definition in synthetic_tool_definitions()
    ]
    if persistent:
        with pytest.raises(failure_type) as failed:
            await run_native_agent(
                saver,
                thread_id="initial-read",
                request=None,
                recovery=original,
                runtime=runtime,
                tools=tools,
                max_model_steps=1,
                max_tool_calls=2,
                unknown_tool_output="unregistered",
                save_retry_policy=NO_WAIT,
            )
        assert failed.value.recovery is original
        assert reads == NO_WAIT.max_attempts
        assert events == (["model"] if channel == "response_snapshot" else [])
    else:
        with pytest.raises(ModelStepLimitError):
            await run_native_agent(
                saver,
                thread_id="initial-read",
                request=None,
                recovery=original,
                runtime=runtime,
                tools=tools,
                max_model_steps=1,
                max_tool_calls=2,
                unknown_tool_output="unregistered",
                save_retry_policy=NO_WAIT,
            )
        assert events == ["model", "read"]


@pytest.mark.parametrize("channel", ["response_snapshot", "input_count"])
async def test_read_and_save_failures_share_one_entry_retry_budget(monkeypatch, channel):
    from caliburn.agent_execution import native_agent

    events = []
    saver = TransientResultFault(channel, error_type=UndefinedTable)
    runtime = recording_runtime(events)
    failure_type = ResponseStepSaveError if channel == "response_snapshot" else InputCountSaveError
    with pytest.raises(failure_type) as stopped:
        await run_response_step(
            saver,
            thread_id="shared-budget",
            request=request_fixture(),
            runtime=runtime,
            max_tool_calls=2,
            save_retry_policy=NO_WAIT,
        )
    original = stopped.value.recovery
    factory = native_agent.create_agent
    calls = []

    def graph_factory(*args, **kwargs):
        graph = factory(*args, **kwargs)
        read = graph.aget_state

        async def failed_read(config):
            calls.append("read")
            if calls == ["read"]:
                raise ConnectionFailure("synthetic preflight read unavailable")
            return await read(config)

        async def failed_save(*args, **kwargs):
            calls.append("save")
            raise ConnectionFailure("synthetic original save unavailable")

        monkeypatch.setattr(graph, "aget_state", failed_read)
        monkeypatch.setattr(graph, "ainvoke", failed_save)
        return graph

    monkeypatch.setattr(native_agent, "create_agent", graph_factory)
    with pytest.raises(failure_type) as failed:
        await run_native_agent(
            saver,
            thread_id="shared-budget",
            request=None,
            recovery=original,
            runtime=runtime,
            tools=[],
            max_model_steps=1,
            max_tool_calls=2,
            unknown_tool_output="unregistered",
            save_retry_policy=NO_WAIT,
        )
    assert failed.value.recovery is original
    assert calls == ["read", "read", "save", "save"]
    assert events == (["model"] if channel == "response_snapshot" else [])
