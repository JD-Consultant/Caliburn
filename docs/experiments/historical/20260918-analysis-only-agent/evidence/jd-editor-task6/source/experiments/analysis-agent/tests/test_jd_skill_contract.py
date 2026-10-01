"""Task6: actual SDK disclosure and read-only method boundary, no natural eval.

Removing the new package method or its mount breaks the first real request/read.
Only the provider HTTP is synthetic; service, graph, middleware and tools are real.
"""
import json

import pytest
from langchain_core.messages import ToolMessage
from langgraph.store.memory import InMemoryStore

from test_analysis_skills import SKILLS, create_document, payload, state, system_text
from test_consolidation import call, done
from test_service import service_harness


PATH = '/skills/write-customized-jd/'
ASSETS = {
    'SKILL.md': '# 客製化職務說明書撰寫與修訂',
    'references/complete-work-guide.md': '# 完整工作理解與核對',
    'references/writing-and-correction.md': '# 成文與有界更正',
}


@pytest.mark.parametrize('with_store', [False, True])
def test_sdk_discovers_method_then_reads_only_requested_asset(tmp_path, with_store):
    with service_harness(tmp_path, store=InMemoryStore() if with_store else None) as (service, sent, replies):
        document = create_document(service)
        replies.extend([*(call('read_file', file_path=PATH+path, limit=1000) for path in ASSETS), done()])
        run = service.submit(document, 'skill', '請整理已說明的工作；不清楚的部分先保留。')
        service.join(document)
        first = payload(sent[0])
        assert PATH+'SKILL.md' in system_text(first), 'New JD method must be discoverable in the actual request'
        for old in SKILLS:
            assert '/skills/'+old+'/SKILL.md' in system_text(first)
        assert not any(heading in json.dumps(first, ensure_ascii=False) for heading in ASSETS.values())
        results = [m for m in state(service, document)['messages'] if isinstance(m, ToolMessage)]
        assert len(results) == 3
        for index, ((path, heading), result) in enumerate(zip(ASSETS.items(), results)):
            assert result.status == 'success' and heading in result.content
            next_request = payload(sent[index+1])
            outputs = [item for item in next_request['input'] if item.get('type') == 'function_call_output']
            assert outputs[-1]['call_id'] == result.tool_call_id
            assert outputs[-1]['output'] == result.content
            assert next_request['tools'] == first['tools']
        assert service.get_run(document, run['id'])['status'] == 'completed'
        assert service.messages(document)[0]['text'] == '請整理已說明的工作；不清楚的部分先保留。'


@pytest.mark.parametrize('operation', ['write', 'edit', 'delete', 'upload_files'])
def test_new_method_assets_never_grant_mutation(operation):
    from analysis_agent.skills import SkillAssets, analysis_files
    backend = analysis_files(SkillAssets())
    path = PATH+'SKILL.md'
    before = backend.download_files([path])[0].content
    assert before
    arguments = {'write': (path, 'changed'), 'edit': (path, '工作', 'changed'),
                 'delete': (path,), 'upload_files': ([(path, b'changed')],)}
    if operation == 'delete':
        assert backend.delete(path).error
    else:
        with pytest.raises(NotImplementedError):
            getattr(backend, operation)(*arguments[operation])
    assert backend.download_files([path])[0].content == before
