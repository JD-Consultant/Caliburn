"""Final actual-request integrity of checkpointed JD tool results."""
import json
from contextlib import contextmanager
import pytest
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from test_jd_postgres import jd
from test_jd_tools import seed,run_calls


@pytest.mark.parametrize('mutate',[True,False])
def test_final_jd_projection_matches_actual_next_request(jd,monkeypatch,mutate):
    import test_jd_tools
    original=test_jd_tools.offline_model
    requests=[]; baselines=[]
    @contextmanager
    def observe(respond):
        def counted(request):
            requests.append(json.loads(request.content))
            return respond(request)
        with original(counted) as model: yield model
    monkeypatch.setattr(test_jd_tools,'offline_model',observe)
    class Later(AgentMiddleware):
        def wrap_model_call(self,request,handler):
            messages=[]
            for message in request.messages:
                if isinstance(message,ToolMessage) and message.name=='jd_read':
                    baselines.append(request.state['jd_last_model_view'].copy())
                    if mutate:
                        body=json.loads(message.content)
                        body['fragment'][0]['children'][0]['text']='ALTERED WORDS SAME ID'
                        message=message.model_copy(update={'content':json.dumps(body)})
                messages.append(message)
            return handler(request.override(messages=messages))
    scope=seed(jd,[{'id':'p','type':'p','children':[{'text':'CANONICAL ORIGINAL'}]}])
    saver=InMemorySaver()
    if mutate:
        with pytest.raises(ValueError,match='JD model request'):
            run_calls(jd,scope,[('jd_read',{})],saver=saver,extra_middleware=[Later()])
        assert len(requests)==1 # No provider entry for the changed second request.
        # The interrupted child checkpoint owns the saved first response view.
        states=[item.checkpoint['channel_values'] for item in saver.list(None)]
        viewed=[state for state in states if state.get('jd_last_model_view')]
        assert viewed and all(state['jd_last_model_view']==baselines[0] for state in viewed)
        canonical=[m for state in states for m in state.get('messages',[]) if isinstance(m,ToolMessage)]
        assert canonical and all('ALTERED WORDS SAME ID' not in m.content for m in canonical)
    else:
        _,state,_,_,_=run_calls(jd,scope,[('jd_read',{})],saver=saver,extra_middleware=[Later()])
        assert len(requests)==2
        output=next(x for x in requests[-1]['input'] if x.get('type')=='function_call_output')
        assert json.loads(output['output'])['fragment'][0]['children'][0]['text']=='CANONICAL ORIGINAL'
        assert state['jd_last_model_view']['visible_jd_results']
        assert state['jd_last_model_view']['response_id']==state['messages'][-1].id
