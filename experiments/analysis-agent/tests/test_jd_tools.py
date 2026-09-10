"""Task 3: actual graph tools over the same JD PG/native owners."""
import json
from pathlib import Path
from uuid import uuid4
import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from test_jd_postgres import jd
from test_provider_recovery import offline_model
from test_native_continuity import response_body, assistant_text
from analysis_agent.jd_contract import manual_intent, revision_ref
from analysis_agent.jd_types import JdScope, JdReadQuery


def seed(jd, value=None):
    scope=JdScope(jd.create_document('Task3 '+str(uuid4()))['id'])
    if value is not None:
        base=jd.store.current(scope)
        assert jd.manual_save(manual_intent(scope,{'request_key':str(uuid4()),'base_revision_ref':revision_ref(scope,base.id),'value':value})).status=='committed'
    return scope


def test_current_read_then_exact_monthly_edit_and_attached_saved_input(jd):
    import httpx
    from analysis_agent.jd_tools import JdToolSession
    from analysis_agent.sources import ConversationReader
    from analysis_agent.conversation import build_conversation
    value=json.loads((Path(__file__).parents[2]/'jd-editor/fixtures/r2-canonical.json').read_text(encoding='utf-8'))
    scope=seed(jd,value)
    responses=[]
    def respond(request):
        body=json.loads(request.content); responses.append(body)
        outputs=[i for i in body['input'] if i.get('type')=='function_call_output']
        if not outputs:
            name,args='jd_read',{}
        elif len(outputs)==1:
            read=json.loads(outputs[-1]['output'])
            target=next(t for t in read['targets'] if t['element']['id']=='task8-description')
            source=reader.capture_input('input-1')
            name,args='jd_edit',{'commands':[
                {'type':'replace_block_content','target_ref':target['target_ref'],'content':[{'text':'僅對約定服務執行每月檢查；異常依既有故障處理程序交接。'}]},
                {'type':'set_properties','target_ref':target['target_ref'],'set':{'source_refs':[source]}}]}
        else:
            assert json.loads(outputs[-1]['output'])['status']=='committed'
            return httpx.Response(200,json=response_body([assistant_text('已保存；故障程序保留。')],response_id='resp_final'))
        return httpx.Response(200,json=response_body([{'type':'function_call','id':'fc'+str(len(responses)),'call_id':'call'+str(len(responses)),'name':name,'arguments':json.dumps(args),'status':'completed'}],response_id='resp_'+str(len(responses))))
    with offline_model(respond) as model:
        saver=InMemorySaver(); base=build_conversation(model=model,checkpointer=saver,instructions='test')
        reader=ConversationReader(base,scope.document_id)
        session=JdToolSession(jd,reader)
        graph=build_conversation(model=model,checkpointer=saver,instructions='test',tools=session.tools,middleware=[session])
        reader.graph=graph
        result=graph.invoke({'messages':[HumanMessage('僅對約定服務執行每月檢查。',id='input-1')]},{'configurable':{'thread_id':scope.document_id}},durability='sync')
    assert result['turn_outcome']['status']=='completed'
    after=jd.store.current(scope)
    assert '僅對約定服務執行每月檢查；異常依既有故障處理程序交接。' in json.dumps(after.value,ensure_ascii=False)
    from copy import deepcopy
    from analysis_agent.jd_references import elements
    expected=deepcopy(value)
    changed=next(n for n in elements(expected) if n['id']=='task8-description')
    changed['children']=[{'text':'僅對約定服務執行每月檢查；異常依既有故障處理程序交接。'}]
    changed['source_refs']=[next(iter(result['jd_sources']))]
    assert after.value==expected
    assert len(responses)==3


def run_calls(jd,scope,actions,*,page_size=64,saver=None,selection=None,max_tool_calls=15,compaction=False,extra_middleware=()):
    import httpx
    from analysis_agent.jd_tools import JdToolSession
    from analysis_agent.sources import ConversationReader
    from analysis_agent.conversation import build_conversation
    requests=[]; values=[]
    def respond(request):
        body=json.loads(request.content); requests.append(body)
        outputs=[item for item in body['input'] if item.get('type')=='function_call_output']
        if outputs:
            value=json.loads(outputs[-1]['output'])
            if len(values)<len(outputs): values.append(value)
        if len(values)>=len(actions):
            return httpx.Response(200,json=response_body(([{'type':'compaction','id':'cmp_'+str(uuid4()),'encrypted_content':'opaque-fixed'}] if compaction else [])+[assistant_text('done')],response_id='resp_'+str(uuid4())))
        name,args=actions[len(values)]
        args=args(values) if callable(args) else args
        return httpx.Response(200,json=response_body([{'type':'function_call','id':'fc_'+str(uuid4()),
            'call_id':'call_'+str(uuid4()),'name':name,'arguments':json.dumps(args),'status':'completed'}],response_id='resp_'+str(uuid4())))
    with offline_model(respond) as model:
        saver=saver or InMemorySaver()
        reader=ConversationReader(build_conversation(model=model,checkpointer=saver,instructions='test'),scope.document_id)
        session=JdToolSession(jd,reader,page_size=page_size)
        graph=build_conversation(model=model,checkpointer=saver,instructions='test',tools=session.tools,middleware=[session,*extra_middleware],max_tool_calls=max_tool_calls)
        reader.graph=graph
        input_id=str(uuid4())
        update={'messages':[HumanMessage('固定工具驗收',id=input_id)],'jd_selection':None}
        if selection: update['jd_selection']={**selection,'input':input_id}
        result=graph.invoke(update,{'configurable':{'thread_id':scope.document_id}},durability='sync')
        # Last tool result may end at the original limit before another request.
        from langchain_core.messages import ToolMessage
        values=[json.loads(m.content) for m in result['messages'] if isinstance(m,ToolMessage) and m.status=='success' and m.name in {'jd_read','jd_edit','jd_change_read'}]
        return values,result,requests,graph,session


def replacement(ref,text='changed'):
    return {'commands':[{'type':'replace_block_content','target_ref':ref,'content':[{'text':text}]}]}


def test_history_head_targets_stay_readonly_and_guess_is_rejected(jd):
    scope=seed(jd)
    values,result,_,_,_=run_calls(jd,scope,[('jd_read',{}),
        ('jd_read',lambda v:{'revision_ref':v[0]['revision_ref']}),
        ('jd_edit',lambda v:replacement(v[1]['targets'][0]['target_ref'])),
        ('jd_edit',replacement('guessed-real-id'))])
    assert values[1]['access']=='read_only'
    assert values[2]['status']==values[3]['status']=='invalid_input'
    assert jd.store.current(scope).origin=='initial'


def test_current_and_history_pages_are_pinned_and_new_current_targets_write(jd):
    value=[{'id':'p'+str(i),'type':'p','children':[{'text':str(i)}]} for i in range(4)]
    scope=seed(jd,value)
    values,_,_,_,_=run_calls(jd,scope,[('jd_read',{}),
        ('jd_read',lambda v:{'continuation_ref':v[0]['continuation_ref']}),
        ('jd_edit',lambda v:replacement(v[1]['targets'][0]['target_ref'])),
        ('jd_read',lambda v:{'revision_ref':v[0]['revision_ref']}),
        ('jd_read',lambda v:{'continuation_ref':v[3]['continuation_ref']}),
        ('jd_edit',lambda v:replacement(v[4]['targets'][0]['target_ref']))],page_size=2)
    assert values[0]['fragment']+values[1]['fragment']==value
    assert values[2]['status']=='committed'
    assert values[3]['fragment']+values[4]['fragment']==value
    assert values[5]['status']=='invalid_input'
    assert values[4]['revision_ref']==values[0]['revision_ref']


def test_mixed_bases_rejected_before_engine(jd):
    scope=seed(jd)
    values,_,_,_,_=run_calls(jd,scope,[('jd_read',{}),
        ('jd_edit',lambda v:replacement(v[0]['targets'][0]['target_ref'])),('jd_read',{}),
        ('jd_edit',lambda v:{'commands':[
            *replacement(v[0]['targets'][0]['target_ref'])['commands'],
            *replacement(v[2]['targets'][0]['target_ref'])['commands']]})])
    assert values[1]['status']=='committed'
    assert values[3]['status']=='invalid_input'


@pytest.mark.parametrize('args',[
    {'commands':[{'type':'replace_selection','selection_ref':'x','target_ref':'y','content':[]}]},
    {'commands':[{'type':'set_properties','target_ref':'x','set':{'approved':True}}]},
    {'commands':[{'type':'insert_content','target_ref':'x','placement':'after','content':[{'type':'p','children':[{'type':'p','children':[{'text':'bad'}]}]}]}]},
])
def test_invalid_full_schema_never_enters_engine(jd,monkeypatch,args):
    scope=seed(jd);calls=[]
    monkeypatch.setattr(jd.engine,'transform',lambda *a: calls.append(a))
    values,_,_,_,_=run_calls(jd,scope,[('jd_edit',args)])
    assert values[0]['status']=='invalid_input'
    assert calls==[]


def test_no_change_receipt_and_revision_comparison_are_distinct(jd):
    scope=seed(jd)
    values,_,_,_,_=run_calls(jd,scope,[('jd_read',{}),
        ('jd_edit',lambda v:replacement(v[0]['targets'][0]['target_ref'],'')),
        ('jd_change_read',lambda v:{'change_ref':v[1]['change_ref']}),
        ('jd_change_read',lambda v:{'before_revision_ref':v[0]['revision_ref'],'after_revision_ref':v[0]['revision_ref']})])
    assert values[1]['status']=='no_change'
    assert values[2]['mode']=='change' and values[2]['origin']=='ai'
    assert values[2]['before_fragment']==values[2]['after_fragment']==[]
    assert values[3]['mode']=='revision_comparison' and values[3]['origin'] is None


def test_create_then_read_link_and_unset_use_generated_ids(jd):
    from analysis_agent.jd_references import elements
    value=json.loads((Path(__file__).parents[2]/'jd-editor/fixtures/r2-canonical.json').read_text(encoding='utf-8'))
    def new(node):
        if isinstance(node,list): return [new(n) for n in node]
        if isinstance(node,dict): return {k:new(v) for k,v in node.items() if k not in {'id','source_refs','knowledge_ids','skill_ids'}}
        return node
    scope=seed(jd)
    def links(values):
        targets=values[-1]['targets']
        task=next(t for t in targets if t['element']['type']=='jd_task')
        knowledge=next(t for t in targets if t['element']['type']=='jd_knowledge')
        skill=next(t for t in targets if t['element']['type']=='jd_skill')
        return {'commands':[{'type':'set_properties','target_ref':task['target_ref'],
            'set':{'knowledge_refs':[knowledge['target_ref']],'skill_refs':[skill['target_ref']]}}]}
    values,_,_,_,_=run_calls(jd,scope,[('jd_read',{}),('jd_edit',lambda v:{'commands':[
        {'type':'insert_content','target_ref':v[-1]['targets'][0]['target_ref'],'placement':'before','content':new(value)},
        {'type':'remove_content','target_ref':v[-1]['targets'][0]['target_ref']}]}),('jd_read',{}),('jd_edit',links),
        ('jd_read',{}),('jd_edit',lambda v:{'commands':[{'type':'set_properties','target_ref':next(t['target_ref'] for t in v[-1]['targets'] if t['element']['type']=='jd_task'),
            'unset':['knowledge_refs','skill_refs']}]})])
    assert values[1]['status']==values[3]['status']==values[5]['status']=='committed'
    linked=next(t for t in values[4]['targets'] if t['element']['type']=='jd_task')
    assert len(linked['knowledge_refs'])==len(linked['skill_refs'])==1
    knowledge=next(t for t in values[4]['targets'] if t['element']['id']==linked['element']['knowledge_ids'][0])
    assert len(knowledge['used_by_task_refs'])==1
    final=next(n for n in elements(jd.store.current(scope).value) if n['type']=='jd_task')
    assert 'knowledge_ids' not in final and 'skill_ids' not in final


def test_unconfirmed_write_stops_model_loop_and_retains_exact_binding(jd,monkeypatch):
    from analysis_agent.jd_types import JdWriteOutcome
    from analysis_agent.publication import PublicationUncertain
    scope=seed(jd);saver=InMemorySaver();attempts=[]
    def uncertain(intent,**kwargs):
        attempts.append(intent)
        return JdWriteOutcome(scope,intent.operation_id,intent.base_id,None,'outcome_unknown','ai',durability='unconfirmed',next_action='reconcile_operation')
    monkeypatch.setattr(jd,'edit',uncertain)
    with pytest.raises(PublicationUncertain):
        run_calls(jd,scope,[('jd_read',{}),('jd_edit',lambda v:replacement(v[-1]['targets'][0]['target_ref']))],saver=saver)
    root=saver.get_tuple({'configurable':{'thread_id':scope.document_id}})
    checkpoints=list(saver.list({'configurable':{'thread_id':scope.document_id}}))
    pending=[c.checkpoint['channel_values'].get('jd_pending_operation') for c in checkpoints]
    binding=next(p for p in pending if p)
    assert binding['operation']==str(attempts[0].operation_id)
    assert binding['digest']==attempts[0].digest
    assert len(attempts)==1


def test_same_stop_signal_reaches_existing_native_transform(jd,monkeypatch):
    from threading import Event
    from analysis_agent.jd_types import JdEditIntent
    from analysis_agent.jd_contract import request_digest
    scope=seed(jd);base=jd.store.current(scope);stop=Event();observed=[]
    transform=jd.engine.transform
    def capture(value,commands,*,cancel=None):
        observed.append(cancel)
        return transform(value,commands,cancel=cancel)
    monkeypatch.setattr(jd.engine,'transform',capture)
    commands=[{'type':'replace_block_content','target_id':base.value[0]['id'],'content':[{'text':'new'}]}]
    outcome=jd.edit(JdEditIntent(scope,uuid4(),base.id,request_digest(scope,base.id,commands,'ai'),commands),cancel=stop)
    assert outcome.status=='committed' and observed==[stop]
