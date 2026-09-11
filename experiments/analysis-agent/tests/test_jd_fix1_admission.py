"""R01/R04–06 actual App seams, original review counterexamples as barriers."""
from threading import Event,Thread
from uuid import uuid4
import pytest
from test_service import service_harness
from test_jd_postgres import jd,prepared
from test_jd_manual_recovery import recovery_client,pending
from analysis_agent.service import ServiceConflict
from analysis_agent.jd_contract import outcome_to_wire


def test_r01_archive_between_admission_sections_cannot_save_input(tmp_path):
    with service_harness(tmp_path) as (service,sent,_):
        document=service.create_document('archive race')['id']
        original=service.lock
        class Interleaving:
            trigger=None
            def __enter__(self): original.acquire();return self
            def __exit__(self,*args):
                original.release()
                trigger,self.trigger=self.trigger,None
                if trigger:trigger()
        lock=Interleaving();service.lock=lock
        lock.trigger=lambda:service.update_document(document,{'command':'set_archived','archived':True,'expected_metadata_version':1})
        with pytest.raises(ServiceConflict):service.submit(document,'original','must not be admitted')
        assert not service.catalog.runs(document) and not service.messages(document) and not sent


@pytest.mark.parametrize('sibling',[False,True])
def test_r05_full_original_post_preserves_terminal_if_cleanup_cannot_finish(jd,tmp_path,monkeypatch,sibling):
    with recovery_client(jd,tmp_path) as (client,service):
        intent,key,context,descriptor=pending(jd,service)
        terminal=jd.manual_save(intent)
        original=context.graph.update_state
        def clear_fails(config,value,**kwargs):
            if value.get('jd_manual_pending','missing') is None:raise RuntimeError('clear failed')
            return original(config,value,**kwargs)
        monkeypatch.setattr(context.graph,'update_state',clear_fails)
        if sibling:context.active_entries+=1
        try:
            from analysis_agent.jd_contract import revision_ref
            result=client.post(f'/documents/{intent.scope.document_id}/jd/manual-save',json={
                'request_key':key,'base_revision_ref':revision_ref(intent.scope,intent.base_id),'value':intent.value})
            assert result.status_code==200 and result.json()==outcome_to_wire(terminal)
            assert context.graph.get_state(context.config).values['jd_manual_pending']==descriptor
            assert service.manual_recovery(intent.scope.document_id,key)['write_blocked']
        finally:
            monkeypatch.setattr(context.graph,'update_state',original)
            if sibling:context.active_entries-=1


def test_r04_recovery_pg_wait_allows_other_document_admission(jd,tmp_path,monkeypatch):
    from sqlalchemy import select
    from analysis_agent.jd_store import head
    with recovery_client(jd,tmp_path) as (client,service):
        intent,key,context,_=pending(jd,service)
        other=service.create_document('independent')['id']
        connection=jd.store.engine.connect();transaction=connection.begin()
        connection.execute(select(head).where(head.c.document_id==intent.scope.document_id).with_for_update())
        entered,admitted=Event(),Event();errors=[]
        original=jd.store._execute
        def observed(connection,deadline,statement,params=None):
            if getattr(statement,'_for_update_arg',None) is not None:entered.set()
            return original(connection,deadline,statement,params)
        monkeypatch.setattr(jd.store,'_execute',observed)
        def recovery():
            try:service.recover_manual(intent.scope.document_id,key)
            except Exception as exc:errors.append(exc)
        first=Thread(target=recovery);first.start()
        second=Thread(target=lambda:(service.submit(other,'other','other doc'),admitted.set()))
        try:
            assert entered.wait(5)
            second.start()
            assert admitted.wait(2),'A head lock must not hold global admission'
        finally:
            transaction.rollback();connection.close();first.join(10);second.join(10)
        assert not errors
        service.join(other)


def test_r06_close_waits_for_admitted_recovery_then_refuses_new_attempt(jd,tmp_path,monkeypatch):
    with recovery_client(jd,tmp_path) as (client,service):
        intent,key,context,_=pending(jd,service)
        entered,release,closed=Event(),Event(),Event()
        original=context.native_calls.cleanup
        def wait_cleanup():
            if not entered.is_set():
                entered.set();assert release.wait(5)
            return original()
        monkeypatch.setattr(context.native_calls,'cleanup',wait_cleanup)
        results=[];errors=[]
        def recover():
            try:results.append(service.recover_manual(intent.scope.document_id,key))
            except Exception as exc:errors.append(exc)
        worker=Thread(target=recover);worker.start()
        assert entered.wait(5)
        closer=Thread(target=lambda:(service.close(),closed.set()));closer.start()
        try:
            assert not closed.wait(.2)
            with pytest.raises(ServiceConflict):service.recover_manual(intent.scope.document_id,key)
        finally:
            release.set();worker.join(10);closer.join(10)
        assert closed.is_set() and not context.closing
        assert not errors and len(results)==1 and not worker.is_alive() and not closer.is_alive()


def test_r03_retained_read_reports_restart_without_fabricating_run(jd,tmp_path):
    with recovery_client(jd,tmp_path) as (client,service):
        document=service.create_document('retained read')['id']
        context=service._context(document)
        token,call=context.native_calls.register(lambda process:False,.01)
        context.native_calls.finish(token)
        try:
            result=client.get(f'/documents/{document}/jd/manual-recovery').json()
            assert result['restart_required'] is True
            assert result['status']=='no_pending' and result['request_key'] is None
            assert result['write_blocked'] and not result['can_recover']
            assert service.catalog.runs(document)==[]
            assert not context.graph.get_state(context.config).values.get('jd_manual_pending')
        finally:
            call.ready=True
            context.native_calls.finish(token)


@pytest.mark.parametrize('action',['stop','abandon'])
def test_r04_foreground_closure_does_not_hold_other_document(action,tmp_path,monkeypatch):
    import httpx
    with service_harness(tmp_path) as (service,_,replies):
        document=service.create_document('interrupted')['id']
        other=service.create_document('independent')['id']
        replies.extend(httpx.ReadTimeout('offline') for _ in range(3))
        run=service.submit(document,'first','第一則');service.join(document)
        entered,release,admitted=Event(),Event(),Event();errors=[]
        original=service._close_turn
        def hold(context,**kwargs):
            if context.reader.document_id==document:
                entered.set();assert release.wait(5)
            return original(context,**kwargs)
        monkeypatch.setattr(service,'_close_turn',hold)
        def close():
            try:
                if action=='stop':service.stop(document,run['id'])
                else:service.submit(document,'second','第二則',abandon_pending=True)
            except Exception as exc:errors.append(exc)
        first=Thread(target=close);first.start()
        second=Thread(target=lambda:(service.submit(other,'independent','可繼續'),admitted.set()))
        try:
            assert entered.wait(5);second.start()
            assert admitted.wait(2)
        finally:
            release.set();first.join(10);second.join(10)
        assert not errors
        service.join(document);service.join(other)
