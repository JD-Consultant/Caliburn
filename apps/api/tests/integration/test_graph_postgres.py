"""Verify official saver durability in separate processes against an explicit local test DB."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo


@pytest.mark.postgres
@pytest.mark.parametrize(
    "worker_name,expected_counts",
    [
        ("checkpoint_worker.py", [(1, 0), (0, 1)]),
        ("response_loop_worker.py", [(2, 1), (0, 0)]),
    ],
)
def test_native_items_survive_process_restart_without_reexecuting_saved_node(
    worker_name: str,
    expected_counts: list[tuple[int, int]],
) -> None:
    dsn = os.environ.get("CALIBURN_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set CALIBURN_TEST_DATABASE_URL to an isolated local database ending in _test")
    info = conninfo_to_dict(dsn)
    if info.get("host") not in {"127.0.0.1", "localhost", "::1"} or not info.get(
        "dbname", ""
    ).endswith("_test"):
        pytest.fail("The persistence probe requires an explicit loopback test database")
    schema = "t01_" + uuid4().hex
    worker = Path(__file__).parents[1] / "fixtures" / worker_name
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            env = os.environ.copy()
            env["CALIBURN_TEST_DATABASE_URL"] = make_conninfo(
                dsn, options=f"-c search_path={schema}"
            )
            thread_id = "t01-" + uuid4().hex
            summaries = []
            for mode in ("write", "resume"):
                process = subprocess.run(
                    [sys.executable, str(worker), mode, thread_id],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=30,
                )
                assert process.returncode == 0, process.stderr
                summaries.append(json.loads(process.stdout))
            assert summaries == [
                {"mode": mode, "model_calls": models, "observation_calls": observations}
                for mode, (models, observations) in zip(
                    ("write", "resume"), expected_counts, strict=True
                )
            ]
        finally:
            # Only this test's freshly created schema; never drop a database or pre-existing schema.
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
