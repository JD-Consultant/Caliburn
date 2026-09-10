import os
import json
from pathlib import Path
from uuid import uuid4
import pytest
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

EVIDENCE = Path(__file__).parents[3] / '.superpowers/sdd/2026-09-10-jd-editor-core-implementation' / ('task-2-pg-' + str(uuid4()) + '.jsonl')


@pytest.fixture
def jd():
    from analysis_agent.catalog import Catalog
    from analysis_agent.jd_store import JdStore
    from analysis_agent.jd_engine import JdEngine
    from analysis_agent.jd_service import JdService
    dsn = os.environ.get('Q019_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('Dedicated JD PostgreSQL DSN required; not a persistence pass')
    params = conninfo_to_dict(dsn)
    assert params.get('dbname') == 'q019_jd_app_20260910'
    assert params.get('host') in {'localhost', '127.0.0.1'}
    assert 1 <= int(params.get('connect_timeout', 0)) <= 5
    engine = create_engine(URL.create('postgresql+psycopg'), connect_args=params, hide_parameters=True)
    catalog = Catalog(engine)
    catalog.setup()
    store = JdStore(engine)
    store.setup()
    with engine.connect() as conn:
        assert conn.scalar(text('SHOW server_version')).startswith('16.')
        assert conn.scalar(text('SHOW fsync')) == 'on'
        assert conn.scalar(text('SHOW synchronous_commit')) == 'on'
        assert set(conn.scalars(text("SELECT relpersistence FROM pg_class WHERE relname IN ('jd_head','jd_revision','jd_operation')"))) == {'p'}
    service = JdService(store, JdEngine(), catalog)
    documents = []
    create = service.create_document
    def tracked_create(title, **kwargs):
        result = create(title, **kwargs)
        documents.append(result['id'])
        return result
    service.create_document = tracked_create
    yield service
    with engine.connect() as conn:
        snapshots = {table: [dict(row) for document in documents for row in conn.execute(
            text('SELECT * FROM ' + table + ' WHERE document_id=:d'), {'d': document}).mappings()]
            for table in ('jd_head', 'jd_revision', 'jd_operation')}
        settings = {name: conn.scalar(text('SHOW ' + name)) for name in ('server_version', 'fsync', 'synchronous_commit')}
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open('a', encoding='utf-8') as evidence:
        evidence.write(json.dumps({'settings': settings, 'documents': documents, 'snapshot': snapshots},
                                  ensure_ascii=False, default=str) + '\n')
    print('PG exact snapshot:', EVIDENCE.name)
    engine.dispose()


def test_create_has_canonical_initial_head(jd):
    from analysis_agent.jd_types import JdScope, JdReadQuery
    document = jd.create_document('JD test ' + str(uuid4()))
    scope = JdScope(document['id'])
    view = jd.read(scope, JdReadQuery())
    assert view.revision.origin == 'initial'
    assert view.revision.parent_id is None
    assert view.revision.value[0]['type'] == 'p'
    assert view.revision.value[0]['children'] == [{'text': ''}]
    assert view.revision.value[0]['id']


def test_commit_replay_and_conflict(jd):
    from analysis_agent.jd_contract import manual_intent, revision_ref
    from analysis_agent.jd_types import JdScope, JdReadQuery
    doc = jd.create_document('JD test ' + str(uuid4()))
    scope = JdScope(doc['id'])
    base = jd.read(scope, JdReadQuery()).revision
    body = {'request_key': str(uuid4()), 'base_revision_ref': revision_ref(scope, base.id),
            'value': [{'type': 'p', 'id': 'p', 'children': [{'text': '工作'}]}]}
    intent = manual_intent(scope, body)
    first = jd.manual_save(intent)
    assert first.status == 'committed'
    assert jd.manual_save(intent) == first
    body['value'][0]['children'][0]['text'] = '衝突'
    assert jd.manual_save(manual_intent(scope, body)).status == 'operation_conflict'
    assert jd.store.receipt(scope, intent.operation_id, intent.digest) == first


def prepared(jd, text_value='工作'):
    from analysis_agent.jd_contract import manual_intent, revision_ref
    from analysis_agent.jd_types import JdScope, JdReadQuery
    scope = JdScope(jd.create_document('JD test ' + str(uuid4()))['id'])
    base = jd.read(scope, JdReadQuery()).revision
    value = [{'type': 'p', 'id': 'p', 'children': [{'text': text_value}]}]
    return manual_intent(scope, {'request_key': str(uuid4()), 'base_revision_ref': revision_ref(scope, base.id), 'value': value})


def counts(jd, scope):
    with jd.store.engine.connect() as conn:
        return tuple(conn.scalar(text('SELECT count(*) FROM ' + table + ' WHERE document_id=:d'),
                                 {'d': scope.document_id}) for table in ('jd_head', 'jd_revision', 'jd_operation'))


def test_no_change_and_terminal_failure(jd, monkeypatch):
    from dataclasses import replace
    from analysis_agent.jd_types import JdReadQuery
    from analysis_agent.jd_contract import request_digest
    i = prepared(jd)
    base = jd.read(i.scope, JdReadQuery()).revision
    same = replace(i, value=base.value, digest=request_digest(i.scope, base.id, base.value, 'manual'))
    assert jd.manual_save(same).status == 'no_change'
    assert counts(jd, i.scope) == (1, 1, 1)
    changed = replace(i, operation_id=uuid4())
    assert jd.manual_save(changed).status == 'committed'
    stale = replace(i, operation_id=uuid4())
    first = jd.manual_save(stale)
    assert first.status == 'stale_base'
    monkeypatch.setattr(jd.engine, 'validate_value', lambda *a, **k: pytest.fail('terminal replay executed Node'))
    assert jd.manual_save(stale) == first


def test_two_connections_one_winner(jd):
    from concurrent.futures import ThreadPoolExecutor
    from dataclasses import replace
    from threading import Barrier
    from sqlalchemy import event
    i = prepared(jd)
    other = replace(i, operation_id=uuid4())
    barrier, seen = Barrier(2, timeout=10), set()
    def at_lock(conn, cursor, statement, parameters, context, executemany):
        if 'FOR UPDATE' in statement:
            seen.add(id(conn.connection.driver_connection))
            barrier.wait()
    event.listen(jd.store.engine, 'before_cursor_execute', at_lock)
    try:
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(jd.manual_save, intent) for intent in (i, other)]
            outcomes = [future.result(timeout=25) for future in futures]
    finally:
        event.remove(jd.store.engine, 'before_cursor_execute', at_lock)
    assert len(seen) == 2
    assert sorted(o.status for o in outcomes) == ['committed', 'stale_base']
    assert counts(jd, i.scope) == (1, 2, 2)
    for intent, outcome in zip((i, other), outcomes):
        assert jd.store.receipt(i.scope, intent.operation_id, intent.digest) == outcome


@pytest.mark.parametrize('stage', ['revision', 'receipt', 'head'])
def test_rollback_and_unknown_are_distinct(jd, stage):
    from sqlalchemy import event
    i = prepared(jd)
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith({'revision': 'INSERT INTO jd_revision', 'receipt': 'INSERT INTO jd_operation',
                                 'head': 'UPDATE jd_head'}[stage]):
            raise RuntimeError('injected transaction failure')
    event.listen(jd.store.engine, 'after_cursor_execute', fail)
    try:
        with pytest.raises(RuntimeError, match='injected'):
            jd.manual_save(i)
    finally:
        event.remove(jd.store.engine, 'after_cursor_execute', fail)
    assert counts(jd, i.scope) == (1, 1, 0)


def test_scope_and_missing_document(jd):
    from analysis_agent.jd_types import JdScope, JdReadQuery, JdMissing
    i, other = prepared(jd), prepared(jd)
    assert jd.read(other.scope, JdReadQuery(revision_id=i.base_id)).status == 'target_missing'
    with pytest.raises(JdMissing):
        jd.store.current(JdScope('missing-' + str(uuid4())))
    with pytest.raises(JdMissing):
        jd.store.revision(other.scope, i.base_id)
    legacy = jd.catalog.create_document('legacy test ' + str(uuid4()))
    assert jd.read(JdScope(legacy['id']), JdReadQuery()).status == 'target_missing'


def test_manual_snapshot_has_no_invented_operations(jd):
    from analysis_agent.jd_types import JdChangeQuery
    i = prepared(jd)
    o = jd.manual_save(i)
    assert o.operations is None and o.affected_ids == []
    view = jd.change_read(i.scope, JdChangeQuery(operation_id=i.operation_id))
    assert view.before.value != view.after.value
    assert view.after.value == i.value
    history = jd.store.history(i.scope, i.base_id, o.result_id)
    assert (history.total, history.manual, history.ai) == (1, 1, 0)
    assert history.latest == (o,)


def test_fresh_process_receipt_first(jd):
    import json
    from pathlib import Path
    import subprocess
    import sys
    from analysis_agent.jd_contract import manual_intent, revision_ref, outcome_to_wire
    i = prepared(jd)
    body = {'request_key': str(uuid4()), 'base_revision_ref': revision_ref(i.scope, i.base_id), 'value': i.value}
    payload = {'document': i.scope.document_id, 'body': body, 'mode': 'exit_after_commit'}
    args = [sys.executable, str(Path(__file__).with_name('jd_process_worker.py'))]
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1] / 'src')}
    lost = subprocess.run(args, input=json.dumps(payload), text=True, capture_output=True, env=env, timeout=30)
    assert lost.returncode == 73, lost.stderr
    payload['mode'] = 'recover'
    recovered = subprocess.run(args, input=json.dumps(payload), text=True, capture_output=True, env=env, timeout=30)
    assert recovered.returncode == 0, recovered.stderr
    intent = manual_intent(i.scope, body)
    outcome = jd.store.receipt(i.scope, intent.operation_id, intent.digest)
    assert json.loads(recovered.stdout) == outcome_to_wire(outcome)
    assert outcome.status == 'committed' and counts(jd, i.scope) == (1, 2, 1)
    assert jd.store.current(i.scope).value == i.value
    print(recovered.stdout)


def test_commit_ack_lost_is_unknown_then_receipt(jd, monkeypatch):
    from sqlalchemy.exc import OperationalError
    i = prepared(jd)
    commit = jd.store.engine.dialect.do_commit
    def lost(connection):
        commit(connection)
        raise OperationalError('COMMIT', None, Exception('reply lost'), connection_invalidated=True)
    monkeypatch.setattr(jd.store.engine.dialect, 'do_commit', lost)
    result = jd.manual_save(i)
    assert (result.status, result.durability, result.next_action) == ('outcome_unknown', 'unconfirmed', 'reconcile_operation')
    monkeypatch.setattr(jd.store.engine.dialect, 'do_commit', commit)
    recovered = jd.store.receipt(i.scope, i.operation_id, i.digest)
    assert recovered.status == 'committed' and counts(jd, i.scope) == (1, 2, 1)


def test_closed_vs_unconfirmed_failure(jd, monkeypatch):
    from analysis_agent.jd_engine import JdEngineFailure
    from sqlalchemy.exc import OperationalError
    from sqlalchemy import event
    i = prepared(jd)
    def broken(*args, **kwargs):
        raise JdEngineFailure()
    monkeypatch.setattr(jd.engine, 'validate_value', broken)
    def no_receipt(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO jd_operation'):
            raise OperationalError('INSERT', None, Exception('unavailable'))
    event.listen(jd.store.engine, 'before_cursor_execute', no_receipt)
    try:
        result = jd.manual_save(i)
    finally:
        event.remove(jd.store.engine, 'before_cursor_execute', no_receipt)
    assert (result.status, result.durability, result.next_action) == ('engine_failed', 'unconfirmed', 'reconcile_operation')
    assert counts(jd, i.scope) == (1, 1, 0)
    final = jd.manual_save(i)
    assert final.status == 'engine_failed' and final.durability == 'confirmed'
    assert jd.manual_save(i) == final


def test_history_counts_manual_revert_mixed_and_nonancestor(jd):
    from dataclasses import replace
    from analysis_agent.jd_contract import request_digest
    from analysis_agent.jd_types import JdEditIntent, JdMissing
    i = prepared(jd)
    initial = jd.store.current(i.scope)
    first = jd.manual_save(i)
    reverted = replace(i, operation_id=uuid4(), base_id=first.result_id, value=initial.value,
                       digest=request_digest(i.scope, first.result_id, initial.value, 'manual'))
    second = jd.manual_save(reverted)
    commands = [{'type': 'replace_block_content', 'target_id': initial.value[0]['id'], 'content': [{'text': 'AI'}]}]
    third = jd.edit(JdEditIntent(i.scope, uuid4(), second.result_id,
                    request_digest(i.scope, second.result_id, commands, 'ai'), commands))
    assert third.status == 'committed'
    history = jd.store.history(i.scope, initial.id, third.result_id)
    assert (history.total, history.manual, history.ai) == (3, 2, 1)
    assert [o.result_id for o in history.latest] == [third.result_id, second.result_id, first.result_id]
    assert jd.store.producer(i.scope, initial.id) is None
    assert jd.store.producer(i.scope, third.result_id) == third
    with pytest.raises(JdMissing):
        jd.store.history(i.scope, third.result_id, initial.id)


def test_no_change_full_jsonb_equality_and_native_net_zero(jd):
    from dataclasses import replace
    from analysis_agent.jd_contract import request_digest
    from analysis_agent.jd_types import JdEditIntent
    i = prepared(jd)
    first = jd.manual_save(i)
    commands = [{'type': 'replace_block_content', 'target_id': 'p', 'content': [{'text': s}]} for s in ('暫時', '工作')]
    netzero = jd.edit(JdEditIntent(i.scope, uuid4(), first.result_id,
        request_digest(i.scope, first.result_id, commands, 'ai'), commands))
    assert netzero.status == 'no_change' and netzero.operations is None and netzero.affected_ids == []
    assert counts(jd, i.scope) == (1, 2, 2)
    changed = [{'id': 'p', 'type': 'p', 'children': [{'text': '工作', 'bold': True}]}]
    marked = replace(i, operation_id=uuid4(), base_id=first.result_id, value=changed,
                     digest=request_digest(i.scope, first.result_id, changed, 'manual'))
    assert jd.manual_save(marked).status == 'committed'


def test_initial_transaction_failure_leaves_no_catalog(jd):
    from sqlalchemy import event
    title = 'JD atomic create ' + str(uuid4())
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO jd_head'):
            raise RuntimeError('initial head failed')
    event.listen(jd.store.engine, 'before_cursor_execute', fail)
    try:
        with pytest.raises(RuntimeError):
            jd.create_document(title)
    finally:
        event.remove(jd.store.engine, 'before_cursor_execute', fail)
    assert not any(row['title'] == title for row in jd.catalog.documents())


def test_failed_receipt_commit_unconfirmed_remains_unchanged(jd, monkeypatch):
    from analysis_agent.jd_engine import JdEngineFailure
    from analysis_agent.jd_contract import outcome_to_wire
    from sqlalchemy.exc import OperationalError
    i = prepared(jd)
    def fail(*args, **kwargs):
        raise JdEngineFailure()
    monkeypatch.setattr(jd.engine, 'validate_value', fail)
    commit = jd.store.engine.dialect.do_commit
    def lost(connection):
        commit(connection)
        raise OperationalError('COMMIT', None, Exception('reply lost'))
    monkeypatch.setattr(jd.store.engine.dialect, 'do_commit', lost)
    result = jd.manual_save(i)
    assert (result.status, result.durability, result.next_action) == ('engine_failed', 'unconfirmed', 'reconcile_operation')
    assert outcome_to_wire(result)['document_effect'] == 'unchanged'


def test_read_failed_is_typed_stop(jd, monkeypatch):
    from analysis_agent.jd_types import JdReadQuery, JdChangeQuery
    from analysis_agent.jd_contract import read_failure_to_wire
    from sqlalchemy.exc import OperationalError
    i = prepared(jd)
    def fail(*args, **kwargs):
        raise OperationalError('SELECT', None, Exception('offline'))
    monkeypatch.setattr(jd.store, 'current', fail)
    result = jd.read(i.scope, JdReadQuery())
    assert result.status == 'read_failed'
    assert read_failure_to_wire(result)['next_action'] == 'stop'
    monkeypatch.setattr(jd.store, 'revision', fail)
    result = jd.change_read(i.scope, JdChangeQuery(before_id=i.base_id, after_id=i.base_id))
    assert read_failure_to_wire(result)['next_action'] == 'stop'


def test_single_direction_revision_constraints(jd):
    from copy import deepcopy
    from dataclasses import replace
    from sqlalchemy.exc import IntegrityError
    from analysis_agent.jd_contract import outcome_to_wire, outcome_from_row
    from analysis_agent.jd_store import revision, operation, head
    i = prepared(jd)
    first = jd.manual_save(i)
    with jd.store.engine.connect() as conn:
        row = dict(conn.execute(operation.select().where(operation.c.document_id == i.scope.document_id)).mappings().one())
    # Every malformed receipt must fail SQL CHECK even if NULL keys are absent.
    corruptions = [lambda r: r['receipt'].pop('status'),
                   lambda r: r['receipt'].update(receipt_durability='unconfirmed'),
                   lambda r: r['receipt'].update(actual_changes=None),
                   lambda r: r.update(result_revision_id=r['base_revision_id']),
                   lambda r: r.update(request_digest='bad'),
                   lambda r: r.update(origin='initial')]
    for corrupt in corruptions:
        candidate = deepcopy(row)
        candidate['operation_id'] = uuid4()
        corrupt(candidate)
        with pytest.raises(IntegrityError):
            with jd.store.engine.begin() as conn:
                conn.execute(operation.insert().values(**candidate))
    # Producer partial UNIQUE catches second committed result, not no_change.
    duplicate = deepcopy(row)
    duplicate['operation_id'] = uuid4()
    duplicate['receipt'] = outcome_to_wire(replace(first, operation_id=duplicate['operation_id']))
    with pytest.raises(IntegrityError):
        with jd.store.engine.begin() as conn:
            conn.execute(operation.insert().values(**duplicate))
    other = prepared(jd)
    for fields in [dict(origin='manual', parent_revision_id=None),
                   dict(origin='initial', parent_revision_id=i.base_id),
                   dict(origin='manual', parent_revision_id=other.base_id),
                   dict(origin='manual', parent_revision_id=i.base_id)]:
        with pytest.raises(IntegrityError):
            with jd.store.engine.begin() as conn:
                conn.execute(revision.insert().values(document_id=i.scope.document_id, revision_id=uuid4(),
                    format_version=2, engine_profile='jd-plate-clean-v2', value=i.value, **fields))
    mismatched = deepcopy(row)
    mismatched['operation_id'] = uuid4()
    with pytest.raises(ValueError, match='identity'):
        outcome_from_row(i.scope, mismatched)


def test_two_no_change_receipts_share_base(jd):
    from dataclasses import replace
    from analysis_agent.jd_contract import request_digest
    i = prepared(jd)
    base = jd.store.current(i.scope)
    i = replace(i, value=base.value, digest=request_digest(i.scope, base.id, base.value, 'manual'))
    a = jd.manual_save(i)
    b = jd.manual_save(replace(i, operation_id=uuid4()))
    assert a.status == b.status == 'no_change' and a.result_id == b.result_id == base.id
    assert counts(jd, i.scope) == (1, 1, 2)


def test_sql_total_budget_and_real_lock_cancellation(jd):
    import time
    from analysis_agent.jd_store import JdStore, head
    from analysis_agent.jd_service import JdService
    i = prepared(jd)
    bounded = JdStore(jd.store.engine, timeout=.2)
    service = JdService(bounded, jd.engine, jd.catalog)
    with jd.store.engine.connect() as blocker:
        blocker.execute(head.select().where(head.c.document_id == i.scope.document_id).with_for_update())
        started = time.monotonic()
        result = service.manual_save(i)
        assert result.status == 'save_failed' and result.durability == 'unconfirmed'
        assert time.monotonic() - started < 3
        blocker.rollback()
    assert counts(jd, i.scope) == (1, 1, 0)
    with bounded._connection() as (conn, deadline):
        with pytest.raises((TimeoutError, __import__('sqlalchemy').exc.DBAPIError)):
            bounded._execute(conn, deadline, text('SELECT pg_sleep(2)'))


def test_array_order_repeats_props_and_refs_are_not_containment(jd):
    from dataclasses import replace
    from analysis_agent.jd_contract import request_digest
    i = prepared(jd)
    saved = jd.manual_save(i)
    values = [
        [{'id': 'p', 'type': 'p', 'children': [{'text': '工作'}]}, {'id': 'q', 'type': 'p', 'children': [{'text': '工作'}]}],
        [{'id': 'q', 'type': 'p', 'children': [{'text': '工作'}]}, {'id': 'p', 'type': 'p', 'children': [{'text': '工作'}]}],
        [{'id': 'q', 'type': 'p', 'children': [{'text': '工作', 'italic': True}]}, {'id': 'p', 'type': 'p', 'children': [{'text': '工作'}]}],
    ]
    for value in values:
        intent = replace(i, operation_id=uuid4(), base_id=saved.result_id, value=value,
                         digest=request_digest(i.scope, saved.result_id, value, 'manual'))
        saved = jd.manual_save(intent)
        assert saved.status == 'committed'
        assert jd.store.current(i.scope).value == value


def test_initial_create_uses_total_sql_budget(jd):
    import time
    from sqlalchemy import event
    title = 'JD timed create ' + str(uuid4())
    jd.store.timeout = .1
    def pause(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO q019_document'):
            time.sleep(.15)
    event.listen(jd.store.engine, 'after_cursor_execute', pause)
    try:
        with pytest.raises(TimeoutError):
            jd.create_document(title)
    finally:
        event.remove(jd.store.engine, 'after_cursor_execute', pause)
    assert not any(row['title'] == title for row in jd.catalog.documents())


def test_missing_catalog_unbound_but_missing_base_has_terminal_receipt(jd):
    from dataclasses import replace
    from analysis_agent.jd_types import JdScope
    from analysis_agent.jd_contract import request_digest, outcome_to_wire
    i = prepared(jd)
    absent = replace(i, scope=JdScope('missing-' + str(uuid4())))
    absent = replace(absent, digest=request_digest(absent.scope, absent.base_id, absent.value, 'manual'))
    result = jd.manual_save(absent)
    assert result.operation_id is None and result.next_action == 'reread_current'
    assert outcome_to_wire(result)['receipt_durability'] == 'unconfirmed'
    bad_base = uuid4()
    bad = replace(i, base_id=bad_base, digest=request_digest(i.scope, bad_base, i.value, 'manual'))
    result = jd.manual_save(bad)
    assert result.status == 'target_missing' and result.durability == 'confirmed' and result.base_id is None
    assert jd.store.receipt(i.scope, i.operation_id, bad.digest) == result


def test_format2_links_historical_values_and_failure_zero_publication(jd):
    from copy import deepcopy
    from dataclasses import replace
    from analysis_agent.jd_contract import request_digest
    from analysis_agent.jd_types import JdReadQuery
    value = json.loads((Path(__file__).parents[2] / 'jd-editor/fixtures/r2-canonical.json').read_text(encoding='utf-8'))
    i = prepared(jd)
    i = replace(i, value=value, digest=request_digest(i.scope, i.base_id, value, 'manual'))
    first = jd.manual_save(i)
    assert first.status == 'committed'
    edited = deepcopy(value)
    def walk(nodes):
        for n in nodes:
            yield n
            yield from walk(n.get('children', []))
    task = next(n for n in walk(edited) if n.get('knowledge_ids'))
    task['knowledge_ids'] = []
    second = replace(i, operation_id=uuid4(), base_id=first.result_id, value=edited,
                     digest=request_digest(i.scope, first.result_id, edited, 'manual'))
    saved = jd.manual_save(second)
    assert saved.status == 'committed'
    assert jd.read(i.scope, JdReadQuery(revision_id=first.result_id)).revision.value == value
    assert jd.store.current(i.scope).value == edited
    task['knowledge_ids'] = ['not-an-existing-knowledge-item']
    invalid = replace(i, operation_id=uuid4(), base_id=saved.result_id, value=edited,
                      digest=request_digest(i.scope, saved.result_id, edited, 'manual'))
    failed = jd.manual_save(invalid)
    assert failed.status in {'invalid_input', 'unsupported_content'}
    assert jd.store.current(i.scope).id == saved.result_id
    assert counts(jd, i.scope) == (1, 3, 3)
