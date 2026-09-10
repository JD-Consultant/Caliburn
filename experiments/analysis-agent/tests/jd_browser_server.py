"""Finite browser fixture: actual API/AnalysisService/PG/three JD tool factories.

The only model transport is MockTransport; no key/env/provider fallback exists.
"""
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import httpx
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from analysis_agent.api import create_app
from analysis_agent.catalog import Catalog
from analysis_agent.jd_store import JdStore
from analysis_agent.jd_engine import JdEngine
from analysis_agent.jd_service import JdService
from analysis_agent.jd_contract import manual_intent, revision_ref
from analysis_agent.jd_types import JdScope
from analysis_agent.provider import build_model
from analysis_agent.service import AnalysisService
from analysis_agent.publication import Base
from test_native_continuity import response_body, assistant_text

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT/'.superpowers/sdd/2026-09-10-jd-editor-core-implementation'


@contextmanager
def resources():
    dsn = os.environ['Q019_TEST_DATABASE_URL']
    params = conninfo_to_dict(dsn)
    assert params['dbname'] == 'q019_jd_app_20260910' and params['host'] == '127.0.0.1'
    def respond(request):
        body = json.loads(request.content)
        with (EVIDENCE/'task4-browser-provider.jsonl').open('a',encoding='utf-8') as log:
            log.write(json.dumps(body,ensure_ascii=False)+'\n')
        items = body.get('input', [])
        last = max((i for i,item in enumerate(items) if item.get('role') == 'user' and 'app_jd_context' not in json.dumps(item)), default=-1)
        turn = items[last:]
        user = json.dumps(items[last],ensure_ascii=False) if last >= 0 else ''
        outputs = [item for item in turn if item.get('type') == 'function_call_output']
        action = None
        if '請改選取' in user:
            if not outputs:
                action = ('jd_read', {})
            elif len(outputs) == 1:
                read = json.loads(outputs[0]['output'])
                if read.get('selection'):
                    action = ('jd_edit', {'commands':[{'type':'replace_selection',
                        'selection_ref':read['selection']['selection_ref'], 'content':[{'text':'第二處修正'}]}]})
        if action:
            output = [{'type':'function_call','id':'fc_'+str(uuid4()),'call_id':'call_'+str(uuid4()),
                'name':action[0],'arguments':json.dumps(action[1],ensure_ascii=False),'status':'completed'}]
        else:
            output = [assistant_text('已收到你的說明。這是固定離線驗收回覆。',item_id='msg_'+str(uuid4()))]
        return httpx.Response(200,json=response_body(output,response_id='resp_'+str(uuid4())))
    with ExitStack() as stack:
        engine = create_engine(URL.create('postgresql+psycopg'),connect_args=params,hide_parameters=True)
        stack.callback(engine.dispose)
        saver = stack.enter_context(PostgresSaver.from_conn_string(dsn)); saver.setup()
        store = stack.enter_context(PostgresStore.from_conn_string(dsn)); store.setup()
        catalog = Catalog(engine); catalog.setup(); catalog.upgrade_document_metadata()
        jd_store = JdStore(engine); jd_store.setup(); Base.metadata.create_all(engine)
        worker = JdEngine()
        binary = json.loads(subprocess.check_output([worker.node,'-p','JSON.stringify({execPath:process.execPath,version:process.version,versions:process.versions})'],text=True))
        jd = JdService(jd_store,worker,catalog)
        client=stack.enter_context(httpx.Client(transport=httpx.MockTransport(respond)))
        model=build_model(model='gpt-5.6-luna',api_key='offline-not-a-key',http_client=client)
        stack.callback(model.root_client.close)
        service=AnalysisService(catalog=catalog,saver=saver,store=store,model=model,jd=jd,instructions='固定離線驗收顧問。')
        stack.callback(service.close); service.start()
        document=service.create_document('設備維護工程師・完整驗收稿',request_key=str(uuid4()))['id']
        run=service.submit(document,str(uuid4()),'我負責設備維護，驗收素材由這次已保存問答提供。');service.join(document)
        reference=service.reader(document).capture_input(run['id'])
        value=json.loads((ROOT/'experiments/jd-editor/fixtures/r2-canonical.json').read_text(encoding='utf-8'))
        def sources(nodes):
            for node in nodes:
                if 'source_refs' in node: node['source_refs']=[reference]
                if 'children' in node:sources(node['children'])
        sources(value)
        scope=JdScope(document);base=jd.store.current(scope)
        result=jd.manual_save(manual_intent(scope,{'request_key':str(uuid4()),'base_revision_ref':revision_ref(scope,base.id),'value':value}))
        assert result.status=='committed'
        (EVIDENCE/'task4-browser-server.json').write_text(json.dumps({'document':document,'url':'http://127.0.0.1:3001/workspace/'+document,
            'worker_node':worker.node,'binary':binary,'fixed_transport':True,'real_provider_requests':0,'pid':os.getpid()},ensure_ascii=False,indent=2),encoding='utf-8')
        yield service


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_app(resources),host='127.0.0.1',port=8091,workers=1,reload=False,proxy_headers=False)
