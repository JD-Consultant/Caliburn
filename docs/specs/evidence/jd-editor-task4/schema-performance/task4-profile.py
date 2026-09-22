import cProfile, io, json, os, pstats, time
from pathlib import Path
from types import SimpleNamespace
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from analysis_agent.catalog import Catalog
from analysis_agent.jd_store import JdStore
from analysis_agent.jd_service import JdService
from analysis_agent.jd_engine import JdEngine
from analysis_agent.jd_types import JdScope
from analysis_agent import jd_routes, jd_contract
from jd_editor_contract import models

folder=Path(__file__).parent
params=conninfo_to_dict(os.environ['Q019_TEST_DATABASE_URL'])
assert params['dbname']=='q019_jd_app_20260910'
engine=create_engine(URL.create('postgresql+psycopg'),connect_args=params,hide_parameters=True)
catalog=Catalog(engine); store=JdStore(engine); service=SimpleNamespace(jd=JdService(store,JdEngine(),catalog))
scope=JdScope(json.loads((folder/'task4-browser-server.json').read_text())['document'])
timings=[]
def timed(name,fn,*args):
    start=time.perf_counter(); result=fn(*args);timings.append({'stage':name,'seconds':time.perf_counter()-start});return result
original=jd_routes.validate
def observe(name,value):
    timed('jsonschema '+name,jd_contract._validator(name).validate,value)
    parsed=timed('pydantic '+name,getattr(models,name).model_validate,value)
    return timed('dump '+name,lambda:parsed.model_dump(mode='json',exclude_unset=True))
jd_routes.validate=observe
old_current=store.current
store.current=lambda scope:timed('DB current',old_current,scope)
prof=cProfile.Profile();prof.enable();result=timed('complete read mapper',jd_routes.read_document,service,scope,{})
timed('FastAPI response Pydantic',models.JdReadResult.model_validate,result)
timed('serialize JSON',json.dumps,result)
prof.disable();stream=io.StringIO();pstats.Stats(prof,stream=stream).sort_stats('cumtime').print_stats(35)
(folder/'task4-read-profile.json').write_text(json.dumps(timings,indent=2),encoding='utf-8')
(folder/'task4-read-profile.txt').write_text(stream.getvalue(),encoding='utf-8')
print(json.dumps(timings,indent=2));engine.dispose()
