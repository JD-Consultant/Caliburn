"""C recovery with new provider/Saver/Store/ORM clients, dedicated PostgreSQL."""
import json
import os
from uuid import uuid4

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from analysis_agent.live_memory import MemorySession
from analysis_agent.memory import MemoryArtifacts
from analysis_agent.provider import build_model
from analysis_agent.publication import PublicationStore, HeadRow, ReceiptRow
from analysis_agent.runtime import build_agent
from analysis_agent.sources import ConversationReader
from test_consolidation import call, done
from test_live_memory import edit


@pytest.mark.parametrize('failure', ['before-save', 'before-publish', 'after-commit', 'after-commit-newer-head'])
def test_c_restart_resumes_durable_request_and_refreshes_a(failure):
    dsn = os.environ.get('Q019_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('Dedicated q019_agent_test required; not a durability pass')
    params = conninfo_to_dict(dsn)
    assert params.get('dbname') == 'q019_agent_test'
    assert params.get('host') in ('localhost', '127.0.0.1')
    assert 1 <= int(params.get('connect_timeout', '0')) <= 10
    dsn = make_conninfo(dsn, options='-c statement_timeout=10000 -c lock_timeout=5000')
    def engine():
        return create_engine(URL.create('postgresql+psycopg'), connect_args=conninfo_to_dict(dsn), hide_parameters=True)
    document = 'q019-test-' + str(uuid4())
    config = {'configurable': {'thread_id': document}}
    sent, replies, attempted_ids = [], [call('repair_memory', edits=[edit('不存在')]),
        call('repair_memory', edits=[edit(), edit('主管', '處長', '/memory/guide.md')])], []
    def respond(request):
        sent.append(json.loads(request.content))
        assert replies, 'No new model request allowed before recovering the pending C tool'
        response = replies.pop(0)
        response['id'] = f'resp_{len(sent)}'
        for i, item in enumerate(response['output']):
            item['id'] = f'item_{len(sent)}_{i}'
            if item['type'] == 'function_call':
                item['call_id'] = f'call_{len(sent)}_{i}'
        return httpx.Response(200, json=response)
    class FailedSave(MemoryArtifacts):
        def save_memory(self, **kwargs):
            raise RuntimeError('injected Store unavailable')
    class FailedPublish(PublicationStore):
        def publish(self, request):
            attempted_ids.append(request.operation_id)
            if failure.startswith('after-commit'):
                super().publish(request)
            raise RuntimeError('injected publication reply lost')
    def compose(model, saver, pub):
        reader = ConversationReader(build_agent(model=model, checkpointer=saver, instructions='read only'), document)
        session = MemorySession(pub, reader)
        return build_agent(model=model, checkpointer=saver, instructions='test', middleware=[session], tools=session.tools), reader
    first_engine = engine()
    try:
        with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
            store.setup()
            saver.setup()
            with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
                initial = build_agent(model=model, checkpointer=saver, instructions='test')
                initial.update_state(config, {'messages': [HumanMessage('主管核准。', id='h0'),
                    AIMessage('是主管核准嗎？', id='a0', response_metadata={'status': 'completed'})]}, as_node='model')
                reader = ConversationReader(initial, document)
                source = reader.capture('h0', 'a0')
                artifacts = MemoryArtifacts(store, document)
                pub = PublicationStore(first_engine, artifacts)
                pub.setup()
                base = artifacts.save_memory(knowledge='例外由主管核准。', guide='主管核准')
                pub.publish(pub.prepare(base, expected_revision=0, kind='consolidation', processed_source=source))
                if failure == 'before-save':
                    pub = PublicationStore(first_engine, FailedSave(store, document))
                else:
                    pub = FailedPublish(first_engine, artifacts)
                agent, _ = compose(model, saver, pub)
                with pytest.raises(RuntimeError, match='injected'):
                    agent.invoke({'messages': [HumanMessage('我說錯了，是處長。', id='h1')]}, config, durability='sync')
                assert len(sent) == 2
                snapshot = agent.get_state(config)
                assert snapshot.next == ('tools',)
                assert snapshot.values['memory_read_head']['revision'] == 1
                assert snapshot.values['memory_repair_failures'] == 1
                initial_guide = snapshot.values['memory_initial_guide']
                assert pub.current().revision == (2 if failure.startswith('after-commit') else 1)
        first_engine.dispose()
        second_engine = engine()
        try:
            with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
                with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                    model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
                    pub = PublicationStore(second_engine, MemoryArtifacts(store, document))
                    if failure == 'after-commit-newer-head':
                        newer = pub.artifacts.save_memory(knowledge='例外由處長核准。另有特殊案例。', guide='處長／特殊案例')
                        pub.publish(pub.prepare(newer, expected_revision=2, kind='repair'))
                    expected_revision = 3 if failure == 'after-commit-newer-head' else 2
                    agent, reader = compose(model, saver, pub)
                    replies.extend([call('read_file', file_path='/memory/knowledge.md'), done()])
                    result = agent.invoke(None, config, durability='sync')
                    assert len(sent) == 4 and not replies
                    assert pub.current().revision == expected_revision and pub.current().processed_source == source
                    receipts = pub.repair_receipts(after_revision=1, through_revision=2)
                    assert len(receipts) == 1
                    if attempted_ids:
                        assert receipts[0].operation_id == attempted_ids[0]
                    assert result['memory_read_head']['revision'] == expected_revision
                    assert result['memory_repair_failures'] == 1
                    assert result['memory_initial_guide'] == initial_guide
                    tools = [m for m in result['messages'] if isinstance(m, ToolMessage)]
                    assert json.loads(tools[1].content)['status'] == 'applied'
                    assert '處長' in tools[2].content
                    if expected_revision == 3:
                        assert json.loads(tools[1].content)['applied_head']['revision'] == 2
                        assert '特殊案例' in tools[2].content
                    segments = reader.read(receipts[0].repair_sources[0])['segments']
                    assert [(s['role'], s['text']) for s in segments] == [('assistant', '是主管核准嗎？'), ('user', '我說錯了，是處長。')]
                    assert not agent.get_state(config).next
        finally:
            second_engine.dispose()
    finally:
        first_engine.dispose()
        cleanup_engine = engine()
        try:
            with Session(cleanup_engine) as session, session.begin():
                for row in session.scalars(select(ReceiptRow).where(ReceiptRow.document_id == document)):
                    session.delete(row)
                row = session.get(HeadRow, document)
                if row:
                    session.delete(row)
            with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
                items, offset = [], 0
                while page := store.search(('q019-memory', document), limit=100, offset=offset):
                    items.extend(page)
                    offset += len(page)
                for item in items:
                    store.delete(item.namespace, item.key)
                saver.delete_thread(document)
        finally:
            cleanup_engine.dispose()
