"""Opt-in real PostgreSQL constraints, distinct from an App save/recovery test.

Initialize explicitly with scripts/init_test_database.py before setting
JD_RELATIONAL_TEST_DB=1. No production configuration or automatic setup is read.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from jd_relational.storage import schema as db


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                                reason="explicit isolated PostgreSQL test opt-in required")


@pytest.fixture(scope="module")
def engine():
    url = sa.URL.create("postgresql+psycopg", username="jd_test", password="jd-local-test-only",
                        host="127.0.0.1", port=55436, database="caliburn_jd_relational_test")
    value = sa.create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    calls = []

    @sa.event.listens_for(value, "before_cursor_execute")
    def record_execution(conn, cursor, statement, parameters, context, executemany):
        calls.append(executemany)

    try:
        with value.connect() as conn:
            assert conn.execute(sa.text(
                "SELECT current_database(), current_user, current_setting('server_version_num')::integer"
            )).one() == ("caliburn_jd_relational_test", "jd_test", 180006)
            assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == "20260913_0001"
        yield value
        assert calls and not any(calls), "This probe must not implicitly enter executemany."
    finally:
        value.dispose()


@pytest.fixture
def conn(engine):
    with engine.connect() as value:
        transaction = value.begin()
        try:
            yield value
        finally:
            transaction.rollback()


def document(conn):
    doc = str(uuid4())
    now = datetime.now(timezone.utc)
    conn.execute(db.jd_document.insert().values(id=doc, title="合成工作", metadata_version=1,
        create_request_key=str(uuid4()), create_payload_digest="a" * 64, created_at=now, updated_at=now))
    conn.execute(db.jd_profile.insert().values(document_id=doc, purpose="保存真實工作"))
    rev = revision(conn, doc)
    conn.execute(db.jd_head.insert().values(document_id=doc, current_revision_id=rev,
                                            revision_number=1, updated_at=now))
    return doc, rev


def revision(conn, doc, *, parent=None, number=1, origin=None):
    identity = uuid4()
    conn.execute(db.jd_revision.insert().values(document_id=doc, revision_id=identity,
        revision_number=number, parent_revision_id=parent, origin=origin or ("initial" if parent is None else "manual"),
        format_version=3, engine_profile="jd-relational-v1", snapshot={"probe": "DDL only"},
        content_digest="b" * 64, created_at=datetime.now(timezone.utc)))
    return identity


def item(conn, table, doc, **values):
    identity_column = list(table.primary_key.columns)[1]
    identity = values.pop(identity_column.name, uuid4())
    conn.execute(table.insert().values(document_id=doc, **{identity_column.name: identity}, position=0, **values))
    return identity


def source(conn, doc, **target):
    return item(conn, db.jd_source_link, doc, source_ref="synthetic-interview:1",
                basis_digest="c" * 64, **target)


def rejected(conn, statement, constraint, sqlstate="23503"):
    with pytest.raises(IntegrityError) as error:
        with conn.begin_nested():
            conn.execute(statement)
    assert error.value.orig.sqlstate == sqlstate
    assert error.value.orig.diag.constraint_name == constraint
    assert conn.execute(sa.select(sa.literal(True))).scalar_one()  # outer transaction remains usable


def count(conn, table, doc):
    return conn.execute(sa.select(sa.func.count()).select_from(table).where(table.c.document_id == doc)).scalar_one()


def test_actual_database_has_thirteen_business_tables_and_technical_version(conn):
    assert set(sa.inspect(conn).get_table_names(schema="public")) == db.JD_TABLE_NAMES | {"alembic_version"}


def test_nullable_unassigned_task_and_cross_document_parent_rejection(conn):
    doc, _ = document(conn)
    other, _ = document(conn)
    duty = item(conn, db.jd_duty, other, name="他人的工作")
    task = item(conn, db.jd_task, doc, name="尚未整理完整的任務", duty_id=None)
    rejected(conn, db.jd_task.update().where(db.jd_task.c.task_id == task).values(duty_id=duty), "fk_jd_task_duty")
    assert conn.execute(sa.select(db.jd_task.c.duty_id).where(db.jd_task.c.task_id == task)).scalar_one() is None


def test_duty_removal_requires_explicit_unassign_and_preserves_task_children(conn):
    doc, _ = document(conn)
    duty = item(conn, db.jd_duty, doc, name="系統維護")
    task = item(conn, db.jd_task, doc, name="檢查", description="僅限合約內系統", duty_id=duty)
    for kind in ("outcome", "requirement"):
        item(conn, db.jd_task_detail, doc, task_id=task, kind=kind, text="獨立內容")
    cap = item(conn, db.jd_capability, doc, kind="skill", name="診斷")
    conn.execute(db.jd_task_capability.insert().values(document_id=doc, task_id=task, capability_id=cap, position=0))
    source(conn, doc, linked_task_id=task, linked_capability_id=cap)
    stmt = db.jd_duty.delete().where(db.jd_duty.c.document_id == doc, db.jd_duty.c.duty_id == duty)
    rejected(conn, stmt, "fk_jd_task_duty", "23001")
    conn.execute(db.jd_task.update().where(db.jd_task.c.document_id == doc).values(duty_id=None))
    conn.execute(stmt)
    assert [count(conn, t, doc) for t in (db.jd_task, db.jd_task_detail, db.jd_task_capability, db.jd_source_link)] == [1, 2, 1, 1]
    assert conn.execute(sa.select(db.jd_task.c.description).where(db.jd_task.c.task_id == task)).scalar_one() == "僅限合約內系統"


def test_move_task_preserves_identity_and_details(conn):
    doc, _ = document(conn)
    duties = [item(conn, db.jd_duty, doc, name=name) for name in ("維護", "支援")]
    task = item(conn, db.jd_task, doc, name="異常處理", duty_id=duties[0])
    detail = item(conn, db.jd_task_detail, doc, task_id=task, kind="outcome", text="處理紀錄")
    conn.execute(db.jd_task.update().where(db.jd_task.c.task_id == task).values(duty_id=duties[1]))
    assert conn.execute(sa.select(db.jd_task_detail.c.task_id).where(db.jd_task_detail.c.detail_id == detail)).scalar_one() == task
    assert conn.execute(sa.select(db.jd_task.c.duty_id).where(db.jd_task.c.task_id == task)).scalar_one() == duties[1]


def test_capability_restrict_and_task_owned_cascade_leave_shared_library(conn):
    doc, _ = document(conn)
    task = item(conn, db.jd_task, doc, name="檢查")
    detail = item(conn, db.jd_task_detail, doc, task_id=task, kind="requirement", text="遵循現況")
    cap = item(conn, db.jd_capability, doc, kind="knowledge", name="作業知識")
    item(conn, db.jd_capability, doc, kind="knowledge", name="作業知識")  # no global name deduplication
    conn.execute(db.jd_task_capability.insert().values(document_id=doc, task_id=task, capability_id=cap, position=0))
    source(conn, doc, detail_id=detail)
    source(conn, doc, linked_task_id=task, linked_capability_id=cap)
    rejected(conn, db.jd_capability.delete().where(db.jd_capability.c.capability_id == cap), "fk_jd_task_capability_capability", "23001")
    conn.execute(db.jd_task.delete().where(db.jd_task.c.task_id == task))
    assert [count(conn, t, doc) for t in (db.jd_task_detail, db.jd_task_capability, db.jd_source_link, db.jd_capability)] == [0, 0, 0, 2]


@pytest.mark.parametrize("target,constraint", [
    ({}, "ck_jd_source_link_one_target"),
    ({"profile_field": "purpose", "task_id": uuid4()}, "ck_jd_source_link_one_target"),
    ({"linked_task_id": uuid4()}, "ck_jd_source_link_relation_pair"),
    ({"profile_field": "purpose", "linked_capability_id": uuid4()}, "ck_jd_source_link_relation_pair"),
    ({"profile_field": "imagined_field"}, "ck_jd_source_link_profile_field"),
])
def test_source_target_checks_are_executed_by_postgres(conn, target, constraint):
    doc, _ = document(conn)
    rejected(conn, db.jd_source_link.insert().values(document_id=doc, source_link_id=uuid4(),
        source_ref="synthetic", basis_digest="c" * 64, position=0, **target), constraint, "23514")


def test_source_profile_nullable_composite_fk_and_task_scope(conn):
    doc, _ = document(conn)
    other, _ = document(conn)
    task = item(conn, db.jd_task, other, name="他人的任務")
    source(conn, doc, profile_field="purpose")  # nullable FK targets work with MATCH SIMPLE
    rejected(conn, db.jd_source_link.insert().values(document_id=doc, source_link_id=uuid4(),
        source_ref="synthetic", basis_digest="c" * 64, position=0, task_id=task), "fk_jd_source_link_task")


@pytest.mark.parametrize("foreign_document", [False, True])
def test_source_relation_requires_an_existing_same_document_junction(conn, foreign_document):
    doc, _ = document(conn)
    target_doc, _ = document(conn) if foreign_document else (doc, None)
    task = item(conn, db.jd_task, target_doc, name="範圍內任務")
    cap = item(conn, db.jd_capability, target_doc, name="所需知識", kind="knowledge")
    if foreign_document:
        conn.execute(db.jd_task_capability.insert().values(document_id=target_doc, task_id=task,
                                                           capability_id=cap, position=0))
    # Either the endpoints exist without their relation, or the complete relation belongs to another JD.
    rejected(conn, db.jd_source_link.insert().values(document_id=doc, source_link_id=uuid4(),
        source_ref="synthetic", basis_digest="c" * 64, position=0,
        linked_task_id=task, linked_capability_id=cap), "fk_jd_source_link_relation")
    assert count(conn, db.jd_source_link, doc) == 0


def test_revision_initial_unique_linear_successor_and_head_document_scope(conn):
    doc, initial = document(conn)
    other, other_initial = document(conn)
    with pytest.raises(IntegrityError) as error:
        with conn.begin_nested():
            revision(conn, doc, number=9)
    assert error.value.orig.diag.constraint_name == "uq_jd_revision_initial"
    revision(conn, doc, parent=initial, number=2)
    with pytest.raises(IntegrityError) as error:
        with conn.begin_nested():
            revision(conn, doc, parent=initial, number=3)
    assert error.value.orig.diag.constraint_name == "uq_jd_revision_parent"
    rejected(conn, db.jd_head.update().where(db.jd_head.c.document_id == doc).values(current_revision_id=other_initial), "fk_jd_head_revision")


@pytest.mark.parametrize("patch,constraint", [
    ({"origin": "ai"}, "ck_jd_operation_origin_run"),
    ({"ai_run_id": "run"}, "ck_jd_operation_origin_run"),
    ({"status": "outcome_unknown", "result_revision_id": None}, "ck_jd_operation_status"),
    ({"status": "save_failed", "result_revision_id": "base"}, "ck_jd_operation_result"),
    ({"status": "committed", "result_revision_id": "base"}, "ck_jd_operation_result"),
    ({"status": "no_change", "result_revision_id": None}, "ck_jd_operation_result"),
])
def test_durable_operation_rejects_invalid_terminal_state(conn, patch, constraint):
    doc, base = document(conn)
    values = dict(document_id=doc, operation_id=uuid4(), request_digest="d" * 64,
        origin="manual", base_revision_id=base, result_revision_id=base, status="no_change",
        receipt={"probe": "DDL only"}, created_at=datetime.now(timezone.utc))
    values.update({key: base if value == "base" else value for key, value in patch.items()})
    rejected(conn, db.jd_operation.insert().values(**values), constraint, "23514")


def test_one_committed_operation_produces_revision_while_no_change_receipts_can_share_it(conn):
    doc, base = document(conn)
    result = revision(conn, doc, parent=base, number=2)
    values = dict(document_id=doc, request_digest="d" * 64, origin="ai", ai_run_id="synthetic-run",
        base_revision_id=base, result_revision_id=result, status="committed",
        receipt={"probe": "DDL only"}, created_at=datetime.now(timezone.utc))
    conn.execute(db.jd_operation.insert().values(operation_id=uuid4(), **values))
    rejected(conn, db.jd_operation.insert().values(operation_id=uuid4(), **values), "uq_jd_operation_committed_result", "23505")
    for _ in range(2):
        conn.execute(db.jd_operation.insert().values(operation_id=uuid4(), **{**values, "status": "no_change", "base_revision_id": result}))
    assert count(conn, db.jd_operation, doc) == 3


def test_committed_rows_reopen_from_a_fresh_process(engine):
    with engine.begin() as conn:
        doc, _ = document(conn)
        item(conn, db.jd_task, doc, name="繁中、標點\n第二行")
    # Fixed code and synthetic document ID only; credentials are the public test fixture.
    code = """
import json, sys
import sqlalchemy as sa
from jd_relational.storage.schema import jd_task
engine = sa.create_engine('postgresql+psycopg://jd_test:jd-local-test-only@127.0.0.1:55436/caliburn_jd_relational_test', hide_parameters=True)
with engine.connect() as conn:
    value = conn.execute(sa.select(jd_task.c.name).where(jd_task.c.document_id == sys.argv[1])).scalar_one()
print(json.dumps(value, ensure_ascii=True))
engine.dispose()
"""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    result = subprocess.run([sys.executable, "-c", code, doc], env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == "繁中、標點\n第二行"
    # This one synthetic document remains to demonstrate a real committed roundtrip.
