"""Per-input durable scope with the real Agent loop; only HTTP is synthetic."""
import json

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from analysis_agent.provider import build_model
from analysis_agent.conversation import build_conversation
from test_consolidation import call, done
from test_live_memory import h, edit, knowledge, tool_results


def factory(**kwargs):
    return build_conversation(**kwargs)


def test_resume_keeps_budget_new_employee_input_gets_new_budget():
    payloads, calls = [], []
    saver = InMemorySaver()
    config = {'configurable': {'thread_id': 'per-input'}}

    @tool
    def read_case(case_name: str) -> str:
        """Read one stored case."""
        calls.append(case_name)
        if len(calls) == 1:
            raise RuntimeError('injected read interruption')
        return 'A 是接案網站'

    def respond(request):
        payloads.append(json.loads(request.content))
        answer = call('read_case', case_name='A')
        answer['id'] = f'resp_{len(payloads)}'
        answer['output'][0]['id'] = f'fc_{len(payloads)}'
        answer['output'][0]['call_id'] = f'call_{len(payloads)}'
        return httpx.Response(200, json=answer)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        def compose():
            return factory(model=model, checkpointer=saver, instructions='test',
                           tools=[read_case], max_model_steps=2, max_tool_calls=8)
        graph = compose()
        with pytest.raises(RuntimeError, match='injected'):
            graph.invoke({'messages': [HumanMessage('A 案例', id='h1')]}, config, durability='sync')
        assert len(payloads) == 1
        assert graph.get_state(config, subgraphs=True).next
        graph = compose()
        first = graph.invoke(None, config, durability='sync')
        assert len(payloads) == 2, 'resume must not reset the durable input budget'
        assert len(calls) == 3  # one failed read, replay it, then the second read
        second = graph.invoke({'messages': [HumanMessage('B 案例', id='h2')]}, config, durability='sync')
        assert len(payloads) == 4, 'a new employee input must get a new budget'
        assert [m.id for m in second['messages'] if isinstance(m, HumanMessage)] == ['h1', 'h2']
        assert first['turn_outcome']['status'] == second['turn_outcome']['status'] == 'limit'
        assert second['turn_outcome']['model_calls'] == 2
        assert not second['messages'][-1].response_metadata.get('status')
        assert 'thread_model_call_count' not in second
        assert all(isinstance(m, ToolMessage) for m in second['messages'] if m.type == 'tool')


def test_native_items_round_trip_through_root_and_child(monkeypatch):
    import test_agent_runtime
    monkeypatch.setattr(test_agent_runtime, 'build_agent', build_conversation)
    test_agent_runtime.test_agent_keeps_canonical_tool_history_but_compacts_only_next_request()


def compose_memory(h, **limits):
    from analysis_agent.live_memory import MemorySession
    session = MemorySession(h.pub, h.source)
    return build_conversation(model=h.model, checkpointer=h.saver, instructions='test',
                              middleware=[session], tools=session.tools, **limits)


def test_calibrated_normal_deep_read_correction_and_final_answer(h):
    # Seven legitimate tool uses: search, knowledge, detail, original Q/A,
    # a failed precise edit, corrected edit, and verify updated content.
    extraction = h.artifacts.save_extraction(
        summary='主管核准之案例詳記', candidates='主管核准', slug='approval',
        source_reference=h.ref)
    h.replies.extend([
        call('grep', pattern='主管', path='/memory/knowledge.md'),
        call('read_file', file_path='/memory/knowledge.md'),
        call('read_file', file_path=extraction.summary_path),
        call('read_conversation', reference=h.ref),
        call('repair_memory', edits=[edit('不存在')]),
        call('repair_memory', edits=[edit()]),
        call('read_file', file_path='/memory/knowledge.md'), done(),
    ])
    graph = compose_memory(h)
    result = graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    assert result['turn_outcome']['status'] == 'completed'
    assert result['turn_outcome']['model_calls'] == 8
    assert result['turn_outcome']['tool_calls'] == 7
    assert not h.replies
    assert knowledge(h) == '例外由處長核准。'
    assert '處長' in tool_results(result)[-1].content
    receipts = h.pub.repair_receipts(after_revision=1, through_revision=2)
    assert len(receipts) == 1
    assert [s['role'] for s in h.source.read(receipts[0].repair_sources[0])['segments']] == ['assistant', 'user']
    assert graph.get_state(h.config).next == ()


def test_tool_limit_pairs_unexecuted_call_without_forging_success(h):
    h.replies.extend([call('read_file', file_path='/memory/knowledge.md'),
                     call('repair_memory', edits=[edit()])])
    graph = compose_memory(h, max_tool_calls=1)
    result = graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    assert result['turn_outcome'] == {'input_id': 'h1', 'status': 'limit', 'model_calls': 2, 'tool_calls': 1}
    assert h.pub.current().revision == 1
    assert tool_results(result)[-1].status == 'error'
    assert tool_results(result)[-1].tool_call_id == result['messages'][-3].tool_calls[0]['id']
    assert not result['messages'][-1].response_metadata.get('status')


@pytest.mark.parametrize('status', ['incomplete', 'failed'])
def test_invalid_provider_completion_stays_pending_before_tools(h, status):
    response = call('repair_memory', edits=[edit()])
    response['status'] = status
    h.replies.append(response)
    graph = compose_memory(h)
    with pytest.raises(ValueError, match='Incomplete model'):
        graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    snapshot = graph.get_state(h.config, subgraphs=True)
    assert snapshot.next == ('analysis',)
    assert h.pub.current().revision == 1
    assert snapshot.tasks[0].state.next
    assert snapshot.tasks[0].state.values['messages'][-1].response_metadata['status'] == status
    assert not snapshot.values.get('turn_outcome')
    assert len(h.sent) == 1


def test_unknown_publication_result_resumes_same_operation_without_new_model(h, monkeypatch):
    h.replies.extend([call('repair_memory', edits=[edit()])])
    publish = h.pub.publish
    attempted = []
    def lost_reply(request):
        attempted.append(request.operation_id)
        publish(request)
        raise RuntimeError('injected lost receipt reply')
    monkeypatch.setattr(h.pub, 'publish', lost_reply)
    graph = compose_memory(h)
    with pytest.raises(RuntimeError, match='lost receipt'):
        graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    snapshot = graph.get_state(h.config, subgraphs=True)
    child = snapshot.tasks[0].state
    assert child.next == ('tools',)
    assert not child.values['turn_outcome']
    assert child.values['memory_read_head']['revision'] == 1
    assert h.pub.current().revision == 2
    assert len(h.sent) == 1
    monkeypatch.setattr(h.pub, 'publish', publish)
    h.replies.extend([call('read_file', file_path='/memory/knowledge.md'), done()])
    result = compose_memory(h).invoke(None, h.config, durability='sync')
    assert result['turn_outcome'] == {'input_id': 'h1', 'status': 'completed', 'model_calls': 3, 'tool_calls': 2}
    assert len(h.sent) == 3
    receipts = h.pub.repair_receipts(after_revision=1, through_revision=2)
    assert [r.operation_id for r in receipts] == attempted
    assert '處長' in tool_results(result)[-1].content
    assert [m.id for m in result['messages'] if isinstance(m, HumanMessage)] == ['h0', 'h1']


def test_known_tool_schema_error_goes_back_to_model(h):
    h.replies.extend([call('repair_memory', edits=[{'path': '/memory/knowledge.md'}]),
                     call('repair_memory', edits=[edit()]), done()])
    result = compose_memory(h).invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    feedback = json.loads(tool_results(result)[0].content)
    assert feedback['status'] == 'invalid_edit' and feedback['retryable']
    assert 'old_text' in feedback['detail']
    assert result['turn_outcome']['status'] == 'completed'
    assert h.pub.current().revision == 2


def test_stale_c_refresh_is_not_implicit_background_context_change(h):
    def intervening_publication():
        newer = h.artifacts.save_memory(knowledge='主管核准；另有特殊例外', guide='主管／特殊例外')
        h.pub.publish(h.pub.prepare(newer, expected_revision=1, kind='repair', repair_sources=(h.ref,)))
        return call('repair_memory', edits=[edit()])
    h.replies.extend([intervening_publication, call('read_file', file_path='/memory/knowledge.md'),
                     call('repair_memory', edits=[edit()]), done()])
    result = compose_memory(h).invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    assert json.loads(tool_results(result)[0].content)['status'] == 'stale'
    assert '特殊例外' in tool_results(result)[1].content
    assert knowledge(h) == '處長核准；另有特殊例外'
    for payload in h.sent:
        system = [i for i in payload['input'] if i.get('role') in ('system', 'developer')]
        assert '主管核准：' in json.dumps(system, ensure_ascii=False)
        assert '主管／特殊例外' not in json.dumps(system, ensure_ascii=False)


def test_new_document_still_has_no_other_conversation(monkeypatch):
    import test_agent_runtime
    monkeypatch.setattr(test_agent_runtime, 'build_agent', build_conversation)
    test_agent_runtime.test_new_document_cannot_receive_another_documents_conversation()


@pytest.mark.parametrize('status, attempts', [(400, 1), (401, 1), (429, 3), (503, 3)])
def test_root_child_does_not_add_transport_retries(status, attempts, monkeypatch):
    import time
    from openai import APIStatusError
    from test_provider_recovery import status_error
    requests = []
    monkeypatch.setattr(time, 'sleep', lambda _: None)
    def respond(request):
        requests.append(request)
        return status_error(status)
    with httpx.Client(transport=httpx.MockTransport(respond), trust_env=False) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        graph = build_conversation(model=model, checkpointer=InMemorySaver(), instructions='test')
        config = {'configurable': {'thread_id': 'transport-root'}}
        with pytest.raises(APIStatusError):
            graph.invoke({'messages': [HumanMessage('我做網站', id='h1')]}, config, durability='sync')
        assert len(requests) == attempts
        state = graph.get_state(config, subgraphs=True)
        assert state.next == ('analysis',)
        assert not state.tasks[0].state.values['turn_outcome']
        assert [m.id for m in state.values['messages']] == ['h1']


def test_last_admitted_tool_still_leaves_room_for_final_answer(h):
    h.replies.extend([call('read_file', file_path='/memory/knowledge.md') for _ in range(8)] + [done()])
    result = compose_memory(h).invoke({'messages': [HumanMessage('離線額度邊界', id='h1')]}, h.config, durability='sync')
    assert result['turn_outcome'] == {'input_id': 'h1', 'status': 'completed', 'model_calls': 9, 'tool_calls': 8}
    assert not h.replies


def test_limit_then_short_correction_keeps_real_question_not_technical_source(h):
    from test_native_continuity import assistant_text
    answer = call('read_file', file_path='/memory/knowledge.md')
    answer['output'].insert(0, assistant_text('主管核准嗎？', phase='commentary'))
    h.replies.append(answer)
    graph = compose_memory(h, max_model_steps=1)
    graph.invoke({'messages': [HumanMessage('談核准工作', id='h1')]}, h.config, durability='sync')
    h.replies.append(call('repair_memory', edits=[edit()]))
    result = graph.invoke({'messages': [HumanMessage('不是，是處長', id='h2')]}, h.config, durability='sync')
    receipt = h.pub.repair_receipts(after_revision=1, through_revision=2)[0]
    source = h.source.read(receipt.repair_sources[0])
    assert [(s['role'], s['text']) for s in source['segments']] == [
        ('assistant', '主管核准嗎？'), ('user', '不是，是處長')]
    # Runtime notices remain canonical; exclusion is only the source projection.
    assert any('Model call limits exceeded' in m.text for m in result['messages'])
    assert 'runtime_notice' in source['omitted_content_types']


@pytest.mark.parametrize('corrected', [True, False])
def test_malformed_tool_json_returns_identity_paired_error_with_bounded_correction(h, corrected):
    broken = call('repair_memory', edits=[])
    broken['output'][0]['arguments'] = '{broken'
    import copy
    h.replies.extend([copy.deepcopy(broken),
                     call('repair_memory', edits=[edit()]) if corrected else copy.deepcopy(broken)])
    if corrected:
        h.replies.append(done())
    graph = compose_memory(h)
    result = graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    assert len(h.sent) == (3 if corrected else 2)
    assert result['turn_outcome']['model_calls'] == (3 if corrected else 2)
    assert result['turn_outcome']['status'] == ('completed' if corrected else 'tool_error')
    assert h.pub.current().revision == (2 if corrected else 1)
    assert not graph.get_state(h.config).next
    first_call = next(m for m in result['messages'] if isinstance(m, AIMessage) and m.invalid_tool_calls)
    assert first_call.invalid_tool_calls[0]['args'] == '{broken'
    error = tool_results(result)[0]
    assert error.tool_call_id == first_call.invalid_tool_calls[0]['id'] and error.status == 'error'
    assert 'JSON' in error.content and 'not executed' in error.content
    wire = h.sent[1]['input']
    assert next(i for i in wire if i.get('type') == 'function_call')['arguments'] == '{broken'
    assert next(i for i in wire if i.get('type') == 'function_call_output')['call_id'] == error.tool_call_id


def test_malformed_tool_correction_budget_survives_model_interruption(h):
    import copy
    from langchain.agents.middleware import wrap_model_call
    from analysis_agent.live_memory import MemorySession
    broken = call('repair_memory', edits=[])
    broken['output'][0]['arguments'] = '{broken'
    h.replies.extend([copy.deepcopy(broken), copy.deepcopy(broken)])
    entered = []
    @wrap_model_call
    def interrupt_second_model(request, handler):
        entered.append(True)
        if len(entered) == 2:
            raise RuntimeError('injected second model interruption')
        return handler(request)
    session = MemorySession(h.pub, h.source)
    graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test',
                              middleware=[session, interrupt_second_model], tools=session.tools)
    with pytest.raises(RuntimeError, match='second model interruption'):
        graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    snapshot = graph.get_state(h.config, subgraphs=True)
    assert snapshot.tasks[0].state.values['invalid_json_count'] == 1
    assert len(h.sent) == 1
    result = graph.invoke(None, h.config, durability='sync')
    assert result['turn_outcome']['status'] == 'tool_error'
    assert result['turn_outcome']['model_calls'] == 2 and len(h.sent) == 2
    assert h.pub.current().revision == 1


@pytest.mark.parametrize('terminal', ['completed', 'limit', 'configuration_error', 'cancelled'])
def test_terminal_source_preserves_employee_and_question_with_runtime_boundary(h, terminal):
    import analysis_agent.conversation as conversation
    from analysis_agent.sources import ConversationReader
    graph = compose_memory(h, max_model_steps=1)
    if terminal in ('completed', 'limit'):
        h.replies.append(done() if terminal == 'completed' else call('read_file', file_path='/memory/knowledge.md'))
        result = graph.invoke({'messages': [HumanMessage('不是，是處長', id='h1')]}, h.config, durability='sync')
    else:
        from langchain.agents.middleware import wrap_model_call
        from analysis_agent.live_memory import MemorySession
        @wrap_model_call
        def fail(request, handler):
            raise RuntimeError('injected configuration failure')
        session = MemorySession(h.pub, h.source)
        graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test',
                                   middleware=[session, fail], tools=session.tools)
        with pytest.raises(RuntimeError):
            graph.invoke({'messages': [HumanMessage('不是，是處長', id='h1')]}, h.config, durability='sync')
        assert hasattr(conversation, 'close_turn'), 'Missing known-quiescent safe closure'
        result = conversation.close_turn(graph, h.config, reason=terminal, quiescent=True)
    reader = ConversationReader(graph, 'document-a')
    ref = reader.capture('h1', result['messages'][-1].id)
    windows = reader.extraction_windows(ref)
    page = reader.read(windows[0]['source_reference'])
    assert page['turns'] == [{'input_id': 'h1', 'status': terminal, 'answer_succeeded': terminal == 'completed'}]
    assert page['segments'][0]['text'] == '不是，是處長'
    context = reader.read(windows[0]['context_reference'])
    assert context['segments'][-1]['text'] == '是由主管核准嗎？'
    assert not graph.get_state(h.config).next
    assert [m.id for m in result['messages'] if isinstance(m, HumanMessage)] == ['h0', 'h1']


@pytest.mark.parametrize('committed', [False, True])
def test_nested_uncertain_publication_has_runtime_operation_binding(h, monkeypatch, committed):
    # T2-B01: C stays tool-hidden, but public persisted state must identify its
    # exact operation without the caller having the fault injector's variables.
    h.replies.append(call('repair_memory', edits=[edit()]))
    publish = h.pub.publish
    operations = []
    def unknown(request):
        operations.append(request.operation_id)
        if committed:
            publish(request)
        raise RuntimeError('injected unknown commit result')
    monkeypatch.setattr(h.pub, 'publish', unknown)
    graph = compose_memory(h)
    with pytest.raises(RuntimeError, match='unknown commit'):
        graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    child = graph.get_state(h.config, subgraphs=True).tasks[0].state
    assert child.next == ('tools',)
    assert child.tasks[0].state is None
    assert 'request' not in child.values
    assert not tool_results(child.values)
    assert [name for name, _ in graph.get_subgraphs(recurse=True)] == ['analysis']
    binding = child.values.get('memory_repair_binding')
    assert binding, 'Missing durable tool-call to C operation binding'
    assert binding['operation_id'] == operations[0]
    assert binding['call_id'] == child.values['messages'][-1].tool_calls[0]['id']
    assert (h.pub.receipt(operations[0]) is not None) is committed
    assert h.pub.current().revision == (2 if committed else 1)
    assert [m.id for m in graph.get_state(h.config).values['messages'] if isinstance(m, HumanMessage)] == ['h0', 'h1']
    assert len(h.sent) == 1


@pytest.mark.parametrize('committed', [False, True])
def test_cancel_reconciles_exact_c_without_publishing_or_model_calls(h, monkeypatch, committed):
    from analysis_agent.live_memory import MemorySession
    import analysis_agent.conversation as conversation
    from analysis_agent.publication import PublicationUncertain
    h.replies.append(call('repair_memory', edits=[edit()]))
    original = h.pub.publish
    def lose_reply(request):
        if committed:
            original(request)
        raise PublicationUncertain('injected unknown commit')
    monkeypatch.setattr(h.pub, 'publish', lose_reply)
    session = MemorySession(h.pub, h.source)
    graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test',
                               middleware=[session], tools=session.tools)
    with pytest.raises(PublicationUncertain):
        graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    before = graph.get_state(h.config, subgraphs=True)
    raw = [m.model_dump() for m in before.tasks[0].state.values['messages']]
    assert hasattr(conversation, 'close_turn'), 'Missing safe closure'
    if not committed:
        with pytest.raises(PublicationUncertain):
            conversation.close_turn(graph, h.config, reason='cancelled', quiescent=True, memory_session=session)
        assert graph.get_state(h.config).config == before.config
        assert not tool_results(graph.get_state(h.config, subgraphs=True).tasks[0].state.values)
        assert h.pub.current().revision == 1
    else:
        # A later B/C publication must not be reverted to the recovered receipt.
        newer = h.artifacts.save_memory(knowledge='最新工作內容', guide='最新導覽')
        original(h.pub.prepare(newer, expected_revision=2, kind='repair'))
        # Reconstructed runtime uses only durable binding + real publication.
        session = MemorySession(h.pub, h.source)
        result = conversation.close_turn(graph, h.config, reason='cancelled', quiescent=True, memory_session=session)
        feedback = json.loads(tool_results(result)[-1].content)
        assert feedback['status'] == 'applied'
        assert feedback['applied_head']['revision'] == 2 and feedback['head']['revision'] == 3
        assert result['messages'][:len(raw)] == before.tasks[0].state.values['messages']
        assert [m.model_dump() for m in result['messages'][:len(raw)]] == raw
        assert h.pub.current().revision == 3 and knowledge(h) == '最新工作內容'
        assert result['turn_outcome']['status'] == 'cancelled'
        assert not graph.get_state(h.config).next
        assert conversation.close_turn(graph, h.config, reason='cancelled', quiescent=True) == result
    assert len(h.sent) == 1


def test_cancel_before_tools_pairs_not_executed_preserving_raw_and_new_input(h):
    from langchain.agents.middleware import AgentMiddleware
    from analysis_agent.live_memory import MemorySession
    import analysis_agent.conversation as conversation
    class StopBeforeTools(AgentMiddleware):
        def after_model(self, state, runtime):
            raise RuntimeError('injected before tools')
    response = call('repair_memory', edits=[edit()])
    response['output'].insert(0, {'type': 'reasoning', 'id': 'rs_cancel',
        'encrypted_content': 'opaque-cancel', 'summary': []})
    h.replies.append(response)
    session = MemorySession(h.pub, h.source)
    graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test',
        middleware=[StopBeforeTools(), session], tools=session.tools)
    with pytest.raises(RuntimeError, match='before tools'):
        graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    before = graph.get_state(h.config, subgraphs=True).tasks[0].state.values['messages']
    assert hasattr(conversation, 'close_turn'), 'Missing safe closure'
    with pytest.raises(ValueError, match='quiescent'):
        conversation.close_turn(graph, h.config, reason='cancelled', quiescent=False)
    result = conversation.close_turn(graph, h.config, reason='cancelled', quiescent=True, memory_session=session)
    paired = tool_results(result)[-1]
    assert paired.status == 'error' and 'not executed' in paired.content
    assert paired.tool_call_id == before[-1].tool_calls[0]['id']
    assert [m.model_dump() for m in result['messages'][:len(before)]] == [m.model_dump() for m in before]
    assert h.pub.current().revision == 1 and len(h.sent) == 1


def test_new_input_requires_safe_abandonment_and_never_reappends_old_human(h):
    from langchain.agents.middleware import wrap_model_call
    import analysis_agent.conversation as conversation
    @wrap_model_call
    def fail(request, handler):
        raise RuntimeError('configuration broken')
    graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test', middleware=[fail])
    with pytest.raises(RuntimeError):
        graph.invoke({'messages': [HumanMessage('保留這個案例', id='h1')]}, h.config, durability='sync')
    assert hasattr(conversation, 'send_input'), 'Missing close-before-new-input entry'
    with pytest.raises(ValueError, match='pending'):
        conversation.send_input(graph, h.config, HumanMessage('新案例', id='h2'))
    graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test')
    h.replies.append(done())
    result = conversation.send_input(graph, h.config, HumanMessage('新案例', id='h2'), abandon_pending=True, quiescent=True)
    assert [m.id for m in result['messages'] if isinstance(m, HumanMessage)] == ['h0', 'h1', 'h2']
    from analysis_agent.sources import ConversationReader
    reader = ConversationReader(graph, 'document-a')
    page = reader.read(reader.capture('h1', result['messages'][-1].id))
    assert page['turns'] == [
        {'input_id': 'h1', 'status': 'cancelled', 'answer_succeeded': False},
        {'input_id': 'h2', 'status': 'completed', 'answer_succeeded': True}]
    assert result['turn_outcome']['model_calls'] == 1 and len(h.sent) == 1


@pytest.mark.parametrize('committed_c', [False, True])
def test_close_checkpoint_reply_loss_leaves_terminal_child_not_runnable_work(h, monkeypatch, committed_c):
    from langchain.agents.middleware import wrap_model_call
    from analysis_agent.live_memory import MemorySession
    from analysis_agent.conversation import close_turn
    @wrap_model_call
    def fail_after_c(request, handler):
        if not committed_c or any(isinstance(m, ToolMessage) for m in request.messages):
            raise RuntimeError('model configuration unavailable')
        return handler(request)
    session = MemorySession(h.pub, h.source)
    graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test',
        middleware=[session, fail_after_c], tools=session.tools)
    if committed_c:
        h.replies.append(call('repair_memory', edits=[edit()]))
    with pytest.raises(RuntimeError, match='configuration unavailable'):
        graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    update = graph.update_state
    def fail_root_update(config, values, **kwargs):
        if kwargs.get('as_node') == 'analysis':
            raise RuntimeError('root closure unavailable')
        return update(config, values, **kwargs)
    monkeypatch.setattr(graph, 'update_state', fail_root_update)
    with pytest.raises(RuntimeError, match='root closure unavailable'):
        close_turn(graph, h.config, reason='cancelled', quiescent=True, memory_session=session)
    pending = graph.get_state(h.config, subgraphs=True)
    assert pending.tasks[0].state.next == (), 'Saved closure must not leave model/tools runnable'
    assert pending.tasks[0].state.values['turn_outcome']['status'] == 'cancelled'
    before = [m.model_dump() for m in pending.tasks[0].state.values['messages']]
    monkeypatch.setattr(graph, 'update_state', update)
    result = close_turn(graph, h.config, reason='configuration_error', quiescent=True, memory_session=session)
    assert result['turn_outcome']['status'] == 'cancelled', 'Do not rewrite a saved terminal result'
    assert [m.model_dump() for m in result['messages']] == before
    assert h.pub.current().revision == (2 if committed_c else 1)
    assert len(h.sent) == int(committed_c)
    assert not graph.get_state(h.config).next


@pytest.mark.parametrize('stage', ['incomplete', 'unknown_read', 'receipt_unavailable'])
def test_closure_never_forges_unknown_tool_results_or_provider_metadata(h, monkeypatch, stage):
    from analysis_agent.conversation import close_turn
    from analysis_agent.live_memory import MemorySession
    from analysis_agent.publication import PublicationUncertain
    from langchain.agents.middleware import wrap_tool_call
    @wrap_tool_call
    def interrupted_read(request, handler):
        if stage == 'unknown_read':
            raise RuntimeError('read outcome unknown')
        return handler(request)
    session = MemorySession(h.pub, h.source)
    graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test',
        middleware=[session, interrupted_read], tools=session.tools)
    if stage == 'incomplete':
        answer = done()
        answer['status'] = 'incomplete'
        answer['incomplete_details'] = {'reason': 'max_output_tokens'}
    elif stage == 'unknown_read':
        answer = call('read_file', file_path='/memory/knowledge.md')
    else:
        answer = call('repair_memory', edits=[edit()])
        original = h.pub.publish
        def lost_reply(request):
            original(request)
            raise PublicationUncertain('lost reply')
        monkeypatch.setattr(h.pub, 'publish', lost_reply)
    h.replies.append(answer)
    with pytest.raises((ValueError, RuntimeError, PublicationUncertain)):
        graph.invoke({'messages': [HumanMessage('保留工作', id='h1')]}, h.config, durability='sync')
    before = graph.get_state(h.config, subgraphs=True)
    if stage == 'incomplete':
        raw = before.tasks[0].state.values['messages'][-1].model_dump()
        result = close_turn(graph, h.config, reason='cancelled', quiescent=True, memory_session=session)
        assert result['messages'][-2].model_dump() == raw
        assert result['messages'][-2].response_metadata['status'] == 'incomplete'
    else:
        if stage == 'receipt_unavailable':
            from sqlalchemy.exc import OperationalError
            def unavailable(operation_id):
                raise OperationalError('injected offline', {}, Exception('database unavailable'))
            monkeypatch.setattr(h.pub, 'receipt', unavailable)
        with pytest.raises(PublicationUncertain):
            close_turn(graph, h.config, reason='cancelled', quiescent=True, memory_session=session)
        assert graph.get_state(h.config).config == before.config
        assert not tool_results(graph.get_state(h.config, subgraphs=True).tasks[0].state.values)
    assert len(h.sent) == 1


def test_closure_rejects_historical_checkpoint_and_does_not_fork_cancellation(h):
    from langchain.agents.middleware import wrap_model_call
    from analysis_agent.conversation import close_turn, send_input
    @wrap_model_call
    def fail(request, handler):
        raise RuntimeError('pending model')
    graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test', middleware=[fail])
    with pytest.raises(RuntimeError):
        graph.invoke({'messages': [HumanMessage('保留原話', id='h1')]}, h.config, durability='sync')
    historical = graph.get_state(h.config).config
    with pytest.raises(ValueError, match='latest'):
        close_turn(graph, historical, reason='cancelled', quiescent=True)
    with pytest.raises(ValueError, match='latest'):
        send_input(graph, historical, HumanMessage('新案例', id='h2'), abandon_pending=True, quiescent=True)
    assert graph.get_state(h.config).config == historical


def test_uncertain_c_blocks_b1_and_new_input_before_any_new_work(h, monkeypatch):
    from analysis_agent.conversation import send_input
    from analysis_agent.live_memory import MemorySession
    from analysis_agent.publication import PublicationUncertain
    from analysis_agent.extraction import ExtractionWorkflow
    from analysis_agent.sources import ConversationReader
    h.replies.append(call('repair_memory', edits=[edit()]))
    def unknown(request):
        raise PublicationUncertain('unknown result')
    monkeypatch.setattr(h.pub, 'publish', unknown)
    session = MemorySession(h.pub, h.source)
    graph = build_conversation(model=h.model, checkpointer=h.saver, instructions='test',
        middleware=[session], tools=session.tools)
    with pytest.raises(PublicationUncertain):
        graph.invoke({'messages': [HumanMessage('改成處長', id='h1')]}, h.config, durability='sync')
    reader = ConversationReader(graph, 'document-a')
    with pytest.raises(PublicationUncertain):
        send_input(graph, h.config, HumanMessage('新案例', id='h2'), abandon_pending=True,
                   quiescent=True, memory_session=session)
    pending_ref = reader.capture_input('h1')
    workflow = ExtractionWorkflow(reader, h.artifacts, h.model, h.saver)
    with pytest.raises(ValueError, match='completed'):
        workflow.start(pending_ref)
    assert not workflow.graph.get_state(workflow.config).values
    assert h.pub.current().processed_source == h.ref and h.pub.current().revision == 1
    assert [m.id for m in graph.get_state(h.config).values['messages'] if isinstance(m, HumanMessage)] == ['h0', 'h1']
    assert len(h.sent) == 1
