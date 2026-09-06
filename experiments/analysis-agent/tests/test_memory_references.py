"""Regressions for real saved references, not model semantic correctness."""
import base64
import json

import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.store.memory import InMemoryStore

from analysis_agent.memory import MemoryArtifacts
from test_live_memory import h, edit, knowledge
from test_consolidation import harness, call, done, workflow_class


def changed_reference(reference, **changes):
    data = json.loads(base64.urlsafe_b64decode(reference[13:]))
    data.update(changes)
    return 'conversation:' + base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


@pytest.mark.parametrize('format_', [
    '{}', '__{}__', '_{}_', '**{}**', '*{}*', '`{}`', '<{}>',
    '[詳記]({})', '[詳記][a]\n\n[a]: {}', '```text\n{}\n```',
])
def test_real_summary_in_markdown_is_publishable_and_preserved(h, format_):
    files = h.artifacts.save_extraction(summary='A案例', candidates='核准', slug='A', source_reference=h.ref)
    content = format_.format(files.summary_path)
    version = h.artifacts.save_memory(knowledge=content, guide='A')
    h.pub.publish(h.pub.prepare(version, expected_revision=1, kind='repair'))
    assert knowledge(h) == content
    assert 'A案例' in h.artifacts.read_text(files.summary_path)


@pytest.mark.parametrize('bad', [
    '/interviews/', 'conversation:', 'conversation:???',
    'conversation:broken', '/interviews/missing/summary.md',
])
@pytest.mark.parametrize('format_', ['{}', '[來源]({})', '`{}`', '__{}__'])
def test_malformed_controlled_reference_cannot_enter_memory(h, bad, format_):
    with pytest.raises(ValueError, match='reference'):
        h.artifacts.save_memory(knowledge=format_.format(bad), guide='A')
    assert h.pub.current().revision == 1


@pytest.mark.parametrize('changes', [
    {'checkpoint': 'nonexistent'}, {'first': 'missing'},
    {'last': 'missing'}, {'first': 'a0', 'last': 'h0'}, {'document': 'another-document'},
])
def test_raw_reference_uses_real_snapshot_range_and_document(h, changes):
    ref = changed_reference(h.ref, **changes)
    with pytest.raises(ValueError):
        h.artifacts.validate_texts(knowledge=f'[原話]({ref})', guide='A')
    assert h.pub.current().revision == 1


@pytest.mark.parametrize('format_', ['{}', '__{}__', '[原話]({})', '`{}`'])
def test_real_raw_reference_can_be_read_after_publication(h, format_):
    version = h.artifacts.save_memory(knowledge=format_.format(h.ref), guide='A')
    h.pub.publish(h.pub.prepare(version, expected_revision=1, kind='repair'))
    assert h.source.read(h.ref)['segments'][0]['text'] == '例外由主管核准。'


def test_artifact_only_client_must_not_skip_raw_reference_validation(h):
    artifacts = MemoryArtifacts(InMemoryStore(), 'document-a')
    with pytest.raises(ValueError, match='reference'):
        artifacts.save_memory(knowledge=h.ref, guide='A')


def test_prepublication_check_rejects_broken_raw_reference_even_if_store_was_written_directly(h):
    version = h.artifacts.save_memory(knowledge='核准', guide='A')
    # Bypass only the artifact writer to exercise the publication boundary.
    h.artifacts._backend('versions', version.version_id).upload_files([
        ('/memory/knowledge.md', b'[source](conversation:???)')])
    with pytest.raises(ValueError, match='reference'):
        h.pub.prepare(version, expected_revision=1, kind='repair')
    assert h.pub.current().revision == 1


def test_b2_gets_actionable_raw_reference_error_and_can_correct_it(harness):
    h = harness
    h.replies.extend([
        call('write_file', file_path='/memory/knowledge.md', content='[原話](conversation:???)'),
        call('validate_memory'),
        call('edit_file', file_path='/memory/knowledge.md', old_string='conversation:???', new_string=h.ref),
        call('validate_memory'), done(),
    ])
    workflow_class()(h.b1, h.pub, h.model, h.saver).start()
    feedback = [i['output'] for p in h.sent for i in p.get('input', [])
                if i.get('type') == 'function_call_output']
    assert any('reference' in str(text).lower() and 'copy' in str(text).lower() for text in feedback)
    assert h.pub.current().revision == 1
    assert h.ref in h.artifacts.read_text('/memory/knowledge.md', h.pub.current().memory)


def test_c_rejects_malformed_raw_reference_without_partial_publication(h):
    h.replies.extend([call('repair_memory', edits=[edit(new='處長 [原話](conversation:???)')]), done()])
    result = h.agent().invoke({'messages': [HumanMessage('不是主管，是處長。', id='h1')]}, h.config)
    assert h.pub.current().revision == 1
    assert knowledge(h) == '例外由主管核准。'
    errors = [m for m in result['messages'] if isinstance(m, ToolMessage) and m.status == 'error']
    assert errors and 'reference' in errors[0].content.lower()


def test_b2_cannot_skip_validation_tool_and_publish_bad_reference(harness):
    h = harness
    h.replies.extend([call('write_file', file_path='/memory/knowledge.md', content='conversation:???'), done()])
    with pytest.raises(ModelCallLimitExceededError, match='limit'):
        workflow_class()(h.b1, h.pub, h.model, h.saver, max_model_steps=2).start()
    assert len(h.sent) == 3  # No budget for correction; no further HTTP.
    assert h.pub.current() is None


def test_duplicate_reference_definitions_cannot_hide_an_invalid_controlled_address(h):
    with pytest.raises(ValueError, match='reference'):
        h.artifacts.validate_texts(
            knowledge='[a]: https://example.org\n[a]: conversation:???', guide='A')


@pytest.mark.parametrize('text', [
    'https://example.org/interviews/missing/summary.md',
    '[external](https://example.org/interviews/missing/summary.md)',
    'https://example.org/?conversation:???',
    '`https://example.org/interviews/missing/summary.md`',
    'https://example.org/;/interviews/missing/summary.md',
    '`https://example.org/;/interviews/missing/summary.md`',
    'https://example.org/?q=anything;/interviews/missing/summary.md',
])
def test_external_url_is_not_a_local_artifact_reference(h, text):
    h.artifacts.validate_texts(knowledge=text, guide='A')


@pytest.mark.parametrize('format_', [
    '`{}.`', '```text\n{}.\n```', '[detail]({}.)',
    '`{}。`', '```text\n{}。\n```', '`{}；`', '[detail]({}。)',
])
def test_explicit_literal_address_is_not_silently_repaired(h, format_):
    files = h.artifacts.save_extraction(summary='A', candidates='A', slug='A', source_reference=h.ref)
    with pytest.raises(ValueError, match='reference'):
        h.artifacts.validate_texts(knowledge=format_.format(files.summary_path), guide='A')
