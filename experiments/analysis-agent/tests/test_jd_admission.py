"""Manual bindings never create a conversation turn or permit an early writer."""
from copy import deepcopy
from types import SimpleNamespace
from threading import Event
from uuid import uuid4
import pytest
from test_service import service_harness
from test_jd_postgres import jd, prepared


@pytest.mark.parametrize('closed_turn', [False, True])
def test_root_only_manual_binding_preserves_messages_and_first_true_input(tmp_path, closed_turn):
    import analysis_agent.conversation as conversation
    assert hasattr(conversation, 'save_manual_pending'), 'Root-only manual identity is missing'
    with service_harness(tmp_path) as (service, sent, _):
        document = service.create_document('手改首次文件')['id']
        if closed_turn:
            service.submit(document, 'first', '之前真正訪談'); service.join(document)
        context = service._context(document)
        before = deepcopy(context.graph.get_state(context.config))
        count = len(sent)
        descriptor = {'operation': str(uuid4()), 'base': str(uuid4()), 'digest': 'a'*64,
                      'request_key': str(uuid4()), 'origin': 'manual'}
        conversation.save_manual_pending(context.graph, context.config, descriptor)
        after = context.graph.get_state(context.config)
        assert not after.next and after.values['jd_manual_pending'] == descriptor
        # First official checkpoint materializes neutral reducer defaults.
        for name, default in (('messages', []), ('turn_outcome', None), ('closed_turns', {})):
            assert after.values.get(name, default) == before.values.get(name, default)
        assert len(sent) == count
        conversation.save_manual_pending(context.graph, context.config, None)
        service.submit(document, 'next', '第一則或接續的真實輸入'); service.join(document)
        assert len(sent) == count + 1
        assert context.graph.get_state(context.config).values.get('jd_manual_pending') is None


def test_stop_after_native_cleanup_does_not_publish_computed_candidate():
    from analysis_agent.jd_contract import manual_intent, revision_ref
    from analysis_agent.jd_types import JdScope, JdRevision, JdCandidate
    from analysis_agent.jd_service import JdService
    from analysis_agent.jd_engine import JdNativeCalls
    scope, marker, stop, publications = JdScope('manual'), object(), Event(), []
    base = JdRevision(scope, uuid4(), None, 'initial', [{'id':'p','type':'p','children':[{'text':''}]}])
    intent = manual_intent(scope, {'request_key':str(uuid4()), 'base_revision_ref':revision_ref(scope,base.id),
        'value':[{'id':'p','type':'p','children':[{'text':'candidate'}]}]})
    def compute(value, **kwargs):
        stop.set()
        return JdCandidate(value, [], [])
    def publish(intent, candidate=None, **kwargs):
        publications.append((candidate, kwargs))
        return kwargs.get('error')
    service = JdService(SimpleNamespace(engine=marker, receipt=lambda *a:None,
        current=lambda *a:base, revision=lambda *a:base, publish=publish),
        SimpleNamespace(validate_value=compute), SimpleNamespace(engine=marker))
    import inspect
    assert 'cancel' in inspect.signature(service.manual_save).parameters, 'Manual cancel admission missing'
    outcome = service.manual_save(intent, cancel=stop, native_calls=JdNativeCalls())
    assert outcome.status == 'save_failed' and outcome.durability == 'confirmed'
    assert len(publications) == 1 and publications[0][0] is None


def test_manual_descriptor_precedes_native_and_other_document_keeps_working(jd, tmp_path, monkeypatch):
    from threading import Thread
    from analysis_agent.service import ServiceConflict
    from analysis_agent.jd_contract import manual_operation_id
    intent = prepared(jd)
    # prepared uses an opaque UUID operation derived from its request key.
    request_key = str(uuid4())
    from analysis_agent.jd_contract import manual_intent, revision_ref
    intent = manual_intent(intent.scope, {'request_key':request_key,
        'base_revision_ref':revision_ref(intent.scope,intent.base_id),'value':intent.value})
    entered, release, results = Event(), Event(), []
    with service_harness(tmp_path, engine=jd.catalog.engine) as (service,sent,_):
        service.jd = jd
        assert hasattr(service,'save_manual'), 'Manual/run admission must share the service owner'
        other = service.create_document('另份文件')['id']
        context = service._context(intent.scope.document_id)
        original = jd.engine.validate_value
        def wait_native(value, **kwargs):
            pending = context.graph.get_state(context.config).values['jd_manual_pending']
            assert pending == {'operation':str(intent.operation_id),'base':str(intent.base_id),
                'digest':intent.digest,'request_key':request_key,'origin':'manual'}
            assert 'value' not in pending
            assert kwargs['native_calls'] is context.native_calls
            entered.set(); assert release.wait(10)
            return original(value, **kwargs)
        monkeypatch.setattr(jd.engine,'validate_value',wait_native)
        thread = Thread(target=lambda:results.append(service.save_manual(intent,request_key)))
        thread.start()
        try:
            assert entered.wait(5)
            with pytest.raises(ServiceConflict):
                service.submit(intent.scope.document_id,'forbidden','同文件不能進AI')
            with pytest.raises(ServiceConflict):
                service.update_document(intent.scope.document_id,{'command':'set_archived','archived':True,'expected_metadata_version':1})
            service.submit(other,'allowed','另一文件可訪談'); service.join(other)
            assert len(sent) == 1
        finally:
            release.set(); thread.join(10)
        assert not thread.is_alive() and results[0].status=='committed'
        assert context.graph.get_state(context.config).values['jd_manual_pending'] is None
        assert service.save_manual(intent,request_key)==results[0]


def test_actual_pg_root_descriptor_survives_reply_loss_without_candidate_or_fake_input(jd,tmp_path,monkeypatch):
    import os
    from langgraph.checkpoint.postgres import PostgresSaver
    from analysis_agent.jd_contract import manual_intent,revision_ref
    from analysis_agent.windows_lifecycle import require_bootstrap
    from analysis_agent.service import AnalysisService
    intent = prepared(jd)
    key = str(uuid4())
    intent = manual_intent(intent.scope,{'request_key':key,'base_revision_ref':revision_ref(intent.scope,intent.base_id),'value':intent.value})
    with PostgresSaver.from_conn_string(os.environ['Q019_TEST_DATABASE_URL']) as saver:
        saver.setup()
        with service_harness(tmp_path,engine=jd.catalog.engine,saver=saver) as (service,sent,_):
            service.jd=jd
            context=service._context(intent.scope.document_id)
            before=context.graph.get_state(context.config)
            original=context.graph.update_state
            def lost(config,values,**kwargs):
                result=original(config,values,**kwargs)
                if values.get('jd_manual_pending'):
                    raise RuntimeError('root descriptor stored, reply lost')
                return result
            monkeypatch.setattr(context.graph,'update_state',lost)
            native=[]
            monkeypatch.setattr(jd.engine,'validate_value',lambda *a,**kw:native.append(a))
            with pytest.raises(RuntimeError,match='reply lost'):
                service.save_manual(intent,key)
            saved=context.graph.get_state(context.config)
            assert not saved.next and saved.values['messages']==[] and saved.values['closed_turns']=={}
            assert saved.values.get('turn_outcome') is None and not native and not sent
            print('Root-only actual PG:',{'before':before.values,'after':saved.values,'next':saved.next,'provider_attempts':len(sent)})
            fresh=AnalysisService(catalog=service.catalog,saver=saver,model=service.model,instructions='offline',jd=jd,lifecycle=require_bootstrap())
            try:
                fresh.start()
                recovered=fresh._context(intent.scope.document_id).graph.get_state(context.config)
                assert recovered.values.get('jd_manual_pending') is None, 'Startup must enumerate persisted manual admission without browser cache'
                terminal=jd.store.receipt(intent.scope,intent.operation_id,intent.digest)
                assert terminal.status=='save_failed' and terminal.durability=='confirmed'
                assert not native and not sent and not fresh.catalog.runs(intent.scope.document_id)
            finally:
                fresh.close()


def test_selection_wait_does_not_hold_other_document_admission(jd,tmp_path,monkeypatch):
    from threading import Thread
    from analysis_agent.jd_contract import revision_ref
    intent=prepared(jd)
    assert jd.manual_save(intent).status=='committed'
    base=jd.store.current(intent.scope).id
    entered,release,other_done=Event(),Event(),Event()
    errors=[]
    with service_harness(tmp_path,engine=jd.catalog.engine) as (service,sent,_):
        service.jd=jd
        other=service.create_document('Selection sibling')['id']
        original=jd.engine.selection
        def paused(*args,**kwargs):
            entered.set(); assert release.wait(10)
            return original(*args,**kwargs)
        monkeypatch.setattr(jd.engine,'selection',paused)
        def selected():
            try:
                service.submit(intent.scope.document_id,'selection','原選取',jd_selection={
                    'base_revision_ref':revision_ref(intent.scope,base),
                    'range':{'anchor':{'path':[0,0],'offset':0},'focus':{'path':[0,0],'offset':1}}})
            except Exception as exc: errors.append(exc)
        worker=Thread(target=selected);worker.start()
        sibling=Thread(target=lambda:(service.submit(other,'sibling','另一文件'),other_done.set()))
        try:
            assert entered.wait(5)
            sibling.start()
            assert other_done.wait(3),'A selection must not hold the global admission lock'
        finally:
            release.set();worker.join(10);sibling.join(10)
        assert not errors
        service.join(intent.scope.document_id);service.join(other)


@pytest.mark.parametrize('entry',['manual','read','selection','create'])
def test_close_signals_and_drains_every_native_app_entry(jd,tmp_path,monkeypatch,entry):
    from threading import Thread
    from analysis_agent.jd_contract import manual_intent,revision_ref
    from analysis_agent.jd_routes import read_document,locator
    intent=prepared(jd)
    assert jd.manual_save(intent).status=='committed'
    base=jd.store.current(intent.scope)
    key=str(uuid4())
    intent=manual_intent(intent.scope,{'request_key':key,'base_revision_ref':revision_ref(intent.scope,base.id),'value':intent.value})
    entered,unwound=Event(),Event()
    outcomes=[]
    with service_harness(tmp_path,engine=jd.catalog.engine) as (service,sent,_):
        service.jd=jd
        context=service._context(intent.scope.document_id)
        name='selection' if entry in {'selection','read'} else 'validate_value'
        original=getattr(jd.engine,name)
        def waiting(*args,**kwargs):
            entered.set()
            assert kwargs.get('cancel') is not None,'Each entry must carry its App shutdown signal'
            assert kwargs['cancel'].wait(5),'App close must signal this native entry'
            try: return original(*args,**kwargs)
            finally: unwound.set()
        monkeypatch.setattr(jd.engine,name,waiting)
        def work():
            try:
                if entry=='manual': result=service.save_manual(intent,key)
                elif entry=='read': result=read_document(service,intent.scope,{'selection_ref':locator(intent.scope,'selection',revision=str(base.id),
                    range={'anchor':{'path':[0,0],'offset':0},'focus':{'path':[0,0],'offset':1}})})
                elif entry=='create': result=service.create_document('shutdown-create',request_key=str(uuid4()))
                else: result=service.submit(intent.scope.document_id,'shutdown-select','原句',jd_selection={
                    'base_revision_ref':revision_ref(intent.scope,base.id),
                    'range':{'anchor':{'path':[0,0],'offset':0},'focus':{'path':[0,0],'offset':1}}})
                outcomes.append(result)
            except Exception as exc: outcomes.append(type(exc).__name__)
        worker=Thread(target=work);worker.start()
        assert entered.wait(5)
        service.close()
        worker.join(5)
        assert unwound.is_set() and not worker.is_alive()
        assert not service.accepting and not context.active_entries and not service.create_active
        assert context.native_calls.quiescent and service.create_calls.quiescent
        assert not context.graph.get_state(context.config).values.get('jd_manual_pending')
        assert not service.catalog.runs(intent.scope.document_id) and not sent
