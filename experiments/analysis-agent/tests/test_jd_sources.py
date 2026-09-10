def test_source_validation_has_explicit_issuance_boundary():
    from analysis_agent.jd_references import validate_sources
    import pytest
    with pytest.raises(ValueError,match='issued'):
        validate_sources(['conversation:invented'],{},None)


def test_actual_canonical_sources_scope_closed_window_and_omitted_tools(jd):
    import base64,json
    from uuid import uuid4
    from test_jd_tools import seed,run_calls
    from analysis_agent.jd_references import validate_sources
    from analysis_agent.sources import parse_reference
    from langchain_core.messages import HumanMessage,ToolMessage
    import pytest
    scope=seed(jd)
    _,state,_,_,session=run_calls(jd,scope,[('jd_read',{})])
    human=next(m for m in state['messages'] if isinstance(m,HumanMessage))
    reference=session.source.capture(human.id,state['messages'][-1].id)
    with pytest.raises(ValueError,match='issued'): validate_sources([reference],{},session.source)
    validate_sources([reference],{reference:{'tool_call':'actual-read'}},session.source)
    page=session.source.read(reference)
    assert page['segments'][0]['text']=='固定工具驗收'
    assert 'tool' in page['omitted_content_types']
    def changed(**kwargs):
        fields={**parse_reference(reference,scope.document_id),**kwargs}
        return 'conversation:'+base64.urlsafe_b64encode(json.dumps(fields).encode()).decode()
    for bad in [changed(document='other'),changed(checkpoint=str(uuid4()))]:
        with pytest.raises(ValueError): validate_sources([bad],{bad:{'tool_call':'read'}},session.source)
    message=next(m for m in state['messages'] if isinstance(m,ToolMessage))
    bad=changed(first=message.id,last=message.id)
    with pytest.raises(ValueError): validate_sources([bad],{bad:{'current_input':message.id}},session.source)

from test_jd_postgres import jd


def test_original_memory_reader_with_jd_guard_issues_exact_historical_source(jd):
    import json,httpx
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.store.memory import InMemoryStore
    from langchain_core.messages import HumanMessage
    from analysis_agent.memory import MemoryArtifacts
    from analysis_agent.live_memory import MemorySession
    from analysis_agent.publication import PublicationStore
    from analysis_agent.conversation import build_conversation
    from analysis_agent.jd_tools import JdToolSession
    from analysis_agent.sources import ConversationReader
    from test_jd_tools import seed,run_calls
    from test_provider_recovery import offline_model
    from test_native_continuity import response_body,assistant_text
    from uuid import uuid4
    scope=seed(jd);saver=InMemorySaver()
    _,prior,_,oldgraph,oldsession=run_calls(jd,scope,[],saver=saver)
    reference=oldsession.source.capture(prior['messages'][0].id,prior['messages'][-1].id)
    seen=[]
    def respond(request):
        body=json.loads(request.content);seen.append(body)
        outputs=[x for x in body['input'] if x.get('type')=='function_call_output']
        if not outputs: name,args='read_conversation',{'reference':reference}
        elif len(outputs)==1:
            original=json.loads(outputs[-1]['output'])
            assert original['reference']==reference and original['segments'][0]['text']=='固定工具驗收'
            name,args='jd_read',{}
        elif len(outputs)==2:
            read=json.loads(outputs[-1]['output'])
            name,args='jd_edit',{'commands':[{'type':'set_properties','target_ref':read['targets'][0]['target_ref'],'set':{'source_refs':[reference]}}]}
        else:
            assert json.loads(outputs[-1]['output'])['status']=='committed'
            return httpx.Response(200,json=response_body([assistant_text('done')],response_id='resp_'+str(uuid4())))
        return httpx.Response(200,json=response_body([{'type':'function_call','id':'fc_'+str(uuid4()),'call_id':'call_'+str(uuid4()),
            'name':name,'arguments':json.dumps(args),'status':'completed'}],response_id='resp_'+str(uuid4())))
    with offline_model(respond) as model:
        reader=ConversationReader(oldgraph,scope.document_id)
        publication=PublicationStore(jd.catalog.engine,MemoryArtifacts(InMemoryStore(),scope.document_id,source=reader));publication.setup()
        memory=MemorySession(publication,reader)
        session=JdToolSession(jd,reader,source_read_tools=memory.read_tools)
        graph=build_conversation(model=model,checkpointer=saver,instructions='test',tools=[*memory.tools,*session.tools],middleware=[session,memory]);reader.graph=graph
        result=graph.invoke({'messages':[HumanMessage('保留已查原話',id=str(uuid4()))]}, {'configurable':{'thread_id':scope.document_id}},durability='sync')
    assert reference in result['jd_sources']
    assert jd.store.current(scope).value[0]['source_refs']==[reference]
    assert 'strict' not in next(t for t in seen[0]['tools'] if t['name']=='read_conversation')
    assert publication.current() is None
