"""FH01–FH04: real Windows host/PG restart; only SDK traffic is synthetic.

Opt-in only, fixed dedicated native schema initialized separately. No setup,
DDL, deletion, provider call, fake Future or supplied stopped proof here.
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

from ai_host_recovery_worker import DATASET, INSTALLATION, SCHEMA, WORKER_CRASH_CODE
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL + native Windows opt-in required")


@pytest.fixture(scope="module", autouse=True)
def dedicated_schema(engine):
    with engine.connect() as conn:
        assert set(conn.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname=:schema"),
            {"schema": SCHEMA}).scalars()) == {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}, "Initialize jd_ai_host_test explicitly first."
        assert list(conn.execute(sa.text("SELECT v FROM jd_ai_host_test.checkpoint_migrations ORDER BY v")).scalars()) == list(range(10))


def evidence_directory():
    result = Path(__file__).resolve().parents[3] / ".research-tmp" / f"jd-ai-host-recovery-{uuid4().hex}"
    result.mkdir(parents=True)
    return result


def await_report(process, report, timeout=55):
    deadline = monotonic() + timeout
    while not report.exists() and process.poll() is None and monotonic() < deadline:
        sleep(0.03)
    assert report.exists(), f"Owned host produced no report; exit={process.poll()}; evidence={report.parent}"
    return json.loads(report.read_text(encoding="utf-8"))


@contextmanager
def worker(mode, directory, manifest):
    report = directory / f"{mode}-{uuid4().hex}.json"
    environment = {**os.environ, "PYTHONUTF8": "1", "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
                   "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    with report.with_suffix(".stdout").open("w", encoding="utf-8") as stdout, report.with_suffix(".stderr").open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("ai_host_recovery_worker.py")),
            mode, str(manifest), str(report)], stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
            text=True, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
        native_process = None
        try:
            import win32api
            import win32con
            import win32event
            boot = await_report(process, report.with_suffix(".boot.json"))
            assert boot["parent_pid"] == process.pid or boot["pid"] == process.pid
            assert boot["installation_id"] == INSTALLATION and boot["dataset_id"] == DATASET
            native_process = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, boot["pid"])
            value = await_report(process, report)
            assert value["pid"] == boot["pid"]
            assert value["event"] != "error", value
            yield process, value, report
        finally:
            if process.poll() is None:
                try:
                    process.communicate("STOP\n", timeout=15)
                except (subprocess.TimeoutExpired, OSError, ValueError):
                    if native_process is not None:
                        win32api.TerminateProcess(native_process, 74)
                        assert win32event.WaitForSingleObject(native_process, 10000) == win32con.WAIT_OBJECT_0
                    if process.poll() is None:
                        process.kill()  # Exact owned launcher; no port/PID enumeration.
                        process.wait(timeout=10)
            if native_process is not None:
                native_process.Close()
            report.with_suffix(".process.json").write_text(json.dumps({"launcher_pid": process.pid,
                "exit_code": process.returncode, "report": report.name}), encoding="utf-8")


def stop(process, report):
    process.communicate("STOP\n", timeout=15)
    assert process.returncode == 0
    assert json.loads(report.with_suffix(".finished.json").read_text(encoding="utf-8"))["closed"] is True


def crash(process):
    process.communicate("CRASH\n", timeout=12)
    assert process.returncode == WORKER_CRASH_CODE


def original(manifest):
    return json.loads(manifest.read_text(encoding="utf-8"))


def check_recovered(result, count):
    assert result["event"] == "recovered" and result["ready_before"] is False and result["ready_after"] is True
    assert result["recovered_count"] == count
    assert result["counts"] == {"model": 0, "tools": 0, "execute": 0, "setup": 0}
    for document in result["documents"]:
        assert document["root_next"] == []
        if document["ai"] is not None:
            assert document["ai"]["closed"] is True


def preserved(before, after):
    for key in ("document_id", "snapshot", "revision_id", "revision_number", "revision_count", "archived"):
        assert after[key] == before[key]
    old, new = before["ai"], after["ai"]
    assert new["record"] == {**old["record"], "status": "failed"}
    assert new["messages"][:len(old["messages"])] == old["messages"]
    for key in ("bindings", "model_view", "read_binding"):
        assert new[key] == old[key]
    # Recovery appends paired ToolMessages only, never an invented final answer.
    assert all(m["type"] == "tool" for m in new["messages"][len(old["messages"]):])


def new_result(before, after, index, status):
    binding = before["ai"]["bindings"][index]
    receipt = next(r for r in after["receipts"] if r["operation_id"] == binding["operation_id"])
    for key in ("operation_id", "request_digest", "document_id", "base_revision_id", "origin"):
        assert receipt[key] == binding[key]
    assert receipt["ai_run_id"] == binding["run_id"] and receipt["status"] == status
    messages = [m for m in after["ai"]["messages"] if m["type"] == "tool" and m["tool_call_id"] == binding["tool_call_id"]]
    assert len(messages) == 1
    result = json.loads(messages[0]["content"])
    assert result["status"] == status and result["receipt_durability"] == "confirmed"


def test_fh01_normal_closed_run_is_exactly_read_only_after_real_host_restart():
    directory = evidence_directory()
    manifest = directory / "original.json"
    with worker("normal", directory, manifest) as (old, first, report):
        assert first["event"] == "completed" and first["counts"] == {"model": 3, "tools": 2, "execute": 1, "setup": 0}
        before = original(manifest)
        assert before["documents"][0]["ai"]["record"]["status"] == "completed"
        assert before["documents"][1]["archived"] is True
        stop(old, report)
    with worker("recover", directory, manifest) as (new, result, report):
        check_recovered(result, 0)
        assert result["documents"] == before["documents"]
        stop(new, report)


def test_fh02_live_host_blocks_before_db_then_real_uncommitted_process_exit_recovers_failure():
    directory = evidence_directory()
    manifest = directory / "original.json"
    with worker("sql_pending", directory, manifest) as (old, first, _):
        assert first["event"] == "pending"
        assert first["witness"]["transaction_revision_count"] == 2
        assert first["witness"]["transaction_operation_count"] == 1
        before = original(manifest)["documents"][0]
        assert before["revision_count"] == 1 and before["receipts"] == []
        with worker("contend", directory, manifest) as (contender, blocked, _):
            contender.wait(timeout=5)
            assert blocked["error"] == "host_already_running" and blocked["db_attempts"] == 0
            assert contender.returncode == 0
        assert old.poll() is None
        crash(old)
    with worker("recover", directory, manifest) as (new, result, report):
        check_recovered(result, 1)
        after = result["documents"][0]
        preserved(before, after)
        assert len(after["receipts"]) == 1
        new_result(before, after, 0, "save_failed")
        stop(new, report)


def test_fh03_original_a_and_commit_ack_lost_b_keep_exact_receipts_without_replay():
    directory = evidence_directory()
    manifest = directory / "original.json"
    with worker("commit_loss", directory, manifest) as (old, first, _):
        assert first["event"] == "pending" and first["counts"]["model"] == 4
        assert first["witness"]["real_commit_ack_lost"] and first["witness"]["local_closure_suppressed"]
        before = original(manifest)["documents"][0]
        assert before["revision_count"] == 3 and len(before["receipts"]) == 2
        assert all(r["status"] == "committed" for r in before["receipts"])
        assert before["ai"]["record"]["status"] == "running" and not before["ai"]["closed"]
        crash(old)
    with worker("recover", directory, manifest) as (new, result, report):
        check_recovered(result, 1)
        after = result["documents"][0]
        preserved(before, after)
        assert after["receipts"] == before["receipts"]
        new_result(before, after, 0, "committed")
        new_result(before, after, 1, "committed")
        stop(new, report)


def test_fh04_after_model_before_sql_and_original_start_input_are_closed_together():
    directory = evidence_directory()
    manifest = directory / "original.json"
    with worker("two_boundaries", directory, manifest) as (old, first, _):
        assert first["event"] == "pending" and first["counts"] == {"model": 3, "tools": 1, "execute": 0, "setup": 0}
        data = original(manifest)
        before_a, before_b = data["documents"]
        assert data["witness"]["after_model_binding_put_confirmed"]
        assert len(before_a["ai"]["bindings"]) == 1 and before_a["receipts"] == []
        assert before_b["ai"]["bindings"] == [] and before_b["root_next"] == ["__start__"]
        assert before_b["root_metadata"]["source"] == "input"
        assert before_b["root_config"]["configurable"]["checkpoint_id"] == data["witness"]["native_start"]["checkpoint_id"]
        previous = data["witness"]["previous_second"]["messages"]
        assert before_b["ai"]["messages"][:len(previous)] == previous
        assert before_b["ai"]["messages"][-1:] == data["witness"]["native_start"]["messages"]
        crash(old)
    with worker("recover", directory, manifest) as (new, result, report):
        check_recovered(result, 2)
        after_a, after_b = result["documents"]
        preserved(before_a, after_a)
        preserved(before_b, after_b)
        new_result(before_a, after_a, 0, "save_failed")
        assert len(after_a["receipts"]) == 1 and after_b["receipts"] == []
        assert after_b["ai"]["messages"] == before_b["ai"]["messages"]
        stop(new, report)
