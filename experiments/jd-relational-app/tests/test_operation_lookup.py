"""Admission lookup: original confirmed result or absence, never stopped proof."""

from dataclasses import asdict, replace
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa

from jd_relational.intents import AdmittedIdentity
from jd_relational.storage import schema as db
from jd_relational.storage.service import JdStorage, StorageError
from test_storage_postgres import engine
from test_storage_service import FakeAuthority, intent_for, task_args


PG = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                        reason="explicit isolated PostgreSQL test opt-in required")


class ForbiddenAuthority:
    def require_bound(self, *args):
        raise AssertionError("Lookup must not consult writer admission.")

    def require_stopped(self, *args):
        raise AssertionError("Lookup must not consult writer death.")


class DisconnectedEngine:
    dialect = SimpleNamespace(name="postgresql", driver="psycopg")

    def __init__(self):
        self.calls = 0

    def connect(self):
        self.calls += 1
        raise RuntimeError("private connection details")


def identity():
    return AdmittedIdentity(str(uuid4()), uuid4(), uuid4(), "manual", None, "a" * 64, "jd_set_text")


@PG
def test_absent_catalog_document_cannot_admit_an_unenumerable_pending(engine):
    from jd_relational.manual_runtime import ManualRuntime, RuntimeFailure
    from test_manual_runtime import Checkpoints, intent
    checkpoints = Checkpoints()
    owner = ManualRuntime(checkpoints, lambda authority: JdStorage(engine, authority))
    value = intent()
    try:
        with pytest.raises(RuntimeFailure, match="^document_missing$"):
            owner.submit(value)
        assert not checkpoints.pending
    finally:
        assert owner.close(timeout=2)


@pytest.mark.parametrize("field,value", [
    ("document_id", ""), ("document_id", "\x00private"),
    ("operation_id", "not-uuid"), ("base_revision_id", "not-uuid"),
    ("origin", "caller"), ("ai_run_id", "unexpected-manual-run"),
    ("request_digest", "incorrect"), ("command_kind", "invented_tool"),
])
def test_every_loaded_identity_field_is_revalidated_before_db(field, value):
    engine = DisconnectedEngine()
    descriptor = identity()
    object.__setattr__(descriptor, field, value)
    with pytest.raises(StorageError, match="^invalid_input$") as error:
        JdStorage(engine, ForbiddenAuthority()).lookup(descriptor)
    assert engine.calls == 0 and error.value.__suppress_context__


@pytest.mark.parametrize("value", [None, {}, "operation", SimpleNamespace()])
def test_non_identity_input_is_rejected_without_db(value):
    engine = DisconnectedEngine()
    with pytest.raises(StorageError, match="^invalid_input$"):
        JdStorage(engine, ForbiddenAuthority()).lookup(value)
    assert engine.calls == 0


def test_connection_failure_is_read_failed_without_raw_cause():
    engine = DisconnectedEngine()
    with pytest.raises(StorageError, match="^read_failed$") as error:
        JdStorage(engine, ForbiddenAuthority()).lookup(identity())
    assert engine.calls == 1 and error.value.__suppress_context__


def row_state(engine, document):
    with engine.connect() as conn:
        return {table.name: [dict(row) for row in conn.execute(sa.select(table).where(
            (table.c.id if table.name == "jd_document" else table.c.document_id) == document
        ).order_by(*table.primary_key.columns)).mappings()] for table in db.metadata.sorted_tables}


def prepare(engine, status="committed", *, ai=False):
    store = JdStorage(engine, FakeAuthority())
    current = store.read_current(store.create_document(uuid4(), "合成原操作查詢"))
    if status == "invalid_input":
        arguments = {**task_args(), "name": None, "description": None}
        tool = "jd_create_task"
    else:
        arguments = {"target_field_ref": "profile.purpose", "text": None if status == "no_change" else "原次內容", "basis_refs": []}
        tool = "jd_set_text"
    intent = intent_for(store, current, tool, arguments,
                        origin="ai" if ai else "manual", ai_run_id="original-run" if ai else None)
    if status == "save_failed":
        store.authority.bound.clear()
        store.authority.stopped.add(intent.operation_id)
        saved = store.reconcile_stopped(intent.identity)
    else:
        saved = store.execute(intent)
    assert saved.confirmed and saved.status == status
    return store, current, intent, saved


@PG
@pytest.mark.parametrize("status", ["committed", "no_change", "invalid_input", "save_failed"])
def test_original_terminal_lookup_is_readonly_and_unchanged_after_new_head(engine, monkeypatch, status):
    import jd_relational.storage.service as service
    store, current, intent, saved = prepare(engine, status)
    latest = store.read_current(current.document_id)
    later = intent_for(store, latest, "jd_set_text", {"target_field_ref": "profile.purpose", "text": "較晚手改", "basis_refs": []})
    assert store.execute(later).confirmed
    before = row_state(engine, current.document_id)
    # Cover every table this document can own rows in, so a lookup that wrote
    # anywhere is caught. Comparing against JD_TABLE_NAMES alone cannot fail,
    # because row_state builds its keys from the same metadata; this names the
    # content tables and the background admission row separately, so a new
    # table has to be placed deliberately rather than slipping in.
    assert set(before) == set(db.JD_CONTENT_TABLE_NAMES) | {"jd_memory_admission"}
    assert "jd_memory_admission" in before, "the admission row must be under this check too"
    store.authority = ForbiddenAuthority()
    def forbidden(*args, **kwargs):
        pytest.fail("Lookup must not reconstruct content, source or command material.")
    monkeypatch.setattr(service, "read_domain", forbidden)
    monkeypatch.setattr(service, "prepare_edit", forbidden)
    verbs, modes = [], []
    def observe(conn, cursor, statement, parameters, context, executemany):
        verbs.append(statement.split()[0].upper())
        if statement.startswith("SELECT jd_operation."):
            modes.append((conn.exec_driver_sql("SHOW transaction_read_only").scalar_one(),
                          conn.exec_driver_sql("SHOW transaction_isolation").scalar_one()))
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        looked_up = store.lookup(AdmittedIdentity(**asdict(intent.identity)))
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert looked_up == saved and looked_up.confirmed
    assert looked_up.receipt.result_revision_id == saved.receipt.result_revision_id
    assert modes == [("on", "repeatable read")]
    assert set(verbs) <= {"SELECT", "SHOW"}
    assert row_state(engine, current.document_id) == before


@PG
@pytest.mark.parametrize("field", ["request_digest", "origin", "base_revision_id", "ai_run_id", "command_kind"])
def test_conflicting_original_identity_is_not_accepted_or_modified(engine, field):
    store, current, intent, saved = prepare(engine, ai=True)
    mutations = {"request_digest": {"request_digest": "f" * 64},
                 "origin": {"origin": "manual", "ai_run_id": None},
                 "base_revision_id": {"base_revision_id": uuid4()},
                 "ai_run_id": {"ai_run_id": "different-run"},
                 "command_kind": {"command_kind": "jd_create_task"}}
    before = row_state(engine, current.document_id)
    store.authority = ForbiddenAuthority()
    with pytest.raises(StorageError, match="^operation_conflict$"):
        store.lookup(replace(intent.identity, **mutations[field]))
    assert store.lookup(intent.identity) == saved
    assert row_state(engine, current.document_id) == before


@PG
def test_absence_and_other_document_are_none_without_writing_receipt(engine):
    store, current, intent, _ = prepare(engine)
    other = store.create_document(uuid4(), "另一份合成文件")
    before = {doc: row_state(engine, doc) for doc in (current.document_id, other)}
    store.authority = ForbiddenAuthority()
    assert store.lookup(replace(intent.identity, operation_id=uuid4())) is None
    assert store.lookup(replace(intent.identity, document_id=other)) is None
    with pytest.raises(StorageError, match="^document_missing$"):
        store.lookup(replace(intent.identity, document_id=str(uuid4())))
    assert {doc: row_state(engine, doc) for doc in before} == before


@PG
def test_driver_query_failure_is_fixed_and_cannot_be_confused_with_absence(engine):
    store, current, intent, _ = prepare(engine)
    before = row_state(engine, current.document_id)
    store.authority = ForbiddenAuthority()
    def broken(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT jd_operation."):
            raise RuntimeError("private SQL sentinel")
    sa.event.listen(engine, "before_cursor_execute", broken)
    try:
        with pytest.raises(StorageError, match="^read_failed$") as error:
            store.lookup(intent.identity)
        assert error.value.__suppress_context__
    finally:
        sa.event.remove(engine, "before_cursor_execute", broken)
    assert row_state(engine, current.document_id) == before
