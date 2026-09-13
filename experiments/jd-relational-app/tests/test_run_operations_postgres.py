"""Opt-in real PG run-receipt reads; FakeAuthority prepares synthetic rows only.

This proves the read transaction and stored material, not AI admission, native
run completeness, HTTP, writer death, or a provider. Existing isolated PG only;
no schema setup, deletion, or production configuration is performed here.
"""

from copy import deepcopy
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa

from jd_relational.storage import schema as db
from jd_relational.storage.history import HistoryError, HistoryReader
from jd_relational.storage.service import JdStorage
from test_storage_postgres import engine
from test_storage_service import FakeAuthority, change, intent_for


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


@pytest.fixture
def store(engine):
    return JdStorage(engine, FakeAuthority())


@pytest.fixture
def current(store):
    return store.read_current(store.create_document(uuid4(), "合成原 AI 回合操作查核"))


@pytest.fixture
def reader(engine):
    return HistoryReader(engine)


def text_args(text):
    return {"target_field_ref": "profile.purpose", "text": text, "basis_refs": []}


def ai_change(store, current, run_id, text):
    return change(store, current, "jd_set_text", text_args(text), origin="ai", ai_run_id=run_id)


def scoped_counts(engine, document_id):
    with engine.connect() as conn:
        return {table.name: conn.execute(sa.select(sa.func.count()).select_from(table).where(
            (table.c.id if table is db.jd_document else table.c.document_id) == document_id)).scalar_one()
            for table in db.metadata.tables.values()}


def test_exact_run_returns_original_saved_statuses_after_new_head_without_writes(reader, store, current, engine):
    run_id = str(uuid4())
    first, first_intent, committed = ai_change(store, current, run_id, "原回合已保存")
    same_intent = intent_for(store, first, "jd_set_text", text_args("原回合已保存"), origin="ai", ai_run_id=run_id)
    no_change = store.execute(same_intent)
    assert no_change.confirmed and no_change.status == "no_change"
    stale_intent = intent_for(store, first, "jd_set_text", text_args("此內容不可套用"), origin="ai", ai_run_id=run_id)
    later, _, _ = change(store, first, "jd_set_text", text_args("後續人工修改"))
    stale = store.execute(stale_intent)
    assert stale.confirmed and stale.status == "stale_view"
    later, _, _ = ai_change(store, later, str(uuid4()), "不同 AI 回合")
    other = store.read_current(store.create_document(uuid4(), "另一份合成文件"))
    ai_change(store, other, run_id, "同 run 字串但不同文件")

    before = scoped_counts(engine, current.document_id)
    statements = []

    def trace(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa.event.listen(engine, "before_cursor_execute", trace)
    try:
        operations = reader.read_run_operations(current.document_id, run_id)
    finally:
        sa.event.remove(engine, "before_cursor_execute", trace)
    assert len(statements) == 2 and all(sql.lstrip().startswith("SELECT ") for sql in statements)
    assert not any("jd_head" in sql or "jd_revision" in sql for sql in statements)
    expected = tuple(sorted((committed.receipt, no_change.receipt, stale.receipt), key=lambda row: row.operation_id))
    assert operations == expected
    assert operations == tuple(sorted(operations, key=lambda row: row.operation_id))
    assert {row.origin for row in operations} == {"ai"}
    assert {row.ai_run_id for row in operations} == {run_id}
    assert {row.document_id for row in operations} == {current.document_id}
    assert committed.receipt.result_revision_id == no_change.receipt.result_revision_id == first.revision_id
    assert stale.receipt.base_revision_id == first.revision_id and stale.receipt.result_revision_id is None
    assert store.get_operation(current.document_id, first_intent.operation_id) == committed.receipt
    assert store.read_current(current.document_id).revision_id == later.revision_id
    assert scoped_counts(engine, current.document_id) == before


def test_existing_document_with_no_saved_run_rows_is_distinct_from_missing_document(reader, store, current):
    run_id = str(uuid4())
    other = store.read_current(store.create_document(uuid4(), "只在另一份合成文件有操作"))
    ai_change(store, other, run_id, "不可跨文件查入")
    assert reader.read_run_operations(current.document_id, run_id) == ()
    assert reader.read_run_operations(current.document_id, str(uuid4())) == ()
    with pytest.raises(HistoryError, match="^document_missing$"):
        reader.read_run_operations(str(uuid4()), run_id)


def test_exact_limit_succeeds_and_one_extra_saved_row_refuses_partial_result(reader, store, current):
    run_id = str(uuid4())
    current, _, first = ai_change(store, current, run_id, "第一筆")
    assert reader.read_run_operations(current.document_id, run_id, limit=1) == (first.receipt,)
    current, _, second = ai_change(store, current, run_id, "第二筆")
    with pytest.raises(HistoryError, match="^run_operations_limit_exceeded$"):
        reader.read_run_operations(current.document_id, run_id, limit=1)
    operations = reader.read_run_operations(current.document_id, run_id, limit=2)
    assert {row.operation_id for row in operations} == {first.operation_id, second.operation_id}


def test_repeatable_read_excludes_a_same_run_commit_after_its_snapshot(reader, store, current, engine):
    run_id = str(uuid4())
    current, _, first = ai_change(store, current, run_id, "快照前已提交")
    next_intent = intent_for(store, current, "jd_set_text", text_args("快照開始後提交"), origin="ai", ai_run_id=run_id)
    observed = []
    subsequent = []

    def after_document(conn, cursor, statement, parameters, context, executemany):
        if observed or not statement.startswith("SELECT jd_document.id"):
            return
        observed.append("snapshot_established")
        observed.extend((conn.execute(sa.text("SHOW transaction_isolation")).scalar_one(),
                         conn.execute(sa.text("SHOW transaction_read_only")).scalar_one()))
        subsequent.append(store.execute(next_intent))  # A different checked-out PG connection commits here.

    sa.event.listen(engine, "after_cursor_execute", after_document)
    try:
        original_snapshot = reader.read_run_operations(current.document_id, run_id)
    finally:
        sa.event.remove(engine, "after_cursor_execute", after_document)
    assert observed == ["snapshot_established", "repeatable read", "on"]
    assert len(subsequent) == 1 and subsequent[0].confirmed and subsequent[0].status == "committed"
    assert original_snapshot == (first.receipt,)
    later_snapshot = reader.read_run_operations(current.document_id, run_id)
    assert {row.operation_id for row in later_snapshot} == {first.operation_id, next_intent.operation_id}


def test_invalid_saved_receipt_is_rejected_without_exposing_stored_private_text(reader, store, current, engine):
    run_id = str(uuid4())
    current, intent, saved = ai_change(store, current, run_id, "只讀錯誤測試")
    statement = db.jd_operation.update().where(db.jd_operation.c.document_id == current.document_id,
                                               db.jd_operation.c.operation_id == intent.operation_id)
    original = saved.receipt.body.model_dump()
    corrupt = deepcopy(original)
    corrupt["format_version"] = 999
    corrupt["SyntheticPrivateRunReceipt"] = "SyntheticPrivateRunReceipt"
    try:
        with engine.begin() as conn:
            conn.execute(statement.values(receipt=corrupt))
        with pytest.raises(HistoryError, match="^stored_content_mismatch$") as caught:
            reader.read_run_operations(current.document_id, run_id)
        assert "SyntheticPrivateRunReceipt" not in str(caught.value)
        assert caught.value.__suppress_context__
    finally:
        with engine.begin() as conn:
            conn.execute(statement.values(receipt=original))  # Restore only this test's new synthetic row.
    assert reader.read_run_operations(current.document_id, run_id) == (saved.receipt,)
