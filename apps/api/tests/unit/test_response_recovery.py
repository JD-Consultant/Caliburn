"""An intact model result survives saver failure without becoming a second durable store."""

from dataclasses import replace
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses import Response

from caliburn.agent_execution.response_steps import UnsupportedModelResponseError
from caliburn.agent_execution.tool_steps import (
    ResponseStepRuntime,
    ResponseStepSaveError,
    run_response_step,
)


async def ensure_active() -> None:
    """Storage-only unit fixture, without a business owner."""


class EntireResponseSaveFault(InMemorySaver):
    fail_response_saves = True
    fail_after_commit = False

    async def aput(self, config, checkpoint, metadata, new_versions):
        if self.fail_response_saves and checkpoint["channel_values"].get("response_snapshot"):
            if self.fail_after_commit:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic checkpoint unavailable")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if self.fail_response_saves and any(name == "response_snapshot" for name, _ in writes):
            raise ConnectionError("synthetic pending writes unavailable")
        await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.asyncio
async def test_public_step_preserves_original_response_when_both_saver_writes_fail() -> None:
    response = Response.model_validate_json(
        (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(encoding="utf-8")
    )
    calls = []

    async def request(items):
        calls.append("model")
        return response

    async def prepare(call, operation_id):
        pytest.fail("The unsaved response cannot dispatch tools")

    async def execute(prepared):
        pytest.fail("The unsaved response cannot execute tools")

    with pytest.raises(ResponseStepSaveError) as failure:
        await run_response_step(
            EntireResponseSaveFault(),
            thread_id="original-response",
            input_items=[{"role": "user", "content": "synthetic"}],
            runtime=ResponseStepRuntime(request, prepare, execute, ensure_active),
            max_tool_calls=16,
        )

    assert calls == ["model"]
    assert hasattr(failure.value, "recovery"), "Intact original R must reach the recovery caller"


def recording_runtime(events: list[str]) -> ResponseStepRuntime:
    async def request(items):
        events.append("model")
        return Response.model_validate_json(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(
                encoding="utf-8"
            )
        )

    async def prepare(call, operation_id):
        events.append("read")
        return "original observation"

    async def execute(prepared):
        pytest.fail("Read-only fixture")

    return ResponseStepRuntime(request, prepare, execute, ensure_active)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_after_commit", [False, True])
async def test_recovery_adopts_original_or_saved_result_without_requery_or_rewind(
    fail_after_commit: bool,
) -> None:
    saver = EntireResponseSaveFault()
    saver.fail_after_commit = fail_after_commit
    events = []
    runtime = recording_runtime(events)
    options = {"thread_id": "held-result", "runtime": runtime, "max_tool_calls": 16}
    with pytest.raises(ResponseStepSaveError) as failure:
        await run_response_step(saver, input_items=[], **options)
    recovery = failure.value.recovery
    assert events == ["model"]
    assert "encrypted_content" not in repr(recovery)

    if not fail_after_commit:
        # A second storage outage must retain the very same result and operation identity.
        with pytest.raises(ResponseStepSaveError) as again:
            await run_response_step(saver, input_items=None, recovery=recovery, **options)
        assert again.value.recovery is recovery
        assert events == ["model"]

    saver.fail_response_saves = False
    result = await run_response_step(saver, input_items=None, recovery=recovery, **options)
    assert result["response_snapshot"] == recovery.update["response_snapshot"]
    assert result["operation_seed"] == recovery.update["operation_seed"]
    assert events == ["model", "read"]
    # A repeated acknowledgement cannot reset later results or append the same items twice.
    assert await run_response_step(saver, input_items=None, recovery=recovery, **options) == result
    assert events == ["model", "read"]


@pytest.mark.asyncio
async def test_held_result_cannot_adopt_a_different_request_or_thread() -> None:
    saver = EntireResponseSaveFault()
    events = []
    runtime = recording_runtime(events)
    options = {"thread_id": "bound-result", "runtime": runtime, "max_tool_calls": 16}
    with pytest.raises(ResponseStepSaveError) as failure:
        await run_response_step(
            saver, input_items=[{"role": "user", "content": "first"}], **options
        )
    recovery = failure.value.recovery
    saver.fail_response_saves = False
    with pytest.raises(ValueError, match="original Step"):
        await run_response_step(saver, input_items=[], recovery=recovery, **options)
    with pytest.raises(ValueError, match="original Step"):
        await run_response_step(
            saver,
            input_items=None,
            recovery=recovery,
            **{**options, "thread_id": "another-step"},
        )
    with pytest.raises(ValueError, match="saved request boundary"):
        await run_response_step(
            saver,
            input_items=None,
            recovery=replace(recovery, input_items=[]),
            **options,
        )
    assert events == ["model"]


@pytest.mark.asyncio
async def test_saved_different_response_is_not_overwritten_by_held_result() -> None:
    saver = EntireResponseSaveFault()
    events = []
    options = {
        "thread_id": "saved-conflict",
        "runtime": recording_runtime(events),
        "max_tool_calls": 16,
    }
    with pytest.raises(ResponseStepSaveError) as failure:
        await run_response_step(saver, input_items=[], **options)
    recovery = failure.value.recovery
    saver.fail_response_saves = False
    result = await run_response_step(saver, input_items=None, recovery=recovery, **options)
    changed = {
        **recovery.update,
        "response_snapshot": {**recovery.update["response_snapshot"], "id": "another-response"},
    }
    with pytest.raises(ValueError, match="different model result"):
        await run_response_step(
            saver,
            input_items=None,
            recovery=replace(recovery, update=changed),
            **options,
        )
    assert await run_response_step(saver, input_items=None, **options) == result
    assert events == ["model", "read"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_guard", [False, True])
async def test_reused_recovery_handoff_does_not_reclassify_later_failure(fail_guard: bool) -> None:
    saver = EntireResponseSaveFault()
    runtime = recording_runtime([])

    async def prepare(call, operation_id):
        return {"operation_id": operation_id}

    async def execute(prepared):
        raise ConnectionError("synthetic tool owner unavailable")

    options = {
        "thread_id": "later-tool-failure",
        "runtime": replace(runtime, prepare_tool=prepare, execute_tool=execute),
        "max_tool_calls": 16,
    }
    with pytest.raises(ResponseStepSaveError) as failure:
        await run_response_step(saver, input_items=[], **options)
    saver.fail_response_saves = False
    with pytest.raises(ConnectionError, match="tool owner"):
        await run_response_step(saver, input_items=None, recovery=failure.value.recovery, **options)
    if fail_guard:
        checks = 0

        async def require_current_writer():
            nonlocal checks
            checks += 1
            if checks > 1:
                raise PermissionError("synthetic writer changed before tool")

        options["runtime"] = replace(options["runtime"], ensure_active=require_current_writer)
    expected = PermissionError if fail_guard else ConnectionError
    with pytest.raises(expected):
        await run_response_step(saver, input_items=None, recovery=failure.value.recovery, **options)


@pytest.mark.asyncio
async def test_invalid_response_protocol_is_not_treated_as_unsaved_result() -> None:
    runtime = recording_runtime([])

    async def request(items):
        response = await runtime.request_model(items)
        response.output[1].phase = None
        return response

    with pytest.raises(UnsupportedModelResponseError):
        await run_response_step(
            InMemorySaver(),
            thread_id="invalid-phase",
            input_items=[],
            runtime=replace(runtime, request_model=request),
            max_tool_calls=16,
        )


@pytest.mark.asyncio
async def test_late_model_result_cannot_dispatch_after_execution_becomes_inactive() -> None:
    events = []
    runtime = recording_runtime(events)
    active = True

    async def guard():
        if not active:
            raise PermissionError("Synthetic execution cancelled")

    async def request(items):
        nonlocal active
        response = await runtime.request_model(items)
        active = False
        return response

    with pytest.raises(PermissionError, match="cancelled"):
        await run_response_step(
            InMemorySaver(),
            thread_id="cancel-during-http",
            input_items=[],
            runtime=replace(runtime, request_model=request, ensure_active=guard),
            max_tool_calls=16,
        )
    assert events == ["model"]
