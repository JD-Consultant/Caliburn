"""Current-input provenance across canonical, safely closed technical turns."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from analysis_agent.conversation import ConversationState
from analysis_agent.sources import ConversationReader


def reader_for(messages, boundaries):
    graph = StateGraph(ConversationState)
    graph.add_node('saved', lambda state: {})
    graph.add_edge(START, 'saved')
    graph.add_edge('saved', END)
    compiled = graph.compile(checkpointer=InMemorySaver())
    compiled.update_state({'configurable': {'thread_id': 'source-test'}},
        {'messages': messages, 'closed_turns': boundaries}, as_node='saved')
    return ConversationReader(compiled, 'source-test')


def closed_turn(index, text):
    call_id = f'call{index}'
    return [
        HumanMessage(text, id=f'h{index}'),
        AIMessage('', id=f'a{index}', tool_calls=[{'name': 'read_file', 'args': {}, 'id': call_id}]),
        ToolMessage('tool data, not an employee statement', tool_call_id=call_id, id=f't{index}'),
        AIMessage('本輪未完成', id=f'n{index}', additional_kwargs={'analysis_agent_origin': 'runtime_notice'}),
    ]


@pytest.mark.parametrize('has_question', [True, False])
def test_current_input_keeps_intervening_answers_without_copying_tool_or_notice(has_question):
    messages = [AIMessage('是由主管核准嗎？', id='q0')] if has_question else []
    messages += closed_turn(1, '不是，是處長') + closed_turn(2, 'A案也是')
    messages += [HumanMessage('剛剛說的是A案', id='h3')]
    reader = reader_for(messages, {f'h{i}': {'end_id': f'n{i}', 'status': 'limit'} for i in (1, 2)})
    before = [m.model_dump() for m in reader._snapshot().values['messages']]
    page = reader.read(reader.capture_input('h3'))
    expected = ['是由主管核准嗎？'] if has_question else []
    assert [s['text'] for s in page['segments']] == expected + ['不是，是處長', 'A案也是', '剛剛說的是A案']
    assert 'runtime_notice' in page['omitted_content_types']
    assert [m.model_dump() for m in reader._snapshot().values['messages']] == before


@pytest.mark.parametrize('boundary', [None,
    {'end_id': 'wrong-id', 'status': 'limit'}, {'end_id': 'n1', 'status': 'running'}])
@pytest.mark.parametrize('visible_ai', [False, True])
def test_current_input_cannot_silently_cross_an_unresolved_turn(boundary, visible_ai):
    prior = closed_turn(1, '不是，是處長')
    if visible_ai:
        prior[-1] = AIMessage('未確認是否成功的文字', id='n1')
    reader = reader_for(prior + [HumanMessage('對', id='h2')], {'h1': boundary} if boundary else {})
    with pytest.raises(ValueError, match='safely closed'):
        reader.capture_input('h2')


def test_current_input_stops_at_the_nearest_visible_question():
    prior = closed_turn(1, '舊但無關的未封口內容')
    messages = prior + [HumanMessage('A案', id='h2'),
        AIMessage('A案由谁核准？', id='q2', response_metadata={'status': 'completed'}),
        HumanMessage('處長', id='h3')]
    reader = reader_for(messages, {})
    assert [s['text'] for s in reader.read(reader.capture_input('h3'))['segments']] == ['A案由谁核准？', '處長']


def test_first_input_needs_no_invented_question():
    reader = reader_for([HumanMessage('我開發網站', id='h1')], {})
    assert [s['text'] for s in reader.read(reader.capture_input('h1'))['segments']] == ['我開發網站']


def test_correction_source_keeps_large_context_readable_in_pages():
    reader = reader_for([AIMessage('問' * 3100, id='q0'),
        *closed_turn(1, '不是，是處長'), HumanMessage('對', id='h2')],
        {'h1': {'end_id': 'n1', 'status': 'limit'}})
    reference = reader.capture_input('h2')
    first = reader.read(reference)
    assert first['next_offset'] == 3000
    second = reader.read(reference, first['next_offset'])
    assert ''.join(s['text'] for p in (first, second) for s in p['segments']) == '問' * 3100 + '不是，是處長對'
    assert second['next_offset'] is None
