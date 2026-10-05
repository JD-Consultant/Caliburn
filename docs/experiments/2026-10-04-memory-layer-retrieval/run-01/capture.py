"""Current production Memory roles and parent in a dedicated PostgreSQL test schema."""
import asyncio, json, subprocess, sys, time
from dataclasses import asdict, is_dataclass
from sqlalchemy import URL
from decimal import Decimal
from uuid import uuid4
from common import *
sys.path.insert(0,str(ROOT/'apps/api/src'))
import httpx2, psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from openai.types.responses import Response
from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.memory_analysis.dispatch import MemoryRoleDispatch
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind,ExecutionScope
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings,ModelSettings
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

probe=load('layer_memory_probe',ROOT/'docs/experiments/product-validation/data/memory-compaction-publish-2026-10-04/experiment.py')
provider=load('layer_provider_observations',ROOT/'docs/experiments/product-validation/data/design-comparisons-2026-10-04/provider_observations.py')

def database_settings():
 # Credentials remain in process memory, never written to artifacts or printed.
 info=read_container('caliburn-jd-postgres-18-6')
 env=dict(x.split('=',1) for x in info['Config']['Env'] if '=' in x)
 port=info['NetworkSettings']['Ports']['5432/tcp'][0]
 assert port['HostIp']=='127.0.0.1' and port['HostPort']=='55437'
 args={'host':'127.0.0.1','port':55437,'user':env['POSTGRES_USER'],'password':env['POSTGRES_PASSWORD']}
 name='caliburn_rag_memory_test'
 with psycopg.connect(make_conninfo(dbname='postgres',**args),autocommit=True) as c:
  exists=c.execute('SELECT 1 FROM pg_database WHERE datname=%s',(name,)).fetchone()
  if not exists:c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
 schema='eval_rag_memory_'+uuid4().hex
 dump('database-isolation.json',{'host':'127.0.0.1','port':55437,'database':name,'schema':schema,'new_database':not bool(exists),'container':'caliburn-jd-postgres-18-6','production_schema_touched':False})
 url=URL.create('postgresql',username=args['user'],password=args['password'],host=args['host'],port=args['port'],database=name).render_as_string(hide_password=False)
 return DatabaseSettings(url=url,schema=schema)

async def export_snapshot(candidates,snapshot):
 objects=[]
 for layer in MemoryLayer:
  for entry in await candidates.read_snapshot_map(snapshot.job_file_id,snapshot.snapshot_id,layer):
   objects.append(asdict(await candidates.read_snapshot_object(snapshot.job_file_id,snapshot.snapshot_id,entry.object_id)))
 def normalize(x):
  if isinstance(x,(set,frozenset)):return sorted(x,key=str)
  if is_dataclass(x):return asdict(x)
  return str(x)
 return json.loads(json.dumps({'snapshot':asdict(snapshot),'objects':objects},ensure_ascii=False,default=normalize))

def read_container(name):
 return json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]

def seed(settings,file_id,messages):
 with psycopg.connect(settings.url,options=f'-c search_path={settings.schema}') as c:
  c.execute("INSERT INTO job_files(job_file_id,creation_command_id,initial_display_name,display_name,employee_name) VALUES(%s,%s,'合成檢索實驗','合成檢索實驗','合成')",(file_id,uuid4()))
  last=None
  for m in messages:
   source=uuid4()
   c.execute('INSERT INTO interview_texts(job_file_id,source_id,speaker,interview_text) VALUES(%s,%s,%s,%s)',(file_id,source,m['speaker'],m['text']))
   c.execute('INSERT INTO formal_interviews(job_file_id,interview_sequence,source_id) VALUES(%s,%s,%s)',(file_id,m['interview_sequence'],source))
   if m['speaker']=='employee':last=source
  assert last is not None
  return last

class Recorder:
 def __init__(self):
  self.case='setup';self.count=0;self.calls=0;self.spent=Decimal(0);self.reserve=Decimal(0)
  self.headers={};self.received=time.monotonic();self.started=time.monotonic();self.sent=0
  self.profile=model_profile('gpt-6-luna')
 async def request(self,req):
  assert req.url.host=='api.openai.com'
  payload=json.loads(req.content)
  if req.url.path.endswith('/responses'):
   delay=provider.admission_delay(self.headers,time.monotonic()-self.received,self.count)
   if delay>180 or time.monotonic()-self.started+delay>5400:raise asyncio.CancelledError('bounded_admission_stop')
   if delay:await asyncio.sleep(delay)
   assert payload['model']=='gpt-6-luna' and payload['store'] is False
   self.reserve=self.profile.pricing.reserve_response_cost(input_tokens=self.count,max_output_tokens=payload['max_output_tokens'])
   if self.calls>=160 or self.spent+self.reserve>Decimal('1.00'):raise asyncio.CancelledError('budget_stop')
   self.calls+=1;self.sent=time.perf_counter()
  elif not req.url.path.endswith('/input_tokens'):raise asyncio.CancelledError('unexpected_provider_path')
  append('memory-trace.jsonl',{'case_id':self.case,'event':'request','path':req.url.path,'payload':probe.public_document(payload)})
 async def response(self,res):
  await res.aread();self.headers=provider.rate_headers(res.headers);self.received=time.monotonic()
  p=res.json();append('memory-trace.jsonl',{'case_id':self.case,'event':'response','path':res.request.url.path,'http_status':res.status_code,'payload':probe.public_document(p)})
  if res.status_code!=200:
   if res.request.url.path.endswith('/responses'):
    self.spent+=self.reserve
    append('memory-usage.jsonl',{'case_id':self.case,'accounted_usd':str(self.reserve),'usage_known':False,'status_code':res.status_code})
   raise asyncio.CancelledError('provider_error_no_retry')
  if res.request.url.path.endswith('/input_tokens'):self.count=p['input_tokens']
  else:
   response=Response.model_validate(p);cost=self.profile.pricing.estimate_response_cost(response)
   accounted=cost if cost is not None else self.reserve;self.spent+=accounted
   append('memory-usage.jsonl',{'case_id':self.case,'resolved_model':response.model,'accounted_usd':str(accounted),'estimated_usd':str(cost) if cost is not None else None,'usage_known':cost is not None,'usage':p.get('usage'),'seconds':time.perf_counter()-self.sent})
   if cost is None or response.status!='completed':raise asyncio.CancelledError('incomplete_or_unknown_usage')

async def main():
 check_manifest();settings=database_settings()
 await asyncio.to_thread(probe.initialize_schema,settings)
 database=Database(settings);recorder=Recorder()
 try:
  async with httpx2.AsyncClient(event_hooks={'request':[recorder.request],'response':[recorder.response]},timeout=120) as transport:
   async with create_responses_client(api_key=read_openai_api_key(ROOT/'apps/api/.env'),timeout_seconds=120,http_client=transport) as client:
    dsn=make_conninfo(settings.url,options=f'-c search_path={settings.schema}')
    async with AsyncPostgresSaver.from_conn_string(dsn,serde=create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)) as saver:
     await saver.setup()
     model=ModelSettings(api_key='configured-by-client',max_output_tokens=8192,max_model_steps=32,max_outbound_attempts=64,max_attempts_per_request=1,turn_timeout_seconds=1800,max_cost_usd=Decimal('1.00'))
     dispatch=MemoryRoleDispatch(WorkSituationAnalystRunner(database.sessions,saver,client,model),WorkUnderstandingAnalystRunner(database.sessions,saver,client,model))
     parent=MemoryBatchWorkflow(database.sessions,run_role=dispatch);candidates=MemoryCandidateWorkflow(database.sessions)
     published=[]
     for ident,messages in read(HERE/'replay-messages.json').items():
      recorder.case=ident;file_id=uuid4();source_id=await asyncio.to_thread(seed,settings,file_id,messages)
      scope=ExecutionScope(file_id,uuid4(),ExecutionKind.MEMORY_BATCH)
      async with database.sessions.begin() as session:
       await executions.admit_execution(session,scope);writer=await executions.claim_writer(session,scope,writer_id=uuid4())
      await candidates.start(writer,source_id);tick=time.perf_counter();calls=recorder.calls;spent=recorder.spent
      snapshot=await parent.run(writer)
      fixed=await export_snapshot(candidates,snapshot)
      dump('snapshots/'+ident+'.json',fixed)
      published.append((ident,snapshot,fixed))
      append('memory-captures.jsonl',{'case_id':ident,'snapshot_id':str(snapshot.snapshot_id),'job_file_id':str(file_id),'execution_id':str(scope.execution_id),'published':True,'seconds':time.perf_counter()-tick,'model_calls':recorder.calls-calls,'accounted_usd':str(recorder.spent-spent)})
      print(ident+' published: '+str(len(fixed['objects']))+' objects; '+str(recorder.calls-calls)+' calls',flush=True)
     for ident,snapshot,fixed in published:
      assert fixed==await export_snapshot(candidates,snapshot),ident
     dump('memory-complete.json',{'cases':len(published),'all_snapshots_reread_unchanged':True,'calls':recorder.calls,'accounted_usd':str(recorder.spent)})
 except BaseException as e:
  dump('memory-failure.json',{'type':type(e).__name__,'case_id':recorder.case,'calls':recorder.calls,'accounted_usd':str(recorder.spent),'schema_retained':settings.schema})
  raise
 finally:await database.close()
if __name__=='__main__':
 if sys.argv[1:]!=['--live']:raise SystemExit('explicit --live required')
 with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:runner.run(main())
