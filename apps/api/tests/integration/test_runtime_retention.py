"""Release originals only after durable terminal state or confirmed whole-file deletion."""

import asyncio
from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres import PostgresSaver

from caliburn.adapters.database import Database, consistent_read_session
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.native_checkpoint_reads import read_native_records
from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.agent_execution.response_runtime import HeldModelResponse, ResponseStepSaveError
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionBusyError,
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
)
from caliburn.features.job_files.models import CreateJobFile
from caliburn.workflows.consultant_turns.supervisor import ConsultantSupervisor
from caliburn.workflows.job_files import JobFileWorkflow
from caliburn.workflows.work_memory.supervisor import MemorySupervisor

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        (kind, status)
        for kind in ExecutionKind
        for status in (ExecutionStatus.ACTIVE, ExecutionStatus.COMPLETED, ExecutionStatus.FAILED)
    ]
    + [
        (ExecutionKind.CONSULTANT_TURN, ExecutionStatus.CANCELLED),
        (ExecutionKind.CONSULTANT_TURN, ExecutionStatus.PAUSED),
        *[(kind, None) for kind in ExecutionKind],
    ],
)
@pytest.mark.parametrize("runner_failed", [False, True], ids=["returned", "failed"])
def test_runner_cleanup_checks_formal_outcome_before_releasing_original(
    database_settings, database_connection, monkeypatch, kind, status, runner_failed
):
    request_id = uuid4()
    thread_id = f"synthetic-retained:{uuid4()}"
    response = {"id": "resp_original", "output": []}
    saver = PostgresSaver(database_connection, serde=create_graph_serializer())
    saver.setup()
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"request_id": request_id, "response_snapshot": response}
    checkpoint["channel_versions"] = {key: "1" for key in checkpoint["channel_values"]}
    saver.put(
        {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
        checkpoint,
        {"source": "loop", "step": 0, "parents": {}},
        checkpoint["channel_versions"],
    )

    async def scenario():
        db = Database(database_settings)
        held = HeldModelResponse(thread_id, request_id, {}, response)
        entered, release, exited = asyncio.Event(), asyncio.Event(), asyncio.Event()
        task = None

        async def run(_writer):
            entered.set()
            try:
                await release.wait()  # Formal terminal status is not invocation exit.
            finally:
                exited.set()
            if runner_failed:
                raise ResponseStepSaveError(held)

        async def leader_check():
            pass

        supervisor = (
            ConsultantSupervisor(
                sessions=db.sessions, run=run, process_lock=PostgresProcessLock(database_settings)
            )
            if kind == ExecutionKind.CONSULTANT_TURN
            else MemorySupervisor(db.sessions, run=run, check_leadership=leader_check)
        )
        try:
            file = await JobFileWorkflow(db.sessions).create(
                CreateJobFile(uuid4(), "合成檔", "合成人員")
            )
            scope = ExecutionScope(file.job_file.job_file_id, uuid4(), kind)
            async with db.sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
                if status == ExecutionStatus.PAUSED:
                    await executions.pause_execution(session, writer)
                elif status != ExecutionStatus.ACTIVE:
                    await executions.finish_execution(
                        session, writer, status or ExecutionStatus.COMPLETED
                    )
            if status is None:

                async def unavailable(*_args, **_kwargs):
                    raise ConnectionError("synthetic outcome read failure")

                monkeypatch.setattr(executions, "read_execution", unavailable)
            supervisor._attempted.add(scope)
            task = asyncio.create_task(supervisor._run_once(writer))
            key = scope if kind == ExecutionKind.CONSULTANT_TURN else scope.job_file_id
            supervisor._tasks[key] = task
            await asyncio.wait_for(entered.wait(), 3)
            assert scope in supervisor._attempted
            assert supervisor.has_file_runner(scope.job_file_id)
            assert not task.done() and not exited.is_set()
            release.set()
            await asyncio.wait_for(task, 3)
            assert exited.is_set()
            assert not supervisor.has_file_runner(scope.job_file_id)
            terminal = status in (
                ExecutionStatus.COMPLETED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.FAILED,
            )
            assert (scope in supervisor._attempted) is not terminal
            if runner_failed and not terminal:
                assert supervisor.failures[scope].recovery is held
            else:
                assert scope not in supervisor.failures
            # Releasing local retention never deletes the persisted native original.
            async with consistent_read_session(db.sessions) as session:
                records = await read_native_records(
                    session, threads={thread_id: "synthetic"}, channels=("response_snapshot",)
                )
            assert [record["values"]["response_snapshot"] for record in records] == [response]
        finally:
            release.set()
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)
            await db.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


@pytest.mark.parametrize("kind", list(ExecutionKind))
def test_confirmed_deletion_releases_only_that_files_stopped_originals(
    database_settings, client, kind
):
    async def scenario():
        db = Database(database_settings)
        held = HeldModelResponse("synthetic-thread", uuid4(), {}, {})

        async def run(_writer):
            raise ResponseStepSaveError(held)

        async def leader_check():
            pass

        supervisor = (
            ConsultantSupervisor(
                sessions=db.sessions, run=run, process_lock=PostgresProcessLock(database_settings)
            )
            if kind == ExecutionKind.CONSULTANT_TURN
            else MemorySupervisor(db.sessions, run=run, check_leadership=leader_check)
        )
        flow = JobFileWorkflow(
            db.sessions,
            consultant_supervisor=supervisor if kind == ExecutionKind.CONSULTANT_TURN else None,
            memory_supervisor=supervisor if kind == ExecutionKind.MEMORY_BATCH else None,
        )
        writers = []
        try:
            for _ in range(2):
                file = await flow.create(CreateJobFile(uuid4(), "合成檔", "合成人員"))
                scope = ExecutionScope(file.job_file.job_file_id, uuid4(), kind)
                async with db.sessions.begin() as session:
                    await executions.admit_execution(session, scope)
                    writer = await executions.claim_writer(session, scope, writer_id=uuid4())
                supervisor._attempted.add(scope)
                await supervisor._run_once(writer)
                writers.append(writer)
            removed, other = writers
            observed_failures = supervisor.failures
            with pytest.raises(ExecutionBusyError):
                await flow.delete(removed.scope.job_file_id)
            assert supervisor.failures[removed.scope].recovery is held
            async with db.sessions.begin() as session:
                await executions.finish_execution(session, removed, ExecutionStatus.FAILED)
            await flow.delete(removed.scope.job_file_id)
            await flow.delete(removed.scope.job_file_id)
            assert removed.scope not in supervisor.failures
            assert removed.scope not in observed_failures
            assert removed.scope not in supervisor._attempted
            assert supervisor.failures[other.scope].recovery is held
            assert other.scope in supervisor._attempted
        finally:
            await db.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
