"""Captured AI operation ranges: real SQL/codec, bounded fake connection only.

No database, Saver, provider or writer authority is used. These tests do not
establish that the caller supplied a complete or terminal native run.
"""

from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

from jd_relational.changes import compare_snapshots
from jd_relational.snapshots import empty_domain, snapshot_digest, snapshot_from_domain
from jd_relational.storage import schema as db
from jd_relational.storage.history import HistoryError, HistoryReader
from jd_relational.storage.receipts import SavedOperation, body_for


DOCUMENT = str(uuid4())
RUN = "existing-native-run"
PRIVATE = "SyntheticPrivateRunChangeData"


def revision_id(number):
    return UUID(int=100 + number)


def operation_id(number):
    # UUID and timestamp order deliberately oppose revision order.
    return UUID(int=1000 - number)


def revision_row(number, *, text=None, origin="ai", run_id=RUN):
    domain = empty_domain(DOCUMENT, str(revision_id(number)))
    domain["profile"]["purpose"] = text
    snapshot = snapshot_from_domain(domain)
    initial = number == 1
    created = datetime(2026, 9, 13, tzinfo=timezone.utc) - timedelta(seconds=number)
    row = dict(document_id=DOCUMENT, revision_id=revision_id(number), revision_number=number,
        parent_revision_id=None if initial else revision_id(number - 1),
        origin="initial" if initial else origin, format_version=3, engine_profile="jd-relational-v1",
        snapshot=snapshot, content_digest=snapshot_digest(snapshot), created_at=created,
        _parent_number=None if initial else number - 1)
    operation = dict(document_id=DOCUMENT, operation_id=operation_id(number), request_digest="a" * 64,
        origin=origin, ai_run_id=run_id if origin == "ai" else None,
        base_revision_id=revision_id(number - 1), result_revision_id=revision_id(number),
        status="committed", receipt=body_for("jd_set_text", "committed").model_dump(), created_at=created)
    row.update({f"_op_{column.name}": None if initial else operation[column.name]
                for column in db.jd_operation.c})
    return row


def metadata(row):
    return {key: deepcopy(value) for key, value in row.items() if key != "snapshot"}


def receipt(row):
    return SavedOperation.from_row({column.name: row[f"_op_{column.name}"] for column in db.jd_operation.c})


class Connection:
    def __init__(self, rows=(), *, endpoints=(), exists=True, fail_at=None):
        self.rows = [metadata(row) for row in rows]
        self.endpoints = {row["revision_id"]: deepcopy(row) for row in endpoints}
        self.exists, self.fail_at = exists, fail_at
        self.trace, self.statements = [], []

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
        if len(self.statements) == self.fail_at:
            raise RuntimeError(PRIVATE)
        if len(self.statements) == 1:
            return SimpleNamespace(scalar_one_or_none=lambda: DOCUMENT if self.exists else None)
        if "snapshot" in statement.selected_columns.keys():
            key = statement.compile().params["revision_id_1"]
            return SimpleNamespace(mappings=lambda: SimpleNamespace(
                one_or_none=lambda: deepcopy(self.endpoints.get(key))))
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: deepcopy(self.rows)))


def reader_with(conn):
    return HistoryReader(SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"),
                                        connect=lambda: conn))


def disconnected_reader():
    return HistoryReader(SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"),
        connect=lambda: pytest.fail("invalid input must not acquire a connection")))


@pytest.mark.parametrize("field,value", [
    ("document_id", ""), ("document_id", " \n"), ("document_id", None),
    ("document_id", uuid4()), ("document_id", "bad\x00id"), ("document_id", "bad\ud800id"),
    ("run_id", ""), ("run_id", " \n"), ("run_id", None),
    ("run_id", uuid4()), ("run_id", "bad\x00id"), ("run_id", "bad\ud800id"),
    ("operation_ids", []), ("operation_ids", None), ("operation_ids", (str(uuid4()),)),
    ("operation_ids", (True,)), ("operation_ids", (None,)),
    ("operation_ids", (operation_id(2), operation_id(2))),
    ("operation_ids", tuple(UUID(int=i + 1) for i in range(97))),
])
def test_invalid_input_rejected_before_connection(field, value):
    args = dict(document_id=DOCUMENT, run_id=RUN, operation_ids=(operation_id(2),))
    args[field] = value
    with pytest.raises(HistoryError, match="^invalid_input$"):
        disconnected_reader().read_run_change(**args)


def test_empty_captured_ids_check_document_but_do_not_claim_a_complete_empty_run():
    conn = Connection()
    value = reader_with(conn).read_run_change(DOCUMENT, RUN, ())
    assert value.continuity == "none" and value.receipts == ()
    assert value.base is None and value.result is None
    assert set(value.__dataclass_fields__) == {"continuity", "receipts", "base", "result"}
    assert len(conn.statements) == 1
    assert conn.trace == [("options", {"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}),
                          "connect", "begin", "query", "closed"]


@pytest.mark.parametrize("ids", [(), (operation_id(2),)])
def test_missing_document_never_becomes_empty_material(ids):
    conn = Connection(exists=False)
    with pytest.raises(HistoryError, match="^document_missing$"):
        reader_with(conn).read_run_change(DOCUMENT, RUN, ids)
    assert len(conn.statements) == 1 and conn.trace[-1] == "closed"


def test_continuous_range_orders_by_revision_and_only_reads_two_full_endpoints(monkeypatch):
    first, second, third = revision_row(1), revision_row(2, text="中途"), revision_row(3, text="最後")
    conn = Connection([third, second], endpoints=[first, third])
    calls = []
    original = SavedOperation.from_row

    def decode(cls, row):
        calls.append(row["operation_id"])
        return original(row)

    monkeypatch.setattr(SavedOperation, "from_row", classmethod(decode))
    value = reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(3), operation_id(2)))
    assert value.continuity == "continuous"
    assert value.receipts == (receipt(second), receipt(third))
    assert value.base.revision_id == revision_id(1) and value.result.revision_id == revision_id(3)
    assert value.base.snapshot == first["snapshot"] and value.result.snapshot == third["snapshot"]
    assert operation_id(2) in calls and operation_id(3) in calls
    assert len(conn.statements) == 4 and all(statement.is_select for statement in conn.statements)
    assert conn.trace.count("begin") == 1 and conn.trace[-1] == "closed"
    batch = conn.statements[1]
    assert "snapshot" not in batch.selected_columns.keys()
    compiled = batch.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "jd_head" not in sql and "snapshot" not in sql
    assert "producer.operation_id IN" in sql and "producer.ai_run_id =" in sql
    assert "producer.origin =" in sql and "producer.document_id =" in sql
    assert "jd_revision.parent_revision_id" in sql and "parent.revision_number" in sql
    assert "committed" in compiled.params.values() and RUN in compiled.params.values()
    assert set(compiled.params["operation_id_1"]) == {operation_id(2), operation_id(3)}
    assert [stmt.compile().params["revision_id_1"] for stmt in conn.statements[2:]] == [revision_id(1), revision_id(3)]


def test_same_field_changed_back_preserves_two_events_with_no_net_content():
    initial, middle, final = revision_row(1), revision_row(2, text="中途"), revision_row(3)
    conn = Connection([middle, final], endpoints=[initial, final])
    value = reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(2), operation_id(3)))
    assert value.continuity == "continuous" and len(value.receipts) == 2
    assert value.base.revision_id != value.result.revision_id
    assert compare_snapshots(value.base.snapshot, value.result.snapshot) == ()


@pytest.mark.parametrize("intervening", ["manual", "other_run"])
def test_intervening_revision_makes_range_discontinuous_without_fetching_snapshots(intervening):
    second, fourth = revision_row(2), revision_row(4)
    gap = revision_row(3, origin="manual" if intervening == "manual" else "ai", run_id="other-run")
    assert fourth["parent_revision_id"] == gap["revision_id"]
    conn = Connection([fourth, second])
    value = reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(2), operation_id(4)))
    assert value.continuity == "discontinuous" and value.receipts == (receipt(second), receipt(fourth))
    assert value.base is None and value.result is None and len(conn.statements) == 2


def test_adjacent_numbers_with_different_parent_identity_are_not_continuous():
    second, third = revision_row(2), revision_row(3)
    third["parent_revision_id"] = third["_op_base_revision_id"] = uuid4()
    conn = Connection([second, third])
    value = reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(2), operation_id(3)))
    assert value.continuity == "discontinuous" and value.base is None and value.result is None
    assert len(conn.statements) == 2


def test_captured_single_operation_ignores_later_same_run_commits():
    first, second, later = revision_row(1), revision_row(2), revision_row(3)
    conn = Connection([second], endpoints=[first, second, later])
    value = reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(2),))
    assert value.continuity == "continuous" and value.result.revision_id == revision_id(2)
    assert value.receipts == (receipt(second),)
    assert conn.statements[1].compile().params["operation_id_1"] == [operation_id(2)]
    assert all("jd_head" not in str(statement) for statement in conn.statements)


def test_exact_96_operations_still_use_one_metadata_batch_and_two_endpoints():
    rows = [revision_row(number) for number in range(2, 98)]
    conn = Connection(rows[::-1], endpoints=[revision_row(1), rows[-1]])
    value = reader_with(conn).read_run_change(DOCUMENT, RUN, tuple(operation_id(n) for n in range(97, 1, -1)))
    assert value.continuity == "continuous" and len(value.receipts) == 96
    assert value.result.revision_number == 97 and len(conn.statements) == 4


@pytest.mark.parametrize("rows", [[], [metadata(revision_row(2))]])
def test_missing_or_filtered_cross_scope_operation_is_not_a_partial_range(rows):
    conn = Connection(rows)
    with pytest.raises(HistoryError, match="^operation_missing$"):
        reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(2), operation_id(3)))
    assert len(conn.statements) == 2


@pytest.mark.parametrize("field,value", [
    ("document_id", str(uuid4())), ("_op_document_id", str(uuid4())),
    ("_op_ai_run_id", "other-run"), ("_op_origin", "manual"), ("origin", "manual"),
    ("_op_operation_id", uuid4()), ("_op_base_revision_id", uuid4()),
    ("_op_result_revision_id", uuid4()), ("parent_revision_id", uuid4()),
    ("_parent_number", None), ("_parent_number", 9), ("revision_number", 1),
    ("format_version", 999), ("engine_profile", "unknown-profile"),
])
def test_damaged_metadata_or_out_of_scope_returned_row_fails_closed(field, value):
    row = revision_row(2)
    row[field] = value
    conn = Connection([row])
    with pytest.raises(HistoryError, match="^stored_content_mismatch$"):
        reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(2),))
    assert len(conn.statements) == 2


def test_wrongly_selected_no_change_and_malformed_receipt_are_not_committed():
    for damage in ("no_change", "bad_body"):
        row = revision_row(2)
        if damage == "no_change":
            row["_op_status"] = "no_change"
            row["_op_result_revision_id"] = row["_op_base_revision_id"]
            row["_op_receipt"] = body_for("jd_set_text", "no_change").model_dump()
        else:
            row["_op_receipt"][PRIVATE] = PRIVATE
        conn = Connection([row])
        with pytest.raises(HistoryError, match="^stored_content_mismatch$") as caught:
            reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(2),))
        assert PRIVATE not in str(caught.value)


def test_duplicate_batch_rows_are_rejected_instead_of_counted_as_two_events():
    row = revision_row(2)
    with pytest.raises(HistoryError, match="^stored_content_mismatch$"):
        reader_with(Connection([row, row])).read_run_change(DOCUMENT, RUN, (operation_id(2),))


@pytest.mark.parametrize("damage", ["digest", "format", "missing"])
def test_full_endpoint_uses_existing_snapshot_validation(damage):
    first, second = revision_row(1), revision_row(2)
    endpoint = deepcopy(second)
    if damage == "digest":
        endpoint["content_digest"] = "b" * 64
    elif damage == "format":
        endpoint["snapshot"]["format_version"] = 999
    conn = Connection([second], endpoints=[first] if damage == "missing" else [first, endpoint])
    with pytest.raises(HistoryError, match="^revision_missing$" if damage == "missing" else "^stored_content_mismatch$"):
        reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(2),))
    assert len(conn.statements) == 4 and conn.trace[-1] == "closed"


@pytest.mark.parametrize("stage", [1, 2, 3, 4])
def test_driver_fault_at_any_stage_is_safe_and_releases_connection(stage):
    first, second = revision_row(1), revision_row(2)
    conn = Connection([second], endpoints=[first, second], fail_at=stage)
    with pytest.raises(HistoryError, match="^read_failed$") as caught:
        reader_with(conn).read_run_change(DOCUMENT, RUN, (operation_id(2),))
    assert PRIVATE not in str(caught.value) and caught.value.__suppress_context__
    assert conn.trace[-1] == "closed"
