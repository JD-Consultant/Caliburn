import pytest

def test_api_selection_uses_ssot_capture_shape():
    from analysis_agent.api import MessageInput
    from pydantic import ValidationError
    capture={'base_revision_ref':'revision','range':{'anchor':{'path':[0,0],'offset':1},'focus':{'path':[0,0],'offset':2}}}
    model=MessageInput(request_key='request',text='只改選取',jd_selection=capture)
    assert model.model_dump()['jd_selection']==capture
    with pytest.raises(ValidationError):
        MessageInput(request_key='request',text='文字',jd_selection={**capture,'selection_ref':'invented'})


def test_real_api_native_selection_admission_and_exact_replacement(jd):
    import json,subprocess
    from pathlib import Path
    from contextlib import contextmanager
    import httpx
    from fastapi.testclient import TestClient
    from langgraph.checkpoint.memory import InMemorySaver
    from analysis_agent.api import create_app
    from analysis_agent.service import AnalysisService
    from analysis_agent.jd_contract import revision_ref
    from test_jd_tools import seed
    from test_provider_recovery import offline_model
    from test_native_continuity import response_body,assistant_text
    import os
    fixture=Path(__file__).parents[2]/'jd-editor/fixtures/task3-selection.mjs'
    native=json.loads(subprocess.run(['node',str(fixture)],check=True,capture_output=True,encoding='utf-8',
        env={key:value for key,value in os.environ.items() if key in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP'}}).stdout)
    scope=seed(jd,native['value']);base=jd.store.current(scope); seen=[]
    def respond(request):
        body=json.loads(request.content);seen.append(body)
        results=[i for i in body['input'] if i.get('type')=='function_call_output']
        if not results: name,args='jd_read',{}
        elif len(results)==1:
            result=json.loads(results[0]['output'])
            assert result['selection']['content']==[{'text':'同文'}]
            name,args='jd_edit',{'commands':[{'type':'replace_selection','selection_ref':result['selection']['selection_ref'],'content':[{'text':'末段'}]}]}
        else: return httpx.Response(200,json=response_body([assistant_text('完成')],response_id='selection_final'))
        return httpx.Response(200,json=response_body([{'type':'function_call','id':'fc'+str(len(seen)),'call_id':'sc'+str(len(seen)),
            'name':name,'arguments':json.dumps(args),'status':'completed'}],response_id='selection'+str(len(seen))))
    @contextmanager
    def resources():
        with offline_model(respond) as model:
            service=AnalysisService(catalog=jd.catalog,jd=jd,saver=InMemorySaver(),model=model,instructions='test')
            service.start()
            try: yield service
            finally: service.close()
    app=create_app(resources)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        payload={'text':'只改後半','request_key':'selection','jd_selection':{'base_revision_ref':revision_ref(scope,base.id),'range':native['range']}}
        response=client.post(f'/documents/{scope.document_id}/runs',json=payload)
        assert response.status_code==202,response.text
        app.state.service.join(scope.document_id)
        assert app.state.service.get_run(scope.document_id,response.json()['id'])['status']=='completed'
        assert jd.store.current(scope).value[0]['children']==[{'text':'同文末段'}]
        stale=client.post(f'/documents/{scope.document_id}/runs',json={**payload,'request_key':'stale'})
        assert stale.status_code==409
        assert app.state.service.messages(scope.document_id)[0]['text']=='只改後半'
from test_jd_postgres import jd


def test_pg_response_manifest_survives_actual_process_restart(jd):
    import os,json,subprocess,sys
    from pathlib import Path
    from uuid import uuid4
    from test_jd_tools import seed
    from analysis_agent.jd_contract import manual_intent,revision_ref
    scope=seed(jd)
    worker=Path(__file__).with_name('jd_model_view_worker.py')
    env={k:v for k,v in os.environ.items() if k in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','Q019_TEST_DATABASE_URL'}}
    env.update(PYTHONUTF8='1',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false',LANGCHAIN_TRACING='false')
    def run():
        output=subprocess.run([sys.executable,str(worker)],input=json.dumps({'document':scope.document_id}),capture_output=True,
            encoding='utf-8',env=env,timeout=90)
        assert output.returncode==0,output.stderr
        return json.loads(output.stdout)
    first=run(); base=jd.store.current(scope)
    value=[{'id':base.value[0]['id'],'type':'p','children':[{'text':'跨程序人工更動'}]}]
    assert jd.manual_save(manual_intent(scope,{'request_key':str(uuid4()),'base_revision_ref':revision_ref(scope,base.id),'value':value})).status=='committed'
    second=run()
    assert first['pid']!=second['pid']
    assert second['notice']['since_last_response']['manual_count']==1
    assert second['notice']['since_last_response']['before_revision_ref']==revision_ref(scope,base.id)
    assert second['requests']==1
    assert all('app_jd_context' not in str(message) for message in second['canonical'])
