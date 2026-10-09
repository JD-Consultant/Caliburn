"""Release originals only after durable terminal state or confirmed whole-file deletion."""

import asyncio
from uuid import uuid4

import pytest

from caliburn.adapters.database import Database
from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.agent_execution.tool_steps import HeldModelResponse, ResponseStepSaveError
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionBusyError,
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
)
from caliburn.features.job_files.models import CreateJobFile
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from caliburn.workflows.job_files import JobFileWorkflow
from caliburn.workflows.memory_supervisor import MemorySupervisor

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        (kind, status)
        for kind in ExecutionKind
        for status in (ExecutionStatus.ACTIVE, ExecutionStatus.COMPLETED, ExecutionStatus.FAILED)
    ]
    + [(ExecutionKind.CONSULTANT_TURN, ExecutionStatus.CANCELLED)],
)
def test_runner_cleanup_checks_formal_outcome_before_releasing_original(
    database_settings, kind, status
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
        try:
            file = await JobFileWorkflow(db.sessions).create(
                CreateJobFile(uuid4(), "合成檔", "合成人員")
            )
            scope = ExecutionScope(file.job_file.job_file_id, uuid4(), kind)
            async with db.sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
                if status != ExecutionStatus.ACTIVE:
                    await executions.finish_execution(session, writer, status)
            supervisor._attempted.add(scope)
            await supervisor._run_once(writer)
            assert scope in supervisor._attempted  # GC never grants another invocation.
            if status == ExecutionStatus.ACTIVE:
                assert supervisor.failures[scope].recovery is held
            else:
                assert scope not in supervisor.failures
        finally:
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
