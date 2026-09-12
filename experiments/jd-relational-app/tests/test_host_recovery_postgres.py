"""Real dedicated Windows hosts + native PG restart recovery; no supplied proof.

Initialize jd_host_test explicitly. New UUID documents and process evidence stay
in the isolated test database/workspace; no production configuration is read.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep
from uuid import uuid4

import pytest
import sqlalchemy as sa

from host_recovery_worker import SCHEMA, WORKER_CRASH_CODE
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL + native Windows opt-in required")


@pytest.fixture(scope="module")
def installation(engine):
    with engine.connect() as conn:
        assert set(conn.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname=:schema"),
            {"schema": SCHEMA}).scalars()) == {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}, "Initialize jd_host_test explicitly first."
    # One dataset uses one installation key for all sequential scenarios; fresh
    # per pytest invocation, shared by original/new/contending hosts within it.
    return str(uuid4())


def evidence_directory():
    result = Path(__file__).resolve().parents[3] / ".research-tmp" / f"jd-host-recovery-{uuid4().hex}"
    result.mkdir(parents=True)
    return result


def await_report(process, report, *, timeout=45):
    deadline = monotonic() + timeout
    while not report.exists() and process.poll() is None and monotonic() < deadline:
        sleep(0.03)
    assert report.exists(), f"Owned host produced no report; exit={process.poll()}; evidence={report.parent}"
    return json.loads(report.read_text(encoding="utf-8"))


@contextmanager
def worker(mode, installation, directory, manifest):
    report = directory / f"{mode}-{uuid4().hex}.json"
    stdout_path, stderr_path = report.with_suffix(".stdout"), report.with_suffix(".stderr")
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("host_recovery_worker.py")),
            mode, installation, str(manifest), str(report)], stdin=subprocess.PIPE,
            stdout=stdout, stderr=stderr, text=True, env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW)
        native_process = None
        try:
            import win32api
            import win32con
            import win32event
            boot = await_report(process, report.with_suffix(".boot.json"))
            assert boot["parent_pid"] == process.pid or boot["pid"] == process.pid
            native_process = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, boot["pid"])
            value = await_report(process, report)
            assert value["pid"] == boot["pid"]
            assert value["parent_pid"] == process.pid or value["pid"] == process.pid
            yield process, value, report
        finally:
            if process.poll() is None:
                try:
                    process.communicate("STOP\n", timeout=12)
                except (subprocess.TimeoutExpired, OSError, ValueError):
                    if native_process is not None:
                        win32api.TerminateProcess(native_process, 74)
                        assert win32event.WaitForSingleObject(native_process, 10000) == win32con.WAIT_OBJECT_0
                    if process.poll() is None:
                        process.kill()  # Exact Popen-owned launcher, never a port/PID search.
                        process.wait(timeout=10)
            if native_process is not None:
                native_process.Close()
            report.with_suffix(".process.json").write_text(json.dumps({
                "launcher_pid": process.pid, "exit_code": process.returncode,
                "report": report.name}), encoding="utf-8")


def crash(process):
    process.communicate("CRASH\n", timeout=12)
    assert process.returncode == WORKER_CRASH_CODE


def check_recovered(original, recovered, count):
    assert recovered["event"] == "recovered" and recovered["ready_before"] is False
    assert recovered["ready_after"] is True and recovered["recovered_count"] == count
    assert len(recovered["documents"]) == len(original["documents"])
    for before, after in zip(original["documents"], recovered["documents"], strict=True):
        assert after["document_id"] == before["identity"]["document_id"]
        assert after["snapshot"] == before["snapshot"]
        assert after["messages"] == before["messages"]
        assert after["archived"] == before["archived"]
        assert after["pending"] is None and after["operation_count"] == 1
        assert after["receipt"]["operation_id"] == before["identity"]["operation_id"]
        assert after["receipt"]["request_digest"] == before["identity"]["request_digest"]


def test_durable_admission_before_sql_crash_gets_failure_only_on_new_host(installation):
    directory = evidence_directory()
    manifest = directory / "original.json"
    with worker("before_sql", installation, directory, manifest) as (old, first, _):
        assert first["event"] == "pending" and first["original_recovered"] == 0
        original = json.loads(manifest.read_text(encoding="utf-8"))
        assert original["documents"][0]["operation_count"] == 0
        crash(old)
    with worker("recover", installation, directory, manifest) as (new, result, _):
        check_recovered(original, result, 1)
        assert result["documents"][0]["receipt"]["status"] == "save_failed"
        assert result["documents"][0]["revision_count"] == 1
        new.communicate("STOP\n", timeout=12)
        assert new.returncode == 0


def test_committed_ack_lost_crash_returns_exact_original_receipt_without_new_revision(installation):
    directory = evidence_directory()
    manifest = directory / "original.json"
    with worker("commit_loss", installation, directory, manifest) as (old, first, _):
        assert first["event"] == "pending" and first["effect"] == "unknown"
        original = json.loads(manifest.read_text(encoding="utf-8"))
        assert original["documents"][0]["receipt"]["status"] == "committed"
        crash(old)
    with worker("recover", installation, directory, manifest) as (new, result, _):
        check_recovered(original, result, 1)
        row = result["documents"][0]
        assert row["receipt"] == original["documents"][0]["receipt"]
        assert row["revision_count"] == 2
        new.communicate("STOP\n", timeout=12)
        assert new.returncode == 0


def test_second_host_is_refused_before_db_while_original_writer_still_completes(installation):
    directory = evidence_directory()
    manifest = directory / "original.json"
    with worker("before_sql", installation, directory, manifest) as (old, first, first_report):
        assert first["event"] == "pending"
        with worker("contend", installation, directory, manifest) as (other, blocked, _):
            other.wait(timeout=5)
            assert blocked["event"] == "blocked" and blocked["error"] == "host_already_running"
            assert blocked["db_attempts"] == 0 and other.returncode == 0
        assert old.poll() is None
        old.communicate("COMPLETE\n", timeout=12)
        assert old.returncode == 0
        finished = json.loads(first_report.with_suffix(".finished.json").read_text(encoding="utf-8"))
        assert finished["closed"] and finished["statuses"] == ["committed"]


def test_all_catalog_roots_including_archived_are_closed_on_restart(installation):
    directory = evidence_directory()
    manifest = directory / "original.json"
    with worker("two_pending", installation, directory, manifest) as (old, first, _):
        assert first["event"] == "pending"
        original = json.loads(manifest.read_text(encoding="utf-8"))
        assert [row["archived"] for row in original["documents"]] == [False, True]
        assert all(row["operation_count"] == 0 for row in original["documents"])
        crash(old)
    with worker("recover", installation, directory, manifest) as (new, result, _):
        check_recovered(original, result, 2)
        assert all(row["receipt"]["status"] == "save_failed" and row["revision_count"] == 1 for row in result["documents"])
        new.communicate("STOP\n", timeout=12)
        assert new.returncode == 0
