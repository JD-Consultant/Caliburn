"""Bounded startup catalog enumeration; no checkpoint copy or writer permission."""

import os
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from jd_relational.storage import schema as db
from jd_relational.storage.service import JdReader, JdStorage, StorageError
from test_storage_postgres import engine
from test_storage_service import FakeAuthority


PG = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                       reason="explicit isolated PostgreSQL test opt-in required")


class DisconnectedEngine:
    dialect = SimpleNamespace(name="postgresql", driver="psycopg")

    def __init__(self):
        self.calls = 0

    def connect(self):
        self.calls += 1
        raise RuntimeError("private database connection detail")


@pytest.mark.parametrize("arguments", [
    {"after": ""}, {"after": "not-a-uuid"}, {"after": UUID(int=1)},
    {"after": "00000000000000000000000000000001"},
    {"after": "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"},
    {"after": "{00000000-0000-0000-0000-000000000001}"},
    {"after": " 00000000-0000-0000-0000-000000000001"},
    {"after": False}, {"after": []},
    {"limit": 0}, {"limit": 501}, {"limit": -1},
    {"limit": True}, {"limit": 1.0}, {"limit": "100"}, {"limit": None},
])
def test_invalid_cursor_or_limit_never_opens_database(arguments):
    engine = DisconnectedEngine()
    with pytest.raises(StorageError, match="^invalid_input$") as error:
        JdReader(engine).document_ids(**arguments)
    assert engine.calls == 0 and error.value.__suppress_context__


def test_database_failure_is_fixed_and_not_an_empty_page():
    engine = DisconnectedEngine()
    with pytest.raises(StorageError, match="^read_failed$") as error:
        JdReader(engine).document_ids()
    assert engine.calls == 1 and error.value.__suppress_context__


@pytest.mark.parametrize("stored", [None, "not-a-uuid", "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA", UUID(int=1)])
def test_corrupt_stored_id_cannot_silently_skip_a_document_or_become_a_cursor(stored, monkeypatch):
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def begin(self): return self
        def execute(self, statement):
            return SimpleNamespace(scalars=lambda: [str(UUID(int=1)), stored])
    reader = JdReader(DisconnectedEngine())
    monkeypatch.setattr(reader, "_connection", lambda **kwargs: Connection())
    with pytest.raises(StorageError, match="^read_failed$") as error:
        reader.document_ids()
    assert error.value.__suppress_context__


@pytest.fixture
def added_documents(engine):
    # Only fresh fixture documents are written; previously saved rows stay intact.
    store = JdStorage(engine, FakeAuthority())
    documents = [store.create_document(uuid4(), f"合成啟動列舉 {index}") for index in range(3)]
    with engine.begin() as conn:
        conn.execute(db.jd_document.update().where(db.jd_document.c.id == documents[1]).values(archived=True))
    return documents


def catalog(engine):
    with engine.connect() as conn:
        return tuple(dict(row) for row in conn.execute(sa.select(db.jd_document).order_by(db.jd_document.c.id)).mappings())


@PG
def test_keyset_pages_list_all_documents_including_archived_without_catalog_changes(engine, added_documents):
    before = catalog(engine)
    expected = tuple(row["id"] for row in before)
    archived = added_documents[1]
    assert next(row for row in before if row["id"] == archived)["archived"]
    reader, actual, after = JdReader(engine), [], None
    while True:
        page = reader.document_ids(after=after, limit=37)
        assert type(page) is tuple and len(page) <= 37
        assert all(str(UUID(value)) == value for value in page)
        if not page:
            break
        actual.extend(page)
        after = page[-1]
        assert len(actual) <= len(expected)
    assert tuple(actual) == expected and archived in actual
    assert set(added_documents).issubset(actual)
    assert len(actual) == len(set(actual))
    assert reader.document_ids(limit=1) == expected[:1]
    assert reader.document_ids() == expected[:100]
    assert reader.document_ids(limit=500) == expected[:500]
    assert catalog(engine) == before


@PG
def test_cursor_is_exclusive_and_terminal_page_is_empty(engine, added_documents):
    expected = tuple(row["id"] for row in catalog(engine))
    anchor = added_documents[0]
    index = expected.index(anchor)
    assert JdReader(engine).document_ids(after=anchor, limit=500) == expected[index + 1:index + 501]
    assert JdReader(engine).document_ids(after=str(UUID(int=2**128 - 1))) == ()


@PG
def test_each_page_uses_one_short_native_readonly_transaction_and_id_only_sql(engine, added_documents):
    statements, modes = [], []
    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
        if statement.startswith("SELECT jd_document.id"):
            modes.append((conn.exec_driver_sql("SHOW transaction_read_only").scalar_one(),
                          conn.exec_driver_sql("SHOW transaction_isolation").scalar_one()))
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        JdReader(engine).document_ids(after=added_documents[0], limit=2)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert modes == [("on", "repeatable read")]
    queries = [sql for sql in statements if sql.startswith("SELECT")]
    assert len(queries) == 1
    assert queries[0].split("\n")[0].strip() == "SELECT jd_document.id"
    assert "ORDER BY jd_document.id" in queries[0] and "LIMIT" in queries[0]
    assert "jd_document.id >" in queries[0] and "archived" not in queries[0]
    assert "FOR UPDATE" not in queries[0]
    assert all(sql.split()[0] in {"SELECT", "SHOW"} for sql in statements)


@PG
def test_query_failure_is_safe_and_does_not_return_partial_ids(engine):
    def broken(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT jd_document.id"):
            raise RuntimeError("synthetic private listing driver detail")
    sa.event.listen(engine, "before_cursor_execute", broken)
    try:
        with pytest.raises(StorageError, match="^read_failed$") as error:
            JdReader(engine).document_ids()
        assert error.value.__suppress_context__
    finally:
        sa.event.remove(engine, "before_cursor_execute", broken)
