"""R06 narrow pure fixture, actual frozen stop/close methods; no DB/native."""
import ast
import json
from pathlib import Path
from threading import RLock,Condition,Event,Thread
from types import SimpleNamespace as Obj

path=Path('.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-5-fix1-snapshot/experiments/analysis-agent/src/analysis_agent/service.py')
root=ast.parse(path.read_text(encoding='utf-8-sig'))
cls=next(n for n in root.body if isinstance(n,ast.ClassDef) and n.name=='AnalysisService')
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'stop','close'}]
class PublicationUncertain(Exception):pass
class ServiceConflict(Exception):pass
ns={'PublicationUncertain':PublicationUncertain,'ServiceConflict':ServiceConflict,
    'current_values':lambda snapshot:snapshot.values,'pending_input_id':lambda snapshot:'run-A'}
exec(compile(ast.Module(body=methods,type_ignores=[]),str(path),'exec'),ns)
snapshot=Obj(next=('analysis',),values={})
owner=Obj(cleanup=lambda:True)
context=Obj(graph=Obj(get_state=lambda *a,**kw:snapshot),config={},closing=False,close_entries=0,
    generation=0,active_entries=0,stop=Event(),read_stop=Event(),native_calls=owner,jd_session=None)
lock=RLock()
row={'id':'run-A','status':'interrupted'}
service=Obj(lock=lock,entries_changed=Condition(lock),accepting=True,contexts={'A':context},
    create_stop=Event(),create_active=0,create_calls=owner,scheduler=None,jd=None,
    executor=Obj(shutdown=lambda **kw:None),_context=lambda d:context,_running=lambda d:False,
    catalog=Obj(run=lambda *a:row,update_run=lambda *a,**kw:row),_reconcile=lambda row:None)
def seal(context):snapshot.next=()
service._close_turn=seal
projection_started,release_projection=Event(),Event()
state={'get_calls':0,'resources_closed':False}
def get_run(*args):
    state['get_calls']+=1
    if state['get_calls']==2:
        state['close_entries_at_final_projection']=context.close_entries
        projection_started.set()
        assert release_projection.wait(3)
        if state['resources_closed']:raise RuntimeError('Saver/DB already disposed')
    return row
service.get_run=get_run
errors=[]
def stopping():
    try:ns['stop'](service,'A','run-A')
    except Exception as exc:errors.append(str(exc))
worker=Thread(target=stopping);worker.start()
assert projection_started.wait(3)
ns['close'](service)
state['close_returned_while_stop_projection_pending']=worker.is_alive()
state['resources_closed']=True
release_projection.set();worker.join(3)
print(json.dumps({**state,'stop_errors':errors,'worker_alive':worker.is_alive()}))
