"""Real fresh-process receipt recovery; stdin carries only synthetic JD data."""
import json
import os
import sys
from uuid import UUID
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from analysis_agent.catalog import Catalog
from analysis_agent.jd_contract import manual_intent, outcome_to_wire
from analysis_agent.jd_engine import JdEngine
from analysis_agent.jd_service import JdService
from analysis_agent.jd_store import JdStore
from analysis_agent.jd_types import JdScope

params = conninfo_to_dict(os.environ['Q019_TEST_DATABASE_URL'])
assert params['dbname'] == 'q019_jd_app_20260910' and params['host'] in {'localhost', '127.0.0.1'}
assert 1 <= int(params['connect_timeout']) <= 5
engine = create_engine(URL.create('postgresql+psycopg'), connect_args=params, hide_parameters=True)
request = json.load(sys.stdin)
service = JdService(JdStore(engine), JdEngine(), Catalog(engine))
intent = manual_intent(JdScope(request['document']), request['body'])
if request['mode'] == 'exit_after_commit':
    commit = engine.dialect.do_commit
    def committed_then_exit(connection):
        commit(connection)
        os._exit(73)
    engine.dialect.do_commit = committed_then_exit
else:
    def forbidden(*args, **kwargs):
        raise AssertionError('Receipt recovery must not invoke Node')
    service.engine.validate_value = forbidden
result = service.manual_save(intent)
print(json.dumps(outcome_to_wire(result), ensure_ascii=False))
engine.dispose()
