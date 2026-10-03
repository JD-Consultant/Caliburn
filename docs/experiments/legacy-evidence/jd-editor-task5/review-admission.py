"""Pure stdlib: execute frozen submit/update_document methods, no real services."""
import ast
import hashlib
import json
from pathlib import Path
import sys
from threading import Event
from types import SimpleNamespace, ModuleType

source = Path('.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-5-snapshot/experiments/analysis-agent/src/analysis_agent/service.py')
tree = ast.parse(source.read_text(encoding='utf-8-sig'))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AnalysisService')
selected = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in {'submit', 'update_document', 'recover_manual', 'save_manual'}]
code = ast.Module(body=selected, type_ignores=[])
class ServiceConflict(Exception): pass
contract = ModuleType('analysis_agent.jd_contract')
contract.validate = lambda name, value: value
contract.parse_ref = lambda *args: None
types = ModuleType('analysis_agent.jd_types')
types.JdScope = lambda value: value
sys.modules['analysis_agent.jd_contract'] = contract
sys.modules['analysis_agent.jd_types'] = types
ns = {'hashlib':hashlib, 'ServiceConflict':ServiceConflict,
      'HumanMessage':lambda text,id:SimpleNamespace(content=text,id=id), 'START':'START'}
exec(compile(code,str(source),'exec'), ns)
class Catalog:
    def __init__(self): self.doc={'id':'A','archived':False,'metadata_version':1};self.rows=[]
    def document(self, document): return dict(self.doc)
    def runs(self, document): return list(self.rows)
    def update_document(self, document, command):
        self.doc['archived']=command['archived'];self.doc['metadata_version']+=1
        return dict(self.doc)
    def create_run(self, document, key, digest):
        row={'id':'new-input','document_id':document,'request_key':key,'input_digest':digest,'status':'receiving'}
        self.rows.append(row);return row
class Graph:
    def __init__(self): self.messages=[]
    def get_state(self, config): return SimpleNamespace(next=(),values={'messages':self.messages})
    def update_state(self, config, values, **kwargs): self.messages.extend(values['messages'])
class InterleavingLock:
    """On first unlock schedule archive before submit's second lock acquisition."""
    def __init__(self): self.trigger=None
    def __enter__(self): pass
    def __exit__(self,*args):
        trigger,self.trigger=self.trigger,None
        if trigger: trigger()
catalog=Catalog();graph=Graph();lock=InterleavingLock()
context=SimpleNamespace(graph=graph,config={},stop=Event(),generation=0)
service=SimpleNamespace(accepting=True,catalog=catalog,lock=lock,
    _context=lambda d:context,_running=lambda d:False,_jd_busy=lambda c:False)
starts=[]
service._launch=lambda c,r:starts.append(r['id'])
service.get_run=lambda d,r:catalog.rows[-1]
lock.trigger=lambda:ns['update_document'](service,'A',{'command':'set_archived','archived':True,'expected_metadata_version':1})
result=ns['submit'](service,'A','request-A','employee input')
print(json.dumps({'case':'archive_between_submit_lock_sections','archived':catalog.doc['archived'],
    'created_runs':len(catalog.rows),'saved_inputs':len(graph.messages),'launch_calls':starts,'result':result}))

# Named risk: a potentially blocked SQL stage still occupies the global lock.
from threading import RLock, Thread
class PublicationUncertain(Exception): pass
ns['PublicationUncertain'] = PublicationUncertain
recovery_lock = RLock()
recovery_context=SimpleNamespace(closing=False,generation=0,native_calls=SimpleNamespace(cleanup=lambda:True))
recovery_service=SimpleNamespace(lock=recovery_lock,accepting=True)
descriptor={'request_key':'original-A'}
recovery_service.manual_recovery=lambda d,k:{'status':'unknown','can_recover':True}
recovery_service._context=lambda d:recovery_context
recovery_service._manual_pending=lambda c:descriptor
sql_entered,release_sql=Event(),Event()
def sql_stage(context):
    sql_entered.set()
    assert release_sql.wait(3)
recovery_service._reconcile_manual=sql_stage
errors=[]
def recovering():
    try: ns['recover_manual'](recovery_service,'A','original-A')
    except BaseException as exc: errors.append(type(exc).__name__)
worker=Thread(target=recovering);worker.start()
assert sql_entered.wait(3)
other_document_lock_available = recovery_lock.acquire(blocking=False)
if other_document_lock_available: recovery_lock.release()
release_sql.set();worker.join(3)
print(json.dumps({'case':'recovery_pg_stage_global_lock','other_document_lock_available':other_document_lock_available,'errors':errors}))

# Named risk: a saved terminal receipt is bypassed on an exact full-payload retry.
contract.validate_intent_digest=lambda intent:None
contract.manual_operation_id=lambda scope,key:'original-operation'
references=ModuleType('analysis_agent.jd_references');references.source_refs=lambda value:[]
conversation=ModuleType('analysis_agent.conversation');conversation.save_manual_pending=lambda *args:None
sys.modules['analysis_agent.jd_references']=references
sys.modules['analysis_agent.conversation']=conversation
manual_context=SimpleNamespace(manual_active=False,config={},graph=SimpleNamespace(
    get_state=lambda config:SimpleNamespace(values={'jd_manual_pending':{'request_key':'original-A','digest':'fixed-digest'}})))
receipt_reads=[]
def terminal_receipt(*args):
    receipt_reads.append(args)
    return SimpleNamespace(status='committed',durability='confirmed')
def clear_failed(context): raise PublicationUncertain('Original result is terminal but admission cleanup is unconfirmed')
manual_service=SimpleNamespace(lock=RLock(),_context=lambda d:manual_context,
    _reconcile_manual=clear_failed,jd=SimpleNamespace(store=SimpleNamespace(receipt=terminal_receipt)))
intent=SimpleNamespace(scope=SimpleNamespace(document_id='A'),operation_id='original-operation',digest='fixed-digest')
try:
    ns['save_manual'](manual_service,intent,'original-A')
    outcome='returned'
except PublicationUncertain:
    outcome='PublicationUncertain'
print(json.dumps({'case':'terminal_receipt_full_retry_clear_failed','outcome':outcome,'terminal_receipt_reads':len(receipt_reads)}))
