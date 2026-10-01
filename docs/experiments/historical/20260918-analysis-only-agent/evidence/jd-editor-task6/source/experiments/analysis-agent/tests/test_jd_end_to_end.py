"""Actual API, Saver/Store, JD SQL, native Node, and fixed model intentions.

No natural model assertions: this validates the saved consequences of explicit
synthetic tool calls. Fresh process and headed browser observations are separate.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import ToolMessage

from analysis_agent.api import create_app, ADVISOR_INSTRUCTIONS
from analysis_agent.jd_types import JdScope
from analysis_agent.jd_references import elements
from jd_offline_service import FixedInterview, resources, scenario, text_of, current_turn
from test_jd_postgres import jd


@contextmanager
def app_client(transport):
    @contextmanager
    def opened():
        with resources(transport) as service:
            yield service
    with TestClient(create_app(opened),base_url='http://127.0.0.1:8091') as client:
        yield client,client.app.state.service


def submit(client,service,doc,key):
    response=client.post(f'/documents/{doc}/runs',json={'request_key':str(uuid4()),'text':scenario()['utterances'][key]})
    assert response.status_code==202,response.text
    run=response.json();service.join(doc)
    final=client.get(f'/documents/{doc}/runs/{run["id"]}').json()
    assert final['status']=='completed',final
    return final


def plain(value):
    if isinstance(value,list):return [plain(item) for item in value]
    if isinstance(value,dict):return {k:plain(v) for k,v in value.items() if k not in ('id','source_refs','knowledge_ids','skill_ids')}
    return value


def read(client,doc):
    response=client.get(f'/documents/{doc}/jd')
    assert response.status_code==200,response.text
    return response.json()


def notice(body):
    return next(json.loads(text_of(item)) for item in body['input'] if item.get('role')=='user' and 'app_jd_context' in text_of(item))


def test_fixed_api_interview_writes_corrects_and_preserves_manual_without_memory_facts(jd):
    transport=FixedInterview('../../scratch/task6-e2e-wire.jsonl')
    fixture=scenario()
    with app_client(transport) as (client,service):
        document=client.post('/documents',json={'title':'Task6 合成設備維護','request_key':str(uuid4())}).json()['id']
        before=read(client,document)
        intro=submit(client,service,document,'intro')
        assert read(client,document)['revision_ref']==before['revision_ref']
        assert service.messages(document)[0]['text']==fixture['utterances']['intro']
        first=transport.requests[0]
        assert ADVISOR_INSTRUCTIONS in text_of([i for i in first['input'] if i.get('role') in ('system','developer')])
        assert '目前只做訪談分析，不製作或編輯JD' not in json.dumps(first,ensure_ascii=False)
        assert '/skills/write-customized-jd/SKILL.md' in json.dumps(first,ensure_ascii=False)
        from analysis_agent.jd_tools import NAMES
        from analysis_agent.jd_contract import SCHEMA_PATH
        definitions=json.loads(SCHEMA_PATH.read_text(encoding='utf8'))['$defs']
        tools={t['name']:t for t in first['tools']}
        for name,definition in NAMES.items():
            assert {k:v for k,v in tools[name]['parameters'].items() if k!='$defs'}==definitions[definition]
            assert tools[name]['description']==definitions[definition]['description']
        draft=submit(client,service,document,'draft')
        saved=read(client,document)
        assert plain(saved['fragment'])==fixture['expected_initial_content'], [(i.get('type'),i.get('name'),i.get('output')) for i in transport.requests[-1]['input'] if i.get('type') in ('function_call','function_call_output')]
        nodes=list(elements(saved['fragment']))
        tasks=[n for n in nodes if n['type']=='jd_task']
        assert len(tasks)==2 and len(tasks[0]['knowledge_ids'])==2
        assert tasks[0]['knowledge_ids']==tasks[1]['knowledge_ids']
        assert len(tasks[0]['skill_ids'])==1 and len(tasks[1]['skill_ids'])==2
        source=next(n['source_refs'][0] for n in nodes if n.get('source_refs'))
        page=client.get(f'/documents/{document}/sources',params={'reference':source}).json()
        assert [s['text'] for s in page['segments'] if s['role']=='user']==[fixture['utterances']['draft']]
        assert not service._context(document).memory.publication.current()
        old=deepcopy(saved['fragment'])
        corrected=submit(client,service,document,'correct')
        after=read(client,document)
        node=next(n for n in elements(old) if text_of(n)==fixture['monthly_original'])
        node['children']=[{'text':fixture['monthly_corrected']}]
        actual=next(n for n in elements(after['fragment']) if text_of(n)==fixture['monthly_corrected'])
        node['source_refs']=actual['source_refs']
        assert after['fragment']==old
        assert any(text_of(n)==fixture['fault_description'] for n in elements(after['fragment']))
        correction_source=client.get(f'/documents/{document}/sources',params={'reference':actual['source_refs'][0]}).json()
        assert [s['text'] for s in correction_source['segments'] if s['role']=='user']==[fixture['utterances']['correct']]
        assert not service._context(document).memory.publication.current(), 'Newest correction works before Memory publication'
        manual=deepcopy(after['fragment'])
        requirement=next(n for n in elements(manual) if text_of(n)=='未排除問題交接操作員')
        requirement['children']=[{'text':fixture['manual_text']}]
        request_key=str(uuid4())
        result=client.post(f'/documents/{document}/jd/manual-save',json={'request_key':request_key,'base_revision_ref':after['revision_ref'],'value':manual}).json()
        assert result['status']=='committed'
        # A second real manual revision, followed by a third restoring that one
        # sentence, proves event history is not replaced by a net-only diff.
        for suffix in ('（再核對）',''):
            current=read(client,document)
            value=deepcopy(current['fragment'])
            requirement=next(n for n in elements(value) if n['id']==requirement['id'])
            requirement['children']=[{'text':fixture['manual_text']+suffix}]
            reply=client.post(f'/documents/{document}/jd/manual-save',json={'request_key':str(uuid4()),'base_revision_ref':current['revision_ref'],'value':value}).json()
            assert reply['status']=='committed'
        start=len(transport.requests)
        continued=submit(client,service,document,'continue')
        context=notice(transport.requests[start])
        assert context['turn_start_interval']['manual_count']==3
        assert context['turn_start_interval']['baseline']=='known'
        current=read(client,document)
        assert any(text_of(n)==fixture['manual_text'] for n in elements(current['fragment']))
        assert any(text_of(n)==fixture['continued_purpose'] for n in elements(current['fragment']))
        before_thanks=current['revision_ref']
        for _ in range(2):submit(client,service,document,'thanks')
        assert read(client,document)['revision_ref']==before_thanks
        assert all(m['text']!=fixture['manual_text'] for m in service.messages(document))
        assert not service._context(document).memory.publication.current()
        history=client.post(f'/documents/{document}/jd/changes/read',json={'change_ref':result['change_ref']}).json()
        assert history['before_fragment']!=history['after_fragment']
        other=client.post('/documents',json={'title':'隔離另一份','request_key':str(uuid4())}).json()['id']
        assert read(client,other)['fragment'][0]['children']==[{'text':''}]
        evidence={'document':document,'runs':[intro,draft,corrected,continued], 'requests':transport.requests,
                  'initial':before,'draft':saved,'corrected':after,'final':current,'manual_result':result,'manual_history':history,
                  'source':page,'correction_source':correction_source,'real_provider_requests':0}
        Path('../../scratch/task6-e2e-result.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8')


def test_commit_reply_loss_reconciles_once_and_pure_interview_cancel_has_no_jd_receipt(jd,monkeypatch):
    transport=FixedInterview()
    with app_client(transport) as (client,service):
        doc=client.post('/documents',json={'title':'Task6 丟回覆','request_key':str(uuid4())}).json()['id']
        submit(client,service,doc,'draft')
        original=service.jd.edit
        attempts=[]
        def lost(intent,**kwargs):
            result=original(intent,**kwargs);attempts.append(result)
            assert result.status=='committed'
            raise RuntimeError('Task6 injected post-commit result loss')
        with monkeypatch.context() as fault:
            fault.setattr(service.jd,'edit',lost)
            r=client.post(f'/documents/{doc}/runs',json={'request_key':str(uuid4()),'text':scenario()['utterances']['lost']}).json()
            service.join(doc)
        before=read(client,doc)
        request_count=len(transport.requests)
        stopped=client.post(f'/documents/{doc}/runs/{r["id"]}/stop').json()
        assert stopped['status']=='cancelled',stopped
        assert len(attempts)==1 and len(transport.requests)==request_count
        assert read(client,doc)==before
        from analysis_agent.service import current_values
        messages=current_values(service._context(doc).graph.get_state(service._context(doc).config))['messages']
        matching=[m for m in messages if isinstance(m,ToolMessage) and m.name=='jd_edit' and json.loads(m.content).get('result_revision_ref')==before['revision_ref']]
        assert len(matching)==1 and json.loads(matching[0].content)['status']=='committed'
        transport.cancel_release.clear()
        r=client.post(f'/documents/{doc}/runs',json={'request_key':str(uuid4()),'text':scenario()['utterances']['cancel']}).json()
        assert transport.cancel_entered.wait(10)
        try:
            stopped=client.post(f'/documents/{doc}/runs/{r["id"]}/stop').json()
            assert stopped['status']=='stopping'
        finally:
            transport.cancel_release.set()
        service.join(doc)
        assert client.get(f'/documents/{doc}/runs/{r["id"]}').json()['status']=='cancelled'
        assert read(client,doc)==before
