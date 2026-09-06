"""SK-01: real service/create_agent/tools/SDK, synthetic HTTP only.

These tests prove disclosure and isolation, NOT natural skill selection or
interview quality. The transport deliberately asks for a particular skill.
"""
from copy import deepcopy
import ast
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import InMemorySaver
from psycopg import OperationalError

from test_consolidation import call, done
from test_service import service_harness
from test_live_memory import h, edit, tool_results, system_wire


SKILLS = {
    'work-scope-interview': '# 工作範圍與案例訪談',
    'compare-work-patterns': '# 案例比較與共同工作模式',
    'outcomes-and-expertise': '# 產出、成功判準與知識技能',
}


def skill_path(name):
    return f'/skills/{name}/SKILL.md'


def payload(request):
    assert request.method == 'POST' and request.url.path == '/v1/responses'
    return json.loads(request.content)


def system_text(body):
    return json.dumps([i for i in body['input'] if i.get('role') in ('system', 'developer')],
                      ensure_ascii=False)


def state(service, document):
    context = service._context(document)
    return context.graph.get_state(context.config).values


def create_document(service):
    document = service.create_document('分析 Skills 接線')['id']
    context = service._context(document)
    if context.memory:
        context.memory.publication.setup()
    return document


@pytest.mark.parametrize('with_store', [False, True])
@pytest.mark.parametrize('name', SKILLS)
def test_first_input_advertises_metadata_then_reads_only_selected_body(tmp_path, with_store, name):
    with service_harness(tmp_path, store=InMemoryStore() if with_store else None) as (service, sent, replies):
        document = create_document(service)
        response = call('read_file', file_path=skill_path(name), limit=1000)
        response['output'].insert(0, {'type': 'reasoning', 'id': 'rs_skill',
            'summary': [], 'encrypted_content': 'opaque-before-skill'})
        replies.extend([response, done()])
        run = service.submit(document, 'first', '請從我最近交付的一個網站案例開始。')
        service.join(document)

        first, second = map(payload, sent)
        for skill, heading in SKILLS.items():
            assert skill_path(skill) in system_text(first), 'Missing default Skills metadata/read route'
            assert heading not in json.dumps(first, ensure_ascii=False), 'Body loaded before read_file'
        assert system_text(first) == system_text(second)
        tools = [t['name'] for t in first['tools']]
        expected = {'ls', 'grep', 'read_file', 'request_memory_consolidation'}
        if with_store:
            expected |= {'read_conversation', 'repair_memory'}
            assert service._context(document).memory.publication.current() is None
        assert len(tools) == len(set(tools)) and set(tools) == expected
        assert second['tools'] == first['tools']
        output = next(i for i in second['input'] if i.get('type') == 'function_call_output')
        invocation = next(i for i in second['input'] if i.get('type') == 'function_call')
        assert invocation['call_id'] == output['call_id']
        assert json.loads(invocation['arguments']) == {'file_path': skill_path(name), 'limit': 1000}
        assert SKILLS[name] in output['output']
        assert all(heading not in output['output'] for skill, heading in SKILLS.items() if skill != name)
        assert next(i for i in second['input'] if i.get('type') == 'reasoning')['encrypted_content'] == 'opaque-before-skill'
        saved = state(service, document)
        assert service.get_run(document, run['id'])['status'] == 'completed'
        assert [m.content for m in saved['messages'] if isinstance(m, HumanMessage)] == ['請從我最近交付的一個網站案例開始。']
        assert [m.content for m in saved['messages'] if isinstance(m, ToolMessage)] == [output['output']]
        assert all(not isinstance(m, HumanMessage) or '/skills/' not in m.content for m in saved['messages'])


def test_skill_read_preserves_inline_compaction_pairing_and_canonical_prefix(tmp_path):
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        document = create_document(service)
        response = call('read_file', file_path=skill_path('compare-work-patterns'))
        response['output'][0:0] = [
            {'type': 'reasoning', 'id': 'rs_old', 'summary': [], 'encrypted_content': 'opaque-old'},
            {'type': 'compaction', 'id': 'cmp_skill', 'encrypted_content': 'opaque-compact'},
            {'type': 'reasoning', 'id': 'rs_new', 'summary': [], 'encrypted_content': 'opaque-new'},
        ]
        replies.extend([response, done()])
        first = service.submit(document, 'first', '舊案例完整原文不能被刪除。')
        service.join(document)
        before = deepcopy(state(service, document)['messages'])
        replies.append(done())
        second = service.submit(document, 'second', '這次情境不同。')
        service.join(document)
        for request in sent[1:]:
            wire = [i for i in payload(request)['input'] if i.get('role') not in ('system', 'developer')]
            assert [i['type'] for i in wire[:4]] == ['compaction', 'reasoning', 'function_call', 'function_call_output']
            assert wire[0]['encrypted_content'] == 'opaque-compact'
            assert wire[1]['encrypted_content'] == 'opaque-new'
            assert wire[2]['call_id'] == wire[3]['call_id']
            assert SKILLS['compare-work-patterns'] in wire[3]['output']
            assert 'opaque-old' not in json.dumps(wire)
        after = state(service, document)['messages']
        assert after[:len(before)] == before
        assert before[0].content == '舊案例完整原文不能被刪除。'
        ai = next(m for m in before if isinstance(m, AIMessage))
        assert ai.content[0]['encrypted_content'] == 'opaque-old'
        assert ai.content[1]['encrypted_content'] == 'opaque-compact'
        assert service.get_run(document, first['id'])['status'] == 'completed'
        assert service.get_run(document, second['id'])['status'] == 'completed'


@pytest.mark.parametrize('with_store', [False, True])
@pytest.mark.parametrize('path', [
    '/skills/../service.py', '/skills/../../../../README.md',
    '/skills\\..\\service.py', '/.env', '/README.md',
    str(Path(__file__).resolve()),
    '/skills/' + Path(__file__).resolve().as_posix(),
])
def test_read_file_rejects_traversal_and_host_paths(tmp_path, with_store, path):
    with service_harness(tmp_path, store=InMemoryStore() if with_store else None) as (service, sent, replies):
        document = create_document(service)
        replies.extend([call('read_file', file_path=path), done()])
        run = service.submit(document, 'outside', '只測讀取邊界。')
        service.join(document)
        assert service.get_run(document, run['id'])['status'] == 'completed'
        result = next(m for m in state(service, document)['messages'] if isinstance(m, ToolMessage))
        assert result.status == 'error'
        assert 'SK-01: real service' not in result.content  # This test file is outside the mount.
        assert next(i for i in payload(sent[-1])['input'] if i.get('type') == 'function_call_output')['output'] == result.content


def test_shared_ls_grep_and_read_use_the_same_advertised_mount(tmp_path):
    with service_harness(tmp_path) as (service, sent, replies):
        document = create_document(service)
        replies.extend([call('ls', path='/'), call('ls', path='/skills/'),
                        call('grep', pattern='name:', path='/skills/'), done()])
        run = service.submit(document, 'browse', '查看分析方法。')
        service.join(document)
        results = tool_results(state(service, document))
        assert ast.literal_eval(results[0].content) == ['/skills/']
        for name in SKILLS:
            assert f'/skills/{name}/' in results[1].content
            assert skill_path(name) in results[2].content
            assert skill_path(name) in system_text(payload(sent[0]))
        assert service.get_run(document, run['id'])['status'] == 'completed'


@pytest.mark.parametrize('operation', ['write', 'edit', 'delete', 'upload_files'])
def test_asset_backend_has_no_mutation_capability(operation):
    from analysis_agent.skills import SkillAssets, analysis_files
    backend = analysis_files(SkillAssets())
    path = skill_path('work-scope-interview')
    before = backend.download_files([path])[0].content
    assert before and '# 工作範圍與案例訪談'.encode() in before
    arguments = {'write': (path, 'changed'), 'edit': (path, '工作', 'changed'),
                 'delete': (path,), 'upload_files': ([(path, b'changed')],)}
    if operation == 'delete':
        assert backend.delete(path).error  # Composite reports unsupported deletes as a result.
    else:
        with pytest.raises(NotImplementedError):
            getattr(backend, operation)(*arguments[operation])
    assert backend.download_files([path])[0].content == before


def test_skill_mount_survives_pinned_background_change_and_c_refresh(h):
    from analysis_agent.live_memory import MemorySession
    from analysis_agent.runtime import build_agent
    from analysis_agent.skills import SkillAssets, analysis_skills
    assets = SkillAssets()
    session = MemorySession(h.pub, h.source, skill_assets=assets)
    agent = build_agent(model=h.model, checkpointer=h.saver, instructions='訪談',
                        middleware=[analysis_skills(assets), session], tools=session.tools)

    def background_wins():
        newer = h.artifacts.save_memory(knowledge='例外由處長核准。', guide='處長核准：/memory/knowledge.md')
        h.pub.publish(h.pub.prepare(newer, expected_revision=1, kind='repair', repair_sources=(h.ref,)))
        return call('read_file', file_path='/memory/knowledge.md')

    h.replies.extend([
        call('read_file', file_path=skill_path('work-scope-interview')), background_wins,
        call('repair_memory', edits=[edit('主管', '總監')]),  # stale refresh, not a write
        call('read_file', file_path=skill_path('compare-work-patterns')),
        call('read_file', file_path='/memory/knowledge.md'),
        call('repair_memory', edits=[edit('處長', '總監')]),
        call('read_file', file_path=skill_path('outcomes-and-expertise')),
        call('read_file', file_path='/memory/knowledge.md'), done(),
    ])
    result = agent.invoke({'messages': [HumanMessage('更正，是總監核准。', id='h1')]}, h.config, durability='sync')
    results = tool_results(result)
    assert SKILLS['work-scope-interview'] in results[0].content
    assert '主管' in results[1].content  # Still pinned to v1, despite background v2.
    assert json.loads(results[2].content)['status'] == 'stale'
    assert SKILLS['compare-work-patterns'] in results[3].content
    assert '處長' in results[4].content
    assert json.loads(results[5].content)['head']['revision'] == 3
    assert SKILLS['outcomes-and-expertise'] in results[6].content
    assert '總監' in results[7].content
    assert all(system_wire(p) == system_wire(h.sent[0]) for p in h.sent)
    assert all(p['tools'] == h.sent[0]['tools'] for p in h.sent)


@pytest.mark.parametrize('reopen', [False, True])
def test_pending_skill_read_uses_existing_trusted_read_recovery(tmp_path, monkeypatch, reopen):
    from analysis_agent.skills import SkillAssets
    saver, store = InMemorySaver(), InMemoryStore()
    original = SkillAssets.read
    observed = []

    def lost_result(*args, **kwargs):
        observed.append(original(*args, **kwargs))
        raise OperationalError('synthetic skill read result loss')

    def recover(service, sent, replies, document, run, before):
        assert service.get_run(document, run['id'])['can_resume']
        count = len(sent)
        replies.append(done())
        service.resume(document, run['id'])
        service.join(document)
        saved = state(service, document)
        assert service.get_run(document, run['id'])['status'] == 'completed'
        assert saved['messages'][:len(before)] == before
        result = tool_results(saved)[-1]
        assert result.status == 'success' and SKILLS['work-scope-interview'] in result.content
        assert result.tool_call_id == before[-1].tool_calls[0]['id']
        assert len(sent) == count + 1
        assert sum(m.id == run['id'] for m in saved['messages']) == 1

    with service_harness(tmp_path, saver=saver, store=store) as (service, sent, replies):
        document = create_document(service)
        replies.append(call('read_file', file_path=skill_path('work-scope-interview')))
        with monkeypatch.context() as fault:
            fault.setattr(SkillAssets, 'read', lost_result)
            run = service.submit(document, 'read', '談最近的案例。')
            service.join(document)
        context = service._context(document)
        child = context.graph.get_state(context.config, subgraphs=True).tasks[0].state
        before = deepcopy(child.values['messages'])
        assert child.next == ('tools',) and len(observed) == 1
        assert service.get_run(document, run['id'])['error_code'] == 'runtime_error'
        if not reopen:
            recover(service, sent, replies, document, run, before)
            return
    with service_harness(tmp_path, saver=saver, store=store) as (service, sent, replies):
        recover(service, sent, replies, document, run, before)


def test_skill_tool_body_stays_canonical_but_never_enters_b1_source_or_wire(tmp_path):
    from analysis_agent.extraction import ExtractionWorkflow
    from test_extraction import body
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        document = create_document(service)
        replies.extend([call('read_file', file_path=skill_path('outcomes-and-expertise')), done()])
        run = service.submit(document, 'case', '我檢查網站上線。')
        service.join(document)
        before = deepcopy(state(service, document)['messages'])
        reference = service.reader(document).capture(run['id'], before[-1].id)
        visible = service.reader(document).read(reference)
        assert visible['segments'][0]['text'] == '我檢查網站上線。'
        assert 'tool' in visible['omitted_content_types']
        assert SKILLS['outcomes-and-expertise'] in tool_results({'messages': before})[0].content
        replies.append(body())
        result = ExtractionWorkflow(service.reader(document), service._context(document).memory.artifacts,
                                    service.model, service.saver).start(reference)
        assert len(result['files']) == 1
        b1 = payload(sent[-1])
        assert b1['text']['format']['type'] == 'json_schema' and not b1.get('tools')
        serialized = json.dumps(b1, ensure_ascii=False)
        assert '我檢查網站上線。' in serialized
        for name, heading in SKILLS.items():
            assert heading not in serialized and skill_path(name) not in serialized
            assert heading not in json.dumps(visible, ensure_ascii=False)
        assert state(service, document)['messages'] == before
