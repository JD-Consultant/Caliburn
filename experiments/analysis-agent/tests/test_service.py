"""Application seams use the real graph, ORM and SDK; only HTTP is synthetic."""
from contextlib import contextmanager
from threading import Event
from uuid import uuid4

import httpx
import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import create_engine

from test_consolidation import done, call


@contextmanager
def service_harness(tmp_path, *, saver=None, respond=None, engine=None, store=None,
                    max_model_steps=9, max_tool_calls=8):
    from analysis_agent.catalog import Catalog
    from analysis_agent.service import AnalysisService
    from analysis_agent.provider import build_model
    sent = []
    replies = []
    prefix = uuid4().hex

    def transport(request):
        sent.append(request)
        answer = respond(request) if respond else (replies.pop(0) if replies else done())
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, httpx.Response):
            return answer
        answer['id'] = f'resp_{prefix}_{len(sent)}'
        for i, item in enumerate(answer['output']):
            item['id'] = f'item_{prefix}_{len(sent)}_{i}'
            if item['type'] == 'function_call':
                item['call_id'] = f'call_{prefix}_{len(sent)}_{i}'
        return httpx.Response(200, json=answer)

    engine = engine or create_engine(f'sqlite:///{tmp_path / "catalog.db"}')
    catalog = Catalog(engine)
    catalog.setup()
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        limits = {name: value for name, value in (
            ('max_model_steps', max_model_steps), ('max_tool_calls', max_tool_calls),
        ) if value is not None}
        service = AnalysisService(catalog=catalog, saver=saver or InMemorySaver(), model=model, store=store,
                                  instructions='訪談', max_workers=2, **limits)
        service.start()
        try:
            yield service, sent, replies
        finally:
            service.close()


def test_accepted_input_is_saved_and_double_submit_does_not_invoke_twice(tmp_path):
    from analysis_agent.service import ServiceConflict
    entered, release = Event(), Event()
    def reply(request):
        entered.set()
        assert release.wait(5)
        return done()
    with service_harness(tmp_path, respond=reply) as (service, sent, _):
        doc = service.create_document('前端工程師')['id']
        try:
            run = service.submit(doc, 'req1', '我製作網站。')
            assert entered.wait(5)
            assert service.submit(doc, 'req1', '我製作網站。')['id'] == run['id']
            assert service.messages(doc) == [{'id': run['id'], 'role': 'user', 'text': '我製作網站。'}]
            with pytest.raises(ServiceConflict):
                service.submit(doc, 'req2', '另一个案例')
            with pytest.raises(ServiceConflict):
                service.submit(doc, 'req1', '同 key 不同文字')
        finally:
            release.set()
        service.join(doc)
        assert service.get_run(doc, run['id'])['status'] == 'completed'
        assert len(sent) == 1
        assert len([m for m in service.messages(doc) if m['role'] == 'user']) == 1


def test_service_default_does_not_cut_off_multistep_work_before_final(tmp_path):
    with service_harness(tmp_path, max_model_steps=None, max_tool_calls=None) as (service, sent, replies):
        # A registered side-effect-free tool; the scheduler is not started here.
        replies.extend([*(call('request_memory_consolidation') for _ in range(14)), done()])
        doc = service.create_document('完整回合')['id']
        run = service.submit(doc, 'one', '查回案例')
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'completed'
        assert result['outcome']['model_calls'] == 15
        assert not replies
        assert len(service.messages(doc)) == 2


def test_stop_waits_for_provider_and_does_not_execute_returned_tool(tmp_path):
    from analysis_agent.service import ServiceConflict
    entered, release = Event(), Event()
    def reply(request):
        entered.set()
        assert release.wait(5)
        return call('request_memory_consolidation')
    with service_harness(tmp_path, respond=reply) as (service, sent, _):
        doc = service.create_document('停止')['id']
        try:
            run = service.submit(doc, 'req1', '案例A')
            assert entered.wait(5)
            assert service.stop(doc, run['id'])['status'] == 'stopping'
            with pytest.raises(ServiceConflict):
                service.submit(doc, 'req2', '案例B')
        finally:
            release.set()
        service.join(doc)
        assert service.get_run(doc, run['id'])['status'] == 'cancelled'
        assert len(sent) == 1
        assert service.reader(doc).pending_consolidation_turns() == []
        service.submit(doc, 'req2', '案例B')
        service.join(doc)


def test_reopen_lost_api_reply_reconciles_checkpoint_without_paid_restart(tmp_path):
    saver = InMemorySaver()
    with service_harness(tmp_path, saver=saver) as (service, sent, _):
        doc = service.create_document('重開')['id']
        run = service.submit(doc, 'req1', '案例A')
        service.join(doc)
        # Crash window: graph is complete but the routing projection was not saved.
        service.catalog.update_run(run['id'], status='running')
    with service_harness(tmp_path, saver=saver) as (service, sent, _):
        saved = service.submit(doc, 'req1', '案例A')
        assert saved['id'] == run['id'] and saved['status'] == 'completed'
        assert not sent
        assert service.list_documents()[0]['id'] == doc


def test_transient_failure_resumes_same_input_and_persists_resume_count(tmp_path):
    saver = InMemorySaver()
    with service_harness(tmp_path, saver=saver) as (service, sent, replies):
        replies.extend(httpx.ReadTimeout('secret-free fake interruption') for _ in range(3))
        doc = service.create_document('恢复')['id']
        run = service.submit(doc, 'req1', '案例A')
        service.join(doc)
        failed = service.get_run(doc, run['id'])
        assert failed['status'] == 'interrupted' and failed['can_resume']
        assert failed['usage_complete'] is False
    with service_harness(tmp_path, saver=saver) as (service, sent, _):
        assert not sent
        service.resume(doc, run['id'])
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'completed' and result['resume_count'] == 1
        assert result['usage_complete'] is False  # lost provider usage is not zero
        assert len([m for m in service.messages(doc) if m['role'] == 'user']) == 1


def test_configuration_failure_seals_turn_and_new_input_is_allowed(tmp_path):
    from analysis_agent.service import ServiceConflict
    with service_harness(tmp_path) as (service, sent, replies):
        replies.append(httpx.Response(401, json={'error': {'message': 'SECRET provider body', 'type': 'invalid_api_key'}}))
        doc = service.create_document('配置')['id']
        run = service.submit(doc, 'req1', '案例A')
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'configuration_error' and not result['can_resume']
        assert result['outcome']['status'] == 'configuration_error'
        assert 'SECRET' not in str(result) + str(service.messages(doc))
        with pytest.raises(ServiceConflict):
            service.resume(doc, run['id'])
        service.submit(doc, 'req2', '案例B')
        service.join(doc)
        assert len(sent) == 2


def test_failed_input_save_can_retry_same_key_without_being_stuck(tmp_path, monkeypatch):
    with service_harness(tmp_path) as (service, sent, _):
        doc = service.create_document('保存失敗')['id']
        graph = service.reader(doc).graph
        update = graph.update_state
        def fail(*args, **kwargs):
            raise RuntimeError('injected checkpoint failure')
        monkeypatch.setattr(graph, 'update_state', fail)
        with pytest.raises(RuntimeError, match='checkpoint failure'):
            service.submit(doc, 'one', '案例')
        assert not sent
        monkeypatch.setattr(graph, 'update_state', update)
        retried = service.submit(doc, 'one', '案例')
        service.join(doc)
        assert service.get_run(doc, retried['id'])['status'] == 'completed'
        assert len(service.catalog.runs(doc)) == 1


def test_saved_input_without_worker_is_recovered_not_appended_twice(tmp_path, monkeypatch):
    with service_harness(tmp_path) as (service, sent, _):
        doc = service.create_document('回覆遺失')['id']
        launch = service._launch
        def fail(*args):
            raise RuntimeError('injected before worker launch')
        monkeypatch.setattr(service, '_launch', fail)
        with pytest.raises(RuntimeError, match='before worker'):
            service.submit(doc, 'one', '案例')
        row = service.catalog.runs(doc)[0]
        state = service.reader(doc).graph.get_state({'configurable': {'thread_id': doc}}, subgraphs=True)
        assert service.get_run(doc, row['id'])['can_resume'], (service.get_run(doc, row['id']), state)
        monkeypatch.setattr(service, '_launch', launch)
        service.resume(doc, row['id'])
        service.join(doc)
        assert len(sent) == 1 and len([m for m in service.messages(doc) if m['role'] == 'user']) == 1


def test_explicit_abandon_preserves_original_employee_message(tmp_path):
    with service_harness(tmp_path) as (service, sent, replies):
        doc = service.create_document('不再恢復')['id']
        replies.extend(httpx.ReadTimeout('offline') for _ in range(3))
        first = service.submit(doc, 'one', '案例A')
        service.join(doc)
        second = service.submit(doc, 'two', '案例B', abandon_pending=True)
        service.join(doc)
        assert service.get_run(doc, first['id'])['status'] == 'cancelled'
        assert service.get_run(doc, second['id'])['status'] == 'completed'
        assert [m['text'] for m in service.messages(doc) if m['role'] == 'user'] == ['案例A', '案例B']


def test_shutdown_joins_inflight_provider_before_client_can_close(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    entered, release = Event(), Event()
    def reply(request):
        entered.set()
        assert release.wait(5)
        return done()
    with service_harness(tmp_path, respond=reply) as (service, sent, _):
        doc = service.create_document('關閉')['id']
        run = service.submit(doc, 'one', '案例')
        assert entered.wait(5)
        with ThreadPoolExecutor(max_workers=1) as pool:
            closing = pool.submit(service.close)
            try:
                assert not closing.done()
            finally:
                release.set()
            closing.result(timeout=5)
        assert service.get_run(doc, run['id'])['status'] in {'cancelled', 'completed'}


def test_stop_saved_input_before_child_exists_and_restart_remembers_stop(tmp_path, monkeypatch):
    saver = InMemorySaver()
    with service_harness(tmp_path, saver=saver) as (service, sent, _):
        doc = service.create_document('未啟動就停止')['id']
        def fail(*args):
            raise RuntimeError('injected before worker')
        monkeypatch.setattr(service, '_launch', fail)
        with pytest.raises(RuntimeError):
            service.submit(doc, 'one', '案例')
        row = service.catalog.runs(doc)[0]
        service.catalog.update_run(row['id'], status='stopping')
    with service_harness(tmp_path, saver=saver) as (service, sent, _):
        assert service.get_run(doc, row['id'])['status'] == 'cancelled'
        assert [m['text'] for m in service.messages(doc)] == ['案例']
        assert not sent


def test_completed_usage_is_reported_from_real_provider_metadata(tmp_path):
    with service_harness(tmp_path) as (service, sent, replies):
        answer = done()
        answer['usage'] = {'input_tokens': 31, 'output_tokens': 17, 'total_tokens': 48,
                          'input_tokens_details': {'cached_tokens': 11},
                          'output_tokens_details': {'reasoning_tokens': 12}}
        replies.append(answer)
        doc = service.create_document('用量')['id']
        run = service.submit(doc, 'one', '案例')
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['usage']['input_tokens'] == 31
        assert result['usage']['output_tokens'] == 17
        assert result['usage']['total_tokens'] == 48
        assert result['usage_complete']


def test_stop_after_transport_failure_does_not_offer_unwanted_resume(tmp_path):
    entered, release = Event(), Event()
    def reply(request):
        entered.set()
        assert release.wait(5)
        raise httpx.ReadTimeout('offline')
    with service_harness(tmp_path, respond=reply) as (service, sent, _):
        doc = service.create_document('停止但網路也錯誤')['id']
        run = service.submit(doc, 'one', '案例')
        try:
            assert entered.wait(5)
            service.stop(doc, run['id'])
        finally:
            release.set()
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'cancelled' and not result['can_resume']
        assert result['outcome']['status'] == 'cancelled'


def test_provider_timeout_reaches_actual_http_request():
    from analysis_agent.provider import build_model
    sent = []
    def reply(request):
        sent.append(request)
        return httpx.Response(200, json=done())
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client, request_timeout=13)
        model.invoke('offline')
        assert sent[0].extensions['timeout']['read'] == 13
        assert sent[0].extensions['timeout']['connect'] == 13


@pytest.mark.parametrize('action', ['repeat', 'stop'])
def test_unsaved_old_request_cannot_acknowledge_or_stop_another_live_run(tmp_path, monkeypatch, action):
    from analysis_agent.service import ServiceConflict
    entered, release = Event(), Event()
    def reply(request):
        entered.set()
        assert release.wait(5)
        return done()
    with service_harness(tmp_path, respond=reply) as (service, sent, _):
        doc = service.create_document('未保存的舊請求')['id']
        graph = service.reader(doc).graph
        update = graph.update_state
        def fail(*args, **kwargs):
            raise RuntimeError('injected save failure')
        monkeypatch.setattr(graph, 'update_state', fail)
        with pytest.raises(RuntimeError):
            service.submit(doc, 'old', '未接收')
        old = service.catalog.runs(doc)[0]
        monkeypatch.setattr(graph, 'update_state', update)
        current = service.submit(doc, 'new', '已接收')
        try:
            assert entered.wait(5)
            if action == 'repeat':
                with pytest.raises(ServiceConflict):
                    service.submit(doc, 'old', '未接收')
            else:
                assert service.stop(doc, old['id'])['status'] == 'not_received'
            state = graph.get_state({'configurable': {'thread_id': doc}}, subgraphs=True)
            assert state.next and not state.values.get('closed_turns', {}).get(current['id'])
            assert not service._context(doc).stop.is_set()
            assert old['id'] not in [m.id for m in state.values['messages']]
        finally:
            release.set()
        service.join(doc)
        assert service.get_run(doc, current['id'])['status'] == 'completed'


def test_exhausted_tool_quota_still_allows_resuming_final_model_answer(tmp_path):
    with service_harness(tmp_path, max_tool_calls=1, max_model_steps=3) as (service, sent, replies):
        replies.append(call('request_memory_consolidation'))
        replies.extend(httpx.ReadTimeout('offline') for _ in range(3))
        doc = service.create_document('工具用完但能回答')['id']
        run = service.submit(doc, 'one', '案例')
        service.join(doc)
        assert service.get_run(doc, run['id'])['can_resume']
        service.resume(doc, run['id'])
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'completed'
        assert result['outcome']['model_calls'] == 2 and result['outcome']['tool_calls'] == 1


def test_stop_after_model_hooks_prevents_tool_entry(tmp_path, monkeypatch):
    from langchain.agents.middleware import ToolCallLimitMiddleware
    entered, release = Event(), Event()
    original = ToolCallLimitMiddleware.after_model
    def gate(self, state, runtime):
        result = original(self, state, runtime)
        entered.set()
        assert release.wait(5)
        return result
    monkeypatch.setattr(ToolCallLimitMiddleware, 'after_model', gate)
    with service_harness(tmp_path) as (service, sent, replies):
        replies.append(call('request_memory_consolidation'))
        doc = service.create_document('工具入口停止')['id']
        run = service.submit(doc, 'one', '案例')
        try:
            assert entered.wait(5)
            service.stop(doc, run['id'])
        finally:
            release.set()
        service.join(doc)
        assert service.get_run(doc, run['id'])['status'] == 'cancelled'
        assert service.reader(doc).pending_consolidation_turns() == []
        assert len(sent) == 1


@pytest.mark.parametrize('code', ['credit_balance_exhausted', 'organization_spend_limit_exceeded',
    'project_spend_limit_exceeded', 'organization_usage_limit_exceeded', 'insufficient_quota', None])
def test_billing_errors_do_not_offer_manual_resume(tmp_path, code):
    from analysis_agent.service import ServiceConflict
    saver = InMemorySaver()
    with service_harness(tmp_path, saver=saver) as (service, sent, replies):
        replies.append(httpx.Response(429, headers={'x-should-retry': 'false'}, json={
            'error': {'message': 'PRIVATE billing body', 'type': 'insufficient_quota', 'code': code}}))
        doc = service.create_document('帳務錯誤')['id']
        run = service.submit(doc, 'one', '案例')
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'configuration_error' and not result['can_resume']
        assert result['error_code'] == 'billing_error'
        assert result['outcome']['status'] == 'configuration_error'
        assert 'PRIVATE' not in str(result)
        assert len(sent) == 1  # SDK's server-directed no-retry is unchanged
    with service_harness(tmp_path, saver=saver) as (service, sent, _):
        with pytest.raises(ServiceConflict):
            service.resume(doc, run['id'])
        assert not sent
