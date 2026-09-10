"""Fresh-process PG model checkpoint recovery with a synthetic transport."""
import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from langgraph.checkpoint.postgres import PostgresSaver
from analysis_agent.catalog import Catalog
from analysis_agent.jd_store import JdStore
from analysis_agent.jd_service import JdService
from analysis_agent.jd_engine import JdEngine
from analysis_agent.jd_types import JdScope
from test_jd_tools import run_calls

scope=JdScope(json.loads(sys.stdin.read())['document'])
dsn=os.environ['Q019_TEST_DATABASE_URL'];params=conninfo_to_dict(dsn)
assert params['dbname']=='q019_jd_app_20260910' and params['host']=='127.0.0.1'
engine=create_engine(URL.create('postgresql+psycopg'),connect_args=params,hide_parameters=True)
service=JdService(JdStore(engine),JdEngine(),Catalog(engine))
with PostgresSaver.from_conn_string(dsn) as saver:
    saver.setup()
    _,result,requests,_,_=run_calls(service,scope,[],saver=saver)
    from test_jd_model_view import notice_from
    notice=notice_from(requests[-1])
    print(json.dumps({'manifest':result['jd_last_model_view'],'notice':notice,'requests':len(requests),
        'canonical':[m.content for m in result['messages']],'pid':os.getpid()},ensure_ascii=False))
engine.dispose()
