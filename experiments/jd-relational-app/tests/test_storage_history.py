"""Historical material, with opt-in PostgreSQL and no ref/writer/provider owner."""

from copy import deepcopy
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa

from jd_relational.storage import schema as db
from jd_relational.storage.history import HistoryError, HistoryReader
from jd_relational.storage.service import JdStorage
from test_storage_postgres import engine  # explicit public test database fixture
from test_storage_service import FakeAuthority, change, intent_for, task_args


requires_pg = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                               reason="explicit isolated PostgreSQL test opt-in required")


@pytest.fixture
def store(engine):
    return JdStorage(engine, FakeAuthority())


@pytest.fixture
def current(store):
    return store.read_current(store.create_document(uuid4(), "合成歷史測試"))


@pytest.fixture
def reader(engine):
    return HistoryReader(engine)


def text_change(store, current, text):
    return change(store, current, "jd_set_text", {
        "target_field_ref": "profile.purpose", "text": text, "basis_refs": []})


def disconnected_reader():
    def forbidden_connection():
        pytest.fail("Invalid input must not open a database connection.")
    return HistoryReader(SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"),
                                        connect=forbidden_connection))


@pytest.mark.parametrize("method,args,kwargs", [
    ("read_revision", ("", uuid4()), {}),
    ("read_revision", ("doc", "not-a-UUID-object"), {}),
    ("read_change", ("doc", None), {}),
    ("list_revisions", ("doc",), {"limit": True}),
    ("list_revisions", ("doc",), {"limit": 0}),
    ("list_revisions", ("doc",), {"limit": 101}),
    ("list_revisions", ("doc",), {"before_number": 3}),
    ("list_revisions", ("doc",), {"anchor_revision_id": uuid4(), "before_number": True}),
    ("list_revisions", ("doc",), {"anchor_revision_id": uuid4(), "before_number": 0}),
    ("list_revisions", ("doc",), {"anchor_revision_id": "not-a-UUID-object"}),
])
def test_invalid_arguments_rejected_without_connecting(method, args, kwargs):
    with pytest.raises(HistoryError) as failure:
        getattr(disconnected_reader(), method)(*args, **kwargs)
    assert failure.value.code == "invalid_input"


@pytest.mark.parametrize("method,args", [
    ("read_revision", ("doc", uuid4())),
    ("read_change", ("doc", uuid4())),
    ("list_revisions", ("doc",)),
])
def test_read_errors_hide_driver_payload_and_chain(method, args):
    def fail():
        raise RuntimeError("SyntheticPrivateSqlAndWorkText")
    value = HistoryReader(SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"), connect=fail))
    with pytest.raises(HistoryError) as failure:
        getattr(value, method)(*args)
    assert failure.value.code == "read_failed"
    assert str(failure.value) == "read_failed" and failure.value.__suppress_context__


@requires_pg
def test_initial_and_original_change_remain_readable_after_new_head(reader, store, current):
    initial = reader.read_revision(current.document_id, current.revision_id)
    assert initial.snapshot == current.snapshot and initial.revision_number == 1
    assert initial.origin == "initial" and initial.parent_revision_id is None
    assert initial.producer_operation_id is None and initial.created_at.tzinfo is not None
    second, intent, saved = change(store, current, "jd_create_task", task_args(), origin="ai", ai_run_id="historical-run")
    third, _, _ = text_change(store, second, "較新的用途")
    material = reader.read_change(current.document_id, intent.operation_id)
    assert material.receipt == saved.receipt and material.receipt.ai_run_id == "historical-run"
    assert material.base == initial and material.result.snapshot == second.snapshot
    assert material.result.revision_id != third.revision_id
    assert material.result.producer_operation_id == intent.operation_id
    assert material.result.origin == "ai" and material.result.parent_revision_id == initial.revision_id
    assert reader.read_revision(current.document_id, second.revision_id) == material.result
    # Returned mutable JSON cannot rewrite stored material or another read.
    material.result.snapshot["profile"]["purpose"] = "caller-local change"
    assert reader.read_revision(current.document_id, second.revision_id).snapshot == second.snapshot


@requires_pg
def test_no_change_and_failure_use_original_receipt_without_inventing_diff(reader, store, current):
    no_change = intent_for(store, current, "jd_set_text", {
        "target_field_ref": "profile.purpose", "text": None, "basis_refs": []})
    no_change_saved = store.execute(no_change)
    later, _, _ = text_change(store, current, "新版")
    stale = intent_for(store, current, "jd_set_text", {
        "target_field_ref": "profile.purpose", "text": "不套用", "basis_refs": []})
    failed = store.execute(stale)
    same = reader.read_change(current.document_id, no_change.operation_id)
    assert same.receipt == no_change_saved.receipt and same.receipt.status == "no_change"
    assert same.base == same.result and same.base.revision_id == current.revision_id
    error = reader.read_change(current.document_id, stale.operation_id)
    assert error.receipt == failed.receipt and error.receipt.status == "stale_view"
    assert error.base is None and error.result is None
    assert store.read_current(current.document_id).revision_id == later.revision_id


@requires_pg
def test_scope_and_missing_ids_do_not_fall_back_to_current(reader, store, current):
    other = store.read_current(store.create_document(uuid4(), "另一文件"))
    later, intent, _ = text_change(store, current, "自己的版本")
    for method, args, kwargs, code in [
        ("read_revision", (other.document_id, later.revision_id), {}, "revision_missing"),
        ("read_change", (other.document_id, intent.operation_id), {}, "operation_missing"),
        ("list_revisions", (other.document_id,), {"anchor_revision_id": later.revision_id}, "revision_missing"),
        ("read_revision", (current.document_id, uuid4()), {}, "revision_missing"),
        ("read_change", (current.document_id, uuid4()), {}, "operation_missing"),
        ("list_revisions", (str(uuid4()),), {}, "document_missing"),
    ]:
        with pytest.raises(HistoryError) as failure:
            getattr(reader, method)(*args, **kwargs)
        assert failure.value.code == code


@requires_pg
def test_history_page_anchor_survives_new_head_and_includes_initial(reader, store, current):
    versions = [current]
    for text in ("第二版", "第三版", "第四版"):
        current, _, _ = text_change(store, current, text)
        versions.append(current)
    first = reader.list_revisions(current.document_id, limit=2)
    assert first.anchor_revision_id == current.revision_id and first.anchor_revision_number == 4
    assert [row.revision_number for row in first.revisions] == [4, 3]
    assert first.has_more and first.next_before == 3
    newer, _, _ = text_change(store, current, "第五版")
    second = reader.list_revisions(current.document_id, anchor_revision_id=first.anchor_revision_id,
                                   before_number=first.next_before, limit=2)
    assert second.anchor_revision_id == first.anchor_revision_id
    assert [row.revision_number for row in second.revisions] == [2, 1]
    assert not second.has_more and second.next_before is None
    assert second.revisions[-1].snapshot == versions[0].snapshot
    assert reader.list_revisions(current.document_id, limit=1).anchor_revision_id == newer.revision_id
    empty = reader.list_revisions(current.document_id, anchor_revision_id=first.anchor_revision_id, before_number=1)
    assert empty.revisions == () and not empty.has_more and empty.next_before is None
    with pytest.raises(HistoryError, match="invalid_input"):
        reader.list_revisions(current.document_id, anchor_revision_id=first.anchor_revision_id, before_number=5)


@requires_pg
def test_first_history_page_uses_one_readonly_repeatable_snapshot(reader, store, current, engine):
    current, _, _ = text_change(store, current, "讀取時的 head")
    observed = []
    later = []
    def after_head(conn, cursor, statement, parameters, context, executemany):
        if "FROM jd_head" not in statement or observed:
            return
        observed.append(conn.execute(sa.text("SHOW transaction_isolation")).scalar_one())
        observed.append(conn.execute(sa.text("SHOW transaction_read_only")).scalar_one())
        next_current, _, _ = text_change(store, current, "交錯提交的新 head")
        later.append(next_current)
    sa.event.listen(engine, "after_cursor_execute", after_head)
    try:
        first = reader.list_revisions(current.document_id, limit=10)
    finally:
        sa.event.remove(engine, "after_cursor_execute", after_head)
    assert observed == ["repeatable read", "on"] and len(later) == 1
    assert first.anchor_revision_id == current.revision_id
    assert [row.revision_number for row in first.revisions] == [2, 1]
    assert reader.list_revisions(current.document_id).anchor_revision_id == later[0].revision_id


@requires_pg
@pytest.mark.parametrize("damage", ["format", "profile", "document", "unknown_field", "digest", "number"])
def test_corrupt_snapshot_or_row_metadata_is_rejected(reader, store, current, engine, damage):
    current, intent, _ = text_change(store, current, "已保存的合成內容")
    with engine.connect() as conn:
        original = dict(conn.execute(sa.select(db.jd_revision).where(
            db.jd_revision.c.document_id == current.document_id,
            db.jd_revision.c.revision_id == current.revision_id)).mappings().one())
    values = {"snapshot": deepcopy(original["snapshot"])}
    if damage == "format":
        values["snapshot"]["format_version"] = 999
    elif damage == "profile":
        values["snapshot"]["engine_profile"] = "unsupported"
    elif damage == "document":
        values["snapshot"]["document_id"] = "another-document"
    elif damage == "unknown_field":
        values["snapshot"]["extra_work"] = "must not silently drop"
    elif damage == "digest":
        values["content_digest"] = "0" * 64
    else:
        values["revision_number"] = 30
    statement = db.jd_revision.update().where(db.jd_revision.c.document_id == current.document_id,
                                              db.jd_revision.c.revision_id == current.revision_id)
    try:
        with engine.begin() as conn:
            conn.execute(statement.values(**values))
        for method, args in (("read_revision", (current.document_id, current.revision_id)),
                             ("read_change", (current.document_id, intent.operation_id)),
                             ("list_revisions", (current.document_id,))):
            with pytest.raises(HistoryError, match="stored_content_mismatch"):
                getattr(reader, method)(*args)
    finally:
        with engine.begin() as conn:
            conn.execute(statement.values(**{key: original[key] for key in values}))


@requires_pg
def test_producer_metadata_must_match_the_revision(reader, store, current, engine):
    current, intent, _ = text_change(store, current, "來源與版本一致")
    statement = db.jd_operation.update().where(db.jd_operation.c.document_id == current.document_id,
                                               db.jd_operation.c.operation_id == intent.operation_id)
    try:
        with engine.begin() as conn:
            conn.execute(statement.values(origin="ai", ai_run_id="wrong-origin-fixture"))
        with pytest.raises(HistoryError, match="stored_content_mismatch"):
            reader.read_revision(current.document_id, current.revision_id)
        with pytest.raises(HistoryError, match="stored_content_mismatch"):
            reader.read_change(current.document_id, intent.operation_id)
    finally:
        with engine.begin() as conn:
            conn.execute(statement.values(origin="manual", ai_run_id=None))
