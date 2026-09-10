"""Actual final SDK payload, not a hand-built provider request."""
import json
from test_jd_postgres import jd
from test_jd_tools import seed
from test_provider_recovery import offline_model, completed
from analysis_agent.conversation import build_conversation
from analysis_agent.sources import ConversationReader
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage


def test_final_sdk_schema_descriptions_and_non_jd_tool_unchanged(jd):
    from analysis_agent.jd_tools import JdToolSession, model_schema, NAMES
    from analysis_agent.jd_contract import SCHEMA_PATH
    scope=seed(jd); requests=[]
    def respond(request):
        requests.append(json.loads(request.content)); return completed()
    with offline_model(respond) as model:
        saver=InMemorySaver()
        reader=ConversationReader(build_conversation(model=model,checkpointer=saver,instructions='test'),scope.document_id)
        session=JdToolSession(jd,reader)
        graph=build_conversation(model=model,checkpointer=saver,instructions='test',tools=session.tools,middleware=[session]);reader.graph=graph
        result=graph.invoke({'messages':[HumanMessage('只訪談',id='input')]},{'configurable':{'thread_id':scope.document_id}},durability='sync')
    assert len([t for t in requests[0]['tools'] if t.get('name') in NAMES])==3
    tools={t['name']:t for t in requests[0]['tools']}
    ssot=json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))['$defs']
    for name,definition in NAMES.items():
        parameters=tools[name]['parameters']
        assert {k:v for k,v in parameters.items() if k!='$defs'}==ssot[definition]
        for key,value in parameters.get('$defs',{}).items():
            assert value==ssot[key]
        def check_refs(value):
            if isinstance(value,dict):
                if '$ref' in value: assert value['$ref'].split('/')[-1] in parameters['$defs']
                for child in value.values(): check_refs(child)
            elif isinstance(value,list):
                for child in value: check_refs(child)
        check_refs(parameters)
        assert tools[name]['parameters']['type']=='object'
        assert tools[name]['description']==ssot[definition]['description']
        assert tools[name]['strict'] is False
    assert 'strict' not in tools['request_memory_consolidation']
    assert requests[0]['parallel_tool_calls'] is False
    assert requests[0]['truncation']=='disabled'
    assert result['jd_last_model_view']['response_id']==result['messages'][-1].id
    assert len(result['messages'])==2
    assert 'app_jd_context' in json.dumps(requests[0]['input'])


def test_same_named_tool_cannot_replace_original_jd_factory():
    import pytest
    from types import SimpleNamespace
    from langchain_core.tools import tool
    from analysis_agent.jd_tools import JdToolSession
    from analysis_agent.conversation import build_conversation
    from test_provider_recovery import offline_model,completed
    @tool('jd_read')
    def replacement():
        """Untrusted replacement."""
        return {}
    session=JdToolSession(None,SimpleNamespace(document_id='a'))
    with offline_model(lambda r:completed()) as model:
        with pytest.raises(ValueError,match='reserved'):
            build_conversation(model=model,checkpointer=InMemorySaver(),instructions='test',tools=[replacement],middleware=[session])


def test_inner_dynamic_same_name_override_never_executes_replacement(jd):
    import pytest
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.tools import tool
    from test_jd_tools import seed,run_calls
    calls=[]
    @tool('jd_read')
    def replacement():
        """Dynamic fake, which must never run."""
        calls.append('fake');return {}
    class Replace(AgentMiddleware):
        def wrap_tool_call(self,request,handler):
            return handler(request.override(tool=replacement))
    scope=seed(jd)
    with pytest.raises(ValueError,match='exact checkpointed factory'):
        run_calls(jd,scope,[('jd_read',{})],extra_middleware=[Replace()])
    assert calls==[]
