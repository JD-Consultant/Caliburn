"""NL12: original receipt is read only after the actual PG head lock barrier."""
from threading import Event, Thread
from uuid import uuid4
import pytest
from sqlalchemy import select
from test_jd_postgres import jd, prepared as manual


@pytest.mark.parametrize('commit', [False, True])
def test_recovery_waits_for_original_head_lock_before_scoped_receipt(jd, commit):
    assert hasattr(jd.store, 'reconcile_after_writer_stopped'), 'Stopped-writer PG barrier is missing'
    from analysis_agent.jd_store import head, operation
    from analysis_agent.jd_reconcile import JdWriterStopped
    from analysis_agent.jd_engine import JdNativeCalls
    from analysis_agent.windows_lifecycle import require_bootstrap
    intent = manual(jd)
    # Represent a server transaction whose client has stopped issuing statements.
    conn = jd.store.engine.connect(); transaction = conn.begin()
    conn.execute(select(head).where(head.c.document_id == intent.scope.document_id).with_for_update())
    locked, results, errors = Event(), [], []
    original = jd.store._execute
    def observe(c, deadline, statement, params=None):
        if getattr(statement, '_for_update_arg', None) is not None:
            locked.set()
        return original(c, deadline, statement, params)
    jd.store._execute = observe
    proof = JdWriterStopped(intent.scope, JdNativeCalls(), lambda: True, require_bootstrap())
    def recover():
        try:
            results.append(jd.store.reconcile_after_writer_stopped(intent, proof))
        except BaseException as exc:
            errors.append(exc)
    worker = Thread(target=recover); worker.start()
    try:
        assert locked.wait(5)
        assert not results
        if commit:
            from analysis_agent.jd_store import failure
            from analysis_agent.jd_contract import outcome_to_wire
            outcome = failure(intent, 'save_failed', base_id=intent.base_id)
            conn.execute(operation.insert().values(document_id=intent.scope.document_id,
                operation_id=intent.operation_id, request_digest=intent.digest, origin=intent.origin,
                base_revision_id=intent.base_id, result_revision_id=None,
                status='save_failed', receipt=outcome_to_wire(outcome)))
            transaction.commit()
        else:
            transaction.rollback()
        worker.join(5)
        assert not worker.is_alive() and not errors
        assert len(results) == 1
        assert (results[0].status == 'save_failed') if commit else (results[0] is None)
    finally:
        if transaction.is_active: transaction.rollback()
        conn.close(); worker.join(5)


def test_recovery_refuses_live_native_before_any_receipt_lookup(jd):
    assert hasattr(jd.store, 'reconcile_after_writer_stopped'), 'Stopped-writer PG barrier is missing'
    from analysis_agent.jd_reconcile import JdWriterStopped
    from analysis_agent.jd_engine import JdNativeCalls
    from analysis_agent.publication import PublicationUncertain
    owner = JdNativeCalls()
    token, call = owner.register(lambda p: False, .1)
    intent = manual(jd)
    proof = JdWriterStopped(intent.scope, owner, lambda: True)
    with pytest.raises(PublicationUncertain):
        jd.store.reconcile_after_writer_stopped(intent, proof)


@pytest.mark.parametrize('fault',['head_missing','lock_timeout','connection_lost'])
def test_pg_negative_barrier_never_becomes_known_none(jd,monkeypatch,fault):
    from contextlib import contextmanager
    from sqlalchemy import text
    from analysis_agent.jd_store import head
    from analysis_agent.jd_reconcile import JdWriterStopped,reconcile_identity
    from analysis_agent.jd_engine import JdNativeCalls
    from analysis_agent.jd_types import JdScope
    from analysis_agent.publication import PublicationUncertain
    from dataclasses import replace
    intent=manual(jd)
    if fault=='head_missing':
        document=jd.catalog.create_document('NL12 missing JD head')['id']
        intent=replace(intent,scope=JdScope(document))
    lock=None
    if fault=='lock_timeout':
        lock=jd.store.engine.connect();transaction=lock.begin()
        lock.execute(select(head).where(head.c.document_id==intent.scope.document_id).with_for_update())
        monkeypatch.setattr(jd.store,'timeout',.2)
    if fault=='connection_lost':
        original=jd.store._connection
        @contextmanager
        def disconnected():
            with original() as (connection,deadline):
                own_pid=connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
                connection.rollback()
                with jd.store.engine.connect() as observer:
                    assert observer.execute(text('SELECT pg_terminate_backend(:pid)'),{'pid':own_pid}).scalar_one()
                yield connection,deadline
        monkeypatch.setattr(jd.store,'_connection',disconnected)
    published=[]
    monkeypatch.setattr(jd.store,'publish',lambda *a,**kw:published.append(a))
    try:
        with pytest.raises(PublicationUncertain):
            reconcile_identity(jd.store,intent,JdWriterStopped(intent.scope,JdNativeCalls(),lambda:True))
        assert not published
    finally:
        if lock is not None: transaction.rollback();lock.close()
