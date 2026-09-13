"""Notice events are revision facts, never a diff or a model-read receipt."""

from copy import deepcopy
from dataclasses import asdict
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa

from jd_relational.notice_history import NoticeBoundary, NoticeHistoryReader
from jd_relational.storage import schema as db
from jd_relational.storage.history import HistoryError, HistoryReader
from jd_relational.storage.service import JdStorage
from test_storage_postgres import engine  # explicit localhost:55436 opt-in fixture
from test_storage_service import FakeAuthority, change, intent_for


requires_pg = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                               reason="explicit isolated PostgreSQL test opt-in required")


@pytest.fixture
def store(engine):
    return JdStorage(engine, FakeAuthority())


@pytest.fixture
def current(store):
    return store.read_current(store.create_document(uuid4(), "合成通知窗口"))


@pytest.fixture
def reader(engine):
    return NoticeHistoryReader(engine)


def boundary(current):
    return NoticeBoundary(current.revision_id, current.revision_number)


def set_purpose(store, current, text, *, origin="manual"):
    return change(store, current, "jd_set_text", {
        "target_field_ref": "profile.purpose", "text": text, "basis_refs": [],
    }, origin=origin, ai_run_id="synthetic-notice-run" if origin == "ai" else None)


def disconnected_reader():
    def forbidden():
        pytest.fail("Invalid input must not acquire a database connection.")
    return NoticeHistoryReader(SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql", driver="psycopg"), connect=forbidden))


@pytest.mark.parametrize("document_id,base,limit", [
    ("", None, 20), (None, None, 20), ("bad\x00id", None, 20),
    ("bad\ud800id", None, 20), ("doc", {}, 20),
    ("doc", NoticeBoundary(str(uuid4()), 1), 20),
    ("doc", NoticeBoundary(uuid4(), True), 20),
    ("doc", NoticeBoundary(uuid4(), 0), 20),
    ("doc", NoticeBoundary(uuid4(), 1.0), 20),
    ("doc", None, True), ("doc", None, 0), ("doc", None, 101),
])
def test_invalid_arguments_do_not_connect(document_id, base, limit):
    with pytest.raises(HistoryError, match="^invalid_input$"):
        disconnected_reader().read(document_id, base, limit=limit)


def test_driver_error_has_only_the_shared_safe_code():
    def fail():
        raise RuntimeError("SyntheticPrivateConnectionAndWorkText")
    value = NoticeHistoryReader(SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql", driver="psycopg"), connect=fail))
    with pytest.raises(HistoryError) as failure:
        value.read("doc")
    assert failure.value.code == "read_failed"
    assert str(failure.value) == "read_failed" and failure.value.__suppress_context__


def test_non_postgres_engine_is_not_a_supported_substitute():
    with pytest.raises(HistoryError, match="^unsupported_database$"):
        NoticeHistoryReader(SimpleNamespace(dialect=SimpleNamespace(name="sqlite", driver="pysqlite")))


@requires_pg
def test_initial_without_baseline_is_distinct_from_an_established_empty_window(reader, current):
    first = reader.read(current.document_id)
    repeated = reader.read(current.document_id, boundary(current))
    assert first.baseline is None and repeated.baseline == boundary(current)
    assert first.head == repeated.head == boundary(current)
    assert first.events == repeated.events == ()
    assert first.total_count == repeated.total_count == 0
    assert first.manual_count == first.ai_count == first.omitted_count == 0


@requires_pg
def test_reverting_content_remains_two_events_and_no_change_or_failure_add_none(reader, store, current):
    second, manual, _ = set_purpose(store, current, "暫時更正")
    third, ai, _ = set_purpose(store, second, None, origin="ai")
    unchanged = intent_for(store, third, "jd_set_text", {
        "target_field_ref": "profile.purpose", "text": None, "basis_refs": []})
    assert store.execute(unchanged).status == "no_change"
    stale = intent_for(store, current, "jd_set_text", {
        "target_field_ref": "profile.purpose", "text": "不套用", "basis_refs": []})
    assert store.execute(stale).status == "stale_view"
    notice = reader.read(current.document_id, boundary(current))
    assert notice.head == boundary(third)
    assert notice.manual_count == notice.ai_count == 1 and notice.omitted_count == 0
    assert [event.operation_id for event in notice.events] == [ai.operation_id, manual.operation_id]
    assert [event.result_revision_number for event in notice.events] == [3, 2]
    assert [event.base_revision_number for event in notice.events] == [2, 1]
    assert [event.origin for event in notice.events] == ["ai", "manual"]
    assert notice.events[0].base_revision_id == second.revision_id
    assert notice.events[1].base_revision_id == current.revision_id
    assert all(event.command_kind == "jd_set_text" for event in notice.events)
    assert all(set(asdict(event)) == {"operation_id", "base_revision_id", "base_revision_number",
        "result_revision_id", "result_revision_number", "origin", "command_kind"} for event in notice.events)
    assert current.snapshot["profile"]["purpose"] == third.snapshot["profile"]["purpose"]
    assert reader.read(current.document_id).events == notice.events
    assert reader.read(current.document_id, boundary(third)).total_count == 0


@requires_pg
def test_limited_events_keep_full_counts_and_are_recoverable_under_the_original_anchor(reader, store, current, engine):
    original = current
    for index, origin in enumerate(("manual", "ai", "manual", "ai")):
        current, _, _ = set_purpose(store, current, f"合成版本 {index}", origin=origin)
    notice = reader.read(current.document_id, boundary(original), limit=1)
    assert len(notice.events) == 1 and notice.events[0].result_revision_number == 5
    assert notice.manual_count == notice.ai_count == 2
    assert notice.total_count == 4 and notice.omitted_count == 3
    newer, _, _ = set_purpose(store, current, "通知之後的新版本")
    history = HistoryReader(engine)
    numbers, operation_ids, before = [], [], None
    while True:
        page = history.list_revisions(current.document_id, anchor_revision_id=notice.head.revision_id,
                                      before_number=before, limit=2)
        assert page.anchor_revision_number == notice.head.revision_number
        for revision in page.revisions:
            if revision.revision_number > notice.baseline.revision_number:
                numbers.append(revision.revision_number)
                operation_ids.append(revision.producer_operation_id)
        if not page.has_more:
            break
        before = page.next_before
    assert numbers == [5, 4, 3, 2] and len(set(operation_ids)) == notice.total_count
    assert notice.events[0].operation_id == operation_ids[0]
    assert newer.revision_number not in numbers


@requires_pg
def test_baseline_missing_foreign_and_number_mismatch_never_fall_back(reader, store, current):
    other = store.read_current(store.create_document(uuid4(), "通知另一文件"))
    for baseline, code in [
        (NoticeBoundary(uuid4(), 1), "baseline_missing"),
        (boundary(other), "baseline_missing"),
        (NoticeBoundary(current.revision_id, 2), "baseline_mismatch"),
    ]:
        with pytest.raises(HistoryError, match=f"^{code}$"):
            reader.read(current.document_id, baseline)
    with pytest.raises(HistoryError, match="^document_missing$"):
        reader.read(str(uuid4()))


@requires_pg
@pytest.mark.parametrize("damage,code", [
    ("missing", "head_missing"), ("number", "stored_content_mismatch"),
    ("behind_baseline", "baseline_ahead"),
])
def test_head_inconsistency_and_ahead_baseline_are_rejected(reader, store, current, engine, damage, code):
    second, _, _ = set_purpose(store, current, "第二版")
    with engine.begin() as conn:
        original = dict(conn.execute(sa.select(db.jd_head).where(
            db.jd_head.c.document_id == current.document_id)).mappings().one())
        if damage == "missing":
            conn.execute(db.jd_head.delete().where(db.jd_head.c.document_id == current.document_id))
        else:
            values = {"revision_number": 99} if damage == "number" else {
                "revision_number": 1, "current_revision_id": current.revision_id}
            conn.execute(db.jd_head.update().where(db.jd_head.c.document_id == current.document_id).values(**values))
    try:
        with pytest.raises(HistoryError, match=f"^{code}$"):
            reader.read(current.document_id, boundary(second))
    finally:
        with engine.begin() as conn:
            if damage == "missing":
                conn.execute(db.jd_head.insert().values(**original))
            else:
                conn.execute(db.jd_head.update().where(db.jd_head.c.document_id == current.document_id).values(**original))


@requires_pg
def test_concurrent_commit_after_head_is_excluded_from_counts_and_events(reader, store, current, engine):
    second, _, _ = set_purpose(store, current, "讀取 head")
    isolation, later, own_statements, connections = [], [], [], []

    def after_head(conn, cursor, statement, parameters, context, executemany):
        if "FROM jd_head" not in statement or isolation:
            return
        connections.append(conn)
        isolation.append(conn.execute(sa.text("SHOW transaction_isolation")).scalar_one())
        isolation.append(conn.execute(sa.text("SHOW transaction_read_only")).scalar_one())
        updated, _, _ = set_purpose(store, second, "交錯提交", origin="ai")
        later.append(updated)

    def capture(conn, cursor, statement, parameters, context, executemany):
        if connections and conn is connections[0]:
            own_statements.append(statement)

    sa.event.listen(engine, "before_cursor_execute", capture)
    sa.event.listen(engine, "after_cursor_execute", after_head)
    try:
        notice = reader.read(current.document_id, boundary(current))
    finally:
        sa.event.remove(engine, "after_cursor_execute", after_head)
        sa.event.remove(engine, "before_cursor_execute", capture)
    assert isolation == ["repeatable read", "on"] and len(later) == 1
    assert notice.head == boundary(second)
    assert notice.total_count == notice.manual_count == 1 and notice.ai_count == 0
    assert [event.result_revision_id for event in notice.events] == [second.revision_id]
    assert own_statements and all(query.lstrip().upper().startswith(("SELECT", "SHOW")) for query in own_statements)
    assert all(".snapshot" not in query for query in own_statements)
    assert reader.read(current.document_id, boundary(current)).head == boundary(later[0])


@requires_pg
def test_a_missing_committed_producer_in_an_omitted_event_is_not_silently_counted(reader, store, current, engine):
    second, original, _ = set_purpose(store, current, "第二版")
    third, _, _ = set_purpose(store, second, "第三版")
    with engine.begin() as conn:
        row = dict(conn.execute(sa.select(db.jd_operation).where(
            db.jd_operation.c.document_id == current.document_id,
            db.jd_operation.c.operation_id == original.operation_id)).mappings().one())
        conn.execute(db.jd_operation.delete().where(
            db.jd_operation.c.document_id == current.document_id,
            db.jd_operation.c.operation_id == original.operation_id))
    try:
        with pytest.raises(HistoryError, match="^stored_content_mismatch$"):
            reader.read(current.document_id, boundary(current), limit=1)
    finally:
        with engine.begin() as conn:
            conn.execute(db.jd_operation.insert().values(**row))
    assert reader.read(current.document_id, boundary(current), limit=1).head == boundary(third)


@requires_pg
@pytest.mark.parametrize("damage", ["command_kind", "origin"])
def test_event_uses_valid_original_receipt_and_matching_origin(reader, store, current, engine, damage):
    second, intent, _ = set_purpose(store, current, "合成通知內容不應出現在錯誤")
    operation = sa.and_(db.jd_operation.c.document_id == current.document_id,
                        db.jd_operation.c.operation_id == intent.operation_id)
    with engine.begin() as conn:
        original = dict(conn.execute(sa.select(db.jd_operation).where(operation)).mappings().one())
        if damage == "command_kind":
            body = deepcopy(original["receipt"])
            body["command_kind"] = "SyntheticPrivateUnknownCommand"
            values = {"receipt": body}
        else:
            values = {"origin": "ai", "ai_run_id": "synthetic-other-origin"}
        conn.execute(db.jd_operation.update().where(operation).values(**values))
    try:
        with pytest.raises(HistoryError) as failure:
            reader.read(current.document_id, boundary(current))
        assert str(failure.value) == "stored_content_mismatch"
    finally:
        with engine.begin() as conn:
            conn.execute(db.jd_operation.update().where(operation).values(**original))
    assert reader.read(current.document_id, boundary(current)).head == boundary(second)
