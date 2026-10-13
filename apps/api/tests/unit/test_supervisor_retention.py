"""A stopped runner retains recovery data, not its exception's entire stack."""

import asyncio
import gc
import weakref
from uuid import uuid4

import pytest

from caliburn.agent_execution.context_compaction import (
    CompactionSaveError,
    HeldCompaction,
    HeldPreparationCount,
    PreparationCountSaveError,
)
from caliburn.agent_execution.response_runtime import (
    HeldInputCount,
    HeldModelResponse,
    InputCountSaveError,
    ResponseStepSaveError,
)
from caliburn.agent_execution.result_save_retries import ResultSaveCancelledError
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.workflows.consultant_turns import supervisor as consultant_supervisor
from caliburn.workflows.work_memory import supervisor as memory_supervisor
from tests.unit.test_supervisor_logging import make_supervisor


class TemporaryContext:
    pass


@pytest.mark.parametrize("kind", ["consultant_turn", "memory_batch"])
@pytest.mark.parametrize("failed", [False, True])
@pytest.mark.parametrize("terminal", [False, True])
async def test_attempt_barrier_is_released_only_after_terminal_runner_effects_finish(
    kind, failed, terminal, monkeypatch
):
    supervisor, _, _ = make_supervisor(kind)
    writer = ExecutionWriter(ExecutionScope(uuid4(), uuid4(), ExecutionKind(kind)), uuid4())
    entered, release = asyncio.Event(), asyncio.Event()
    checks = []

    async def run(_writer):
        entered.set()
        await release.wait()  # Represents the runner's owned effect cleanup.
        if failed:
            raise RuntimeError("synthetic terminal settlement")

    async def read_terminal(_sessions, scope):
        assert release.is_set()
        checks.append(scope)
        return terminal

    module = consultant_supervisor if kind == "consultant_turn" else memory_supervisor
    monkeypatch.setattr(module, "has_terminal_outcome", read_terminal)
    supervisor._run = run
    supervisor._attempted.add(writer.scope)
    task = asyncio.create_task(supervisor._run_once(writer))
    key = writer.scope if kind == "consultant_turn" else writer.scope.job_file_id
    supervisor._tasks[key] = task
    await entered.wait()
    assert writer.scope in supervisor._attempted
    assert not task.done()
    release.set()
    await task
    assert checks == [writer.scope]
    assert (writer.scope in supervisor._attempted) is not terminal
    assert key not in supervisor._tasks
    assert (writer.scope in supervisor.failures) is (failed and not terminal)


@pytest.mark.parametrize("kind", ["consultant_turn", "memory_batch"])
@pytest.mark.parametrize("cancelled", [False, True])
async def test_stopped_runner_does_not_retain_unrelated_frame_locals(kind, cancelled):
    supervisor, _, _ = make_supervisor(kind)
    writer = ExecutionWriter(ExecutionScope(uuid4(), uuid4(), ExecutionKind(kind)), uuid4())
    observed = []

    async def run(_writer):
        local_context = TemporaryContext()
        observed.append(weakref.ref(local_context))
        if cancelled:
            raise asyncio.CancelledError()
        raise RuntimeError("private context must not be retained")

    supervisor._run = run
    supervisor._attempted.add(writer.scope)
    try:
        await supervisor._run_once(writer)
    except asyncio.CancelledError:
        pass
    gc.collect()
    assert observed[0]() is None
    assert writer.scope in supervisor._attempted
    failure = supervisor.failures[writer.scope]
    assert failure.interrupted is cancelled
    assert failure.recovery is None
    assert "private" not in repr(failure)


@pytest.mark.parametrize("kind", ["consultant_turn", "memory_batch"])
@pytest.mark.parametrize(
    ("held_type", "error_type"),
    [
        (HeldModelResponse, ResponseStepSaveError),
        (HeldInputCount, InputCountSaveError),
        (HeldCompaction, CompactionSaveError),
        (HeldPreparationCount, PreparationCountSaveError),
    ],
)
@pytest.mark.parametrize("cancelled", [False, True])
async def test_only_typed_original_survives_failed_saving(kind, held_type, error_type, cancelled):
    supervisor, _, _ = make_supervisor(kind)
    writer = ExecutionWriter(ExecutionScope(uuid4(), uuid4(), ExecutionKind(kind)), uuid4())
    held = held_type("original-thread", uuid4(), {}, {})
    observed = []

    async def run(_writer):
        unrelated = TemporaryContext()
        observed.append(weakref.ref(unrelated))
        error = error_type(held)
        if cancelled:
            raise ResultSaveCancelledError(error)
        raise error

    supervisor._run = run
    supervisor._attempted.add(writer.scope)
    try:
        await supervisor._run_once(writer)
    except asyncio.CancelledError:
        pass
    gc.collect()
    assert observed[0]() is None
    assert supervisor.failures[writer.scope].recovery is held
    assert writer.scope in supervisor._attempted


async def test_settlement_failure_keeps_typed_original_without_either_exception_stack():
    from caliburn.workflows.executions.runner_failures import capture_runner_failure

    observed = []
    held = HeldModelResponse("original-thread", uuid4(), {}, {})

    def fail():
        unrelated = TemporaryContext()
        observed.append(weakref.ref(unrelated))
        try:
            raise ResponseStepSaveError(held)
        except ResponseStepSaveError:
            try:
                raise RuntimeError("synthetic failed settlement")
            except RuntimeError as error:
                return capture_runner_failure(error)

    failure = fail()
    gc.collect()
    assert observed[0]() is None
    assert failure.recovery is held
    assert failure.error_type == "RuntimeError"
