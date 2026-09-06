"""Root -> Agent -> C durability against the dedicated PostgreSQL only."""
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

from analysis_agent.conversation import build_conversation
from analysis_agent.live_memory import MemorySession
from analysis_agent.memory import MemoryArtifacts
from analysis_agent.provider import build_model
from analysis_agent.publication import HeadRow, PublicationStore, ReceiptRow
from analysis_agent.sources import ConversationReader
from test_consolidation import call, done
from test_live_memory import edit


@pytest.mark.parametrize('committed', [False, True])
def test_pg_reopen_parent_child_c_preserves_operation_budget_and_sources(committed):
    dsn = os.environ.get('Q019_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('Dedicated q019_agent_test required; root/child durability NOT verified')
    params = conninfo_to_dict(dsn)
    assert params.get('dbname') == 'q019_agent_test'
    assert params.get('host') in ('localhost', '127.0.0.1')
    assert 1 <= int(params.get('connect_timeout', '0')) <= 10
    dsn = make_conninfo(dsn, options='-c statement_timeout=10000 -c lock_timeout=5000')
    document = 'q019-test-' + str(uuid4())
    config = {'configurable': {'thread_id': document}}
    attempts, payloads, replies = [], [], [call('repair_memory', edits=[edit()])]

    def engine():
        return create_engine(URL.create('postgresql+psycopg'), connect_args=conninfo_to_dict(dsn), hide_parameters=True)

    def respond(request):
        payloads.append(json.loads(request.content))
        assert replies, 'Do not call model before recovering C'
        answer = replies.pop(0)
        answer['id'] = f'resp_{len(payloads)}'
        for i, item in enumerate(answer['output']):
            item['id'] = f'item_{len(payloads)}_{i}'
            if item['type'] == 'function_call':
                item['call_id'] = f'call_{len(payloads)}_{i}'
        return httpx.Response(200, json=answer)

    def compose(model, saver, publication):
        root = build_conversation(model=model, checkpointer=saver, instructions='test')
        reader = ConversationReader(root, document)
        session = MemorySession(publication, reader)
        return build_conversation(model=model, checkpointer=saver, instructions='test',
                                  middleware=[session], tools=session.tools,
                                  max_model_steps=3), reader

    class LostPublish(PublicationStore):
        def publish(self, request):
            attempts.append(request.operation_id)
            if committed:
                super().publish(request)
            raise RuntimeError('injected reply loss')

    first_engine = engine()
    try:
        with PostgresSaver.from_conn_string(dsn) as saver, PostgresStore.from_conn_string(dsn) as store:
            saver.setup()
            store.setup()
            with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
                root = build_conversation(model=model, checkpointer=saver, instructions='test')
                root.update_state(config, {'messages': [HumanMessage('主管核准', id='h0'),
                    AIMessage('主管核准嗎？', id='a0', response_metadata={'status': 'completed'})]}, as_node='analysis')
                source = ConversationReader(root, document).capture('h0', 'a0')
                artifacts = MemoryArtifacts(store, document)
                pub = PublicationStore(first_engine, artifacts)
                pub.setup()
                memory = artifacts.save_memory(knowledge='例外由主管核准。', guide='主管核准')
                pub.publish(pub.prepare(memory, expected_revision=0, kind='consolidation', processed_source=source))
                root, _ = compose(model, saver, LostPublish(first_engine, artifacts))
                with pytest.raises(RuntimeError, match='injected reply loss'):
                    root.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, config, durability='sync')
                snapshot = root.get_state(config, subgraphs=True)
                assert snapshot.next == ('analysis',)
                assert [m.id for m in snapshot.values['messages'] if isinstance(m, HumanMessage)] == ['h0', 'h1']
                child = snapshot.tasks[0].state
                assert child.next == ('tools',)
                assert child.values['thread_model_call_count'] == 1
                assert child.values['thread_tool_call_count']['__all__'] == 1
                assert not child.values['turn_outcome']
        first_engine.dispose()
        second_engine = engine()
        try:
            with PostgresSaver.from_conn_string(dsn) as saver, PostgresStore.from_conn_string(dsn) as store:
                with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                    model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
                    pub = PublicationStore(second_engine, MemoryArtifacts(store, document))
                    root, reader = compose(model, saver, pub)
                    replies.extend([call('read_file', file_path='/memory/knowledge.md'), done()])
                    result = root.invoke(None, config, durability='sync')
                    assert len(payloads) == 3 and not replies
                    assert result['turn_outcome'] == {'input_id': 'h1', 'status': 'completed', 'model_calls': 3, 'tool_calls': 2}
                    assert pub.current().revision == 2 and pub.current().processed_source == source
                    receipts = pub.repair_receipts(after_revision=1, through_revision=2)
                    assert [r.operation_id for r in receipts] == attempts
                    assert [(s['role'], s['text']) for s in reader.read(receipts[0].repair_sources[0])['segments']] == [
                        ('assistant', '主管核准嗎？'), ('user', '改成處長')]
                    assert '處長' in [m for m in result['messages'] if isinstance(m, ToolMessage)][-1].content
                    assert not root.get_state(config).next
                    # A third message has fresh counters, but retains prior C result.
                    replies.append(done())
                    result = root.invoke({'messages': [HumanMessage('下一個案例', id='h2')]}, config, durability='sync')
                    assert result['turn_outcome']['model_calls'] == 1
                    assert result['turn_outcome']['tool_calls'] == 0
                    assert [m.id for m in result['messages'] if isinstance(m, HumanMessage)] == ['h0', 'h1', 'h2']
        finally:
            second_engine.dispose()
    finally:
        first_engine.dispose()
        cleanup = engine()
        try:
            with Session(cleanup) as session, session.begin():
                for row in session.scalars(select(ReceiptRow).where(ReceiptRow.document_id == document)):
                    session.delete(row)
                if row := session.get(HeadRow, document):
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
            cleanup.dispose()
