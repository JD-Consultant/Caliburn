"""Live HTTP drain must leave time for the application's durable cleanup."""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
import uvicorn

from caliburn.adapters.owned_tasks import join_owned
from caliburn.bootstrap import create_app
from caliburn.features.executions.models import ExecutionStatus
from caliburn.settings import Settings
from caliburn.transport.http.consultant_turns import get_consultant_status_workflow
from scripts import run_backend


def launcher_options(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        run_backend.Settings, "from_environment", lambda: SimpleNamespace(database=True)
    )
    monkeypatch.setattr(run_backend, "create_app", lambda configured: None)
    monkeypatch.setattr(run_backend, "configure_logging", lambda: Mock())
    monkeypatch.setattr(run_backend.uvicorn, "run", lambda app, **kwargs: captured.update(kwargs))
    monkeypatch.setattr("sys.argv", ["run_backend"])
    run_backend.main()
    return captured


def test_launcher_reserves_shutdown_time_for_saving(monkeypatch):
    options = launcher_options(monkeypatch)
    limit = options.get("timeout_graceful_shutdown")
    assert limit is not None and 0 < limit <= 10, "HTTP drain must leave 80 seconds for saving"


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_live_sse_enters_lifespan_before_slow_save(monkeypatch, stream):
    options = launcher_options(monkeypatch)
    events = []
    entered, release = asyncio.Event(), asyncio.Event()
    app = create_app(Settings())
    original = app.router.lifespan_context
    ready = asyncio.Event()

    async def borrower():
        try:
            await asyncio.Event().wait()
        finally:
            events.append("saving")
            await release.wait()
            events.append("saved")

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            owned = asyncio.create_task(borrower())
            ready.set()
            try:
                yield
            finally:
                events.append("lifespan")
                owned.cancel()
                entered.set()
                try:
                    await join_owned(owned)
                except asyncio.CancelledError:
                    pass
        events.append("dependencies_closed")

    app.router.lifespan_context = lifespan

    class Status:
        async def read(self, *args):
            return SimpleNamespace(status=ExecutionStatus.ACTIVE)

    app.dependency_overrides[get_consultant_status_workflow] = Status
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        log_level="critical",
        timeout_graceful_shutdown=options.get("timeout_graceful_shutdown"),
    )
    sock = config.bind_socket()
    server = uvicorn.Server(config)
    stop_signal = signal.SIGBREAK if sys.platform == "win32" else signal.SIGTERM
    previous_handler = signal.signal(stop_signal, lambda *_: None)
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    response = None
    try:
        await asyncio.wait_for(ready.wait(), 3)
        async with httpx.AsyncClient(trust_env=False, timeout=3) as client:
            if stream:
                url = (
                    f"http://127.0.0.1:{sock.getsockname()[1]}/api/job-files/"
                    "10000000-0000-4000-8000-000000000001/consultant-turns/"
                    "10000000-0000-4000-8000-000000000002/activity-stream"
                )
                response = await client.send(client.build_request("GET", url), stream=True)
                assert response.status_code == 200
            # A real OS signal enters Uvicorn's native handler. The restored no-op
            # handler absorbs Uvicorn's final signal replay inside this test process.
            signal.raise_signal(stop_signal)
            await asyncio.wait_for(entered.wait(), 12)
            assert "saved" not in events and not serving.done()
            release.set()
            await asyncio.wait_for(serving, 3)
            assert events == ["lifespan", "saving", "saved", "dependencies_closed"]
            assert not app.state.consultant_activity_hub._subscribers
    finally:
        release.set()
        if response is not None:
            await response.aclose()
        server.should_exit = True
        await asyncio.wait_for(serving, 3)
        sock.close()
        signal.signal(stop_signal, previous_handler)
