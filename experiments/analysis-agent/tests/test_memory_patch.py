"""SDK patch through real staged tools; synthetic provider, no paid requests."""
import json
import pytest
from pathlib import Path

from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemState
from langgraph.graph import StateGraph, START, END
from analysis_agent.memory_patch import apply_staged_patch

from langchain_core.messages import HumanMessage

from test_consolidation import call, done, harness, knowledge, with_guide, workflow_class
from test_live_memory import h, knowledge as live_knowledge, tool_results


def test_recorded_luna_background_patch_replays_without_changing_other_cases():
    evidence = Path(__file__).resolve().parents[3] / 'docs/specs/evidence/2026-09-07-official-memory-patch-trial.json'
    replay = json.loads(evidence.read_text(encoding='utf-8'))['offline_replay']
    graph = StateGraph(FilesystemState)
    def seed(state):
        StateBackend().write(replay['arguments']['file_path'], replay['before'])
        return {}
    def apply(state):
        apply_staged_patch(**replay['arguments'])
        return {}
    graph.add_node('seed', seed)
    graph.add_node('apply', apply)
    graph.add_edge(START, 'seed')
    graph.add_edge('seed', 'apply')
    graph.add_edge('apply', END)
    result = graph.compile().invoke({'messages': []})
    text = result['files'][replay['arguments']['file_path']]['content']
    assert text == replay['after']
    assert text.split('## 案例差異')[1] == replay['before'].split('## 案例差異')[1]
    assert '財務處長' in text and '每月第一個工作日' in text


@pytest.mark.parametrize('diff,reason', [
    ('', 'nonempty'), ('@@\n unchanged', 'added or removed'),
    ('*** Begin Patch\n*** Update File: /memory/knowledge.md\n@@\n-例外由主管核准。\n+新版\n*** End Patch', 'diff body'),
    ('@@\n-例外由主管核准。\n+新版\n*** End Patch\nignored content', 'diff body'),
    ('@@\n-例外由主管核准。\n+新版\n*** End of File\nignored content', 'diff body'),
    ('@@\n-例外由主管核准。\n+新版\n***\nignored content', 'diff body'),
    ('@@\n-例外由主管核准。\n+' + 'x' * 12001, '12000'),
])
def test_invalid_patch_body_returns_error_and_keeps_published_memory(h, diff, reason):
    h.replies.extend([call('repair_memory', edits=[{'path': '/memory/knowledge.md', 'diff': diff}]), done()])
    result = h.agent().invoke({'messages': [HumanMessage('更正', id='h1')]}, h.config, durability='sync')
    assert json.loads(tool_results(result)[0].content)['status'] == 'invalid_edit'
    assert reason in tool_results(result)[0].content
    assert h.pub.current().revision == 1 and live_knowledge(h) == '例外由主管核准。'


@pytest.mark.parametrize('ending', ['*** End Patch', '*** End of File', '*** End of File\n*** End Patch'])
def test_sdk_terminal_end_patch_is_valid_in_background_tool(harness, ending):
    h = harness
    h.replies.extend([
        with_guide(call('write_file', file_path='/memory/knowledge.md', content='# 月報\n每月彙整\n細節不變')),
        call('apply_memory_patch', file_path='/memory/knowledge.md',
             diff='@@\n # 月報\n-每月彙整\n+每月第一個工作日彙整\n 細節不變\n' + ending),
        done(),
    ])
    workflow_class()(h.b1, h.pub, h.model, h.saver).start()
    assert knowledge(h) == '# 月報\n每月第一個工作日彙整\n細節不變'


def test_background_mismatch_returns_precise_error_and_can_correct(harness):
    h = harness
    h.replies.extend([
        with_guide(call('write_file', file_path='/memory/knowledge.md', content='# A\n每月回報\n細節不變')),
        call('apply_memory_patch', file_path='/memory/knowledge.md', diff='@@\n # 不存在\n-每月回報\n+每週回報'),
        call('read_file', file_path='/memory/knowledge.md'),
        call('apply_memory_patch', file_path='/memory/knowledge.md', diff='@@\n # A\n-每月回報\n+每週回報\n 細節不變'),
        done(),
    ])
    workflow_class()(h.b1, h.pub, h.model, h.saver).start()
    assert 'Invalid Context' in json.dumps(h.sent[3], ensure_ascii=False)
    assert 'nothing from this patch was written' in json.dumps(h.sent[3], ensure_ascii=False)
    assert knowledge(h) == '# A\n每週回報\n細節不變'


def test_background_patch_context_selects_case_and_preserves_other_details(harness):
    h = harness
    original = '# 案例 A\n- 每月回報\n# 案例 B\n- 每月回報\n  - 例外由主管判斷'
    h.replies.extend([
        with_guide(call('write_file', file_path='/memory/knowledge.md', content=original)),
        call('read_file', file_path='/memory/knowledge.md'),
        call('apply_memory_patch', file_path='/memory/knowledge.md',
             diff='@@\n # 案例 B\n-  - 每月回報\n+- 每週回報\n   - 例外由主管判斷'),
        done(),
    ])
    workflow_class()(h.b1, h.pub, h.model, h.saver).start()
    assert knowledge(h) == original.replace('# 案例 B\n- 每月回報', '# 案例 B\n- 每週回報')
    assert 'Not yet published' in json.dumps(h.sent[-1], ensure_ascii=False)


def test_live_patch_late_failure_does_not_publish_then_retry_succeeds(h):
    good = {'path': '/memory/knowledge.md', 'diff': '@@\n-例外由主管核准。\n+例外由處長核准。'}
    bad = {'path': '/memory/guide.md', 'diff': '@@\n-不存在的導覽\n+新的導覽'}
    h.replies.extend([call('repair_memory', edits=[good, bad]),
                      call('read_file', file_path='/memory/knowledge.md'),
                      call('repair_memory', edits=[good]), done()])
    result = h.agent().invoke({'messages': [HumanMessage('更正為處長', id='h1')]}, h.config, durability='sync')
    messages = tool_results(result)
    assert json.loads(messages[0].content)['status'] == 'invalid_edit'
    assert 'Invalid Context' in messages[0].content
    assert '例外由主管核准' in messages[1].content
    assert json.loads(messages[2].content)['status'] == 'applied'
    assert h.pub.current().revision == 2
    assert live_knowledge(h) == '例外由處長核准。'
