"""MT01–10: App-only key recovery, consistent server gate, no replay."""
from contextlib import contextmanager
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from test_service import service_harness
from test_jd_postgres import jd,prepared
from analysis_agent.jd_contract import manual_intent,revision_ref
from analysis_agent.conversation import save_manual_pending


@contextmanager
def recovery_client(jd,tmp_path):
    from analysis_agent.api import create_app
    @contextmanager
    def resources():
        with service_harness(tmp_path,engine=jd.catalog.engine) as (service,sent,_):
            service.jd=jd
            service.test_sent=sent
            yield service
    with TestClient(create_app(resources),base_url='http://127.0.0.1:8091') as client:
        yield client,client.app.state.service


def pending(jd,service):
    intent=prepared(jd)
    key=str(uuid4())
    intent=manual_intent(intent.scope,{'request_key':key,'base_revision_ref':revision_ref(intent.scope,intent.base_id),'value':intent.value})
    context=service._context(intent.scope.document_id)
    descriptor={'operation':str(intent.operation_id),'base':str(intent.base_id),'digest':intent.digest,'request_key':key,'origin':'manual'}
    save_manual_pending(context.graph,context.config,descriptor)
    return intent,key,context,descriptor


def test_get_only_observes_and_explicit_original_key_closes_known_none(jd,tmp_path,monkeypatch):
    with recovery_client(jd,tmp_path) as (client,service):
        intent,key,context,descriptor=pending(jd,service)
        path=f'/documents/{intent.scope.document_id}/jd/manual-recovery'
        before=context.graph.get_state(context.config)
        native=[]
        monkeypatch.setattr(jd.engine,'validate_value',lambda *a,**kw:native.append(a))
        found=client.get(path)
        assert found.status_code==200,found.text
        assert found.headers['cache-control']=='no-store'
        assert found.json()=={'status':'unknown','request_key':key,'write_blocked':True,'can_recover':True,'restart_required':False}
        assert context.graph.get_state(context.config).config==before.config
        assert jd.store.receipt(intent.scope,intent.operation_id) is None
        recovered=client.post(path,json={'request_key':key})
        assert recovered.status_code==200,recovered.text
        result=recovered.json()
        assert result['status']=='available' and result['result']['status']=='save_failed'
        assert not result['write_blocked'] and not result['can_recover']
        assert client.get(path,params={'request_key':key}).json()==result
        assert context.graph.get_state(context.config).values['jd_manual_pending'] is None
        assert not native and not service.test_sent


def test_old_key_never_clears_current_pending_and_active_post_does_not_take_over(jd,tmp_path):
    with recovery_client(jd,tmp_path) as (client,service):
        intent,key,context,descriptor=pending(jd,service)
        path=f'/documents/{intent.scope.document_id}/jd/manual-recovery'
        other=str(uuid4())
        result=client.post(path,json={'request_key':other})
        assert result.status_code==200,result.text
        assert result.json()=={'status':'no_pending','request_key':other,'write_blocked':True,'can_recover':False,'restart_required':False}
        assert context.graph.get_state(context.config).values['jd_manual_pending']==descriptor
        context.manual_active=True; context.active_entries=1
        try:
            assert client.get(path).json()['can_recover'] is False
            assert client.post(path,json={'request_key':key}).status_code==409
        finally:
            context.manual_active=False; context.active_entries=0


def test_terminal_clear_failure_preserves_result_and_matching_cleanup_exit(jd,tmp_path,monkeypatch):
    with recovery_client(jd,tmp_path) as (client,service):
        intent,key,context,descriptor=pending(jd,service)
        terminal=jd.manual_save(intent)
        assert terminal.status=='committed'
        path=f'/documents/{intent.scope.document_id}/jd/manual-recovery'
        original=context.graph.update_state
        def cannot_clear(config,value,**kwargs):
            if 'jd_manual_pending' in value and value['jd_manual_pending'] is None:
                raise RuntimeError('clear failed')
            return original(config,value,**kwargs)
        monkeypatch.setattr(context.graph,'update_state',cannot_clear)
        observed=client.get(path)
        assert observed.status_code==200,observed.text
        context.manual_active=True
        try:
            active=client.post(path,json={'request_key':key})
            assert active.status_code==200 and active.json()['status']=='available'
            assert active.json()['write_blocked'] and not active.json()['can_recover']
        finally:
            context.manual_active=False
        first=client.post(path,json={'request_key':key}).json()
        assert first['status']=='available' and first['result']['status']=='committed'
        assert first['write_blocked'] and first['can_recover']
        monkeypatch.setattr(context.graph,'update_state',original)
        second=client.post(path,json={'request_key':key}).json()
        assert second['result']==first['result'] and not second['write_blocked']
        assert not second['can_recover']


def test_retained_native_unknown_and_competing_recovery_is_one_attempt(jd,tmp_path,monkeypatch):
    from threading import Event,Thread
    with recovery_client(jd,tmp_path) as (client,service):
        intent,key,context,descriptor=pending(jd,service)
        path=f'/documents/{intent.scope.document_id}/jd/manual-recovery'
        token,call=context.native_calls.register(lambda process:False,.01)
        entered,release=Event(),Event()
        calls=[];results=[]
        cleanup=context.native_calls.cleanup
        def held():
            calls.append(token);entered.set();assert release.wait(5)
            return cleanup()
        monkeypatch.setattr(context.native_calls,'cleanup',held)
        first=Thread(target=lambda:results.append(client.post(path,json={'request_key':key})))
        first.start()
        try:
            assert entered.wait(5)
            assert client.post(path,json={'request_key':key}).status_code==409
        finally:
            release.set();first.join(5)
        assert len(calls)==1 and results[0].json()['status']=='unknown'
        assert context.graph.get_state(context.config).values['jd_manual_pending']==descriptor
        assert jd.store.receipt(intent.scope,intent.operation_id) is None
        call.ready=True
        monkeypatch.setattr(context.native_calls,'cleanup',cleanup)
        assert client.post(path,json={'request_key':key}).json()['result']['status']=='save_failed'


def test_archive_does_not_hide_original_result_and_errors_never_report_absence(jd,tmp_path,monkeypatch):
    with recovery_client(jd,tmp_path) as (client,service):
        intent,key,context,_=pending(jd,service)
        service.catalog.update_document(intent.scope.document_id,{'command':'set_archived','archived':True,'expected_metadata_version':1})
        path=f'/documents/{intent.scope.document_id}/jd/manual-recovery'
        result=client.post(path,json={'request_key':key})
        assert result.status_code==200 and result.json()['status']=='available'
        assert result.json()['write_blocked'] and not result.json()['can_recover']
        assert client.post(path,json={'request_key':key,'value':[]}).status_code==422
        original=jd.store.receipt
        def unavailable(*args,**kwargs): raise RuntimeError('DB unavailable')
        monkeypatch.setattr(jd.store,'receipt',unavailable)
        assert client.get(path,params={'request_key':key}).status_code==503
        monkeypatch.setattr(jd.store,'receipt',original)
