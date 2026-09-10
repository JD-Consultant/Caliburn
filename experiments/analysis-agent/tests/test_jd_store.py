from uuid import uuid4
import pytest


def test_manual_digest_scope_and_exact_payload():
    from analysis_agent.jd_contract import manual_intent, revision_ref
    from analysis_agent.jd_types import JdScope
    scope = JdScope('document-a')
    body = {'request_key': str(uuid4()), 'base_revision_ref': revision_ref(scope, uuid4()),
            'value': [{'type': 'p', 'id': 'p', 'children': [{'text': '工作'}]}]}
    first = manual_intent(scope, body)
    assert manual_intent(scope, body) == first
    body['value'][0]['children'][0]['text'] = '新工作'
    assert manual_intent(scope, body).digest != first.digest
    with pytest.raises(ValueError):
        manual_intent(JdScope('document-b'), body)


def test_internal_intent_cannot_bypass_exact_digest():
    from analysis_agent.jd_service import JdService
    from analysis_agent.jd_types import JdScope, JdManualIntent
    from types import SimpleNamespace
    marker = object()
    service = JdService(SimpleNamespace(engine=marker), None, SimpleNamespace(engine=marker))
    intent = JdManualIntent(JdScope('a'), uuid4(), uuid4(), '0' * 64, [{'type': 'p', 'id': 'p', 'children': [{'text': ''}]}])
    with pytest.raises(ValueError, match='digest'):
        service.manual_save(intent)


@pytest.mark.parametrize(('code', 'status', 'action'), [
    ('invalid_input', 'invalid_input', 'correct_arguments'),
    ('invalid_selection', 'invalid_input', 'correct_arguments'),
    ('invalid_span', 'invalid_input', 'correct_arguments'),
    ('target_missing', 'target_missing', 'reread_current'),
    ('unsupported_content', 'unsupported_content', 'stop'),
    ('noncanonical_value', 'unsupported_content', 'stop'),
    ('duplicate_id', 'unsupported_content', 'stop'),
    ('referenced_item', 'unsupported_content', 'stop'),
    ('invalid_relation_kind', 'unsupported_content', 'stop'),
    ('engine_timeout', 'read_failed', 'stop'),
    ('engine_failed', 'read_failed', 'stop'),
])
def test_selection_read_engine_failure_has_typed_wire_result(code, status, action):
    from types import SimpleNamespace
    from analysis_agent.jd_contract import read_failure_to_wire
    from analysis_agent.jd_engine import JdEngineFailure
    from analysis_agent.jd_service import JdService
    from analysis_agent.jd_types import JdScope, JdReadQuery, JdRevision
    scope = JdScope('synthetic-selection')
    value = [{'id': 'p', 'type': 'p', 'children': [{'text': '工作'}]}]
    revision = JdRevision(scope, uuid4(), None, 'initial', value)
    selection = {'anchor': {'path': [0, 0], 'offset': 0}, 'focus': {'path': [0, 0], 'offset': 1}}
    marker, attempts = object(), []
    def select_value(actual_value, actual_selection):
        assert actual_value == value and actual_selection == selection
        attempts.append(code)
        raise JdEngineFailure(code)
    service = JdService(SimpleNamespace(engine=marker, current=lambda actual: revision),
                        SimpleNamespace(selection=select_value), SimpleNamespace(engine=marker))
    view = service.read(scope, JdReadQuery(selection=selection))
    assert view.status == status and view.revision is None and view.fragment == []
    assert read_failure_to_wire(view) == {
        'status': status, 'document_effect': 'unchanged', 'receipt_durability': 'unconfirmed',
        'error': {'code': status, 'message': 'Requested JD content could not be read.', 'command_index': None},
        'next_action': action,
    }
    assert attempts == [code]


@pytest.mark.parametrize('kind', ['cancelled', 'unknown_code', 'bug'])
def test_selection_read_preserves_cancellation_and_unclassified_errors(kind):
    from types import SimpleNamespace
    from analysis_agent.jd_engine import JdEngineFailure
    from analysis_agent.jd_service import JdService
    from analysis_agent.jd_types import JdScope, JdReadQuery, JdRevision
    scope, marker = JdScope('synthetic-selection'), object()
    revision = JdRevision(scope, uuid4(), None, 'initial', [{'id': 'p', 'type': 'p', 'children': [{'text': ''}]}])
    expected = RuntimeError('unexpected implementation bug') if kind == 'bug' else JdEngineFailure(kind)
    def fail(*args):
        raise expected
    service = JdService(SimpleNamespace(engine=marker, current=lambda actual: revision),
                        SimpleNamespace(selection=fail), SimpleNamespace(engine=marker))
    with pytest.raises(type(expected)) as caught:
        service.read(scope, JdReadQuery(selection={'anchor': {}, 'focus': {}}))
    assert caught.value is expected
