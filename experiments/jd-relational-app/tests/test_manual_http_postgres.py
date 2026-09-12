"""Actual Windows owner, native Saver, PostgreSQL and Uvicorn HTTP; no model."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from time import monotonic, sleep
from uuid import uuid4

import httpx2
import pytest
import sqlalchemy as sa

from test_storage_postgres import engine
from test_host_recovery_postgres import await_report


pytestmark = pytest.mark.skipif(sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL + Windows HTTP opt-in required")
ORIGIN = "http://127.0.0.1:3007"


@contextmanager
def server(mode, installation, directory, manifest):
    report = directory / f"{mode}-{uuid4().hex}.json"
    with report.with_suffix(".stdout").open("w", encoding="utf-8") as out, report.with_suffix(".stderr").open("w", encoding="utf-8") as err:
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("manual_http_worker.py")),
            mode, installation, str(manifest), str(report)], stdin=subprocess.PIPE, text=True, stdout=out, stderr=err,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            creationflags=subprocess.CREATE_NO_WINDOW)
        native = None
        try:
            import win32api, win32con, win32event
            boot = await_report(process, report.with_suffix(".boot.json"))
            assert boot["parent_pid"] == process.pid or boot["pid"] == process.pid
            native = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, boot["pid"])
            ready = await_report(process, report)
            assert ready["pid"] == boot["pid"]
            origin = f"http://127.0.0.1:{ready['port']}"
            with httpx2.Client(base_url=origin, timeout=7, trust_env=False, headers={"Origin": ORIGIN}) as client:
                deadline = monotonic() + 10
                while True:
                    try:
                        response = client.get(f"/api/documents/{ready['document']}/jd/state")
                        assert response.status_code == 200, response.text
                        break
                    except httpx2.ConnectError:
                        assert monotonic() < deadline and process.poll() is None
                        sleep(0.03)
                yield process, client, ready, report
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
                native.Close()
            report.with_suffix(".process.json").write_text(json.dumps({"launcher_pid": process.pid,
                "exit_code": process.returncode}), encoding="utf-8")


def edit(client, document, text):
    page = client.post(f"/api/documents/{document}/jd/read", json={"view": "current", "target_ref": None, "cursor": None})
    assert page.status_code == 200, page.text
    value = page.json()
    field = next(row for row in value["records"] if row["type"] == "field" and row["name"] == "purpose")
    return {"operation_id": str(uuid4()), "base_revision_ref": value["revision_ref"],
        "command": {"tool": "jd_set_text", "arguments": {"target_field_ref": field["field_ref"], "text": text, "basis_refs": []}}}


def test_disconnected_write_once_original_result_after_later_edit_and_process_restart(engine):
    directory = Path(__file__).resolve().parents[3] / ".research-tmp" / f"jd-manual-http-{uuid4().hex}"
    directory.mkdir(parents=True)
    installation, manifest = str(uuid4()), directory / "manifest.json"
    with server("new", installation, directory, manifest) as (process, client, ready, report):
        doc = ready["document"]
        body = edit(client, doc, "合約內系統檢查\n原句與空白  😀")
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        path = f"/api/documents/{doc}/jd/edits"
        with socket.create_connection(("127.0.0.1", ready["port"]), timeout=5) as wire:
            wire.sendall((f"POST {path} HTTP/1.1\r\nHost: 127.0.0.1:{ready['port']}\r\n"
                f"Origin: {ORIGIN}\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\n\r\n").encode() + raw)
            entered = await_report(process, report.with_suffix(".entered.json"), timeout=5)
            assert entered["operations"] == [body["operation_id"]]
            # Close without receiving the response, after actual admission.
        started = monotonic()
        status = client.get(f"/api/documents/{doc}/jd/state").json()
        assert monotonic() - started < 1.5
        assert status["running"] and status["write_blocked"]
        lookup_path = f"/api/documents/{doc}/jd/operations/{body['operation_id']}"
        pending = client.get(lookup_path).json()
        assert pending["presence"] == "pending" and pending["result"]["effect"] == "unknown"
        forbidden = client.post(path, json=body, headers={"Origin": "https://malicious.invalid"})
        assert forbidden.status_code == 403
        process.stdin.write("RELEASE\n")
        process.stdin.flush()
        deadline = monotonic() + 7
        while True:
            observed = client.get(lookup_path).json()
            if observed["presence"] == "observed" and not observed["write_state"]["write_blocked"]:
                break
            assert monotonic() < deadline
            sleep(0.03)
        original = observed["result"]
        assert original["status"] == "committed"
        newer = edit(client, doc, "修正後的其他有效工作也保留")
        saved = client.post(path, json=newer)
        assert saved.status_code == 200 and saved.json()["status"] == "committed"
        repeated = client.post(path, json=body)
        assert repeated.status_code == 200 and repeated.json() == original
        process.communicate("STOP\n", timeout=15)
        assert process.returncode == 0
        finished = json.loads(report.with_suffix(".finished.json").read_text(encoding="utf-8"))
        assert finished["operations"] == [body["operation_id"], newer["operation_id"]]
        assert finished["revision_number"] == 3
    with server("resume", installation, directory, manifest) as (process, client, ready, report):
        restored = client.get(lookup_path)
        assert restored.status_code == 200 and restored.json()["result"] == original
        assert not restored.json()["write_state"]["write_blocked"]
        assert client.post(path, json=body).json() == original
        process.communicate("STOP\n", timeout=15)
        assert process.returncode == 0
        finished = json.loads(report.with_suffix(".finished.json").read_text(encoding="utf-8"))
        assert finished["operations"] == [] and finished["revision_number"] == 3
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM jd_operation WHERE document_id=:doc"), {"doc": doc}).scalar_one() == 2
