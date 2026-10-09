"""A separate launcher waits beyond five seconds for a cancelled, blocked native save.

The synthetic console notification cancels the child's await before notifying the
launcher, so this tests cleanup ownership without signalling the user's console.
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from tests.fixtures.process_tree import popen_owned, reap_owned_tree

pytestmark = pytest.mark.postgres


def test_launcher_preserves_blocked_checkpoint_after_console_cancellation(
    client, database_connection: psycopg.Connection, database_settings, tmp_path: Path
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("The launcher integration test requires the project's Node runtime")
    file = client.post(
        "/api/job-files",
        json={
            "command_id": "90000000-0000-4000-8000-000000000001",
            "display_name": "合成關閉測試",
            "employee_name": "合成人員",
        },
    ).json()
    root = Path(__file__).resolve().parents[4]
    probe = tmp_path / "checkpoint_probe.py"
    stop_request = tmp_path / "stop-request"
    cancelled = tmp_path / "cancelled"
    saved = tmp_path / "saved"
    forced = tmp_path / "forced"
    probe.write_text(
        """import asyncio, os
from pathlib import Path
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo
from caliburn.adapters.job_file_checkpointer import JobFilePostgresSaver

async def main():
    dsn = make_conninfo(os.environ["CALIBURN_SHUTDOWN_DSN"],
        options="-c search_path=" + os.environ["CALIBURN_SHUTDOWN_SCHEMA"],
        application_name="caliburn-review-fixes-shutdown")
    async with AsyncPostgresSaver.from_conn_string(dsn) as native:
        await native.setup()
        saver = JobFilePostgresSaver(native)
        config = {"configurable": {"thread_id": os.environ["CALIBURN_SHUTDOWN_FILE"]
            + ":synthetic-shutdown", "checkpoint_ns": ""}}
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"] = {"response_snapshot": {"id": "original-result"}}
        checkpoint["channel_versions"] = {"response_snapshot": "1"}
        task = asyncio.create_task(saver.aput(config, checkpoint,
            {"source": "loop", "step": 0, "parents": {}}, checkpoint["channel_versions"]))
        while not Path(os.environ["CALIBURN_SHUTDOWN_STOP"]).exists():
            await asyncio.sleep(0.01)
        task.cancel()
        Path(os.environ["CALIBURN_SHUTDOWN_CANCELLED"]).write_text("cancelled")
        try:
            await task
        except asyncio.CancelledError:
            pass
        restored = await saver.aget_tuple(config)
        if restored is None or restored.checkpoint["channel_values"].get("response_snapshot") != {
            "id": "original-result"
        }:
            raise RuntimeError("The original result was not retained")
        Path(os.environ["CALIBURN_SHUTDOWN_SAVED"]).write_text("saved")

asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
""",
        encoding="utf-8",
    )
    manager = f"""
import {{ spawn }} from 'node:child_process';
import {{ existsSync, writeFileSync }} from 'node:fs';
import {{ EventEmitter }} from 'node:events';
import {{ runAppProcesses }} from {json.dumps((root / "scripts/app-processes.mjs").as_uri())};
const signals = new EventEmitter();
const poll = setInterval(() => {{
  if (existsSync(process.env.CALIBURN_SHUTDOWN_CANCELLED)) {{
    clearInterval(poll);
    signals.emit('SIGINT');
  }}
}}, 10);
try {{
  await runAppProcesses([{{}}], {{ signals, platform: 'win32',
    start: () => spawn(process.env.CALIBURN_SHUTDOWN_PYTHON,
      [process.env.CALIBURN_SHUTDOWN_PROBE],
      {{ env: process.env, stdio: 'inherit', windowsHide: true }}),
    stop: (child, force) => {{
      writeFileSync(process.env.CALIBURN_SHUTDOWN_FORCED, String(force));
      child.kill('SIGKILL');
    }}
  }});
}} finally {{ clearInterval(poll); }}
"""
    env = {
        **os.environ,
        "CALIBURN_SHUTDOWN_DSN": database_settings.url,
        "CALIBURN_SHUTDOWN_SCHEMA": database_settings.schema,
        "CALIBURN_SHUTDOWN_FILE": file["job_file_id"],
        "CALIBURN_SHUTDOWN_PYTHON": sys.executable,
        "CALIBURN_SHUTDOWN_PROBE": str(probe),
        "CALIBURN_SHUTDOWN_STOP": str(stop_request),
        "CALIBURN_SHUTDOWN_CANCELLED": str(cancelled),
        "CALIBURN_SHUTDOWN_SAVED": str(saved),
        "CALIBURN_SHUTDOWN_FORCED": str(forced),
    }
    database_connection.execute("BEGIN")
    database_connection.execute(
        "SELECT 1 FROM job_files WHERE job_file_id=%s FOR UPDATE", (file["job_file_id"],)
    )
    # The manager and the probe it starts are one owned tree: a failed run reaps both.
    process = popen_owned([node, "--input-type=module", "-e", manager], cwd=root, env=env)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            database_connection.execute("SELECT pg_stat_clear_snapshot()")
            waiting = database_connection.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE application_name='caliburn-review-fixes-shutdown' "
                "AND wait_event_type='Lock'"
            ).fetchone()[0]
            if waiting:
                break
            assert process.poll() is None, "The synthetic checkpoint process exited prematurely"
            time.sleep(0.02)
        else:
            pytest.fail("The synthetic checkpoint never reached the held database lock")
        stop_request.write_text("stop", encoding="utf-8")
        deadline = time.monotonic() + 5
        while not cancelled.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert cancelled.exists()
        time.sleep(6)
        assert process.poll() is None, "The launcher forced a still-saving checkpoint"
        assert not forced.exists()
        database_connection.execute("ROLLBACK")
        assert process.wait(timeout=10) == 0
        assert saved.read_text() == "saved"
        assert not forced.exists()
    finally:
        try:
            database_connection.execute("ROLLBACK")
            stop_request.touch()
        finally:
            # Reaping must not depend on the database connection still being usable.
            reap_owned_tree(process)
    assert (
        database_connection.execute(
            sql.SQL("SELECT count(*) FROM {}.checkpoints WHERE thread_id=%s").format(
                sql.Identifier(database_settings.schema)
            ),
            (file["job_file_id"] + ":synthetic-shutdown",),
        ).fetchone()[0]
        == 1
    )
