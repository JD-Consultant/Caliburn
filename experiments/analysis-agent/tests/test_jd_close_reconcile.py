"""NL05/06: exact original receipt closes both missing and provisional results."""
from dataclasses import replace
import json
from uuid import uuid4
import pytest
from langchain_core.messages import ToolMessage, AIMessage
from test_jd_postgres import jd
from test_jd_tools import replacement
from test_service import service_harness
from test_consolidation import call, done
from analysis_agent.jd_types import JdScope


@pytest.mark.parametrize(('paired','child_terminal'), [(False,False),(True,False),(True,True)])
def test_stop_recovers_committed_original_without_model_native_or_duplicate_result(jd, tmp_path, monkeypatch, paired,child_terminal):
    attempts = []
    original = jd.edit
    def lost(intent, **kwargs):
        attempts.append(intent)
        result = original(intent, **kwargs)
        assert result.status == 'committed'
        if paired:
            from analysis_agent.jd_store import failure
            return failure(intent, 'outcome_unknown', base_id=intent.base_id, confirmed=False)
        raise RuntimeError('commit succeeded, original ToolMessage checkpoint lost')
    monkeypatch.setattr(jd, 'edit', lost)
    def reply(request):
        outputs = [i for i in json.loads(request.content).get('input', []) if i.get('type') == 'function_call_output']
        if not outputs: return call('jd_read')
        if len(outputs) == 1:
            read = json.loads(outputs[-1]['output'])
            return call('jd_edit', **replacement(read['targets'][0]['target_ref'], '已提交原工作'))
        return done()
    with service_harness(tmp_path, engine=jd.catalog.engine, respond=reply) as (service, sent, _):
        service.jd = jd
        document = service.create_document('取消原回執')['id']
        run = service.submit(document, str(uuid4()), '補完整工作')
        service.join(document)
        context = service._context(document)
        before = context.graph.get_state(context.config, subgraphs=True)
        from analysis_agent.service import current_values
        if child_terminal:
            from analysis_agent.conversation import turn_result,turn_boundary
            state = current_values(before)
            notice = AIMessage('本輪停止。',id=str(uuid4()),additional_kwargs={'analysis_agent_origin':'runtime_notice'})
            outcome = turn_result(state,'cancelled')
            child = next(t.state for t in before.tasks if t.name=='analysis')
            context.graph.update_state(child.config,{'messages':[notice],'turn_outcome':outcome,
                'closed_turns':turn_boundary(outcome,notice.id)},as_node='TurnOutcome.after_agent')
            service.catalog.update_run(run['id'],status='running')
            before = context.graph.get_state(context.config,subgraphs=True)
        messages = current_values(before)['messages']
        original_messages = [m.model_dump() for m in messages]
        head = jd.store.current(JdScope(document))
        lookups = []
        original_lookup = jd.store.reconcile_after_writer_stopped
        def lookup(*args):
            lookups.append(args[0].operation_id)
            return original_lookup(*args)
        monkeypatch.setattr(jd.store,'reconcile_after_writer_stopped',lookup)
        service.get_run(document,run['id'])
        assert lookups == [], 'GET must not reconcile or close pending JD bindings'
        stopped = service.stop(document, run['id'])
        assert stopped['status'] == 'cancelled', stopped
        after = context.graph.get_state(context.config)
        assert not after.next and not after.values.get('jd_pending_operation')
        assert jd.store.current(JdScope(document)) == head
        assert len(sent) == 2 and len(attempts) == 1
        assert lookups == [attempts[0].operation_id]
        edit_messages = [m for m in after.values['messages'] if isinstance(m,ToolMessage) and m.name == 'jd_edit']
        assert len(edit_messages) == 1
        if not paired:
            assert json.loads(edit_messages[0].content)['status'] == 'committed'
        saved_by_id = {m.id:m.model_dump() for m in after.values['messages']}
        assert all(saved_by_id[m['id']] == m for m in original_messages)
        assert after.values['jd_last_model_view'] == current_values(before)['jd_last_model_view']
