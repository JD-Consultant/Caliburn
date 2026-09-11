"""NL08: fresh managed App, actual PG/Saver/Node; only fault boundaries are injected."""
import json
import os
import sys

from analysis_agent.windows_lifecycle import bootstrap
lifecycle = bootstrap()
print(json.dumps({'bootstrap':lifecycle.diagnostics}),flush=True)

# No DB, client or native construction can precede the product bootstrap.
from contextlib import ExitStack
import subprocess
from threading import Event,Thread
import httpx
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from analysis_agent.catalog import Catalog
from analysis_agent.jd_contract import manual_intent,outcome_to_wire
from analysis_agent.jd_engine import JdEngine
from analysis_agent.jd_service import JdService
from analysis_agent.jd_store import JdStore
from analysis_agent.jd_types import JdScope
from analysis_agent.provider import build_model
from analysis_agent.service import AnalysisService

request = json.loads(sys.stdin.readline())
params = conninfo_to_dict(os.environ['Q019_TEST_DATABASE_URL'])
assert params['dbname']=='q019_jd_app_20260910' and params['host']=='127.0.0.1'
counts={'native':0,'provider':0}
def forbidden(request):
    counts['provider']+=1
    raise AssertionError('This original manual recovery must never call a provider')
def crash(stage,**data):
    print(json.dumps({'barrier':stage,**data,'counts':counts}),flush=True)
    os._exit(73)

with ExitStack() as stack:
    engine=create_engine(URL.create('postgresql+psycopg'),connect_args=params,hide_parameters=True)
    stack.callback(engine.dispose)
    saver=stack.enter_context(PostgresSaver.from_conn_string(os.environ['Q019_TEST_DATABASE_URL']))
    client=stack.enter_context(httpx.Client(transport=httpx.MockTransport(forbidden)))
    model=build_model(model='gpt-5.6-luna',api_key='offline',http_client=client)
    native=JdEngine()
    jd=JdService(JdStore(engine),native,Catalog(engine))
    service=AnalysisService(catalog=jd.catalog,saver=saver,model=model,instructions='offline',jd=jd,lifecycle=lifecycle)
    actual=subprocess.Popen
    sibling_started=Event()
    sibling_children=[]
    def launch(argv,**kwargs):
        counts['native']+=1
        suspended=request['mode']=='native' or (request['mode']=='two_documents' and argv[-1]=='read-selection')
        if suspended:
            # The genuine fixed Node child is outstanding at API crash, before response.
            kwargs['creationflags'] |= 0x4  # CREATE_SUSPENDED; product Job owns its termination.
        child=actual(argv,**kwargs)
        if request['mode']=='two_documents' and suspended:
            sibling_children.append(child.pid)
            sibling_started.set()
        if request['mode']=='native':
            crash('native_outstanding',child=child.pid,command=argv)
        return child
    subprocess.Popen=launch
    service.start()
    if request['mode'] in {'create_before_commit','create_after_commit','create_retry'}:
        if request['mode']!='create_retry':
            commit=engine.dialect.do_commit
            def create_boundary(connection):
                if request['mode']=='create_before_commit': crash('create_before_commit')
                commit(connection)
                crash('create_after_commit')
            engine.dialect.do_commit=create_boundary
        created=service.create_document('NL13 exact create',request_key=request['key'])
        repeated=service.create_document('NL13 exact create',request_key=request['key'])
        assert repeated['id']==created['id']
        print(json.dumps({'created':created['id'],'counts':counts,'runs':service.catalog.runs(created['id'])}),flush=True)
        service.close()
        raise SystemExit(0)
    scope=JdScope(request['document'])
    key=request['key']
    if request['mode']=='recover':
        result=service.manual_recovery(scope.document_id,key)
        if result.get('result'): result['result']=outcome_to_wire(result['result'])
        state=service._context(scope.document_id).graph.get_state({'configurable':{'thread_id':scope.document_id}})
        print(json.dumps({'recovery':result,'counts':counts,'next':state.next,
            'pending':state.values.get('jd_manual_pending'),'messages':len(state.values.get('messages',[])),
            'runs':len(service.catalog.runs(scope.document_id))}),flush=True)
    else:
        intent=manual_intent(scope,request['body'])
        if request['mode']=='two_documents':
            from analysis_agent.jd_types import JdReadQuery
            sibling_scope=JdScope(request['sibling'])
            def read_sibling():
                with service.jd_read_entry(sibling_scope.document_id) as context:
                    jd.read(sibling_scope,JdReadQuery(selection={
                        'anchor':{'path':[0,0],'offset':0},'focus':{'path':[0,0],'offset':1}}),
                        cancel=context.read_stop,native_calls=context.native_calls)
            thread=Thread(target=read_sibling);thread.start()
            assert sibling_started.wait(5)
        if request['mode']=='after_native':
            validate=native.validate_value
            def completed(*args,**kwargs):
                result=validate(*args,**kwargs)
                crash('native_complete_before_publish',quiet=kwargs['native_calls'].quiescent)
                return result
            native.validate_value=completed
        if request['mode']=='before_head_lock':
            from sqlalchemy import text
            import time
            execute=jd.store._execute
            def blocked_before_head(connection,deadline,statement,params=None):
                if getattr(statement,'_for_update_arg',None) is not None:
                    own_pid=connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
                    def observe_wait():
                        until=time.monotonic()+5
                        with engine.connect() as observer:
                            while time.monotonic()<until:
                                event=observer.execute(text('SELECT wait_event FROM pg_stat_activity WHERE pid=:pid'),{'pid':own_pid}).scalar_one()
                                observer.rollback()
                                if event=='PgSleep':
                                    crash('old_writer_statement_before_head_lock_blocked',later_mutations_sent=0)
                                time.sleep(.01)
                        raise AssertionError('Own PG pre-lock wait was not observed')
                    Thread(target=observe_wait,daemon=True).start()
                    connection.execute(text('SELECT pg_sleep(30)'))
                return execute(connection,deadline,statement,params)
            jd.store._execute=blocked_before_head
        if request['mode'] in {'before_commit','after_commit'}:
            commit=engine.dialect.do_commit
            def boundary(connection):
                if request['mode']=='before_commit': crash('transaction_before_commit')
                commit(connection)
                crash('transaction_committed_before_reply')
            engine.dialect.do_commit=boundary
        outcome=service.save_manual(intent,key)
        if request['mode']=='two_documents':
            assert outcome.status=='committed'
            sibling=service._context(request['sibling'])
            assert sibling.active_entries and not sibling.native_calls.quiescent
            crash('a_committed_b_native_pending',sibling_children=sibling_children,
                sibling_owner=sibling.native_calls.snapshot(),original=outcome_to_wire(outcome))
        print(json.dumps({'saved':outcome_to_wire(outcome),'counts':counts}),flush=True)
    service.close()
