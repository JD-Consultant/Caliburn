"""Known summary -> canonical Q/A; real tools/store/saver, no paid model."""
import base64
import json
from uuid import uuid4

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.memory import InMemoryStore

from analysis_agent.memory import MemoryArtifacts
from analysis_agent.memory_tools import memory_read_tools
from test_memory_read_path import setup_source
from test_native_continuity import assistant_text, response_body


@pytest.fixture
def lookup():
    graph, source, _, config = setup_source()
    ref = source.capture('answer-a', 'answer-a')
    context = source.capture('question-a', 'question-a')
    store = InMemoryStore()
    artifacts = MemoryArtifacts(store, source.document_id)
    record = artifacts.save_extraction(summary='例外由主管核准。', candidates='核准界線',
        slug='核准', source_reference=ref, context_reference=context)
    tools = memory_read_tools(artifacts, None, source)
    node = StateGraph(MessagesState).add_node('tools', ToolNode(tools))
    tool_graph = node.add_edge(START, 'tools').add_edge('tools', END).compile()

    def invoke(reference, *, offset=0, part='source', document='document-a'):
        return tool_graph.invoke({'messages': [AIMessage('', tool_calls=[{
            'id': 'read', 'name': 'read_conversation',
            'args': {'reference': reference, 'offset': offset, 'part': part},
        }])]}, {'configurable': {'thread_id': document}})['messages'][-1]

    return graph, source, config, store, artifacts, record, ref, context, tools, invoke


def test_summary_path_reads_saved_range_not_latest_and_labels_preceding_context(lookup):
    graph, source, config, _, _, record, ref, _, _, invoke = lookup
    graph.update_state(config, {'messages': [HumanMessage('不同工作的新資料', id='later')]}, as_node='model')
    output = invoke(record.summary_path)
    assert output.status == 'success'
    page = json.loads(output.content)
    assert page['segments'] == source.read(ref)['segments']
    assert page['reference'] == ref and page['summary_path'] == record.summary_path
    assert page['part'] == 'source' and page['context_available'] is True
    assert '不同工作' not in output.content and 'opaque-secret' not in output.content
    context = json.loads(invoke(record.summary_path, part='context').content)
    assert context['part'] == 'context'
    assert [(s['role'], s['text']) for s in context['segments']] == [('assistant', '例外也是你核准嗎？')]
    assert '不是，' not in json.dumps(context, ensure_ascii=False)


def test_summary_read_does_not_require_candidates_but_reextraction_still_does(lookup):
    _, _, _, store, artifacts, record, _, _, _, invoke = lookup
    store.delete(('q019-memory', 'document-a', 'interviews'), record.candidates_path.removeprefix('/interviews'))
    assert invoke(record.summary_path).status == 'success'
    with pytest.raises(ValueError, match='Artifact unavailable'):
        artifacts.extraction_window(record.summary_path)


def test_absent_saved_context_is_explicit_and_does_not_guess_nearby_messages(lookup):
    _, _, _, _, artifacts, _, ref, _, _, invoke = lookup
    record = artifacts.save_extraction(summary='本段沒有另存前置脈絡', candidates='', slug='片段', source_reference=ref)
    output = invoke(record.summary_path, part='context')
    assert output.status == 'success'
    page = json.loads(output.content)
    assert page['context_available'] is False and page['reference'] is None
    assert page['segments'] == [] and page['next_offset'] is None
    assert page['part'] == 'context' and '例外也是' not in output.content


def test_direct_live_repair_reference_remains_readable_without_any_summary(lookup):
    graph, source, config, _, _, _, _, _, _, invoke = lookup
    graph.update_state(config, {'messages': [
        AIMessage('核准界線清楚了。', id='closed-a', response_metadata={'status': 'completed'}),
        HumanMessage('我剛剛說錯，是處長。', id='correction'),
    ]}, as_node='model')
    ref = source.capture_input('correction')
    output = invoke(ref)
    assert output.status == 'success'
    assert json.loads(output.content) == source.read(ref)
    assert invoke(ref, part='context').status == 'error'


@pytest.mark.parametrize('path', [
    '/memory/knowledge.md', '/interviews/missing/summary.md',
    '/interviews/../summary.md', '/interviews/' + str(uuid4()) + '/summary.md',
])
def test_invalid_or_missing_summary_returns_framework_tool_error(lookup, path):
    *_, invoke = lookup
    output = invoke(path)
    assert output.status == 'error' and '不是，' not in output.content


def test_cross_document_tool_runtime_cannot_read_even_known_summary(lookup):
    *_, record, _ref, _context, _tools, invoke = lookup
    output = invoke(record.summary_path, document='document-b')
    assert output.status == 'error' and 'another document' in output.content


@pytest.mark.parametrize('fault', ['legacy-header', 'foreign-document', 'missing-checkpoint'])
def test_untrusted_body_or_invalid_saved_locator_never_falls_back_to_latest(lookup, fault):
    _, _, _, _, artifacts, _, ref, _, _, invoke = lookup
    if fault != 'legacy-header':
        data = json.loads(base64.urlsafe_b64decode(ref[13:]))
        data['document' if fault == 'foreign-document' else 'checkpoint'] = (
            'document-b' if fault == 'foreign-document' else '00000000-0000-0000-0000-000000000000')
        ref = 'conversation:' + base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    key = '/' + str(uuid4()) + '/summary.md'
    header = (f'<!-- q019-extraction-source:v1 -->\n# record\n\nSource: {ref}\n'
              'Source scope: complete input range, not per-sentence attribution.\n\n'
              'Context only (not new source): none\nEnd source metadata.\n\n')
    # Arbitrary historical prose containing a header must not become metadata.
    text = ('# legacy\n模型正文\n' if fault == 'legacy-header' else '') + header + 'notes'
    assert not artifacts.interview_backend().write(key, text).error
    output = invoke('/interviews' + key)
    assert output.status == 'error' and '不是，' not in output.content


def test_model_body_cannot_supply_context_when_runtime_saved_none(lookup):
    _, _, _, _, artifacts, _, ref, context, _, invoke = lookup
    record = artifacts.save_extraction(summary='Context only (not new source): ' + context,
        candidates='', slug='body', source_reference=ref)
    page = json.loads(invoke(record.summary_path, part='context').content)
    assert page['context_available'] is False and page['segments'] == []


def test_summary_pagination_preserves_chinese_and_emoji_in_each_selected_window(lookup):
    graph, source, config, _, artifacts, _, _, _, _, invoke = lookup
    question = '請說明' + '專案🛠細節' * 800
    answer = '案例內容' + '甲乙丙丁🛠' * 900
    graph.update_state(config, {'messages': [AIMessage(question, id='long-q'), HumanMessage(answer, id='long-a')]}, as_node='model')
    record = artifacts.save_extraction(summary='長案例', candidates='條件', slug='long',
        source_reference=source.capture('long-a', 'long-a'), context_reference=source.capture('long-q', 'long-q'))
    for part, expected in [('source', answer), ('context', question)]:
        pieces, offset = [], 0
        while True:
            output = invoke(record.summary_path, offset=offset, part=part)
            assert output.status == 'success'
            page = json.loads(output.content)
            assert sum(len(s['text']) for s in page['segments']) <= 3000
            pieces.extend(s['text'] for s in page['segments'])
            if page['next_offset'] is None:
                break
            assert page['next_offset'] > offset
            offset = page['next_offset']
        assert ''.join(pieces) == expected


def test_lookup_schema_hides_runtime_and_exposes_only_selection_and_paging(lookup):
    *_, tools, _invoke = lookup
    read = next(t for t in tools if t.name == 'read_conversation')
    props = read.tool_call_schema.model_json_schema()['properties']
    assert set(props) == {'reference', 'offset', 'part'}
    assert props['part']['enum'] == ['source', 'context']


@pytest.mark.parametrize('offset', [-1])
def test_summary_invalid_offset_returns_error_without_data(lookup, offset):
    *_, record, _ref, _context, _tools, invoke = lookup
    assert invoke(record.summary_path, offset=offset).status == 'error'


@pytest.mark.parametrize('status', ['completed', 'incomplete'])
def test_independent_recall_uses_service_completion_contract_after_source_read(lookup, status):
    """A successful tool is not proof that the subsequent answer completed."""
    from analysis_agent.conversation import build_conversation
    from analysis_agent.memory_tools import memory_access
    from analysis_agent.provider import build_model

    _, source, config, _, artifacts, record, _, _, _, _ = lookup
    version = artifacts.save_memory(knowledge=f'例外核准界線 [詳記]({record.summary_path})', guide='核准界線')
    middleware, tools = memory_access(artifacts, version, source)
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            # A fresh diagnostic conversation, not the employee source history.
            assert '不是，例外由主管核准。' not in json.dumps(payload, ensure_ascii=False)
            body = response_body([{'type': 'function_call', 'id': 'fc_read', 'call_id': 'call_read',
                'name': 'read_conversation', 'arguments': json.dumps({'reference': record.summary_path}),
                'status': 'completed'}], 'resp_lookup')
        else:
            results = [i['output'] for i in payload['input'] if i.get('type') == 'function_call_output']
            assert len(results) == 1
            assert json.loads(results[0])['segments'][0]['text'] == '不是，例外由主管核准。'
            body = response_body([assistant_text('原話確認核准界線。')], 'resp_final')
            body['status'] = status
            if status == 'incomplete':
                body['incomplete_details'] = {'reason': 'max_output_tokens'}
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        graph = build_conversation(model=build_model(model='gpt-5.6-luna', api_key='offline', http_client=client),
            checkpointer=InMemorySaver(), instructions='核對原話', tools=tools, middleware=middleware)
        value = {'messages': [HumanMessage('請回查核准界線的原句。', id='request')]}
        if status == 'incomplete':
            with pytest.raises(ValueError, match='Incomplete model response'):
                graph.invoke(value, config, durability='sync')
            assert graph.get_state(config).next
        else:
            result = graph.invoke(value, config, durability='sync')
            assert result['turn_outcome']['status'] == 'completed'
            assert result['turn_outcome']['model_calls'] == 2
            assert result['messages'][-1].text == '原話確認核准界線。'
    assert len(requests) == 2
