"""C/A boundary tests: real Agent/Store/Saver/ORM, synthetic provider only."""
import importlib.util
import json
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from analysis_agent.memory import MemoryArtifacts
from analysis_agent.publication import PublicationStore
from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
from analysis_agent.sources import ConversationReader
from test_consolidation import call, done


def session_class():
    assert importlib.util.find_spec('analysis_agent.live_memory'), 'Missing C repair and controlled read-head refresh'
    from analysis_agent.live_memory import MemorySession
    return MemorySession


def edit(old='主管', new='處長', path='/memory/knowledge.md'):
    return {'path': path, 'old_text': old, 'new_text': new}


@pytest.fixture
def h():
    replies, sent = [], []
    def respond(request):
        sent.append(json.loads(request.content))
        assert replies, 'Unexpected extra model call'
        reply = replies.pop(0)
        reply = reply() if callable(reply) else reply
        reply['id'] = f'resp_{len(sent)}'
        for i, item in enumerate(reply['output']):
            item['id'] = f'item_{len(sent)}_{i}'
            if item['type'] == 'function_call':
                item['call_id'] = f'call_{len(sent)}_{i}'
        return httpx.Response(200, json=reply)
    saver, store = InMemorySaver(), InMemoryStore()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        graph = build_agent(model=model, checkpointer=saver, instructions='test')
        config = {'configurable': {'thread_id': 'document-a'}}
        graph.update_state(config, {'messages': [HumanMessage('例外由主管核准。', id='h0'), AIMessage('是由主管核准嗎？', id='a0', response_metadata={'status': 'completed'})]}, as_node='model')
        source = ConversationReader(graph, 'document-a')
        ref = source.capture('h0', 'a0')
        artifacts = MemoryArtifacts(store, 'document-a')
        pub = PublicationStore(engine, artifacts)
        pub.setup()
        base = artifacts.save_memory(knowledge='例外由主管核准。', guide='主管核准：/memory/knowledge.md')
        pub.publish(pub.prepare(base, expected_revision=0, kind='consolidation', processed_source=ref))
        obj = SimpleNamespace(replies=replies, sent=sent, model=model, saver=saver, source=source, artifacts=artifacts, pub=pub, config=config, ref=ref)
        def agent():
            session = session_class()(obj.pub, obj.source)
            return build_agent(model=model, checkpointer=saver, instructions='訪談；不要自行判定矛盾。', middleware=[session], tools=session.tools)
        obj.agent = agent
        yield obj
    engine.dispose()


def knowledge(h):
    return h.artifacts.read_text('/memory/knowledge.md', h.pub.current().memory)


def tool_results(result):
    return [m for m in result['messages'] if isinstance(m, ToolMessage)]


def test_repair_refreshes_reads_without_rewriting_initial_guide(h):
    h.replies.extend([call('read_file', file_path='/memory/knowledge.md'),
        call('repair_memory', edits=[edit(), edit('主管', '處長', '/memory/guide.md')]),
        call('read_file', file_path='/memory/knowledge.md'), done()])
    result = h.agent().invoke({'messages': [HumanMessage('我說錯了，是處長核准。', id='h1')]}, h.config, durability='sync')
    assert knowledge(h) == '例外由處長核准。'
    assert '處長' in tool_results(result)[-1].content
    assert result['memory_read_head']['revision'] == 2
    assert h.pub.current().processed_source == h.ref
    receipt = h.pub.repair_receipts(after_revision=1, through_revision=2)[0]
    segments = h.source.read(receipt.repair_sources[0])['segments']
    assert [(s['role'], s['text']) for s in segments] == [('assistant', '是由主管核准嗎？'), ('user', '我說錯了，是處長核准。')]
    for payload in h.sent:
        system = [i for i in payload['input'] if i.get('role') in ('system', 'developer')]
        assert '主管核准：' in json.dumps(system, ensure_ascii=False)
        assert '處長核准：' not in json.dumps(system, ensure_ascii=False)
        assert payload['parallel_tool_calls'] is False
    assert '處長核准：' in json.dumps(h.sent[-1]['input'], ensure_ascii=False)
    schema = next(t for t in h.sent[0]['tools'] if t['name'] == 'repair_memory')['parameters']
    assert set(schema['properties']) == {'edits'}
    assert 'runtime' not in schema['properties']


@pytest.mark.parametrize('bad', [edit('找不到'), edit(path='/interviews/x/summary.md'), edit(path='/memory/missing.md')])
def test_invalid_edit_has_no_partial_publication_and_returns_error(h, bad):
    h.replies.extend([call('repair_memory', edits=[edit(), bad]), done()])
    result = h.agent().invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    assert h.pub.current().revision == 1 and knowledge(h) == '例外由主管核准。'
    feedback = json.loads(tool_results(result)[-1].content)
    assert feedback['status'] == 'invalid_edit' and feedback['retryable']
    assert 'detail' in feedback and 'read_paths' in feedback


def test_stale_refresh_then_reconsider_uses_new_base(h):
    def background_wins():
        newer = h.artifacts.save_memory(knowledge='一般例外由主管核准；特殊例外由總監核准。', guide='一般／特殊核准')
        h.pub.publish(h.pub.prepare(newer, expected_revision=1, kind='repair', repair_sources=(h.ref,)))
        return call('repair_memory', edits=[edit()])
    h.replies.extend([background_wins, call('read_file', file_path='/memory/knowledge.md'),
        call('repair_memory', edits=[edit('一般例外由主管核准', '一般例外由處長核准')]), done()])
    result = h.agent().invoke({'messages': [HumanMessage('一般例外改成處長', id='h1')]}, h.config, durability='sync')
    feedback = json.loads(tool_results(result)[0].content)
    assert feedback['status'] == 'stale' and feedback['head']['revision'] == 2
    assert '特殊例外由總監核准' in tool_results(result)[1].content
    assert knowledge(h) == '一般例外由處長核准；特殊例外由總監核准。'
    assert h.pub.current().revision == 3


def test_repair_failure_budget_is_not_infinite(h):
    h.replies.extend([call('repair_memory', edits=[edit('不存在')]) for _ in range(3)] + [done()])
    result = h.agent().invoke({'messages': [HumanMessage('修改', id='h1')]}, h.config, durability='sync')
    assert json.loads(tool_results(result)[-1].content)['status'] == 'repair_limit'
    assert h.pub.current().revision == 1


def test_background_publication_does_not_silently_refresh_current_run(h):
    def background_wins():
        newer = h.artifacts.save_memory(knowledge='下一版工作', guide='下一版導覽')
        h.pub.publish(h.pub.prepare(newer, expected_revision=1, kind='repair'))
        return call('read_file', file_path='/memory/knowledge.md')
    h.replies.extend([background_wins, done(), call('read_file', file_path='/memory/knowledge.md'), done()])
    agent = h.agent()
    first = agent.invoke({'messages': [HumanMessage('看目前記憶', id='h1')]}, h.config, durability='sync')
    assert '例外由主管核准' in tool_results(first)[-1].content
    second = agent.invoke({'messages': [HumanMessage('再看', id='h2')]}, h.config, durability='sync')
    assert '下一版工作' in tool_results(second)[-1].content
    assert second['memory_read_head']['revision'] == 2


def test_bad_parallel_response_stops_before_any_mutation(h):
    response = call('repair_memory', edits=[edit()])
    response['output'] += call('read_file', file_path='/memory/knowledge.md')['output']
    h.replies.append(response)
    with pytest.raises(ValueError, match='parallel'):
        h.agent().invoke({'messages': [HumanMessage('修改', id='h1')]}, h.config, durability='sync')
    assert h.pub.current().revision == 1


@pytest.mark.parametrize('edits', [[], [edit()] * 9, [edit(new='x'*12001)], [edit(old='')],
    [edit(new='conversation:not-a-reference')], [edit(new='見 /interviews/missing/summary.md')]])
def test_limits_and_invalid_references_reject_without_publication(h, edits):
    h.replies.extend([call('repair_memory', edits=edits), done()])
    result = h.agent().invoke({'messages': [HumanMessage('更正', id='h1')]}, h.config, durability='sync')
    assert json.loads(tool_results(result)[-1].content)['status'] == 'invalid_edit'
    assert h.pub.current().revision == 1


def test_bad_schema_is_counted_and_new_employee_input_resets_budget(h):
    malformed = {'path': '/memory/knowledge.md', 'new_text': '處長'}
    h.replies.extend([call('repair_memory', edits=[malformed]) for _ in range(3)] + [done(),
        call('repair_memory', edits=[edit()]), done()])
    agent = h.agent()
    first = agent.invoke({'messages': [HumanMessage('修正', id='h1')]}, h.config, durability='sync')
    results = [json.loads(m.content) for m in tool_results(first)]
    assert results[0]['status'] == 'invalid_edit' and results[0]['retryable']
    assert results[1]['status'] == 'invalid_edit' and not results[1]['retryable']
    assert results[2]['status'] == 'repair_limit'
    second = agent.invoke({'messages': [HumanMessage('再修正', id='h2')]}, h.config, durability='sync')
    assert knowledge(h) == '例外由處長核准。'
    assert second['memory_repair_failures'] == 0


def test_ambiguous_exact_match_is_not_replace_all(h):
    newer = h.artifacts.save_memory(knowledge='主管核准；主管備查', guide='核准')
    h.pub.publish(h.pub.prepare(newer, expected_revision=1, kind='repair'))
    h.replies.extend([call('repair_memory', edits=[edit()]), done()])
    result = h.agent().invoke({'messages': [HumanMessage('更正', id='h1')]}, h.config, durability='sync')
    assert json.loads(tool_results(result)[-1].content)['status'] == 'invalid_edit'
    assert knowledge(h) == '主管核准；主管備查'


def test_sequential_edits_see_prior_staged_change(h):
    h.replies.extend([call('repair_memory', edits=[edit(), edit('處長', '總監')]), done()])
    h.agent().invoke({'messages': [HumanMessage('總監才對', id='h1')]}, h.config, durability='sync')
    assert knowledge(h) == '例外由總監核准。'
    assert h.pub.current().revision == 2


def test_no_published_memory_does_not_create_fake_files(h):
    empty = MemoryArtifacts(InMemoryStore(), 'document-a')
    empty_engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    h.pub = PublicationStore(empty_engine, empty)
    h.pub.setup()
    try:
        h.replies.extend([call('read_file', file_path='/memory/knowledge.md'), call('repair_memory', edits=[edit()]), done()])
        result = h.agent().invoke({'messages': [HumanMessage('更正', id='h1')]}, h.config, durability='sync')
        assert json.loads(tool_results(result)[-1].content)['status'] == 'no_memory'
        assert h.pub.current() is None
        assert empty.store.search(('q019-memory', 'document-a')) == []
    finally:
        empty_engine.dispose()


def test_scope_denied_before_any_provider_or_memory_action(h):
    with pytest.raises(ValueError, match='another document'):
        h.agent().invoke({'messages': [HumanMessage('更正', id='x1')]}, {'configurable': {'thread_id': 'other'}})
    assert not h.sent
    assert h.pub.current().revision == 1


def test_source_input_must_be_saved_and_current(h):
    with pytest.raises(ValueError, match='latest saved'):
        h.source.capture_input('invented')
