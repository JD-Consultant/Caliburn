import json, copy, sys
sys.path.insert(0,'src')
from pathlib import Path
from importlib.metadata import version
import httpx
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain.agents.middleware import wrap_model_call
from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
artifact_dir=Path(__file__).resolve().parent
repo=artifact_dir.parents[3]
schema=json.loads((repo/'docs/specs/contracts/jd-editor-v1.schema.json').read_text(encoding='utf-8'))
class FixedTool(BaseTool):
    name: str
    description: str
    args_schema: dict
    def _run(self, **kwargs): raise AssertionError('No tool execution is expected')
def extract(name):
    root=copy.deepcopy(schema['$defs'][name]); found={}; pending=[root]
    while pending:
        part=pending.pop()
        if isinstance(part,dict):
            ref=part.get('$ref','')
            if ref.startswith('#/$defs/'):
                key=ref.rsplit('/',1)[1]
                if key not in found:
                    found[key]=copy.deepcopy(schema['$defs'][key]); pending.append(found[key])
            pending.extend(v for k,v in part.items() if k!='$ref')
        elif isinstance(part,list): pending.extend(part)
    if found: root['$defs']=found
    return root
names={'jd_read':'JdReadModelInput','jd_edit':'JdEditModelInput','jd_change_read':'JdChangeReadModelInput'}
parameters={name:extract(defname) for name,defname in names.items()}
jd=[FixedTool(name=name,description=schema['$defs'][names[name]]['description'],args_schema=parameters[name]) for name in names]
other=FixedTool(name='unchanged_existing_shape',description='Non-JD control tool; not executed.',args_schema={'type':'object','properties':{'text':{'type':'string'}},'required':['text']})
converted={t.name:convert_to_openai_tool(t) for t in jd}
print(json.dumps({'versions':{n:version(n) for n in ['langchain','langchain-core','langchain-openai','openai']},'BaseTool_conversion':{name:{'root_type':c['function']['parameters'].get('type'),'has_defs':'$defs' in c['function']['parameters'],'original_refs':json.dumps(parameters[name]).count('"$ref"'),'converted_refs':json.dumps(c['function']['parameters']).count('"$ref"'),'strict_present':'strict' in c['function']} for name,c in converted.items()}},ensure_ascii=False))
@wrap_model_call
def fixed_jd_projection(request, handler):
    projected=[]
    for t in request.tools:
        if any(t is original for original in jd): projected.append({'type':'function','name':t.name,'description':t.description,'parameters':parameters[t.name],'strict':False})
        else: projected.append(t)
    return handler(request.override(tools=projected))
captured=[]
def respond(request):
    captured.append(json.loads(request.content))
    return httpx.Response(400,json={'error':{'message':'fixed offline serialization stop','type':'invalid_request_error'}})
with httpx.Client(transport=httpx.MockTransport(respond)) as client:
    model=build_model(model='gpt-5.6-luna',api_key='offline-fixed',http_client=client)
    agent=build_agent(model=model,checkpointer=None,instructions='fixed serialization only',tools=[*jd,other],middleware=[fixed_jd_projection])
    try: agent.invoke({'messages':[HumanMessage('fixed serialization',id='offline-input')]})
    except Exception as e: print(json.dumps({'stopped_exception':type(e).__name__,'request_count':len(captured)}))
wire={t.get('name'):t for t in captured[0]['tools']}
print(json.dumps({'wire':[{'name':name,'type':wire[name]['type'],'strict':wire[name].get('strict','OMITTED'),'parameters_equal':wire[name].get('parameters')==parameters[name],'has_defs':'$defs' in wire[name].get('parameters',{})} for name in names],'other_strict':wire['unchanged_existing_shape'].get('strict','OMITTED'),'parallel_tool_calls':captured[0].get('parallel_tool_calls'),'store':captured[0].get('store'),'tool_executed':False,'network':'httpx.MockTransport only'},ensure_ascii=False))

assert len(captured)==1, "Exactly one local mock request expected"
assert all(wire[name]['parameters']==parameters[name] for name in names)
assert all(wire[name]['description']==schema['$defs'][names[name]]['description'] for name in names)
assert all(wire[name]['strict'] is False for name in names)
assert 'strict' not in wire['unchanged_existing_shape']
assert captured[0]['parallel_tool_calls'] is False and captured[0]['store'] is False
assert set(wire['jd_edit']['parameters']['properties'])=={'commands'}
assert 'attributes' not in wire['jd_edit']['parameters']['$defs']['JdNewElement']['properties']
assert 'attributes' not in wire['jd_edit']['parameters']['$defs']['JdEditableProperties']['properties']
assert 'JdPropertyUpdateConstraint' in wire['jd_edit']['parameters']['$defs']
assert 'fixed offline serialization only' not in json.dumps(wire)
(artifact_dir/'provider-request.json').write_text(json.dumps(captured[0],ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'formal_descriptions_equal':True,'commands_only':True,'model_html_attributes_absent':True,'shared_property_constraint_present':True,'request_artifact':'provider-request.json','network_requests':0,'tool_executions':0}))
