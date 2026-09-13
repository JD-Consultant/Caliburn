"""Bounded SQL run-receipt reads with real receipt decoding, no database/provider."""

from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

from jd_relational.storage.history import HistoryError, HistoryReader
from jd_relational.storage.receipts import SavedOperation, body_for


DOCUMENT = str(uuid4())
RUN = str(uuid4())
PRIVATE = "SyntheticPrivateReceiptAndDriverText"


def saved_row(status="committed", *, operation_id=None):
    base = uuid4()
    return {"document_id": DOCUMENT, "operation_id": operation_id or uuid4(),
        "request_digest": "a" * 64, "origin": "ai", "ai_run_id": RUN,
        "base_revision_id": base,
        "result_revision_id": uuid4() if status == "committed" else base if status == "no_change" else None,
        "status": status, "receipt": body_for("jd_set_text", status).model_dump(),
        "created_at": datetime.now(timezone.utc)}


class Connection:
    def __init__(self, rows=(), *, exists=True, failure=None):
        self.rows, self.exists, self.failure = rows, exists, failure
        self.trace = []
        self.statements = []

    def execution_options(self, **options):
        self.trace.append(("options", options))
        return self

    def __enter__(self):
        self.trace.append("connect")
        return self

    def __exit__(self, *args):
        self.trace.append("closed")

    def begin(self):
        self.trace.append("begin")
        return nullcontext()

    def execute(self, statement):
        self.trace.append("query")
        self.statements.append(statement)
        if self.failure:
            raise self.failure
        if len(self.statements) == 1:
            return SimpleNamespace(scalar_one_or_none=lambda: DOCUMENT if self.exists else None)
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: list(self.rows)))


def reader_with(connection):
    return HistoryReader(SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql", driver="psycopg"), connect=lambda: connection))


def disconnected_reader():
    return HistoryReader(SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"),
        connect=lambda: pytest.fail("invalid input must not acquire a connection")))


@pytest.mark.parametrize("field,value", [
    ("document_id", ""), ("document_id", " \n"), ("document_id", None),
    ("document_id", uuid4()), ("document_id", "bad\x00id"), ("document_id", "bad\ud800id"),
    ("run_id", ""), ("run_id", " \n"), ("run_id", None),
    ("run_id", uuid4()), ("run_id", "bad\x00id"), ("run_id", "bad\ud800id"),
    ("limit", 0), ("limit", 97), ("limit", -1), ("limit", True),
    ("limit", 2.0), ("limit", "2"), ("limit", None),
])
def test_invalid_input_does_not_connect(field, value):
    arguments = {"document_id": DOCUMENT, "run_id": RUN, "limit": 96, field: value}
    with pytest.raises(HistoryError, match="^invalid_input$"):
        disconnected_reader().read_run_operations(**arguments)


def test_empty_existing_run_is_no_visible_receipts_not_a_failed_operation():
    conn = Connection()
    assert reader_with(conn).read_run_operations(DOCUMENT, RUN) == ()
    assert conn.trace == [
        ("options", {"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}),
        "connect", "begin", "query", "query", "closed"]
    compiled = conn.statements[1].compile(dialect=postgresql.dialect())
    assert compiled.params == {"document_id_1": DOCUMENT, "ai_run_id_1": RUN,
        "origin_1": "ai", "param_1": 97}
    sql = str(compiled)
    assert "jd_operation.document_id =" in sql and "jd_operation.ai_run_id =" in sql
    assert "jd_operation.origin =" in sql and "ORDER BY jd_operation.operation_id" in sql
    assert "jd_revision" not in sql and "jd_head" not in sql
    assert all(statement.is_select for statement in conn.statements)


def test_missing_document_cannot_masquerade_as_empty_run():
    conn = Connection(exists=False)
    with pytest.raises(HistoryError, match="^document_missing$"):
        reader_with(conn).read_run_operations(DOCUMENT, RUN)
    assert len(conn.statements) == 1 and conn.trace[-1] == "closed"


@pytest.mark.parametrize("status", ["committed", "no_change", "invalid_input", "target_missing",
    "stale_view", "relationship_conflict", "dependent_items", "save_failed"])
def test_original_saved_semantics_use_the_shared_receipt_mapper(status, monkeypatch):
    row = saved_row(status)
    calls = []
    original = SavedOperation.from_row

    def decode(cls, value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(SavedOperation, "from_row", classmethod(decode))
    result = reader_with(Connection([row])).read_run_operations(DOCUMENT, RUN, limit=1)
    assert calls == [row] and result == (original(row),)
    assert result[0].operation_id == row["operation_id"]
    assert result[0].body.command_kind == "jd_set_text"
    assert result[0].status == status


def test_limit_plus_one_fails_instead_of_returning_a_partial_set():
    rows = [saved_row(operation_id=UUID(int=value)) for value in (1, 2, 3)]
    conn = Connection(rows)
    with pytest.raises(HistoryError, match="^run_operations_limit_exceeded$"):
        reader_with(conn).read_run_operations(DOCUMENT, RUN, limit=2)
    assert conn.statements[1].compile().params["param_1"] == 3
    assert conn.trace[-1] == "closed"


@pytest.mark.parametrize("damage", ["version", "extra", "success_error", "failure_result", "failure_code"])
def test_malformed_saved_receipt_cannot_be_projected_as_confirmed(damage):
    row = saved_row("save_failed" if damage.startswith("failure") else "committed")
    if damage == "version":
        row["receipt"]["format_version"] = 999
    elif damage == "extra":
        row["receipt"][PRIVATE] = PRIVATE
    elif damage == "success_error":
        row["receipt"]["error"] = {"code": "save_failed", "message": PRIVATE}
    elif damage == "failure_result":
        row["result_revision_id"] = uuid4()
    else:
        row["receipt"]["error"]["code"] = "stale_view"
    with pytest.raises(HistoryError, match="^stored_content_mismatch$") as caught:
        reader_with(Connection([deepcopy(row)])).read_run_operations(DOCUMENT, RUN)
    assert PRIVATE not in str(caught.value) and caught.value.__suppress_context__


def test_driver_error_is_fixed_and_connection_released():
    conn = Connection(failure=RuntimeError(PRIVATE))
    with pytest.raises(HistoryError, match="^read_failed$") as caught:
        reader_with(conn).read_run_operations(DOCUMENT, RUN)
    assert PRIVATE not in str(caught.value) and caught.value.__suppress_context__
    assert conn.trace[-1] == "closed"


def test_existing_persisted_run_identifier_is_not_reinterpreted_as_uuid():
    conn = Connection()
    assert reader_with(conn).read_run_operations(DOCUMENT, "existing-native-run") == ()
    assert conn.statements[1].compile().params["ai_run_id_1"] == "existing-native-run"
