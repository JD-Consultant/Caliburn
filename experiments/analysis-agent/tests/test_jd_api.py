"""Task4 HTTP seams: the real service/router, an offline SDK transport."""
from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient
from test_service import service_harness
from test_jd_postgres import jd


@contextmanager
def client_for(tmp_path):
    from analysis_agent.api import create_app
    @contextmanager
    def resources():
        with service_harness(tmp_path) as harness:
            yield harness[0]
    with TestClient(create_app(resources), base_url='http://127.0.0.1:8091') as client:
        yield client


def test_create_identity_metadata_and_ui_filter_do_not_filter_scheduler(tmp_path):
    with client_for(tmp_path) as client:
        body = {'title': '網站接案', 'request_key': str(uuid4())}
        response = client.post('/documents', json=body)
        assert response.status_code == 201
        doc = response.json()
        assert doc['metadata_version'] == 1 and doc['archived'] is False
        assert client.post('/documents', json=body).json()['id'] == doc['id']
        assert client.post('/documents', json={**body, 'title': '其他'}).status_code == 409
        renamed = client.patch('/documents/'+doc['id'], json={
            'command': 'rename', 'title': '新名稱', 'expected_metadata_version': 1})
        assert renamed.json()['metadata_version'] == 2
        assert client.patch('/documents/'+doc['id'], json={
            'command': 'rename', 'title': '舊回覆', 'expected_metadata_version': 1}).status_code == 409
        archived = client.patch('/documents/'+doc['id'], json={
            'command': 'set_archived', 'archived': True, 'expected_metadata_version': 2})
        assert archived.json()['archived'] is True
        assert client.get('/documents').json() == []
        assert client.get('/documents?archived=true').json()[0]['id'] == doc['id']
        assert client.app.state.service.list_documents()[0]['id'] == doc['id']
        assert client.post('/documents', json=body).json()['id'] == doc['id']


def test_two_web_origins_and_preflight_only(tmp_path):
    with client_for(tmp_path) as client:
        for origin in ('http://127.0.0.1:3001', 'http://localhost:3001'):
            result = client.options('/documents', headers={'Origin': origin,
                'Access-Control-Request-Method': 'PATCH', 'Access-Control-Request-Headers': 'Content-Type'})
            assert result.status_code == 200
            assert result.headers['access-control-allow-origin'] == origin
            assert 'access-control-allow-credentials' not in result.headers
            assert client.get('/documents', headers={'Origin': origin}).status_code == 200
            doc = client.post('/documents', headers={'Origin': origin}, json={
                'title': '來源測試', 'request_key': str(uuid4())})
            assert doc.status_code == 201
            assert client.patch('/documents/'+doc.json()['id'], headers={'Origin': origin}, json={
                'command': 'rename', 'title': '來源更新', 'expected_metadata_version': 1}).status_code == 200
        for origin in ('https://evil.example', 'http://localhost:3000'):
            assert client.get('/documents', headers={'Origin': origin}).status_code == 403


def test_run_lookup_is_read_only_and_digest_covers_abandon_pending(tmp_path):
    with client_for(tmp_path) as client:
        doc = client.post('/documents', json={'title': 'A', 'request_key': str(uuid4())}).json()['id']
        path = f'/documents/{doc}/runs'
        assert client.get(path+'/by-request', params={'request_key': 'x'}).json() == {'found': False}
        body = {'request_key': 'x', 'text': '原始繁中問句', 'abandon_pending': False}
        result = client.post(path, json=body)
        assert result.status_code == 202
        client.app.state.service.join(doc)
        found = client.get(path+'/by-request', params={'request_key': 'x'}).json()
        assert found['found'] and found['input_received']
        assert found['run']['id'] == result.json()['id']
        assert client.post(path, json={**body, 'abandon_pending': True}).status_code == 409
        assert client.get(f'/documents/{doc}/messages').json()[0]['text'] == body['text']
        reference = client.app.state.service.reader(doc).capture_input(result.json()['id'])
        source = client.get(f'/documents/{doc}/sources', params={'reference': reference})
        assert source.status_code == 200
        assert any(s['role'] == 'user' and s['text'] == body['text'] for s in source.json()['segments'])
        assert client.get('/documents/not-this-document/sources', params={'reference': reference}).status_code == 404


def test_pg_routes_manual_receipt_history_and_cross_document_scope(jd, tmp_path):
    from analysis_agent.api import create_app
    # Compose exactly the existing service and JD owner on the same PG engine.
    @contextmanager
    def resources():
        with service_harness(tmp_path, engine=jd.catalog.engine) as (service, _, _):
            service.jd = jd
            yield service
    with TestClient(create_app(resources), base_url='http://127.0.0.1:8091') as client:
        a = jd.create_document('A')['id']
        b = jd.create_document('B')['id']
        path = f'/documents/{a}/jd'
        read = client.get(path)
        assert read.status_code == 200
        before = read.json()
        value = before['fragment']
        value[0]['children'] = [{'text': '第一次工作，第二次工作'}]
        body = {'request_key': str(uuid4()), 'base_revision_ref': before['revision_ref'], 'value': value}
        saved = client.post(path+'/manual-save', json=body)
        assert saved.status_code == 200, saved.text
        assert saved.json()['status'] == 'committed'
        assert client.post(path+'/manual-save', json=body).json() == saved.json()
        current = client.get(path).json()
        assert current['fragment'] == value
        changes = client.post(path+'/changes/read', json={'change_ref': saved.json()['change_ref']}).json()
        assert changes['after_fragment'] == value
        assert changes['before_fragment'][0]['children'] == [{'text': ''}]
        wrong = client.post(f'/documents/{b}/jd/read', json={'revision_ref': current['revision_ref']})
        assert wrong.status_code in (409, 422)
        assert client.get(f'/documents/{b}/jd').json()['fragment'] != value
        selected = {'request_key': 'selection-'+str(uuid4()), 'text': '保留這句原話',
            'jd_selection': {'base_revision_ref': current['revision_ref'],
                'range': {'anchor': {'path': [0, 0], 'offset': 0}, 'focus': {'path': [0, 0], 'offset': 2}}}}
        run = client.post(f'/documents/{a}/runs', json=selected)
        assert run.status_code == 202
        client.app.state.service.join(a)
        import copy
        different = copy.deepcopy(selected)
        different['jd_selection']['range']['focus']['offset'] = 3
        assert client.post(f'/documents/{a}/runs', json=different).status_code == 409
        assert client.get(f'/documents/{a}/messages').json()[0]['text'] == selected['text']
        # An exact terminal receipt remains a read even while new writes are forbidden.
        service = client.app.state.service
        pending = service.catalog.create_run(a, 'busy-'+str(uuid4()), 'digest')
        assert client.post(path+'/manual-save', json=body).json() == saved.json()
        assert client.post(path+'/manual-save', json={**body, 'request_key': str(uuid4())}).status_code == 409
        service.catalog.update_run(pending['id'], status='completed')
        assert client.patch(f'/documents/{a}', json={'command': 'set_archived', 'archived': True,
            'expected_metadata_version': 1}).status_code == 200
        assert client.post(path+'/manual-save', json=body).json() == saved.json()
        assert client.post(path+'/manual-save', json={**body, 'request_key': str(uuid4())}).status_code == 409


def test_pg_manual_rejection_is_explicit_only_after_receipt_check(jd, tmp_path, monkeypatch):
    from analysis_agent.api import create_app
    @contextmanager
    def resources():
        with service_harness(tmp_path, engine=jd.catalog.engine) as (service, _, _):
            service.jd = jd
            yield service
    with TestClient(create_app(resources), base_url='http://127.0.0.1:8091') as client:
        document = jd.create_document('拒絕回覆')['id']
        path = f'/documents/{document}/jd'
        head = client.get(path).json()
        body = {'request_key': str(uuid4()), 'base_revision_ref': head['revision_ref'], 'value': head['fragment']}
        invalid = {**body, 'value': [{'type': 'unknown', 'id': 'bad', 'children': [{'text': '保留'}]}]}
        rejected = client.post(path+'/manual-save', json=invalid)
        assert rejected.status_code == 422
        assert rejected.json()['admission'] == 'not_admitted'
        assert rejected.json()['request_key'] == body['request_key']
        saved = client.post(path+'/manual-save', json=body)
        assert saved.status_code == 200
        # A malformed replay of an identity that already has a receipt is NOT zero-write evidence.
        existing = client.post(path+'/manual-save', json=invalid)
        assert 'admission' not in existing.json()
        existing_normalized = client.post(path+'/manual-save', json={**invalid, 'request_key': body['request_key'].upper()})
        assert 'admission' not in existing_normalized.json()
        monkeypatch.setattr(jd.store, 'receipt', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('receipt unavailable')))
        unavailable = client.post(path+'/manual-save', json={**invalid, 'request_key': str(uuid4())})
        assert unavailable.status_code == 503
        assert 'admission' not in unavailable.json()


def test_pg_create_key_atomic_replay_and_failed_initial_value_leave_no_catalog(jd, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import text
    from analysis_agent.jd_types import JdScope, JdReadQuery
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: jd.create_document('同一次建立', request_key=key), range(2)))
    assert results[0]['id'] == results[1]['id']
    doc = results[0]['id']
    original = jd.read(JdScope(doc), JdReadQuery()).revision.id
    jd.catalog.update_document(doc, {'command': 'rename', 'title': '改名', 'expected_metadata_version': 1})
    jd.catalog.update_document(doc, {'command': 'set_archived', 'archived': True, 'expected_metadata_version': 2})
    assert jd.create_document('同一次建立', request_key=key)['id'] == doc
    assert jd.read(JdScope(doc), JdReadQuery()).revision.id == original
    with jd.catalog.engine.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM jd_revision WHERE document_id=:d'), {'d': doc}) == 1
    failed_key = str(uuid4())
    execute = jd.store._execute
    failed_document = []
    def fail_head(conn, deadline, statement, *args, **kwargs):
        if getattr(getattr(statement, 'table', None), 'name', None) == 'jd_head':
            failed_document.append(statement.compile().params['document_id'])
            raise RuntimeError('after catalog and revision, before head')
        return execute(conn, deadline, statement, *args, **kwargs)
    monkeypatch.setattr(jd.store, '_execute', fail_head)
    import pytest
    with pytest.raises(RuntimeError):
        jd.create_document('失敗建立', request_key=failed_key)
    assert jd.catalog.created_by_request(failed_key, '失敗建立') is None
    with jd.catalog.engine.connect() as conn:
        for table in ('jd_revision', 'jd_head'):
            assert conn.scalar(text('SELECT count(*) FROM '+table+' WHERE document_id=:d'), {'d': failed_document[0]}) == 0
