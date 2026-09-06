"""C/A boundary tests: real Agent/Store/Saver/ORM, synthetic provider only."""
import importlib.util
import json
from dataclasses import asdict
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from analysis_agent.memory import MemoryArtifacts
from analysis_agent.conversation import build_conversation
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
        artifacts = MemoryArtifacts(store, 'document-a', source=source)
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


def system_wire(payload):
    return [item for item in payload['input'] if item.get('role') in ('system', 'developer')]


@pytest.mark.parametrize('entrypoint', ['conversation', 'agent'])
def test_new_input_guide_supersedes_historical_c_feedback_on_sdk_wire(h, entrypoint):
    session = session_class()(h.pub, h.source)
    factory = build_conversation if entrypoint == 'conversation' else build_agent
    graph = factory(model=h.model, checkpointer=h.saver, instructions='訪談',
                    middleware=[session], tools=session.tools)
    # The source reader must observe the canonical root, not a child projection.
    h.source.graph = graph
    h.replies.extend([call('read_file', file_path='/memory/knowledge.md'),
        call('repair_memory', edits=[edit(), edit('主管', '處長', '/memory/guide.md')]),
        call('read_file', file_path='/memory/knowledge.md'), done()])
    first = graph.invoke({'messages': [HumanMessage('更正為處長核准。', id='h1')]},
                         h.config, durability='sync')
    old_result = tool_results(first)[1].model_dump()
    old_feedback = json.loads(old_result['content'])
    assert old_feedback['head']['revision'] == 2
    assert '處長' in tool_results(first)[-1].content
    # Synthetic B publication between inputs; no B model or scheduler involved.
    newer = h.artifacts.save_memory(knowledge='例外由總監核准。', guide='總監核准：/memory/knowledge.md')
    h.pub.publish(h.pub.prepare(newer, expected_revision=2, kind='consolidation',
        processed_source=h.source.capture('h1', first['messages'][-1].id)))
    h.replies.extend([call('read_file', file_path='/memory/knowledge.md'), done()])
    second = graph.invoke({'messages': [HumanMessage('再看目前核准方式。', id='h2')]},
                          h.config, durability='sync')
    assert h.pub.current().revision == 3
    assert '總監' in tool_results(second)[-1].content
    assert next(m.model_dump() for m in second['messages'] if m.id == old_result['id']) == old_result
    historical_wire = next(item for item in h.sent[4]['input']
        if item.get('type') == 'function_call_output' and item['call_id'] == old_result['tool_call_id'])
    assert historical_wire['output'] == old_result['content']
    assert len(h.sent) == 6 and not h.replies
    if entrypoint == 'conversation':
        assert first['turn_outcome']['model_calls'] == 4
        assert second['turn_outcome']['model_calls'] == 2
    first_system, second_system = system_wire(h.sent[0]), system_wire(h.sent[4])
    assert all(system_wire(p) == first_system for p in h.sent[:4])
    assert system_wire(h.sent[5]) == second_system
    first_text = json.dumps(first_system, ensure_ascii=False)
    second_text = json.dumps(second_system, ensure_ascii=False)
    assert 'Initial guide publication revision: 1' in first_text
    assert 'Initial guide publication revision: 3' in second_text
    assert '總監核准：' in second_text and '處長核准：' not in second_text
    assert old_feedback['source_reference'] in first_text
    assert old_feedback['source_reference'] not in second_text
    assert 'Only C tool feedback whose source_reference matches the Current input reference' in second_text
    assert 'Previous-input C feedback is historical and cannot override this input' in second_text
    assert all(p['tools'] == h.sent[0]['tools'] for p in h.sent)
    schema = next(t for t in h.sent[0]['tools'] if t['name'] == 'repair_memory')['parameters']
    assert set(schema['properties']) == {'edits'}
    assert set(schema['properties']['edits']['items']['properties']) == {'path', 'old_text', 'new_text'}


def test_old_partial_state_missing_initial_revision_stays_unknown_on_resume(h):
    agent = h.agent()
    agent.update_state(h.config, {'messages': [HumanMessage('繼續查核准方式。', id='h1')]}, as_node='model')
    reference = h.source.capture_input('h1')
    repaired = h.artifacts.save_memory(knowledge='例外由處長核准。', guide='處長核准')
    head = h.pub.publish(h.pub.prepare(repaired, expected_revision=1, kind='repair', repair_sources=(reference,)))
    # Old checkpoint: fixed v1 guide, refreshed v2 read head, no revision label.
    agent.update_state(h.config, {'memory_turn_id': 'h1',
        'memory_initial_guide': '主管核准：/memory/knowledge.md',
        'memory_read_head': asdict(head), 'memory_source_reference': reference,
        'memory_repair_failures': 0, 'memory_repair_binding': None},
        as_node='MemorySession.before_agent')
    newer = h.artifacts.save_memory(knowledge='例外由總監核准。', guide='總監核准')
    h.pub.publish(h.pub.prepare(newer, expected_revision=2, kind='consolidation', processed_source=h.ref))
    h.replies.extend([call('read_file', file_path='/memory/knowledge.md'), done()])
    result = h.agent().invoke(None, h.config, durability='sync')
    assert result['memory_read_head']['revision'] == 2
    assert '處長' in tool_results(result)[-1].content
    assert system_wire(h.sent[0]) == system_wire(h.sent[1])
    text = json.dumps(system_wire(h.sent[0]), ensure_ascii=False)
    assert '主管核准：' in text and '總監核准' not in text
    assert 'Initial guide publication revision: unknown' in text
    assert 'Initial guide publication revision: 2' not in text
    assert 'Initial guide publication revision: 3' not in text
    assert len(h.sent) == 2 and not h.replies


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
    assert feedback['source_reference'] == result['memory_source_reference']
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
