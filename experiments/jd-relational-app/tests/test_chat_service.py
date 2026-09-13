"""Generated chat DTOs over actual native saved messages and owner state."""
from dataclasses import replace
import json
from threading import Event
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from jd_relational.chat_history import ChatHistoryCodec, ChatHistoryService
from jd_relational.chat_service import ChatError, ChatService, parse_chat_input, _state
from jd_relational.manual_service import ManualService
from jd_relational.references import SignedReference
from test_ai_runtime import HEAD, make_runtime


def service_for(runtime):
    runtime.history.read_run_operations = lambda *a, **k: ()
    return ChatService(runtime, ManualService(runtime.owner, runtime.history, runtime.codec),
        ChatHistoryService(runtime.checkpoints, ChatHistoryCodec(b'synthetic-chat-history-key-32bytes', runtime.codec.dataset_id)))


def request_for(runtime, doc, run, text='原話\r\n  保留'):
    return {'run_id':run, 'text':text, 'expected_jd_revision_ref': runtime.codec.issue(SignedReference(
        document_id=doc, revision_id=str(HEAD), purpose='history', role='revision', kind='revision'))}


def test_saved_terminal_and_original_human_are_generated_valid(make_runtime):
    make, _ = make_runtime
    runtime, _, calls = make()
    service = service_for(runtime)
    doc, run = str(uuid4()), str(uuid4())
    value = request_for(runtime, doc, run)
    service.start(doc, value)
    runtime.lookup(doc, run).wait(5)
    state = service.status(doc, run)
    assert state['input_state'] == 'saved' and state['run_status'] == 'completed'
    assert state['jd_effects'] == {'state':'settled','results':[]}
    assert state['write_state']['write_blocked'] is False
    page = service.messages(doc)
    assert page['messages'][0]['text'] == value['text']
    assert [m['run_id'] for m in page['messages']] == [run,run]
    assert page['messages'][1]['message_id'] == state['response_message_id']
    assert service.start(doc, value) == state and calls == [run]


def test_pending_cancel_and_recover_do_not_replay(make_runtime):
    make, releases = make_runtime
    entered, release = Event(), Event()
    releases.append(release)
    def node(_):
        entered.set()
        assert release.wait(5)
        return {'messages':[AIMessage(id='saved-reply',content='實際回覆')]}
    runtime, _, calls = make(node)
    service = service_for(runtime)
    doc, run = str(uuid4()), str(uuid4())
    service.start(doc, request_for(runtime, doc, run))
    assert entered.wait(2)
    assert service.recover(doc,run)['run_status'] == 'running'
    cancelled = service.cancel(doc,run)
    assert cancelled['stop_requested'] and cancelled['write_state']['write_blocked']
    release.set()
    runtime.lookup(doc,run).wait(5)
    assert service.status(doc,run)['run_status'] == 'cancelled'
    assert calls == [run]


def test_older_terminal_can_remain_blocked_by_new_run(make_runtime):
    make, releases = make_runtime
    entered, release = Event(), Event()
    releases.append(release)
    def node(state):
        if state['messages'][-1].content == '新回合':
            entered.set()
            assert release.wait(5)
        return {'messages':[AIMessage(id=str(uuid4()), content='回覆')]}
    runtime, _, _ = make(node)
    service = service_for(runtime)
    doc, old, new = str(uuid4()), str(uuid4()), str(uuid4())
    runtime.start(doc, old, '原回合', expected_revision_id=HEAD).wait(5)
    new_handle = runtime.start(doc,new,'新回合',expected_revision_id=HEAD)
    assert entered.wait(2)
    state = service.status(doc,old)
    assert state['run_status'] == 'completed' and state['write_state']['write_blocked']
    assert state['jd_effects']['state'] == 'settled'
    release.set(); new_handle.wait(5)


def test_state_rereads_once_when_closure_and_write_gate_cross(make_runtime, monkeypatch):
    make, _ = make_runtime
    runtime, _, _ = make()
    service = service_for(runtime)
    doc, run = str(uuid4()), str(uuid4())
    runtime.start(doc,run,'回合',expected_revision_id=HEAD).wait(5)
    final = runtime.inspect_run(doc,run)
    states = iter([replace(final,run_status='closing',effects_settled=False), final])
    monkeypatch.setattr(runtime,'inspect_run',lambda *a: next(states))
    assert service.status(doc,run)['run_status'] == 'completed'


@pytest.mark.parametrize('value',[None,[],{}, {'run_id':str(uuid4())},
    '{"run_id":"a","run_id":"b"}', '{"x":NaN}', '{"x":Infinity}', '\ud800'])
def test_invalid_original_json_uses_fixed_error(value):
    with pytest.raises(ChatError, match='^invalid_input$'):
        parse_chat_input(value)


def test_utf8_limit_is_not_codepoint_limit(make_runtime):
    make, _ = make_runtime
    runtime, _, _ = make()
    value = request_for(runtime,str(uuid4()),str(uuid4()),'繁' * 43691)
    with pytest.raises(ChatError, match='^invalid_input$'):
        parse_chat_input(value)
    value['text'] = 'a' * (128*1024)
    assert parse_chat_input(value)['text'] == value['text']


def test_strict_empty_control_body():
    assert parse_chat_input('{}',empty=True) == {}
    for value in ('[]','null','{"secret":"private"}','{"x":1,"x":2}'):
        with pytest.raises(ChatError, match='^invalid_input$'):
            parse_chat_input(value,empty=True)


@pytest.mark.parametrize('key',['ready','archived','write_blocked','running'])
def test_app_flags_reject_numeric_literals(make_runtime,key):
    make, _ = make_runtime
    runtime, _, _ = make()
    value = service_for(runtime).status(str(uuid4()),str(uuid4()))
    value['write_state'][key] = int(value['write_state'][key])
    with pytest.raises(ChatError, match='^service_unavailable$'):
        _state(value)


def test_no_fake_success_if_native_or_sql_unavailable(make_runtime,monkeypatch):
    make, _ = make_runtime
    runtime, _, _ = make()
    service = service_for(runtime)
    def failed(*a,**k):
        raise OSError('PrivateDriverPassword')
    monkeypatch.setattr(runtime.history,'read_run_operations',failed)
    with pytest.raises(ChatError,match='^service_unavailable$'):
        service.status(str(uuid4()),str(uuid4()))


def test_missing_document_preserves_not_found_error(make_runtime,monkeypatch):
    from jd_relational.storage.history import HistoryError
    make, _ = make_runtime
    runtime, _, _ = make()
    service = service_for(runtime)
    def missing(*a,**k):
        raise HistoryError('document_missing')
    monkeypatch.setattr(runtime.history,'read_run_operations',missing)
    with pytest.raises(ChatError,match='^document_missing$'):
        service.status(str(uuid4()),str(uuid4()))


@pytest.mark.parametrize('run',[None,True,'bad-run','AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA'])
def test_invalid_run_rejected_before_reads(make_runtime,run):
    make, _ = make_runtime
    runtime, _, _ = make()
    service = service_for(runtime)
    with pytest.raises(ChatError,match='^invalid_input$'):
        service.status(str(uuid4()),run)


def test_disabled_ai_is_a_distinct_exit_and_original_lookup_stays_available(make_runtime):
    make, _ = make_runtime
    runtime, graph, calls = make()
    service = service_for(runtime)
    doc,run = str(uuid4()),str(uuid4())
    value = request_for(runtime,doc,run)
    runtime.start(doc,run,value['text'],expected_revision_id=HEAD).wait(5)
    runtime.execution_enabled = False
    assert service.start(doc,value)['run_status'] == 'completed'
    with pytest.raises(ChatError,match='^ai_unavailable$'):
        service.start(doc,request_for(runtime,doc,str(uuid4())))
    assert calls == [run] and len(service.messages(doc)['messages']) == 2
