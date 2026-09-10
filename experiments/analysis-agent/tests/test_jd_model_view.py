"""Request-only event context: bounded, truthful, response-backed."""
from uuid import uuid4
import pytest
from test_jd_postgres import jd
from test_jd_tools import seed
from analysis_agent.jd_contract import manual_intent, revision_ref


def test_notice_counts_manual_revert_without_claiming_exact_content(jd):
    from analysis_agent.jd_context import prepare_notice
    from analysis_agent.jd_references import IssuedReferences
    scope=seed(jd)
    start=jd.store.current(scope)
    state={'jd_turn_id':'turn','jd_last_model_view':{'document':scope.document_id,'current_revision':str(start.id),'response_id':'prior'}}
    for text in ['人工修改','']:
        current=jd.store.current(scope)
        value=[{'type':'p','id':start.value[0]['id'],'children':[{'text':text}]}]
        assert jd.manual_save(manual_intent(scope,{'request_key':str(uuid4()),'base_revision_ref':revision_ref(scope,current.id),'value':value})).status=='committed'
    from types import SimpleNamespace
    session=SimpleNamespace(service=jd,scope=scope)
    payload,manifest,basis=prepare_notice(session,state,[],IssuedReferences(scope,{}))
    assert payload['since_last_response']['manual_count']==2
    assert payload['current_content']['kind'] in {'exact','text_only_preview'}
    assert manifest['current_revision']==str(jd.store.current(scope).id)
    assert basis['input']=='turn'


def test_source_context_is_app_data_and_never_employee_instruction():
    from analysis_agent.jd_context import CONTEXT_GUIDANCE
    assert 'app_jd_context' in CONTEXT_GUIDANCE
    assert 'untrusted' in CONTEXT_GUIDANCE


def save_text(jd,scope,text):
    current=jd.store.current(scope)
    return jd.manual_save(manual_intent(scope,{'request_key':str(uuid4()),'base_revision_ref':revision_ref(scope,current.id),
        'value':[{'id':current.value[0]['id'],'type':'p','children':[{'text':text}]}]}))


def notice_from(request):
    import json
    for item in reversed(request['input']):
        if item.get('role')=='user':
            content=item.get('content','')
            if isinstance(content,str) and 'app_jd_context' in content:
                return json.loads(content)
            for block in content if isinstance(content,list) else []:
                if 'app_jd_context' in block.get('text',''):
                    return json.loads(block['text'])
    raise AssertionError('Missing actual SDK app context')


def test_next_interview_request_sees_two_saved_revert_events_and_changes_are_navigable(jd):
    from test_jd_tools import run_calls
    from langgraph.checkpoint.memory import InMemorySaver
    saver=InMemorySaver();scope=seed(jd)
    _,first,_,_,_=run_calls(jd,scope,[],saver=saver)
    start=jd.store.current(scope)
    assert save_text(jd,scope,'changed').status=='committed'
    assert save_text(jd,scope,'').status=='committed'
    _,result,requests,_,_=run_calls(jd,scope,[],saver=saver)
    notice=notice_from(requests[0])
    assert notice['since_last_response']['manual_count']==2
    assert len(notice['events'])==2
    assert notice['since_last_response']['before_revision_ref']==revision_ref(scope,start.id)
    assert jd.store.current(scope).value==start.value
    assert all('app_jd_context' not in str(m.content) for m in result['messages'])
    assert result['jd_last_model_view']['response_id']==result['messages'][-1].id
    values,_,_,_,_=run_calls(jd,scope,[('jd_change_read',{'change_ref':notice['events'][0]['change_ref']})],saver=saver)
    assert values[-1]['origin']=='manual'
    assert values[-1]['before_fragment']!=values[-1]['after_fragment']


def test_long_notice_bounded_event_chain_current_preview_and_unread_scope(jd):
    import json
    from test_jd_tools import run_calls
    from langgraph.checkpoint.memory import InMemorySaver
    from analysis_agent.jd_context import encoded
    saver=InMemorySaver();scope=seed(jd)
    run_calls(jd,scope,[],saver=saver)
    for i in range(6): assert save_text(jd,scope,('繁中🙂'+str(i))*1500).status=='committed'
    _,_,requests,_,_=run_calls(jd,scope,[],saver=saver)
    notice=notice_from(requests[0])
    assert len(encoded(notice).encode())<=16384
    assert notice['since_last_response']['manual_count']==6
    assert len(notice['events'])==4
    assert notice['since_last_response']['omitted_events']==2
    assert len(notice['current_content']['text'].encode())<=2048
    assert notice['current_content']['kind']=='text_only_preview'
    assert not notice['current_content']['complete']
    assert all('content' not in e for e in notice['events'])
    # The earliest displayed before revision exposes its creating event;
    # neither a long body nor later head changes changes this history chain.
    oldest=notice['events'][0]['before_revision_ref']
    values,_,_,_,_=run_calls(jd,scope,[('jd_read',{'revision_ref':oldest}),
        ('jd_change_read',lambda v:{'change_ref':v[-1]['change_refs'][0]})],saver=saver)
    assert values[-2]['access']=='read_only'
    assert values[-1]['after_revision_ref']==oldest
    assert '🙂' in json.dumps(values[-1]['after_fragment'],ensure_ascii=False)


def test_saved_marks_event_counts_but_no_change_does_not(jd):
    from test_jd_tools import run_calls
    from langgraph.checkpoint.memory import InMemorySaver
    saver=InMemorySaver();scope=seed(jd)
    run_calls(jd,scope,[],saver=saver)
    base=jd.store.current(scope)
    body={'request_key':str(uuid4()),'base_revision_ref':revision_ref(scope,base.id),
        'value':[{'id':base.value[0]['id'],'type':'p','children':[{'text':'','bold':True}]}]}
    assert jd.manual_save(manual_intent(scope,body)).status=='committed'
    current=jd.store.current(scope)
    body.update(request_key=str(uuid4()),base_revision_ref=revision_ref(scope,current.id))
    assert jd.manual_save(manual_intent(scope,body)).status=='no_change'
    _,_,requests,_,_=run_calls(jd,scope,[],saver=saver)
    notice=notice_from(requests[0])
    assert notice['since_last_response']['manual_count']==1
    assert notice['events'][0]['content']['after_fragment'][0]['children'][0]['bold'] is True


def test_cross_document_manifest_rejected_before_provider(jd):
    import httpx
    from test_provider_recovery import offline_model,completed
    from analysis_agent.jd_tools import JdToolSession
    from analysis_agent.sources import ConversationReader
    from analysis_agent.conversation import build_conversation
    from langgraph.checkpoint.memory import InMemorySaver
    from langchain_core.messages import HumanMessage
    scope=seed(jd); requests=[]
    with offline_model(lambda request: requests.append(request) or completed()) as model:
        saver=InMemorySaver();reader=ConversationReader(build_conversation(model=model,checkpointer=saver,instructions='test'),scope.document_id)
        session=JdToolSession(jd,reader)
        graph=build_conversation(model=model,checkpointer=saver,instructions='test',tools=session.tools,middleware=[session]);reader.graph=graph
        with pytest.raises(ValueError,match='another document'):
            graph.invoke({'messages':[HumanMessage('saved',id='employee')],'jd_last_model_view':{'document':'other'}},
                {'configurable':{'thread_id':scope.document_id}},durability='sync')
        saved=graph.get_state({'configurable':{'thread_id':scope.document_id}})
        assert saved.values['messages'][0].content=='saved'
    assert requests==[]


def test_notice_db_failure_keeps_saved_input_and_never_calls_handler(jd,monkeypatch):
    from test_jd_tools import run_calls
    from langgraph.checkpoint.memory import InMemorySaver
    saver=InMemorySaver();scope=seed(jd)
    run_calls(jd,scope,[],saver=saver)
    def fail(*a): raise RuntimeError('synthetic read failure')
    monkeypatch.setattr(jd.store,'current',fail)
    with pytest.raises(RuntimeError,match='synthetic read failure'):
        run_calls(jd,scope,[],saver=saver)
    state=saver.get_tuple({'configurable':{'thread_id':scope.document_id}}).checkpoint['channel_values']
    assert state['messages'][-1].type=='human'
    assert len(state['messages'])==3


def test_compaction_reinjects_notice_after_native_item_and_does_not_claim_cut_results(jd):
    from test_jd_tools import run_calls
    from langgraph.checkpoint.memory import InMemorySaver
    saver=InMemorySaver();scope=seed(jd)
    _,first,_,_,_=run_calls(jd,scope,[('jd_read',{})],saver=saver,compaction=True)
    previous_results=set(first['jd_results'])
    assert save_text(jd,scope,'跨輪後改').status=='committed'
    _,second,requests,_,_=run_calls(jd,scope,[('jd_read',{})],saver=saver)
    for request in requests:
        notice=notice_from(request)
        assert notice['turn_start_interval']['manual_count']==1
        assert notice['prior_content_availability']=='unknown_after_compaction'
        assert not previous_results.intersection(notice['visible_jd_result_ids'])
        assert request['input'][-1]['role']=='user'
        assert any(item.get('type')=='compaction' for item in request['input'][:-1])
    assert second['jd_last_model_view']['context_cut'] is True
    assert len(second['jd_last_model_view']['visible_jd_results'])==1


def test_original_tool_limit_stops_without_claiming_unread_pages(jd):
    from test_jd_tools import run_calls
    scope=seed(jd,[{'id':'p'+str(i),'type':'p','children':[{'text':str(i)}]} for i in range(3)])
    values,result,requests,_,_=run_calls(jd,scope,[('jd_read',{}),('jd_read',lambda v:{'continuation_ref':v[-1]['continuation_ref']}),
        ('jd_read',lambda v:{'continuation_ref':v[-1]['continuation_ref']})],page_size=1,max_tool_calls=1)
    assert result['turn_outcome']['status']=='limit'
    assert values[0]['continuation_ref'] is not None
    assert result['jd_last_model_view']['visible_jd_results']==['jd-result:'+next(m.tool_call_id for m in result['messages'] if m.type=='tool')]
    assert 'unread scope' in __import__('json').dumps(requests[-1])
    assert len(requests)==2


def test_response_and_manifest_are_saved_before_after_model_stop(jd):
    from analysis_agent.jd_tools import JdToolSession
    from analysis_agent.conversation import build_conversation
    from analysis_agent.sources import ConversationReader
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.messages import HumanMessage,AIMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from test_provider_recovery import offline_model,completed
    scope=seed(jd)
    class StopAfter(AgentMiddleware):
        def after_model(self,state,runtime): raise RuntimeError('stop after saved model')
    with offline_model(lambda request:completed()) as model:
        saver=InMemorySaver();reader=ConversationReader(build_conversation(model=model,checkpointer=saver,instructions='test'),scope.document_id)
        session=JdToolSession(jd,reader)
        graph=build_conversation(model=model,checkpointer=saver,instructions='test',tools=session.tools,middleware=[session,StopAfter()]);reader.graph=graph
        config={'configurable':{'thread_id':scope.document_id}}
        with pytest.raises(RuntimeError,match='stop after saved model'):
            graph.invoke({'messages':[HumanMessage('原始問句',id='saved-input')]},config,durability='sync')
        root=graph.get_state(config,subgraphs=True)
        child=next(task.state for task in root.tasks if task.name=='analysis')
        message=child.values['messages'][-1]
        assert isinstance(message,AIMessage)
        assert child.values['jd_last_model_view']['response_id']==message.id
        assert child.values['messages'][0].content=='原始問句'
        assert all('app_jd_context' not in str(m.content) for m in child.values['messages'])
        assert child.values['jd_last_model_view']['visible_jd_results']==[]


def test_unpaired_old_manifest_is_unknown_not_current_or_no_changes(jd):
    from test_jd_tools import run_calls
    from langgraph.checkpoint.memory import InMemorySaver
    saver=InMemorySaver();scope=seed(jd)
    _,first,_,graph,_=run_calls(jd,scope,[],saver=saver)
    graph.update_state({'configurable':{'thread_id':scope.document_id}},
        {'jd_last_model_view':{**first['jd_last_model_view'],'response_id':'lost-response'}},as_node='analysis')
    assert save_text(jd,scope,'manual').status=='committed'
    _,_,requests,_,_=run_calls(jd,scope,[],saver=saver)
    notice=notice_from(requests[0])
    assert notice['since_last_response']['baseline']=='unknown'
    assert notice['since_last_response']['manual_count'] is None
    assert notice['current_content']['fragment'][0]['children'][0]['text']=='manual'


def test_ai_after_manual_does_not_hide_manual_event_in_interval(jd):
    from test_jd_tools import run_calls
    from langgraph.checkpoint.memory import InMemorySaver
    from analysis_agent.jd_types import JdEditIntent
    from analysis_agent.jd_contract import request_digest
    saver=InMemorySaver();scope=seed(jd)
    run_calls(jd,scope,[],saver=saver)
    assert save_text(jd,scope,'manual').status=='committed'
    base=jd.store.current(scope)
    commands=[{'type':'replace_block_content','target_id':base.value[0]['id'],'content':[{'text':'ai'}]}]
    assert jd.edit(JdEditIntent(scope,uuid4(),base.id,request_digest(scope,base.id,commands,'ai'),commands)).status=='committed'
    _,_,requests,_,_=run_calls(jd,scope,[],saver=saver)
    notice=notice_from(requests[0])
    assert notice['since_last_response']['manual_count']==notice['since_last_response']['ai_count']==1
    assert [event['origin'] for event in notice['events']]==['manual','ai']


def test_notice_capacity_failure_never_advances_response_manifest(jd,monkeypatch):
    from analysis_agent import jd_context
    from test_jd_tools import run_calls
    from langgraph.checkpoint.memory import InMemorySaver
    scope=seed(jd);saver=InMemorySaver()
    _,first,_,_,_=run_calls(jd,scope,[],saver=saver)
    monkeypatch.setattr(jd_context,'MAX_BYTES',1)
    with pytest.raises(jd_context.JdContextFailure,match='budget'):
        run_calls(jd,scope,[],saver=saver)
    state=saver.get_tuple({'configurable':{'thread_id':scope.document_id}}).checkpoint['channel_values']
    assert state['jd_last_model_view']==first['jd_last_model_view']
    assert state['messages'][-1].type=='human'
