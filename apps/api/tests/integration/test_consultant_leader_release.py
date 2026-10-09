"""A shared leader stays fenced until its dependent workers have stopped."""

import asyncio
from contextlib import suppress
from typing import Literal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.database import Database
from caliburn.adapters.process_lock import PostgresProcessLock, ProcessLockUnavailableError
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionWriter
from caliburn.settings import DatabaseSettings
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor

pytestmark = pytest.mark.postgres
ExitPath = Literal["close", "scan_failure", "startup_failure"]


async def unused_runner(writer: ExecutionWriter) -> None:
    raise AssertionError("No consultant was admitted")


async def fail_discovery(session: AsyncSession) -> None:
    raise ConnectionError("synthetic discovery outage")


@pytest.mark.parametrize("exit_path", ["close", "scan_failure", "startup_failure"])
def test_leader_is_not_released_before_dependent_cleanup(
    database_settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch, exit_path: ExitPath
) -> None:
    async def scenario() -> None:
        db = Database(database_settings)
        leader = PostgresProcessLock(database_settings)
        contender = PostgresProcessLock(database_settings)
        cleanup_started = asyncio.Event()
        may_finish_cleanup = asyncio.Event()
        calls = 0

        async def cleanup() -> None:
            nonlocal calls
            calls += 1
            cleanup_started.set()
            await may_finish_cleanup.wait()

        supervisor = ConsultantSupervisor(
            sessions=db.sessions,
            run=unused_runner,
            process_lock=leader,
            before_leader_release=cleanup,
            poll_interval_seconds=60,
        )
        operation: asyncio.Task[None] | None = None
        try:
            if exit_path == "startup_failure":
                monkeypatch.setattr(executions, "list_active_consultants", fail_discovery)
                operation = asyncio.create_task(supervisor.start())
            else:
                await supervisor.start()
                if exit_path == "close":
                    operation = asyncio.create_task(supervisor.close())
                else:
                    monkeypatch.setattr(executions, "list_active_consultants", fail_discovery)
                    supervisor.notify()
            await asyncio.wait_for(cleanup_started.wait(), 3)
            with pytest.raises(ProcessLockUnavailableError):
                await contender.acquire()
            # Do not let explicit close cancel an abnormal monitor's cleanup.
            if operation is None:
                operation = asyncio.create_task(supervisor.close())
            may_finish_cleanup.set()
            if exit_path == "startup_failure":
                with pytest.raises(ConnectionError, match="discovery outage"):
                    await operation
            else:
                await operation
            await supervisor.close()
            await contender.acquire()
            assert calls == 1
            if exit_path == "scan_failure":
                assert supervisor.failure.error_type == "ConnectionError"
        finally:
            may_finish_cleanup.set()
            if operation is not None:
                await asyncio.gather(operation, return_exceptions=True)
            await supervisor.close()
            await leader.close()
            await contender.close()
            await db.close()

    asyncio.run(scenario(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("exit_path", ["close", "scan_failure", "startup_failure"])
def test_failed_dependent_cleanup_retains_fence_without_automatic_retry(
    database_settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch, exit_path: ExitPath
) -> None:
    async def scenario() -> None:
        db = Database(database_settings)
        leader = PostgresProcessLock(database_settings)
        contender = PostgresProcessLock(database_settings)
        cleanup_started = asyncio.Event()
        failure = RuntimeError("synthetic dependent cleanup failure")
        calls = 0

        async def cleanup() -> None:
            nonlocal calls
            calls += 1
            cleanup_started.set()
            raise failure

        supervisor = ConsultantSupervisor(
            sessions=db.sessions,
            run=unused_runner,
            process_lock=leader,
            before_leader_release=cleanup,
            poll_interval_seconds=60,
        )
        try:
            if exit_path == "startup_failure":
                monkeypatch.setattr(executions, "list_active_consultants", fail_discovery)
                with pytest.raises(RuntimeError) as caught:
                    await supervisor.start()
                assert caught.value is failure
            else:
                await supervisor.start()
                if exit_path == "scan_failure":
                    monkeypatch.setattr(executions, "list_active_consultants", fail_discovery)
                    supervisor.notify()
                    await asyncio.wait_for(cleanup_started.wait(), 3)
            for _ in range(2):
                with pytest.raises(RuntimeError) as caught:
                    await supervisor.close()
                assert caught.value is failure
                with pytest.raises(ProcessLockUnavailableError):
                    await contender.acquire()
            assert calls == 1
        finally:
            with suppress(RuntimeError):
                await supervisor.close()
            # Test-only cleanup: production must not forcibly release this fence.
            await leader.close()
            await contender.close()
            await db.close()

    asyncio.run(scenario(), loop_factory=asyncio.SelectorEventLoop)
