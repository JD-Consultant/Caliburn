"""Local lifecycle wakes durable Memory work without tying it to the A response request."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest

from caliburn.adapters.database import Database
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews import service as interviews
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.features.job_files import service as job_files
from caliburn.features.job_files.models import CreateJobFile
from caliburn.settings import DatabaseSettings
from caliburn.workflows.interview_completion import record_formal_interview
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow

pytestmark = pytest.mark.postgres


def execute[T](settings: DatabaseSettings, action: Callable[[Database], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(settings)
        try:
            return await action(database)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(run())


def test_shutdown_preserves_active_batch_and_restart_resumes_same_scope(
    database_settings: DatabaseSettings,
) -> None:
    async def scenario(database: Database) -> None:
        from caliburn.workflows.memory_supervisor import MemorySupervisor

        async with database.sessions.begin() as session:
            created = await job_files.create_job_file(
                session, CreateJobFile(uuid4(), "背景恢復", "合成人員")
            )
            file_id = created.job_file.job_file_id
            await interviews.create_opening(session, file_id)
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
            await executions.admit_execution(session, scope)
            await interviews.accept_input(
                session,
                SubmitInterviewInput(file_id, uuid4(), "盤點工作"),
                execution_id=scope.execution_id,
            )
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        requests = MemoryConsolidationWorkflow(database.sessions)
        await requests.request(writer, uuid4())
        async with database.sessions.begin() as session:
            await record_formal_interview(session, writer, reply_text="請舉例")
            await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
        entered = asyncio.Event()
        seen: list[ExecutionWriter] = []

        async def leader() -> None:
            return None  # External leadership boundary; DB eligibility is real.

        async def run(batch_writer: ExecutionWriter) -> None:
            seen.append(batch_writer)
            entered.set()
            await asyncio.Event().wait()

        first = MemorySupervisor(
            database.sessions, run=run, check_leadership=leader, poll_interval_seconds=0.01
        )
        await first.start()
        await asyncio.wait_for(entered.wait(), 5)
        first.notify()
        await first.close()
        assert len(seen) == 1
        async with database.sessions() as session:
            assert (
                await executions.read_execution(session, seen[0].scope)
            ).status == ExecutionStatus.ACTIVE
        entered.clear()
        second = MemorySupervisor(
            database.sessions, run=run, check_leadership=leader, poll_interval_seconds=0.01
        )
        await second.start()
        await asyncio.wait_for(entered.wait(), 5)
        await second.close()
        assert seen[0].scope == seen[1].scope and seen[0].writer_id != seen[1].writer_id

    execute(database_settings, scenario)


def test_unknown_runner_error_is_not_poll_retry(database_settings: DatabaseSettings) -> None:
    # Use the same real discovery/admission setup via a completed synthetic turn.
    async def scenario(database: Database) -> None:
        from caliburn.workflows.memory_supervisor import MemorySupervisor

        async with database.sessions.begin() as session:
            created = await job_files.create_job_file(
                session, CreateJobFile(uuid4(), "失敗隔離", "合成")
            )
            file_id = created.job_file.job_file_id
            await interviews.create_opening(session, file_id)
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
            await executions.admit_execution(session, scope)
            await interviews.accept_input(
                session,
                SubmitInterviewInput(file_id, uuid4(), "盤點"),
                execution_id=scope.execution_id,
            )
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        await MemoryConsolidationWorkflow(database.sessions).request(writer, uuid4())
        async with database.sessions.begin() as session:
            await record_formal_interview(session, writer, reply_text="請舉例")
            await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
        calls = 0
        failed = asyncio.Event()

        async def leader() -> None:
            return None

        async def run(batch_writer: ExecutionWriter) -> None:
            nonlocal calls
            calls += 1
            failed.set()
            raise ConnectionError("synthetic unknown save")

        supervisor = MemorySupervisor(
            database.sessions, run=run, check_leadership=leader, poll_interval_seconds=0.01
        )
        await supervisor.start()
        await asyncio.wait_for(failed.wait(), 5)
        supervisor.notify()
        await supervisor.scan()
        await supervisor.scan()
        await supervisor.close()
        assert calls == 1 and len(supervisor.failures) == 1

    execute(database_settings, scenario)
