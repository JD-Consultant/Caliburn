"""Real PG leader/session and writer fences; runner boundary is deliberately synthetic."""

import asyncio
from uuid import uuid4

import pytest

from caliburn.adapters.database import Database
from caliburn.adapters.process_lock import PostgresProcessLock, ProcessLockUnavailableError
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.job_files.models import CreateJobFile
from caliburn.features.job_files.service import create_job_file
from caliburn.settings import DatabaseSettings
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor

pytestmark = pytest.mark.postgres


async def admit(
    db: Database,
    status: ExecutionStatus = ExecutionStatus.ACTIVE,
    kind: ExecutionKind = ExecutionKind.CONSULTANT_TURN,
) -> ExecutionWriter:
    async with db.sessions.begin() as session:
        created = await create_job_file(session, CreateJobFile(uuid4(), "合成工作", "合成人員"))
        scope = ExecutionScope(created.job_file.job_file_id, uuid4(), kind)
        await executions.admit_execution(session, scope)
        writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        if status == ExecutionStatus.PAUSED:
            await executions.pause_execution(session, writer)
        elif status != ExecutionStatus.ACTIVE:
            await executions.finish_execution(session, writer, outcome=status)
        return writer


async def lock_exclusion(
    empty_database_settings: DatabaseSettings,
) -> None:
    first = PostgresProcessLock(empty_database_settings)
    second = PostgresProcessLock(empty_database_settings)
    try:
        await first.acquire()
        await first.check()
        with pytest.raises(ProcessLockUnavailableError):
            await second.acquire()
        await first.close()
        await second.acquire()
        await second.check()
    finally:
        await first.close()
        await second.close()


async def startup_and_shutdown(
    database_settings: DatabaseSettings,
) -> None:
    db = Database(database_settings)
    calls: list[ExecutionWriter] = []
    stopped = asyncio.Event()
    first_entered = asyncio.Event()
    second_entered = asyncio.Event()

    async def run(writer: ExecutionWriter) -> None:
        calls.append(writer)
        (first_entered if len(calls) == 1 else second_entered).set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    supervisor = ConsultantSupervisor(
        sessions=db.sessions,
        run=run,
        process_lock=PostgresProcessLock(database_settings),
        poll_interval_seconds=0.02,
    )
    contender = ConsultantSupervisor(
        sessions=db.sessions,
        run=run,
        process_lock=PostgresProcessLock(database_settings),
    )
    try:
        original = await admit(db)
        excluded = [
            await admit(db, status)
            for status in (
                ExecutionStatus.PAUSED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
            )
        ]
        excluded.append(await admit(db, kind=ExecutionKind.MEMORY_BATCH))
        await supervisor.start()
        await asyncio.wait_for(first_entered.wait(), 3)
        for _ in range(10):
            supervisor.notify(original.scope)
        with pytest.raises(ProcessLockUnavailableError):
            await contender.start()
        newcomer = await admit(db)
        supervisor.notify(newcomer.scope)
        await asyncio.wait_for(second_entered.wait(), 3)
        assert {writer.scope for writer in calls} == {original.scope, newcomer.scope}
        assert calls[0].writer_id != original.writer_id
        async with db.sessions() as session:
            assert (await executions.read_execution(session, original.scope)).writer_id == calls[
                0
            ].writer_id
            for old in excluded:
                assert (
                    await executions.read_execution(session, old.scope)
                ).writer_id == old.writer_id
        await supervisor.close()
        assert stopped.is_set()
        async with db.sessions() as session:
            assert (
                await executions.read_execution(session, original.scope)
            ).status == ExecutionStatus.ACTIVE
        # The lease is released only after local runners have actually exited.
        replacement = PostgresProcessLock(database_settings)
        await replacement.acquire()
        await replacement.close()
    finally:
        await supervisor.close()
        await contender.close()
        await db.close()


async def unknown_failure(
    database_settings: DatabaseSettings,
) -> None:
    db = Database(database_settings)
    calls: list[ExecutionWriter] = []
    unknown = RuntimeError("synthetic unknown outbound result")
    first_failed = asyncio.Event()
    next_scanned = asyncio.Event()

    async def run(writer: ExecutionWriter) -> None:
        calls.append(writer)
        if len(calls) == 1:
            first_failed.set()
        else:
            next_scanned.set()
        raise unknown

    supervisor = ConsultantSupervisor(
        sessions=db.sessions,
        run=run,
        process_lock=PostgresProcessLock(database_settings),
        poll_interval_seconds=0.02,
    )
    try:
        writer = await admit(db)
        await supervisor.start()
        await asyncio.wait_for(first_failed.wait(), 3)
        assert supervisor.failures[writer.scope].error_type == type(unknown).__name__
        assert supervisor.stopped_reason(writer.scope) == "runner_failed"
        newcomer = await admit(db)
        supervisor.notify(writer.scope)
        await asyncio.wait_for(next_scanned.wait(), 3)
        assert [call.scope for call in calls] == [writer.scope, newcomer.scope]
        async with db.sessions() as session:
            assert (
                await executions.read_execution(session, writer.scope)
            ).status == ExecutionStatus.ACTIVE
    finally:
        await supervisor.close()
        await db.close()


async def lost_session(
    database_settings: DatabaseSettings,
) -> None:
    db = Database(database_settings)
    lock = PostgresProcessLock(database_settings)
    contender = PostgresProcessLock(database_settings)
    entered = asyncio.Event()
    stopped = asyncio.Event()
    stopping = asyncio.Event()
    may_exit = asyncio.Event()

    async def run(writer: ExecutionWriter) -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopping.set()
            await may_exit.wait()
            stopped.set()

    supervisor = ConsultantSupervisor(
        sessions=db.sessions,
        run=run,
        process_lock=lock,
        poll_interval_seconds=0.02,
    )
    try:
        writer = await admit(db)
        await supervisor.start()
        await asyncio.wait_for(entered.wait(), 3)
        assert lock._connection is not None
        await lock._connection.close()  # Fault only our physical PG session, not the OS fence.
        await asyncio.wait_for(stopping.wait(), 3)
        with pytest.raises(ProcessLockUnavailableError):
            await contender.acquire()
        may_exit.set()
        await asyncio.wait_for(stopped.wait(), 3)
        assert supervisor.failure is not None
        supervisor.notify(writer.scope)
        assert not supervisor.running
        async with db.sessions() as session:
            assert (
                await executions.read_execution(session, writer.scope)
            ).status == ExecutionStatus.ACTIVE
    finally:
        may_exit.set()
        await supervisor.close()
        await contender.close()
        await db.close()


def test_dedicated_session_lock_excludes_contender_until_close(
    empty_database_settings: DatabaseSettings,
) -> None:
    asyncio.run(lock_exclusion(empty_database_settings), loop_factory=asyncio.SelectorEventLoop)


def test_startup_active_only_duplicate_notify_and_shutdown_fencing(
    database_settings: DatabaseSettings,
) -> None:
    asyncio.run(startup_and_shutdown(database_settings), loop_factory=asyncio.SelectorEventLoop)


def test_unknown_runner_failure_is_retained_not_resubmitted(
    database_settings: DatabaseSettings,
) -> None:
    asyncio.run(unknown_failure(database_settings), loop_factory=asyncio.SelectorEventLoop)


def test_lost_leader_session_stops_tasks_without_product_cancellation(
    database_settings: DatabaseSettings,
) -> None:
    asyncio.run(lost_session(database_settings), loop_factory=asyncio.SelectorEventLoop)


def test_immediate_shutdown_releases_session_without_starting_monitor(
    empty_database_settings: DatabaseSettings,
) -> None:
    async def scenario() -> None:
        db = Database(empty_database_settings)

        async def run(writer: ExecutionWriter) -> None:
            raise AssertionError("Empty schema has no runner")

        # Test the real lock but isolate discovery: no schema/migration needed here.
        class EmptySupervisor(ConsultantSupervisor):
            async def _scan(self) -> None:
                await asyncio.sleep(0)

        supervisor = EmptySupervisor(
            sessions=db.sessions,
            run=run,
            process_lock=PostgresProcessLock(empty_database_settings),
        )
        contender = PostgresProcessLock(empty_database_settings)
        try:
            await supervisor.start()
            await supervisor.close()  # No yield between start returning and close.
            await contender.acquire()
        finally:
            await supervisor.close()
            await contender.close()
            await db.close()

    asyncio.run(scenario(), loop_factory=asyncio.SelectorEventLoop)
