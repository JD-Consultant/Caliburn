"""Real protected config + new synthetic PG database + dedicated Windows host.

All created databases and repo-local evidence are retained. Never initialize or
drop the existing fixture database. The consultant is an uninvoked native graph.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep
from uuid import uuid4

import httpx2
from psycopg import Connection, sql
import pytest

from jd_relational.config_file import ConfigFile
from jd_relational.local_configuration import new_configuration, encode_configuration, parse_configuration
from configured_host_worker import connection as configuration_connection, ORIGIN
from test_host_recovery_postgres import await_report
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit synthetic PostgreSQL and Windows opt-in required")
CONNECTION = dict(host="127.0.0.1", port=55436, dbname="caliburn_jd_relational_test",
                  user="jd_test", password="jd-local-test-only", connect_timeout=5)


@pytest.fixture
def fresh_database(engine):
    name = "caliburn_jd_setup_test_" + uuid4().hex
    with Connection.connect(**CONNECTION, autocommit=True) as connection:
        assert connection.execute("SELECT current_database(),current_user,current_setting('server_version_num')::integer").fetchone() == (
            "caliburn_jd_relational_test", "jd_test", 180006)
        connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(name), sql.Identifier("jd_test")))
    directory = Path(__file__).resolve().parents[3] / ".research-tmp" / ("jd-configured-host-" + uuid4().hex)
    directory.mkdir(parents=True)
    (directory / "database.json").write_text(json.dumps({"database": name, "port": 55436}), encoding="utf-8")
    return name, directory


@contextmanager
def worker(mode, database, directory, *, path=None):
    path = path or directory / "host.v1.dpapi"
    report = directory / (mode + "-" + uuid4().hex + ".json")
    with report.with_suffix(".stdout").open("w", encoding="utf-8") as out, report.with_suffix(".stderr").open("w", encoding="utf-8") as err:
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("configured_host_worker.py")),
            mode, str(path), database, str(report)], stdin=subprocess.PIPE, text=True, stdout=out, stderr=err,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            creationflags=subprocess.CREATE_NO_WINDOW)
        native = None
        try:
            import win32api, win32con, win32event
            boot = await_report(process, report.with_suffix(".boot.json"), timeout=10)
            assert boot["pid"] == process.pid or boot["parent_pid"] == process.pid
            native = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, boot["pid"])
            value = await_report(process, report, timeout=45)
            assert value["pid"] == boot["pid"]
            yield process, value, report
        finally:
            if process.poll() is None:
                try:
                    process.communicate("STOP\n", timeout=15)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    if native is not None:
                        win32api.TerminateProcess(native, 74)
                        assert win32event.WaitForSingleObject(native, 10000) == win32con.WAIT_OBJECT_0
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=10)
            if native is not None:
                assert win32event.WaitForSingleObject(native, 10000) == win32con.WAIT_OBJECT_0
                native.Close()
            report.with_suffix(".process.json").write_text(json.dumps({"launcher_pid": process.pid,
                "exit_code": process.returncode}), encoding="utf-8")


def counts(database):
    with Connection.connect(**{**CONNECTION, "dbname": database}) as connection:
        return tuple(connection.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(name))).fetchone()[0]
            for name in ("jd_document", "jd_revision", "jd_operation"))


def schema_identity(database):
    with Connection.connect(**{**CONNECTION, "dbname": database}) as connection:
        return connection.execute("SELECT n.nspname,c.relname,c.oid FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','jd_runtime') "
            "ORDER BY n.nspname,c.relname").fetchall()


@contextmanager
def serving(database, directory):
    with worker("serve", database, directory) as (process, value, report):
        with httpx2.Client(base_url=f"http://127.0.0.1:{value['port']}", timeout=7,
                          trust_env=False, headers={"Origin": ORIGIN, "X-JD-Dataset": value["dataset_id"]}) as client:
            deadline = monotonic() + 10
            while True:
                try:
                    response = client.get("/api/documents")
                    assert response.status_code == 200
                    break
                except httpx2.ConnectError:
                    assert process.poll() is None and monotonic() < deadline
                    sleep(0.03)
            yield process, value, report, client


def finish(process, report):
    process.communicate("STOP\n", timeout=15)
    assert process.returncode == 0
    value = json.loads(report.with_suffix(".finished.json").read_text(encoding="utf-8"))
    assert value["closed"] and value["setup_calls"] == 0
    return value


def test_real_initialize_open_edit_and_restart_keep_original_dataset_and_signer(fresh_database):
    database, directory = fresh_database
    with worker("initialize", database, directory) as (process, value, report):
        assert value["status"] == value["phase"] == "ready"
        assert value["installation_id"] != value["dataset_id"]
        process.communicate(timeout=15)
        assert process.returncode == 0
    with Connection.connect(**{**CONNECTION, "dbname": database}) as connection:
        assert connection.execute("SELECT version_num FROM public.alembic_version").fetchone() == ("20260914_0002",)
        assert connection.execute("SELECT count(*) FROM jd_runtime.checkpoint_migrations").fetchone() == (10,)
        assert connection.execute("SELECT count(*) FROM public.jd_document").fetchone() == (0,)
    initial = value
    objects = schema_identity(database)
    with serving(database, directory) as (process, value, report, client):
        assert value["installation_id"] == initial["installation_id"] and value["dataset_id"] == initial["dataset_id"]
        assert value["phase"] == "ready" and value["recovered"] == 0 and value["setup_calls"] == 0
        create = {"request_key": str(uuid4()), "dataset_id": value["dataset_id"], "title": "客製化的合成工作"}
        wrong = client.post("/api/documents", json=create, headers={"X-JD-Dataset": str(uuid4())})
        assert wrong.status_code == 409 and wrong.json()["code"] == "dataset_changed"
        assert counts(database) == (0, 0, 0)
        created = client.post("/api/documents", json=create)
        assert created.status_code == 200
        document = created.json()["document_id"]
        read = client.post(f"/api/documents/{document}/jd/read", json={"view": "current", "target_ref": None, "cursor": None})
        assert read.status_code == 200
        page = read.json()
        purpose = next(row for row in page["records"] if row["type"] == "field" and row["name"] == "purpose")
        envelope = {"operation_id": str(uuid4()), "base_revision_ref": page["revision_ref"],
            "command": {"tool": "jd_set_text", "arguments": {"target_field_ref": purpose["field_ref"],
                "text": "反映員工真實工作\n只处理合約內的系統 😀", "basis_refs": []}}}
        edit_path = f"/api/documents/{document}/jd/edits"
        assert client.post(edit_path, json=envelope).status_code in {200, 202}
        operation_path = f"/api/documents/{document}/jd/operations/{envelope['operation_id']}"
        deadline = monotonic() + 8
        while True:
            response = client.get(operation_path)
            assert response.status_code == 200
            observed = response.json()
            if observed["presence"] == "observed" and not observed["write_state"]["write_blocked"]:
                break
            assert monotonic() < deadline
            sleep(0.03)
        original = observed["result"]
        assert original["status"] == "committed" and counts(database) == (1, 2, 1)
        metadata_path = f"/api/documents/{document}/metadata"
        metadata = client.get(metadata_path)
        wrong = client.patch(metadata_path, json={"archived": True}, headers={"X-JD-Dataset": str(uuid4()),
            "If-Match": metadata.headers["ETag"], "Content-Type": "application/merge-patch+json"})
        assert wrong.status_code == 409 and client.get(metadata_path).json()["archived"] is False
        wrong = client.post(operation_path + "/recover", json={}, headers={"X-JD-Dataset": str(uuid4())})
        assert wrong.status_code == 409 and counts(database) == (1, 2, 1)
        assert finish(process, report)["operations"] == [envelope["operation_id"]]
    with serving(database, directory) as (process, value, report, client):
        assert value["installation_id"] == initial["installation_id"] and value["dataset_id"] == initial["dataset_id"]
        listed = client.get("/api/documents").json()
        assert listed["dataset_id"] == initial["dataset_id"] and len(listed["documents"]) == 1
        lookup = client.post("/api/document-creations/lookup", json=create)
        assert lookup.status_code == 200 and lookup.json()["document_id"] == document
        assert client.get(operation_path).json()["result"] == original
        # The old signed base/field refs must validate under the saved key;
        # original receipt lookup must not execute the SQL command again.
        replay = client.post(edit_path, json=envelope)
        assert replay.status_code == 200 and replay.json() == original
        assert finish(process, report)["operations"] == []
    assert counts(database) == (1, 2, 1) and schema_identity(database) == objects


def test_published_ready_with_lost_ack_is_readable_without_reinitialization(fresh_database):
    database, directory = fresh_database
    with worker("initialize_lose_ack", database, directory) as (process, initial, report):
        assert initial["status"] == "unconfirmed" and initial["phase"] == "ready"
        process.communicate(timeout=15)
        assert process.returncode == 0
    before = schema_identity(database)
    with serving(database, directory) as (process, value, report, client):
        assert value["installation_id"] == initial["installation_id"] and value["dataset_id"] == initial["dataset_id"]
        assert client.get("/api/documents").json()["documents"] == []
        assert finish(process, report)["operations"] == []
    assert schema_identity(database) == before and counts(database) == (0, 0, 0)


@pytest.mark.parametrize("phase,code", [("missing", "configuration_missing"),
    ("initialization_pending", "configuration_initialization_required"),
    ("initializing", "configuration_initialization_required"), ("maintenance", "configuration_maintenance")])
def test_ordinary_open_missing_or_incomplete_config_never_acquires_resources(engine, phase, code):
    database = "caliburn_jd_setup_test_" + uuid4().hex  # Intentionally not created.
    directory = Path(__file__).resolve().parents[3] / ".research-tmp" / ("jd-configured-host-" + uuid4().hex)
    directory.mkdir(parents=True)
    path = directory / "absent" / "host.v1.dpapi"
    before = None
    if phase != "missing":
        config = new_configuration(**configuration_connection(database))
        config = parse_configuration(json.dumps({**config.model_dump(mode="json"), "phase": phase}).encode("utf-8"))
        ConfigFile(path).create(encode_configuration(config))
        before = path.read_bytes()
    with worker("reject_open", database, directory, path=path) as (process, value, report):
        assert value["status"] == "rejected" and value["code"] == code and value["resource_calls"] == 0
        process.communicate(timeout=15)
        assert process.returncode == 0
    if phase == "missing":
        assert not path.parent.exists()
    else:
        assert path.read_bytes() == before
