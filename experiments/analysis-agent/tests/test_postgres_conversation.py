"""Real DB/process proof, explicitly skipped without an isolated test DSN."""

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from langgraph.checkpoint.postgres import PostgresSaver
import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest


def test_postgres_process_restart_preserves_input_native_items_and_tool_result():
    dsn = os.environ.get("Q019_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set Q019_TEST_DATABASE_URL to dedicated q019_agent_test DB; not a durability pass")
    # Fixed test-only destination. Never setup/migrate the application's DB.
    params = conninfo_to_dict(dsn)
    assert params.get("dbname") == "q019_agent_test", "Only the dedicated q019_agent_test database is allowed"
    assert 1 <= int(params.get("connect_timeout", "0")) <= 10, "Provide connect_timeout between 1 and 10 seconds"
    # Bound SQL/lock waits for parent setup/cleanup as well as child probes.
    # Dedicated-test policy; this deliberately overrides caller startup options.
    dsn = make_conninfo(dsn, options="-c statement_timeout=10000 -c lock_timeout=5000")
    with psycopg.connect(dsn) as connection:
        assert connection.execute("SELECT current_database()").fetchone()[0] == "q019_agent_test"
    thread_id = "q019-test-" + str(uuid4())
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["Q019_TEST_DATABASE_URL"] = dsn
    env["PYTHONPATH"] = str(root / "src")
    env["PYTHONUTF8"] = "1"
    worker = Path(__file__).with_name("postgres_probe.py")
    with PostgresSaver.from_conn_string(dsn) as saver:
        saver.setup()
        try:
            for mode in ("write", "resume"):
                completed = subprocess.run(
                    [sys.executable, str(worker), mode, thread_id],
                    cwd=root, env=env, capture_output=True, text=True,
                    encoding="utf-8", timeout=45, check=False,
                )
                # Do not put a DB password/DSN in the process command or output.
                assert completed.returncode == 0, (mode, completed.stdout, completed.stderr)
        finally:
            # Only this test's generated thread, through the official API.
            saver.delete_thread(thread_id)
