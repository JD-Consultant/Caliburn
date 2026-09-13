"""Real PG whole-run material over captured committed operation identities.

FakeAuthority is used only to prepare this test's synthetic JD saves. These tests
do not prove native run completeness, writer admission/death, HTTP, UI or a model.
Only the existing opt-in 55436 fixture is used: no setup, database creation,
deletion, provider calls, or production configuration. Corruption cases restore
only the specific newly created synthetic row, even if an assertion fails.
"""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa

from jd_relational.changes import compare_snapshots
from jd_relational.storage import schema as db
from jd_relational.storage.history import HistoryError, HistoryReader
from jd_relational.storage.service import JdStorage
from test_storage_postgres import engine
from test_storage_service import FakeAuthority, change, intent_for
from test_run_operations_postgres import scoped_counts


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


@pytest.fixture
def store(engine):
    return JdStorage(engine, FakeAuthority())


@pytest.fixture
def current(store):
    return store.read_current(store.create_document(uuid4(), "合成整輪差異材料驗收"))


@pytest.fixture
def reader(engine):
    return HistoryReader(engine)


def text_args(text):
    return {"target_field_ref": "profile.purpose", "text": text, "basis_refs": []}


def ai_change(store, current, run_id, text, **options):
    return change(store, current, "jd_set_text", text_args(text), origin="ai",
                  ai_run_id=run_id, **options)


def operation_ids(receipts):
    return tuple(row.operation_id for row in receipts)


@contextmanager
def traced_reads(engine):
    """Observe actual PG result widths/row counts; never issue extra queries."""
    observed = []

    def after(conn, cursor, statement, parameters, context, executemany):
        observed.append({"statement": statement,
                         "columns": tuple(column.name for column in cursor.description or ()),
                         "rows": cursor.rowcount})

    sa.event.listen(engine, "after_cursor_execute", after)
    try:
        yield observed
    finally:
        sa.event.remove(engine, "after_cursor_execute", after)


def assert_read_only_budget(statements, *, snapshots):
    assert statements and all(row["statement"].lstrip().startswith("SELECT ") for row in statements)
    assert not any("jd_head" in row["statement"] for row in statements)
    full = [row for row in statements if "snapshot" in row["columns"]]
    assert len(full) <= 2
    assert sum(row["rows"] for row in full) == snapshots


def test_empty_captured_set_is_none_without_snapshots_and_missing_document_is_not_empty(
        reader, store, current, engine):
    run_id = str(uuid4())
    before = scoped_counts(engine, current.document_id)
    with traced_reads(engine) as statements:
        material = reader.read_run_change(current.document_id, run_id, ())
    assert material.continuity == "none" and material.receipts == ()
    assert material.base is None and material.result is None
    assert_read_only_budget(statements, snapshots=0)
    assert len(statements) == 1
    with pytest.raises(HistoryError, match="^document_missing$"):
        reader.read_run_change(str(uuid4()), run_id, ())
    assert scoped_counts(engine, current.document_id) == before


def test_real_multiple_changes_and_change_back_have_empty_net_diff_but_preserve_all_operations(
        reader, store, current, engine):
    run_id = str(uuid4())
    initial = current
    receipts = []
    for text in ("合成工作第一稿", "合成工作第二稿", None):
        current, _, result = ai_change(store, current, run_id, text)
        receipts.append(result.receipt)
    end = current
    later, _, _ = change(store, current, "jd_set_text", text_args("較晚人工內容不可混進原輪"))
    before = scoped_counts(engine, current.document_id)
    with traced_reads(engine) as statements:
        material = reader.read_run_change(current.document_id, run_id, operation_ids(receipts))
    assert material.continuity == "continuous" and material.receipts == tuple(receipts)
    assert material.base.revision_id == initial.revision_id
    assert material.result.revision_id == end.revision_id != later.revision_id
    assert material.base.snapshot == material.result.snapshot == initial.snapshot
    assert compare_snapshots(material.base.snapshot, material.result.snapshot) == ()
    assert len(material.receipts) == 3
    assert_read_only_budget(statements, snapshots=2)
    assert scoped_counts(engine, current.document_id) == before
    # Detached output cannot rewrite the database or another result object.
    material.result.snapshot["profile"]["purpose"] = "caller-local only"
    again = reader.read_run_change(current.document_id, run_id, operation_ids(receipts))
    assert again.result.snapshot == end.snapshot


@pytest.mark.parametrize("intervening_origin", ["manual", "other_run"])
def test_intervening_manual_or_other_run_never_becomes_one_ai_net_change(
        reader, store, current, engine, intervening_origin):
    run_id = str(uuid4())
    current, _, first = ai_change(store, current, run_id, "原輪第一筆")
    if intervening_origin == "manual":
        current, _, intervening = change(store, current, "jd_set_text", text_args("員工獨立更正"))
    else:
        current, _, intervening = ai_change(store, current, str(uuid4()), "另一輪的獨立工作")
    current, _, last = ai_change(store, current, run_id, "原輪後續保存")
    before = scoped_counts(engine, current.document_id)
    with traced_reads(engine) as statements:
        material = reader.read_run_change(current.document_id, run_id,
                                         (last.operation_id, first.operation_id))
    assert material.continuity == "discontinuous"
    assert material.receipts == (first.receipt, last.receipt)
    assert intervening.operation_id not in operation_ids(material.receipts)
    assert material.base is None and material.result is None
    assert_read_only_budget(statements, snapshots=0)
    assert scoped_counts(engine, current.document_id) == before


def test_revision_order_wins_over_uuid_input_and_created_at_order(reader, store, current, engine):
    run_id = str(uuid4())
    ids = sorted((uuid4() for _ in range(3)), reverse=True)
    initial = current
    revisions = []
    for index, identity in enumerate(ids):
        current, _, _ = ai_change(store, current, run_id, f"依版次排序 {index}", operation_id=identity)
        revisions.append(current)
    # Stored wall-clock times are deliberately opposite to the actual revision chain.
    for index, identity in enumerate(ids):
        with engine.begin() as conn:
            conn.execute(db.jd_operation.update().where(
                db.jd_operation.c.document_id == current.document_id,
                db.jd_operation.c.operation_id == identity,
            ).values(created_at=datetime(2001, 1, 1, tzinfo=timezone.utc) + timedelta(days=3-index)))
    material = reader.read_run_change(current.document_id, run_id, (ids[1], ids[2], ids[0]))
    assert material.continuity == "continuous"
    assert operation_ids(material.receipts) == tuple(ids)
    assert [row.created_at for row in material.receipts] == sorted(
        (row.created_at for row in material.receipts), reverse=True)
    assert material.base.revision_id == initial.revision_id
    assert material.result.revision_id == revisions[-1].revision_id


def test_captured_identity_set_excludes_a_later_same_run_operation(reader, store, current, engine):
    run_id = str(uuid4())
    current, _, first = ai_change(store, current, run_id, "查到原回合第一筆")
    captured = (first.operation_id,)
    current, _, later = ai_change(store, current, run_id, "捕捉 IDs 後新增")
    before = scoped_counts(engine, current.document_id)
    material = reader.read_run_change(current.document_id, run_id, captured)
    assert material.continuity == "continuous" and material.receipts == (first.receipt,)
    assert material.result.revision_id == first.receipt.result_revision_id != later.receipt.result_revision_id
    assert scoped_counts(engine, current.document_id) == before


def test_omitted_middle_id_does_not_invent_continuity_even_with_the_same_run(reader, store, current):
    run_id = str(uuid4())
    receipts = []
    for index in range(3):
        current, _, result = ai_change(store, current, run_id, f"同輪保存 {index}")
        receipts.append(result.receipt)
    material = reader.read_run_change(current.document_id, run_id,
                                     (receipts[0].operation_id, receipts[2].operation_id))
    assert material.continuity == "discontinuous"
    assert material.receipts == (receipts[0], receipts[2])
    assert material.base is None and material.result is None


def test_one_repeatable_read_transaction_keeps_receipt_before_concurrent_metadata_and_commit(
        reader, store, current, engine):
    run_id = str(uuid4())
    current, _, first = ai_change(store, current, run_id, "固定快照第一筆")
    current, _, last = ai_change(store, current, run_id, "固定快照第二筆")
    pending = intent_for(store, current, "jd_set_text", text_args("讀取中提交的第三筆"),
                         origin="ai", ai_run_id=run_id)
    update = db.jd_operation.update().where(db.jd_operation.c.document_id == current.document_id,
                                            db.jd_operation.c.operation_id == first.operation_id)
    observed, later = [], []

    def after_document(conn, cursor, statement, parameters, context, executemany):
        if observed or not statement.startswith("SELECT jd_document.id"):
            return
        observed.append("snapshot_established")
        observed.extend((conn.execute(sa.text("SHOW transaction_isolation")).scalar_one(),
                         conn.execute(sa.text("SHOW transaction_read_only")).scalar_one()))
        with engine.begin() as other:
            other.execute(update.values(created_at=first.receipt.created_at + timedelta(days=1)))
        later.append(store.execute(pending))

    sa.event.listen(engine, "after_cursor_execute", after_document)
    try:
        material = reader.read_run_change(current.document_id, run_id,
                                         (first.operation_id, last.operation_id))
    finally:
        sa.event.remove(engine, "after_cursor_execute", after_document)
        with engine.begin() as conn:
            conn.execute(update.values(created_at=first.receipt.created_at))
    assert observed == ["snapshot_established", "repeatable read", "on"]
    assert len(later) == 1 and later[0].confirmed and later[0].status == "committed"
    assert material.receipts == (first.receipt, last.receipt)
    assert material.continuity == "continuous" and material.result.revision_id == current.revision_id
    assert material.result.revision_id != later[0].receipt.result_revision_id
    # A subsequent explicit wider capture can see the new commit; no implicit expansion.
    after = reader.read_run_change(current.document_id, run_id,
                                   (first.operation_id, last.operation_id, pending.operation_id))
    assert len(after.receipts) == 3 and after.result.revision_id == later[0].receipt.result_revision_id


def test_unknown_cross_scope_and_noncommitted_ids_never_return_partial_material(reader, store, current, engine):
    run_id = str(uuid4())
    current, _, good = ai_change(store, current, run_id, "可用的原輪保存")
    same = intent_for(store, current, "jd_set_text", text_args("可用的原輪保存"), origin="ai", ai_run_id=run_id)
    no_change = store.execute(same)
    assert no_change.confirmed and no_change.status == "no_change"
    stale_intent = intent_for(store, current, "jd_set_text", text_args("不會套用的舊意圖"),
                              origin="ai", ai_run_id=run_id)
    current, _, manual = change(store, current, "jd_set_text", text_args("不同人工保存"))
    stale = store.execute(stale_intent)
    assert stale.confirmed and stale.status == "stale_view"
    current, _, other_run = ai_change(store, current, str(uuid4()), "另一原輪保存")
    other_doc = store.read_current(store.create_document(uuid4(), "不屬此範圍的合成文件"))
    _, _, foreign = ai_change(store, other_doc, run_id, "另一文件的同 run 字串")
    before = scoped_counts(engine, current.document_id)
    for invalid_id in (uuid4(), same.operation_id, stale_intent.operation_id,
                       manual.operation_id, other_run.operation_id, foreign.operation_id):
        with pytest.raises(HistoryError, match="^operation_missing$"):
            reader.read_run_change(current.document_id, run_id, (good.operation_id, invalid_id))
    assert scoped_counts(engine, current.document_id) == before


@pytest.mark.parametrize("damage", ["receipt", "middle_parent", "endpoint_digest"])
def test_stored_receipt_metadata_or_endpoint_damage_has_fixed_safe_failure(
        reader, store, current, engine, damage):
    run_id = str(uuid4())
    initial = current
    receipts = []
    for index in range(3):
        current, _, result = ai_change(store, current, run_id, f"合成損壞反例 {index}")
        receipts.append(result.receipt)
    if damage in {"receipt", "middle_parent"}:
        original = receipts[1]
        update = db.jd_operation.update().where(db.jd_operation.c.document_id == current.document_id,
                                                db.jd_operation.c.operation_id == original.operation_id)
        if damage == "receipt":
            restore = {"receipt": original.body.model_dump()}
            corrupt = deepcopy(restore)
            corrupt["receipt"]["format_version"] = 999
            corrupt["receipt"]["SyntheticPrivateRunChange"] = "SyntheticPrivateRunChange"
        else:
            restore = {"base_revision_id": original.base_revision_id}
            corrupt = {"base_revision_id": initial.revision_id}
    else:
        update = db.jd_revision.update().where(db.jd_revision.c.document_id == current.document_id,
                                               db.jd_revision.c.revision_id == current.revision_id)
        with engine.connect() as conn:
            digest = conn.execute(sa.select(db.jd_revision.c.content_digest).where(
                db.jd_revision.c.document_id == current.document_id,
                db.jd_revision.c.revision_id == current.revision_id)).scalar_one()
        restore, corrupt = {"content_digest": digest}, {"content_digest": "0" * 64}
    try:
        with engine.begin() as conn:
            conn.execute(update.values(**corrupt))
        with pytest.raises(HistoryError, match="^stored_content_mismatch$") as caught:
            reader.read_run_change(current.document_id, run_id, operation_ids(receipts))
        assert "SyntheticPrivateRunChange" not in str(caught.value)
    finally:
        with engine.begin() as conn:
            conn.execute(update.values(**restore))
    material = reader.read_run_change(current.document_id, run_id, operation_ids(receipts))
    assert material.continuity == "continuous" and material.receipts == tuple(receipts)


def test_one_and_many_captured_operations_have_constant_queries_and_only_two_snapshots(
        reader, store, current, engine):
    run_id = str(uuid4())
    initial = current
    receipts = []
    for index in range(8):
        current, _, result = ai_change(store, current, run_id, f"有界整輪保存 {index}")
        receipts.append(result.receipt)
    before = scoped_counts(engine, current.document_id)
    with traced_reads(engine) as one:
        single = reader.read_run_change(current.document_id, run_id, (receipts[0].operation_id,))
    with traced_reads(engine) as many:
        material = reader.read_run_change(current.document_id, run_id, tuple(reversed(operation_ids(receipts))))
    assert single.continuity == material.continuity == "continuous"
    assert material.receipts == tuple(receipts)
    assert material.base.revision_id == initial.revision_id and material.result.revision_id == current.revision_id
    assert_read_only_budget(one, snapshots=2)
    assert_read_only_budget(many, snapshots=2)
    assert len(one) == len(many) <= 5  # Same bounded fetch cost, not N snapshots/queries.
    assert scoped_counts(engine, current.document_id) == before
