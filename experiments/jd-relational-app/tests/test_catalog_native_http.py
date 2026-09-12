"""True Windows host, native Saver, PostgreSQL and lost HTTP creation response."""
import json
import os
from pathlib import Path
import socket
import sys
from uuid import uuid4

import pytest
import sqlalchemy as sa

from test_storage_postgres import engine
from test_host_recovery_postgres import await_report
from test_manual_http_postgres import server, edit, ORIGIN

pytestmark = pytest.mark.skipif(sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL + Windows HTTP opt-in required")
PATCH_HEADERS = {"Content-Type": "application/merge-patch+json"}


def test_catalog_lost_creation_response_preserves_identity_and_survives_native_restart(engine):
    directory = Path(__file__).resolve().parents[3] / ".research-tmp" / f"jd-catalog-http-{uuid4().hex}"
    directory.mkdir(parents=True)
    manifest, installation = directory / "document.json", str(uuid4())
    with server("catalog", installation, directory, manifest) as (process, client, ready, report):
        dataset = client.get("/api/documents").json()["dataset_id"]
        body = {"dataset_id": dataset, "request_key": str(uuid4()), "title": "自己的工作，不是公版範本"}
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        connection = socket.create_connection(("127.0.0.1", ready["port"]), timeout=7)
        try:
            connection.sendall((f"POST /api/documents HTTP/1.1\r\nHost: 127.0.0.1:{ready['port']}\r\n"
                f"Origin: {ORIGIN}\r\nContent-Type: application/json\r\nContent-Length: {len(encoded)}\r\n\r\n").encode("ascii") + encoded)
            committed = await_report(process, report.with_suffix(".catalog-created.json"))
        finally:
            connection.close()  # Caller never received the successfully created result.
        document = committed["document"]
        lookup = client.post("/api/document-creations/lookup", json=body)
        assert lookup.status_code == 200 and lookup.json()["document_id"] == document
        process.stdin.write("RELEASE\n")
        process.stdin.flush()
        assert client.post("/api/documents", json=body).json()["document_id"] == document
        read_path = f"/api/documents/{document}/jd/read"
        original = client.post(read_path, json={"view": "current", "target_ref": None, "cursor": None}).json()
        assert all(not record.get("text") for record in original["records"] if record["type"] == "field")
        changed = client.post(f"/api/documents/{document}/jd/edits", json=edit(client, document, "忠實描述我的實際工作"))
        assert changed.status_code == 200 and changed.json()["status"] == "committed"
        path = f"/api/documents/{document}/metadata"
        old = client.get(path)
        renamed = client.patch(path, json={"title": "只修改列表名稱"},
            headers={**PATCH_HEADERS, "If-Match": old.headers["etag"]})
        assert renamed.status_code == 200
        assert client.patch(path, json={"archived": True},
            headers={**PATCH_HEADERS, "If-Match": old.headers["etag"]}).status_code == 412
        archived = client.patch(path, json={"archived": True},
            headers={**PATCH_HEADERS, "If-Match": renamed.headers["etag"]})
        assert archived.status_code == 200 and archived.json()["archived"]
        assert client.post("/api/document-creations/lookup", json=body).json()["document_id"] == document
        assert client.post("/api/documents", json=body).json()["document_id"] == document
        assert client.get(f"/api/documents/{document}/jd/state").json()["write_blocked"]
        snapshot = client.post(read_path, json={"view": "current", "target_ref": None, "cursor": None}).json()
    assert process.returncode == 0
    with server("resume", installation, directory, manifest) as (process, client, ready, report):
        loaded = client.get(path)
        assert loaded.json() == archived.json() and loaded.headers["etag"] == archived.headers["etag"]
        assert client.post("/api/documents", json=body).json()["document_id"] == document
        assert client.post(read_path, json={"view": "current", "target_ref": None, "cursor": None}).json() == snapshot
        restored = client.patch(path, json={"archived": False},
            headers={**PATCH_HEADERS, "If-Match": loaded.headers["etag"]})
        assert restored.status_code == 200 and not restored.json()["archived"]
        assert client.post(read_path, json={"view": "current", "target_ref": None, "cursor": None}).json() == snapshot
    assert process.returncode == 0
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM jd_document WHERE create_request_key=:key"),
                            {"key": body["request_key"]}).scalar_one() == 1
        assert conn.execute(sa.text("SELECT count(*) FROM jd_revision WHERE document_id=:doc"),
                            {"doc": document}).scalar_one() == 2
        assert conn.execute(sa.text("SELECT count(*) FROM jd_operation WHERE document_id=:doc"),
                            {"doc": document}).scalar_one() == 1
