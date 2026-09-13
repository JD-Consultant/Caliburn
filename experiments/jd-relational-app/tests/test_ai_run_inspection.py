"""Public chat observations use native saved input and original SQL receipts."""
from threading import Event
from dataclasses import replace
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from jd_relational.ai_runtime import AiRunSnapshot, AiRuntimeError
from test_ai_runtime import HEAD, make_runtime
from test_foreground_runtime import ai_intent, run_identity
from test_manual_runtime import observation
from jd_relational.consultant_tools import decode_ai_binding
from jd_relational.observation_projection import project_observation
from jd_relational.reads import read_json


def prepare(make_runtime, node=None):
    make, releases = make_runtime
    runtime, graph, calls = make(node)
    runtime.history.read_run_operations = lambda *a, **k: ()
    return runtime, graph, calls, releases


def test_missing_is_unconfirmed_and_terminal_is_saved_with_no_effects(make_runtime):
    runtime, graph, calls, _ = prepare(make_runtime)
    doc, run = str(uuid4()), str(uuid4())
    missing = runtime.inspect_run(doc, run)
    assert isinstance(missing, AiRunSnapshot)
    assert (missing.run_status, missing.input_state, missing.effects_settled) == ('not_found', 'unconfirmed', False)
    runtime.start(doc, run, '原話\r\n  ', expected_revision_id=HEAD).wait(5)
    saved = runtime.inspect_run(doc, run)
    assert (saved.run_status, saved.input_state, saved.effects_settled) == ('completed', 'saved', True)
    assert saved.response_message_id and saved.stop_requested is None and saved.receipts == ()
    assert calls == [run]


def test_active_and_cancellation_observe_actual_future_without_replaying(make_runtime):
    entered, release = Event(), Event()
    def node(state):
        entered.set()
        assert release.wait(5)
        return {'messages': [AIMessage(id='reply', content='已保存文字')]}
    runtime, graph, calls, releases = prepare(make_runtime, node)
    releases.append(release)
    doc, run = str(uuid4()), str(uuid4())
    handle = runtime.start(doc, run, '持續訪談', expected_revision_id=HEAD)
    assert entered.wait(2)
    active = runtime.inspect_run(doc, run)
    assert (active.run_status, active.input_state, active.effects_settled, active.stop_requested) == ('running', 'saved', False, False)
    runtime.request_stop(doc, run)
    assert runtime.inspect_run(doc, run).stop_requested is True
    release.set()
    handle.wait(5)
    assert runtime.inspect_run(doc, run).run_status == 'cancelled'
    assert calls == [run]


def test_disabled_execution_preserves_original_lookup_and_never_saves_new_input(make_runtime):
    runtime, graph, calls, _ = prepare(make_runtime)
    doc, run = str(uuid4()), str(uuid4())
    first = runtime.start(doc, run, '原回合', expected_revision_id=HEAD)
    first.wait(5)
    runtime.execution_enabled = False
    assert runtime.start(doc, run, '原回合', expected_revision_id=HEAD) is first
    before = graph.get_state({'configurable': {'thread_id': doc}})
    with pytest.raises(AiRuntimeError, match='^execution_disabled$'):
        runtime.start(doc, str(uuid4()), '不應保存', expected_revision_id=HEAD)
    assert graph.get_state({'configurable': {'thread_id': doc}}) == before
    assert calls == [run]


def test_non_public_reasoning_is_not_a_response(make_runtime):
    runtime, graph, calls, _ = prepare(make_runtime,
        lambda _: {'messages': [AIMessage(id='reasoning-only', content=[{'type':'thinking', 'thinking':'private'}])]})
    doc, run = str(uuid4()), str(uuid4())
    runtime.start(doc, run, '內容', expected_revision_id=HEAD).wait(5)
    assert runtime.inspect_run(doc, run).response_message_id is None


def test_original_cancel_does_not_cancel_later_running_turn(make_runtime):
    entered, release = Event(), Event()
    def node(state):
        if state['messages'][-1].content == '第二輪':
            entered.set()
            assert release.wait(5)
        return {'messages': [AIMessage(id=str(uuid4()), content='回覆')]}
    runtime, graph, calls, releases = prepare(make_runtime, node)
    releases.append(release)
    doc, old, new = str(uuid4()), str(uuid4()), str(uuid4())
    runtime.start(doc, old, '第一輪', expected_revision_id=HEAD).wait(5)
    handle = runtime.start(doc, new, '第二輪', expected_revision_id=HEAD)
    assert entered.wait(2)
    runtime.request_stop(doc, old)
    assert runtime.inspect_run(doc, new).stop_requested is False
    assert runtime.inspect_run(doc, old).run_status == 'completed'
    release.set()
    assert handle.wait(5).status == 'completed'


def written_run(make_runtime):
    holder = {}
    def node(state):
        runtime = holder['runtime']
        record = state['jd_ai_run']
        identity = run_identity(record['document_id'],run=record['run_id'])
        intent = ai_intent(identity)
        command = intent.command
        call = AIMessage(id='original-call-message',content='',tool_calls=[{
            'id':'original-call','name':command['tool'],'args':command['arguments']}])
        digest = sha256(json.dumps({'name':command['tool'],'args':command['arguments']},
            ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        binding = decode_ai_binding({'format_version':1,'dataset_id':runtime.codec.dataset_id,
            'document_id':identity.document_id,'run_id':identity.run_id,
            'operation_id':str(intent.operation_id),'base_revision_id':str(intent.base_revision_id),
            'origin':'ai','request_digest':intent.request_digest,'command_kind':command['tool'],
            'message_id':call.id,'tool_call_id':'original-call','input_digest':digest},
            dataset_id=runtime.codec.dataset_id,document_id=identity.document_id,run_id=identity.run_id)
        observed = observation(intent.identity)
        observed = replace(observed,receipt=replace(observed.receipt,origin='ai',ai_run_id=identity.run_id))
        runtime.owner.storage.receipts[intent.operation_id] = observed
        holder['receipt'] = observed.receipt
        return {'jd_ai_bindings':[binding.to_dict()], 'messages':[call,
            ToolMessage(id='original-result',tool_call_id='original-call',name=command['tool'],
                content=read_json(project_observation(observed,runtime.codec)),status='success'),
            AIMessage(id='final-public',content='已完成修改')]}
    runtime, graph, calls, releases = prepare(make_runtime,node)
    holder['runtime'] = runtime
    doc, run = str(uuid4()), str(uuid4())
    runtime.start(doc,run,'調整工作',expected_revision_id=HEAD).wait(5)
    runtime.history.read_run_operations = lambda *a,**k: (holder['receipt'],)
    return runtime,doc,run,holder['receipt']


def test_terminal_result_uses_original_sql_and_exact_set(make_runtime):
    runtime,doc,run,row = written_run(make_runtime)
    value = runtime.inspect_run(doc,run)
    assert value.effects_settled and value.receipts[0].receipt == row
    assert value.response_message_id == 'final-public'
    runtime.history.read_run_operations = lambda *a,**k: (row,replace(row,operation_id=uuid4()))
    with pytest.raises(AiRuntimeError,match='^run_recovery_required$'):
        runtime.inspect_run(doc,run)


@pytest.mark.parametrize('field,value',[
    ('request_digest','c'*64),('origin','manual'),('ai_run_id',str(uuid4())),
    ('document_id',str(uuid4())),('base_revision_id',uuid4())])
def test_original_receipt_must_match_binding(make_runtime,field,value):
    runtime,doc,run,row = written_run(make_runtime)
    runtime.history.read_run_operations = lambda *a,**k: (replace(row,**{field:value}),)
    with pytest.raises(AiRuntimeError,match='^invalid_saved_tool_result$'):
        runtime.inspect_run(doc,run)


def test_missing_terminal_receipt_never_becomes_no_changes(make_runtime):
    runtime,doc,run,row = written_run(make_runtime)
    runtime.history.read_run_operations = lambda *a,**k: ()
    with pytest.raises(AiRuntimeError,match='^run_recovery_required$'):
        runtime.inspect_run(doc,run)


def test_known_unsaved_input_stays_distinct_from_missing_after_restart(make_runtime,monkeypatch):
    runtime,graph,calls,_ = prepare(make_runtime)
    def failed(*a,**k):
        raise OSError('private-save-fault')
    original = graph.checkpointer.put
    monkeypatch.setattr(graph.checkpointer,'put',failed)
    doc,run = str(uuid4()),str(uuid4())
    result = runtime.start(doc,run,'尚未保存',expected_revision_id=HEAD).wait(5)
    assert not result.input_saved
    monkeypatch.setattr(graph.checkpointer,'put',original)
    value = runtime.inspect_run(doc,run)
    assert (value.run_status,value.input_state,value.effects_settled) == ('failed','not_saved',True)
    runtime._latest.clear()  # Deliberately discard only the local evidence.
    value = runtime.inspect_run(doc,run)
    assert (value.run_status,value.input_state,value.effects_settled) == ('not_found','unconfirmed',False)


def test_failed_closure_is_explicit_recovery_without_model_replay(make_runtime,monkeypatch):
    runtime,graph,calls,_ = prepare(make_runtime)
    original = graph.update_state
    def failed(*a,**k):
        raise OSError('private-close-fault')
    monkeypatch.setattr(graph,'update_state',failed)
    doc,run = str(uuid4()),str(uuid4())
    handle = runtime.start(doc,run,'已保存原話',expected_revision_id=HEAD)
    with pytest.raises(AiRuntimeError,match='^run_recovery_required$'):
        handle.wait(5)
    assert runtime.inspect_run(doc,run).run_status == 'recovery_required'
    monkeypatch.setattr(graph,'update_state',original)
    runtime.recover_run(doc,run)
    assert runtime.inspect_run(doc,run).run_status == 'completed' and calls == [run]
