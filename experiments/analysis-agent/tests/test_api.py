from uuid import uuid4
from contextlib import contextmanager
from threading import Event

from test_service import service_harness
from test_consolidation import done


def test_api_lifespan_idempotency_and_private_state_projection(tmp_path):
    from fastapi.testclient import TestClient
    from analysis_agent.api import create_app
    entered, release, closed = Event(), Event(), Event()
    def reply(request):
        entered.set()
        assert release.wait(5)
        result = done()
        result['output'].insert(0, {'type': 'reasoning', 'id': 'rs1', 'encrypted_content': 'PRIVATE-REASONING', 'summary': []})
        return result
    @contextmanager
    def resources():
        with service_harness(tmp_path, respond=reply) as (service, sent, _):
            yield service
        closed.set()
    app = create_app(resources)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        doc = client.post('/documents', json={'request_key': str(uuid4()), 'title': '網站接案'}).json()['id']
        try:
            body = {'request_key': 'one', 'text': '我製作網站'}
            result = client.post(f'/documents/{doc}/runs', json=body)
            assert result.status_code == 202
            assert entered.wait(5)
            assert client.get('/health').status_code == 200
            duplicate = client.post(f'/documents/{doc}/runs', json=body)
            assert duplicate.json()['id'] == result.json()['id']
            assert client.post(f'/documents/{doc}/runs', json={**body, 'request_key': 'two'}).status_code == 409
            assert client.get(f'/documents/{doc}/messages').json()[0]['text'] == body['text']
            assert client.post(f'/documents/{doc}/runs', json={**body, 'checkpoint_id': 'evil'}).status_code == 422
            assert client.post('/documents', json={'request_key': str(uuid4()), 'title': 'X'}, headers={'Origin': 'https://evil.example'}).status_code == 403
            assert client.get('/health', headers={'Host': 'evil.example'}).status_code == 400
        finally:
            release.set()
        app.state.service.join(doc)
        detail = client.get(f'/documents/{doc}/runs/{result.json()["id"]}')
        assert detail.json()['status'] == 'completed'
        assert 'PRIVATE-REASONING' not in detail.text + client.get(f'/documents/{doc}/messages').text
        assert '/documents/{document}/runs/{run_id}/resume' in client.get('/openapi.json').json()['paths']
    assert closed.is_set()


def test_api_cross_document_access_and_empty_input(tmp_path):
    from fastapi.testclient import TestClient
    from analysis_agent.api import create_app
    @contextmanager
    def resources():
        with service_harness(tmp_path) as (service, _, _):
            yield service
    with TestClient(create_app(resources), base_url='http://localhost') as client:
        doc = client.post('/documents', json={'request_key': str(uuid4()), 'title': 'A'}).json()['id']
        other = client.post('/documents', json={'request_key': str(uuid4()), 'title': 'B'}).json()['id']
        run = client.post(f'/documents/{doc}/runs', json={'request_key': 'a', 'text': 'A'}).json()['id']
        assert client.get(f'/documents/{other}/runs/{run}').status_code == 404
        assert client.post(f'/documents/{other}/runs/{run}/stop').status_code == 404
        assert client.post(f'/documents/{other}/runs', json={'request_key': 'b', 'text': '  '}).status_code == 422
        assert client.get(f'/documents/{other}/messages').json() == []


def test_api_background_status_is_safe_and_not_a_manual_consolidation_entry(tmp_path):
    from fastapi.testclient import TestClient
    from langgraph.store.memory import InMemoryStore
    from analysis_agent.api import create_app
    from analysis_agent.publication import Base
    from test_scheduling import notify
    from test_extraction import body
    @contextmanager
    def resources():
        with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
            Base.metadata.create_all(service.catalog.engine)
            service.enable_background(max_recoveries=1)
            doc = service.create_document('背景狀態')['id']
            notify(service, doc, replies)
            bad = body()
            bad['status'] = 'incomplete'
            replies.append(bad)
            service.background.tick()
            yield service
    app = create_app(resources)
    with TestClient(app, base_url='http://localhost') as client:
        doc = client.get('/documents').json()[0]['id']
        status = client.get(f'/documents/{doc}/memory-status')
        assert status.json() == {'status': 'blocked', 'error_code': 'background_error', 'recovery_count': 0}
        assert client.get('/documents/missing/memory-status').status_code == 404
        assert client.post(f'/documents/{doc}/memory-status').status_code == 405
