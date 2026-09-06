"""Rebuild clients around genuine PostgreSQL Saver, Store and ORM catalog."""
from contextlib import contextmanager
import json
import os

import httpx
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from analysis_agent.catalog import DocumentRow, RunRow
from analysis_agent.scheduling import BackgroundRow
from analysis_agent.memory import MemoryArtifacts
from analysis_agent.publication import PublicationStore, HeadRow, ReceiptRow
from test_service import service_harness
from test_consolidation import call, done


@pytest.fixture
def pg_service(tmp_path):
    dsn = os.environ.get('Q019_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('Dedicated q019_agent_test required; service durability NOT verified')
    params = conninfo_to_dict(dsn)
    assert params.get('dbname') == 'q019_agent_test'
    assert params.get('host') in ('127.0.0.1', 'localhost') and params.get('port') == '55433'
    assert 1 <= int(params.get('connect_timeout', '0')) <= 10
    dsn = make_conninfo(dsn, options='-c statement_timeout=10000 -c lock_timeout=5000')
    owned = []
    @contextmanager
    def opened():
        engine = create_engine(URL.create('postgresql+psycopg'), connect_args=conninfo_to_dict(dsn), hide_parameters=True)
        try:
            with PostgresSaver.from_conn_string(dsn) as saver, PostgresStore.from_conn_string(dsn) as store:
                saver.setup()
                store.setup()
                pub = PublicationStore(engine, MemoryArtifacts(store, 'q019-schema-setup'))
                pub.setup()
                with service_harness(tmp_path, saver=saver, engine=engine, store=store) as h:
                    yield h
        finally:
            engine.dispose()
    try:
        yield opened, owned
    finally:
        # Only exact document IDs created by this test; no database/table drop.
        engine = create_engine(URL.create('postgresql+psycopg'), connect_args=conninfo_to_dict(dsn), hide_parameters=True)
        try:
            with PostgresSaver.from_conn_string(dsn) as saver, PostgresStore.from_conn_string(dsn) as store:
                for doc in owned:
                    saver.delete_thread(doc)
                    from uuid import NAMESPACE_URL, uuid5
                    for prefix in ('q019-b1:', 'q019-b2:'):
                        saver.delete_thread(str(uuid5(NAMESPACE_URL, prefix + doc)))
                    with Session(engine) as session, session.begin():
                        for cls in (BackgroundRow, RunRow, ReceiptRow, HeadRow):
                            for row in session.scalars(select(cls).where(cls.document_id == doc)):
                                session.delete(row)
                        row = session.get(DocumentRow, doc)
                        if row:
                            session.delete(row)
                    items, offset = [], 0
                    while page := store.search(('q019-memory', doc), limit=100, offset=offset):
                        items.extend(page)
                        offset += len(page)
                    for item in items:
                        store.delete(item.namespace, item.key)
        finally:
            engine.dispose()


@pytest.mark.parametrize('phase', ['saved_input', 'saved_result', 'transport_failure'])
def test_pg_catalog_and_checkpoint_reconcile_across_rebuilt_clients(pg_service, phase, monkeypatch):
    opened, owned = pg_service
    with opened() as (service, sent, replies):
        doc = service.create_document('PG服務重建')['id']
        owned.append(doc)
        if phase == 'saved_input':
            def fail(*args):
                raise RuntimeError('injected before executor')
            monkeypatch.setattr(service, '_launch', fail)
            with pytest.raises(RuntimeError, match='before executor'):
                service.submit(doc, 'same-request', '我製作網站A。')
            run_id = service.catalog.runs(doc)[0]['id']
        else:
            if phase == 'transport_failure':
                replies.extend(httpx.ReadTimeout('offline failure') for _ in range(3))
            run_id = service.submit(doc, 'same-request', '我製作網站A。')['id']
            service.join(doc)
            if phase == 'saved_result':
                service.catalog.update_run(run_id, status='running')
    with opened() as (service, sent, _):
        assert not sent, 'startup must not spend paid work automatically'
        repeated = service.submit(doc, 'same-request', '我製作網站A。')
        assert repeated['id'] == run_id
        if phase != 'saved_result':
            assert repeated['status'] == 'interrupted' and repeated['can_resume']
            service.resume(doc, run_id)
            service.join(doc)
        result = service.get_run(doc, run_id)
        assert result['status'] == 'completed'
        assert result['resume_count'] == (0 if phase == 'saved_result' else 1)
        assert len([m for m in service.messages(doc) if m['role'] == 'user']) == 1
        assert len(sent) == (0 if phase == 'saved_result' else 1)


def test_pg_main_service_reads_document_memory_and_keeps_native_items(pg_service):
    opened, owned = pg_service
    with opened() as (service, sent, replies):
        doc = service.create_document('記憶接線')['id']
        owned.append(doc)
        pub = PublicationStore(service.catalog.engine, MemoryArtifacts(service.store, doc))
        version = pub.artifacts.save_memory(knowledge='我為餐飲客戶製作點餐網站。', guide='餐飲／點餐網站')
        pub.publish(pub.prepare(version, expected_revision=0, kind='repair'))
        replies.append(call('read_file', file_path='/memory/knowledge.md'))
        final = done()
        final['output'].insert(0, {'type': 'reasoning', 'id': 'rs', 'encrypted_content': 'opaque-test', 'summary': []})
        replies.append(final)
        run = service.submit(doc, 'first', '那網站A的部分呢？')
        service.join(doc)
        assert service.get_run(doc, run['id'])['status'] == 'completed'
        assert '餐飲／點餐網站' in sent[0].content.decode()
        assert '點餐網站' in sent[1].content.decode()
        assert 'opaque-test' not in str(service.messages(doc))
    with opened() as (service, sent, _):
        graph = service.reader(doc).graph
        raw = graph.get_state({'configurable': {'thread_id': doc}}).values['messages']
        assert 'opaque-test' in str(raw), 'native reasoning must remain in canonical Saver'
        assert not sent


def test_pg_service_rebuild_validates_and_reads_memory_source_links(pg_service):
    from test_memory_references import changed_reference
    opened, owned = pg_service
    with opened() as (service, sent, _):
        doc = service.create_document('原文引用重建')['id']
        owned.append(doc)
        run = service.submit(doc, 'source', 'A案由處長核准。')
        service.join(doc)
        assert service.get_run(doc, run['id'])['status'] == 'completed'
        context = service._context(doc)
        reader = context.reader
        last = context.graph.get_state(context.config).values['messages'][-1].id
        ref = reader.capture(run['id'], last)
        pub = context.memory.publication
        detail = pub.artifacts.save_extraction(summary='A案：處長核准', candidates='核准責任',
            slug='A', source_reference=ref)
        version = pub.artifacts.save_memory(
            knowledge=f'__{detail.summary_path}__\n[原話]({ref})', guide='A案')
        pub.publish(pub.prepare(version, expected_revision=0, kind='repair'))
    with opened() as (service, sent, _):
        context = service._context(doc)
        pub = context.memory.publication
        pub.artifacts.verify_version(pub.current().memory)
        assert '處長' in pub.artifacts.read_text(detail.summary_path)
        assert context.reader.read(ref)['segments'][0]['text'] == 'A案由處長核准。'
        with pytest.raises(ValueError, match='reference'):
            pub.artifacts.validate_texts(knowledge=changed_reference(ref, checkpoint='missing'), guide='A')
        assert pub.current().revision == 1
        assert not sent, 'validation and deep source read must not call a model'


@pytest.mark.parametrize('committed', [False, True])
def test_pg_uncertain_repair_can_explicitly_resume_same_operation(pg_service, monkeypatch, committed):
    from analysis_agent.publication import PublicationUncertain
    opened, owned = pg_service
    with opened() as (service, sent, replies):
        doc = service.create_document('修補未知但可恢復')['id']
        owned.append(doc)
        context = service._context(doc)
        pub = context.memory.publication
        version = pub.artifacts.save_memory(knowledge='每月', guide='頻率')
        pub.publish(pub.prepare(version, expected_revision=0, kind='repair'))
        publish = pub.publish
        def fail(request):
            if committed:
                publish(request)
            raise PublicationUncertain('injected lost publication result')
        monkeypatch.setattr(pub, 'publish', fail)
        replies.append(call('repair_memory', edits=[{
            'path': '/memory/knowledge.md', 'old_text': '每月', 'new_text': '每週'}]))
        run = service.submit(doc, 'one', '我剛剛說錯，是每週。')
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'uncertain' and result['can_resume']
        state = context.graph.get_state(context.config, subgraphs=True)
        child = next(t.state for t in state.tasks if t.name == 'analysis')
        operation = child.values['memory_repair_binding']['operation_id']
    with opened() as (service, sent, _):
        assert not sent
        assert service.get_run(doc, run['id'])['can_resume']
        service.resume(doc, run['id'])
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'completed'
        pub = service._context(doc).memory.publication
        assert pub.receipt(operation) is not None and pub.current().revision == 2
        assert pub.artifacts.read_text('/memory/knowledge.md', pub.current().memory) == '每週'
        assert len(sent) == 1  # final answer, not regeneration of the repair call


def test_pg_default_api_lifespan_owns_real_clients_and_configures_provider(pg_service, monkeypatch):
    from fastapi.testclient import TestClient
    from analysis_agent.api import create_app
    from analysis_agent import provider
    _, owned = pg_service
    monkeypatch.setenv('Q019_DATABASE_URL', os.environ['Q019_TEST_DATABASE_URL'])
    monkeypatch.setenv('OPENAI_API_KEY', 'offline')
    monkeypatch.setenv('Q019_REQUEST_TIMEOUT_SECONDS', '13')
    monkeypatch.setenv('Q019_MAX_OUTPUT_TOKENS', '1000')
    monkeypatch.setenv('Q019_COMPACT_THRESHOLD', '32000')
    monkeypatch.setenv('Q019_BACKGROUND_POLL_SECONDS', '60')
    monkeypatch.setenv('Q019_BACKGROUND_MAX_RECOVERIES', '1')
    captured, clients = [], []
    actual_build = provider.build_model
    def bind(**kwargs):
        # Keep the actual configured resource/SDK. Only replace its public HTTP
        # send at the network boundary, so this test cannot call a paid model.
        client = kwargs['http_client']
        clients.append(client)
        def send(request, **unused):
            captured.append(request)
            return httpx.Response(200, json=done(), request=request)
        monkeypatch.setattr(client, 'send', send)
        return actual_build(**kwargs)
    monkeypatch.setattr(provider, 'build_model', bind)
    app = create_app()
    with TestClient(app, base_url='http://127.0.0.1') as web:
        assert not captured and not clients[0].is_closed
        doc = web.post('/documents', json={'title': '實際應用啟動'}).json()['id']
        owned.append(doc)
        response = web.post(f'/documents/{doc}/runs', json={'request_key': 'one', 'text': '我是前端工程師'})
        assert response.status_code == 202
        app.state.service.join(doc)
        assert web.get(f'/documents/{doc}/runs/{response.json()["id"]}').json()['status'] == 'completed'
        payload = json.loads(captured[0].content)
        assert payload['max_output_tokens'] == 1000
        assert payload['context_management'][0]['compact_threshold'] == 32000
        assert payload['reasoning'] == {'effort': 'medium', 'context': 'all_turns'}
        assert captured[0].extensions['timeout']['read'] == 13
    assert clients[0].is_closed and not app.state.service.accepting
