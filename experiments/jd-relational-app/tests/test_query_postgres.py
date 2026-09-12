"""Opt-in real PG + ASGI and a test-only loopback Uvicorn child; no providers.

FakeAuthority is confined to fixture construction. The HTTP host is assembled
with JdReader, never JdStorage, and has no mutation endpoint or writer owner.
"""

from contextlib import asynccontextmanager, contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

import httpx2
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from jd_relational.change_reads import ChangeReadService
from jd_relational.query_api import QueryServices, create_query_app
from jd_relational.reads import ReadService
from jd_relational.references import ReferenceCodec
from jd_relational.storage import schema as db
from jd_relational.storage.history import HistoryReader
from jd_relational.storage.service import JdReader, JdStorage
from test_storage_postgres import engine
from test_storage_service import FakeAuthority, change, insert_item, task_args
from test_read_storage_integration import assert_complete_projection


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                               reason="explicit isolated PostgreSQL test opt-in required")
SIGNING_KEY = b"query-http-synthetic-signing-key-only"
DATASET = "query-http-test-dataset"
READ_BODY = {"view": "current", "target_ref": None, "cursor": None}


def make_services(engine):
    codec = ReferenceCodec(SIGNING_KEY, DATASET)
    history = HistoryReader(engine)
    return QueryServices(ReadService(JdReader(engine), history, codec, page_bytes=4096),
                         ChangeReadService(history, codec, page_bytes=6000))


def make_app(engine):
    @asynccontextmanager
    async def resources():
        yield make_services(engine)
    return create_query_app(resources)


@pytest.fixture
def client(engine):
    with TestClient(make_app(engine), base_url="http://127.0.0.1") as value:
        yield value


@pytest.fixture
def prepared(engine):
    store = JdStorage(engine, FakeAuthority())
    current = store.read_current(store.create_document(uuid4(), "合成 HTTP 讀取"))
    for kind, values in (
        ("collaborator", {"name": "客服窗口", "scope_text": "外部承諾由窗口確認"}),
        ("duty", {"name": "系統維運", "scope_text": "合約內系統"}),
        ("knowledge", {"name": "服務範圍", "description": "判斷合約涵蓋項目"}),
        ("skill", {"name": "異常判讀", "description": None}),
        ("qualification", {"text": "目前無固定證照要求"}),
    ):
        item = insert_item("condition" if kind == "qualification" else kind, **values)
        if kind == "qualification":
            item["item"]["container_ref"] = "container:qualification"
        current, _, _ = change(store, current, "jd_insert_item", item)
    duty = next(iter(current.domain["duties"]))
    arguments = task_args(f"tasks:{duty}")
    arguments["description"] = "安全隔離後檢查合約內系統。\n未知原因保留未知😀"
    arguments["outcomes"].append({"text": "異常轉交紀錄", "basis_refs": []})
    arguments["capabilities"] = [{"capability_ref": f"capability:{key}", "basis_refs": []}
                                 for key in current.domain["capabilities"]]
    current, intent, result = change(store, current, "jd_create_task", arguments,
                                     origin="ai", ai_run_id="synthetic-http-run")
    return store, current, intent, result


def path(document, changes=False):
    return f"/api/documents/{document}/jd/" + ("changes/read" if changes else "read")


def read_page(client, document, view="current", target=None, cursor=None):
    response = client.post(path(document), json={"view": view, "target_ref": target, "cursor": cursor})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
    return response.json()


def collect(client, document, *, view="current", target=None, first=None, change_ref=None):
    page, rows, pages, seen = first, [], [], set()
    for _ in range(300):
        if page is None:
            if change_ref is None:
                page = read_page(client, document, view, target, next_cursor if pages else None)
            else:
                response = client.post(path(document, True), json={
                    "change_ref": change_ref, "cursor": next_cursor if pages else None})
                assert response.status_code == 200, response.text
                page = response.json()
        pages.append(page)
        assert page["has_more"] == (page["next_cursor"] is not None)
        assert page["start_index"] == len(rows)
        rows.extend(page["records"])
        if not page["has_more"]:
            assert page["total_records"] is None or page["total_records"] == len(rows)
            return rows, pages
        next_cursor = page["next_cursor"]
        assert next_cursor not in seen
        seen.add(next_cursor)
        page = None
    pytest.fail("Pagination must finish without replaying or losing a cursor.")


def row_state(engine, document):
    """Document-scoped values/counts; other concurrent test documents are ignored."""
    state = {}
    with engine.connect() as conn:
        for table in db.metadata.sorted_tables:
            if table.name not in db.JD_TABLE_NAMES:
                continue
            scope = table.c.id if table.name == "jd_document" else table.c.document_id
            rows = conn.execute(sa.select(table).where(scope == document)
                                .order_by(*table.primary_key.columns)).mappings().all()
            state[table.name] = [dict(row) for row in rows]
    return state


@contextmanager
def observe_queries(engine):
    statements, modes, seen_connections = [], [], set()
    def observed(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip())
        if statement.lstrip().upper().startswith("SELECT") and id(conn) not in seen_connections:
            seen_connections.add(id(conn))
            modes.append((conn.exec_driver_sql("SHOW transaction_isolation").scalar_one(),
                          conn.exec_driver_sql("SHOW transaction_read_only").scalar_one()))
    sa.event.listen(engine, "after_cursor_execute", observed)
    try:
        yield statements
    finally:
        sa.event.remove(engine, "after_cursor_execute", observed)
    assert statements
    assert not any(sql.upper().startswith(("INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP", "ALTER"))
                   for sql in statements)
    assert modes and all(mode == ("repeatable read", "on") for mode in modes)


def test_actual_current_http_reads_all_six_sections_without_any_write(client, engine, prepared):
    _, current, _, _ = prepared
    before = row_state(engine, current.document_id)
    with observe_queries(engine):
        rows, pages = collect(client, current.document_id)
    assert len(pages) > 1 and all(page["access"] == "current" for page in pages)
    assert len({page["revision_ref"] for page in pages}) == 1
    assert {row["title"] for row in rows if row["type"] == "section"} == {
        "基本資料", "職務目的", "職責與任務", "所需知識", "所需技能", "適用條件與責任邊界"}
    assert any(row["type"] == "field" and row["value"] == "安全隔離後檢查合約內系統。\n未知原因保留未知😀" for row in rows)
    assert any(row["type"] == "field" and row["value"] is None for row in rows)
    sources = [row for row in rows if row["type"] == "source"]
    assert sources and all(row["basis_status"] == "current" and row["readability"] == "not_checked" for row in sources)
    assert_complete_projection(rows, current, ReferenceCodec(SIGNING_KEY, DATASET), purpose="current")
    assert row_state(engine, current.document_id) == before


def test_http_history_and_change_keep_original_result_when_head_advances(client, engine, prepared):
    store, current, intent, saved = prepared
    document = current.document_id
    current_first = read_page(client, document)
    index, _ = collect(client, document, view="history")
    original = index[0]
    assert original["revision_number"] == current.revision_number
    historical_first = read_page(client, document, "history", original["revision_ref"])
    first_change_response = client.post(path(document, True), json={"change_ref": original["change_ref"], "cursor": None})
    assert first_change_response.status_code == 200
    first_change = first_change_response.json()
    assert current_first["has_more"] and historical_first["has_more"] and first_change["has_more"]
    task = next(iter(current.domain["tasks"]))
    newer, _, _ = change(store, current, "jd_set_text", {
        "target_field_ref": f"task:{task}.description", "text": "較新的人工更正", "basis_refs": []})
    before = row_state(engine, document)
    with observe_queries(engine):
        stale = client.post(path(document), json={**READ_BODY, "cursor": current_first["next_cursor"]})
        assert stale.status_code == 409 and stale.json()["jd_read_error"]["code"] == "stale_view"
        old_rows, old_pages = collect(client, document, view="history", target=original["revision_ref"], first=historical_first)
        changes, change_pages = collect(client, document, first=first_change, change_ref=original["change_ref"])
        fresh, _ = collect(client, document)
    assert all(page["access"] == "history" for page in old_pages)
    assert_complete_projection(old_rows, current, ReferenceCodec(SIGNING_KEY, DATASET), purpose="history")
    assert any(row["type"] == "field" and row["value"] == "安全隔離後檢查合約內系統。\n未知原因保留未知😀" for row in old_rows)
    assert any(row["type"] == "field" and row["value"] == "較新的人工更正" for row in fresh)
    assert any(row["type"] == "source" and row["basis_status"] == "needs_recheck" for row in fresh)
    assert all(row["basis_status"] == "current" for row in old_rows if row["type"] == "source")
    codec = ReferenceCodec(SIGNING_KEY, DATASET)
    change_identity = codec.resolve(original["change_ref"], document_id=document, roles={"change"}, purposes={"observation"})
    assert change_identity.entity_id == str(intent.operation_id)
    assert change_identity.revision_id == str(saved.receipt.result_revision_id) != str(newer.revision_id)
    fields = [row["record"] for row in changes if row["type"] == "value" and row["record"]["type"] == "field"]
    assert fields and all("較新的人工更正" != row["value"] for row in fields)
    for row in fields:
        codec.resolve(row["field_ref"], document_id=document, roles={"field"}, purposes={"history"})
    assert len(change_pages) > 1 and row_state(engine, document) == before


def test_real_read_scope_and_missing_document_errors_never_write(client, engine, prepared):
    store, current, _, _ = prepared
    other = store.read_current(store.create_document(uuid4(), "另一個 HTTP 文件"))
    index, _ = collect(client, current.document_id, view="history")
    before = row_state(engine, current.document_id), row_state(engine, other.document_id)
    with observe_queries(engine):
        missing = client.post(path(str(uuid4())), json=READ_BODY)
        assert missing.status_code == 404 and missing.json()["jd_read_error"]["code"] == "target_missing"
        for route, arguments in (
            (path(other.document_id), {"view": "history", "target_ref": index[0]["revision_ref"], "cursor": None}),
            (path(other.document_id, True), {"change_ref": index[0]["change_ref"], "cursor": None}),
        ):
            wrong = client.post(route, json=arguments)
            assert wrong.status_code == 422 and wrong.json()["jd_read_error"]["code"] == "invalid_ref"
    assert (row_state(engine, current.document_id), row_state(engine, other.document_id)) == before


def test_driver_failure_reaches_safe_http_problem_and_leaves_rows(client, engine, prepared, caplog):
    _, current, _, _ = prepared
    before, hits = row_state(engine, current.document_id), []
    def broken(conn, cursor, statement, parameters, context, executemany):
        if "FROM jd_head" in statement:
            hits.append(True)
            raise RuntimeError("private-query-driver-SENTINEL")
    sa.event.listen(engine, "before_cursor_execute", broken)
    try:
        response = client.post(path(current.document_id), json=READ_BODY)
    finally:
        sa.event.remove(engine, "before_cursor_execute", broken)
    assert hits and response.status_code == 500
    assert response.json()["jd_read_error"]["code"] == "read_failed"
    assert "private-query-driver-SENTINEL" not in response.text + caplog.text
    assert row_state(engine, current.document_id) == before


def _serve(ready_path, exit_path):
    """Test-only child; public isolated DB configuration, no mutation service."""
    import uvicorn
    if os.environ.get("JD_RELATIONAL_TEST_DB") != "1":
        raise SystemExit("explicit isolated PostgreSQL test opt-in required")
    url = sa.URL.create("postgresql+psycopg", username="jd_test", password="jd-local-test-only",
                        host="127.0.0.1", port=55436, database="caliburn_jd_relational_test")
    child_engine = sa.create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    verbs = []
    sa.event.listen(child_engine, "before_cursor_execute",
        lambda conn, cursor, statement, parameters, context, executemany: verbs.append(statement.split()[0].upper()))
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(64)
    port = listener.getsockname()[1]

    @asynccontextmanager
    async def resources():
        with child_engine.connect() as conn:
            assert conn.execute(sa.text("SELECT current_database(), current_user")).one() == ("caliburn_jd_relational_test", "jd_test")
        ready = Path(ready_path)
        temporary = ready.with_suffix(".tmp")
        temporary.write_text(json.dumps({"pid": os.getpid(), "parent_pid": os.getppid(), "port": port}), encoding="utf-8")
        temporary.replace(ready)
        try:
            yield make_services(child_engine)
        finally:
            child_engine.dispose()

    server = uvicorn.Server(uvicorn.Config(create_query_app(resources), host="127.0.0.1", port=port,
        loop="asyncio", http="h11", workers=1, reload=False, access_log=False,
        proxy_headers=False, log_level="warning", timeout_graceful_shutdown=5))
    def stop_own_server():
        if sys.stdin.readline().strip() in {"STOP", ""}:
            server.should_exit = True
    Thread(target=stop_own_server, daemon=True).start()
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
        Path(exit_path).write_text(json.dumps({"pid": os.getpid(), "port": port,
            "stopped": server.should_exit, "sql_verbs": verbs}), encoding="utf-8")


def test_new_uvicorn_process_serves_real_pg_reads_and_original_change(prepared, engine):
    _, current, intent, _ = prepared
    before = row_state(engine, current.document_id)
    # Keep the PID/exit evidence. Pytest's mode-0700 temp factory is inaccessible
    # in this Windows sandbox; a fresh workspace directory needs no cleanup.
    tmp_path = Path(__file__).resolve().parents[3] / ".research-tmp" / f"jd-query-http-{uuid4().hex}"
    tmp_path.mkdir(parents=True)
    ready, stopped = tmp_path / "query-ready.json", tmp_path / "query-stopped.json"
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"), PYTHONUTF8="1")
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--query-server", str(ready), str(stopped)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    exit_code = None
    try:
        deadline = monotonic() + 20
        while not ready.exists() and child.poll() is None and monotonic() < deadline:
            sleep(0.05)
        assert ready.exists() and child.poll() is None, "The owned query child must finish startup."
        receipt = json.loads(ready.read_text(encoding="utf-8"))
        # Windows' venv launcher may have a different PID from its Python child.
        assert child.pid in {receipt["pid"], receipt["parent_pid"]}
        assert 0 < receipt["port"] < 65536
        with httpx2.Client(base_url=f"http://127.0.0.1:{receipt['port']}", trust_env=False, timeout=5) as client:
            # The listener was bound before lifespan; serving starts immediately afterwards.
            rows, _ = collect(client, current.document_id)
            assert any(row["type"] == "item" and row["kind"] == "task" for row in rows)
            index, _ = collect(client, current.document_id, view="history")
            changes, _ = collect(client, current.document_id, change_ref=index[0]["change_ref"])
            assert any(row["type"] == "change" and row["entity_kind"] == "task" for row in changes)
            decoded = ReferenceCodec(SIGNING_KEY, DATASET).resolve(index[0]["change_ref"],
                document_id=current.document_id, roles={"change"}, purposes={"observation"})
            assert decoded.entity_id == str(intent.operation_id)
            assert client.post(path(current.document_id).replace("/read", "/edit"), json={}).status_code == 404
        child.communicate("STOP\n", timeout=10)
        exit_code = child.returncode
        assert exit_code == 0
        exit_receipt = json.loads(stopped.read_text(encoding="utf-8"))
        assert exit_receipt["pid"] == receipt["pid"] and exit_receipt["stopped"]
        assert set(exit_receipt["sql_verbs"]) <= {"SELECT", "SET", "SHOW"}
        assert "SELECT" in exit_receipt["sql_verbs"]
    finally:
        if child.poll() is None:
            try:
                child.communicate("STOP\n", timeout=10)
            except (subprocess.TimeoutExpired, ValueError):
                child.terminate()  # Only this test's owned launcher, never another port/PID.
                child.communicate(timeout=10)
        (tmp_path / "query-process-result.json").write_text(json.dumps({"launcher_pid": child.pid,
            "exit_code": child.returncode, "graceful": exit_code == 0}), encoding="utf-8")
    assert row_state(engine, current.document_id) == before


if __name__ == "__main__":
    assert len(sys.argv) == 4 and sys.argv[1] == "--query-server"
    _serve(sys.argv[2], sys.argv[3])
