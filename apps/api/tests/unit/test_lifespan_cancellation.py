"""Formal lifespan and supervisors; synthetic borrowed dependencies, no DB/provider."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from psycopg import AsyncConnection

from caliburn import bootstrap
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.app_composition import AppComposition
from caliburn.settings import DatabaseSettings, ModelSettings, Settings
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from caliburn.workflows.memory_supervisor import MemorySupervisor


@pytest.mark.asyncio
async def test_repeated_lifespan_cancel_joins_borrowers_before_closing_dependencies():
    events = []
    cleanup_entered = asyncio.Event()
    release_cleanup = asyncio.Event()
    runner_started = asyncio.Event()

    async def mark(name):
        events.append(name)

    settings = DatabaseSettings(url="postgresql://localhost/synthetic_never_connected")
    database = SimpleNamespace(
        settings=settings,
        sessions=Mock(),
        verify_schema=AsyncMock(),
        close=lambda: mark("database_closed"),
    )
    native = SimpleNamespace(
        conn=Mock(spec=AsyncConnection),
        pipe=None,
        serde=create_graph_serializer(),
    )

    @asynccontextmanager
    async def open_checkpointer(_settings):
        try:
            yield native
        finally:
            events.append("saver_closed")

    lock = SimpleNamespace(
        acquire=AsyncMock(), check=AsyncMock(), close=lambda: mark("leader_closed")
    )

    def consultant(**kwargs):
        supervisor = ConsultantSupervisor(**kwargs)
        supervisor._scan = AsyncMock()  # No persistent discovery/claim in this isolated probe.
        return supervisor

    def memory(*args, **kwargs):
        supervisor = MemorySupervisor(*args, **kwargs)
        supervisor.scan = AsyncMock()
        return supervisor

    async def runner():
        runner_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            events.append("runner_cleanup_started")
            cleanup_entered.set()
            await release_cleanup.wait()
            events.append("runner_cleanup_finished")

    with (
        patch.object(bootstrap, "Database", lambda _: database),
        patch.object(bootstrap, "PostgresProcessLock", lambda _: lock),
        patch.object(bootstrap, "ConsultantSupervisor", consultant),
        patch.object(bootstrap, "MemorySupervisor", memory),
    ):
        app = bootstrap.create_app(
            Settings(database=settings, model=ModelSettings(api_key="synthetic-not-a-key")),
            composition=AppComposition(
                create_responses_client=lambda _: SimpleNamespace(close=lambda: mark("sdk_closed")),
                open_checkpointer=open_checkpointer,
            ),
        )
        lifespan = app.router.lifespan_context(app)
        await lifespan.__aenter__()
        supervisor = app.state.consultant_supervisor
        # One synthetic borrower is registered in the same owned task registry as real runners.
        owned_runner = asyncio.create_task(runner())
        supervisor._tasks["synthetic-scope"] = owned_runner
        await runner_started.wait()
        closing = asyncio.create_task(lifespan.__aexit__(None, None, None))
        await cleanup_entered.wait()
        closing.cancel()
        await asyncio.sleep(0.02)
        closing.cancel()
        await asyncio.sleep(0.02)
        try:
            assert not closing.done(), events
            assert events == ["runner_cleanup_started"]
        finally:
            release_cleanup.set()
            with pytest.raises(asyncio.CancelledError):
                await closing
            await supervisor.close()
        assert events == [
            "runner_cleanup_started",
            "runner_cleanup_finished",
            "leader_closed",
            "sdk_closed",
            "saver_closed",
            "database_closed",
        ]
