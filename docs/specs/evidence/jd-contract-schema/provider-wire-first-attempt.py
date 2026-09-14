import json, copy
from pathlib import Path
from importlib.metadata import version
import httpx
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain.agents.middleware import wrap_model_call
from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
schema=json.loads(Path('../../../../docs/specs/contracts/jd-editor-v1.schema.json').read_text(encoding='utf-8'))
class FixedTool(BaseTool):
    name: str
    description: str='fixed offline serialization only'
    args_schema: dict
    def _run(self, **kwargs):
        raise AssertionError('No tool execution is expected')
# Exact SSOT extraction only: retain referenced definitions without rewriting them.
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
jd=[FixedTool(name=name,args_schema=parameters[name]) for name in names]
other=FixedTool(name='unchanged_existing_shape',args_schema={'type':'object','properties':{'text':{'type':'string'}},'required':['text']})
converted={t.name:convert_to_openai_tool(t) for t in jd}
print(json.dumps({'versions':{n:version(n) for n in ['langchain','langchain-core','langchain-openai','openai']},'BaseTool_conversion':{name:{'root_type':c['function']['parameters'].get('type'),'has_defs':'$defs' in c['function']['parameters'],'original_refs':json.dumps(parameters[name]).count('"$ref"'),'converted_refs':json.dumps(c['function']['parameters']).count('"$ref"'),'strict_present':'strict' in c['function']} for name,c in converted.items()}},ensure_ascii=False))
@wrap_model_call
def fixed_jd_projection(request, handler):
    projected=[]
    for t in request.tools:
        if any(t is original for original in jd):
            projected.append({'type':'function','name':t.name,'description':t.description,'parameters':parameters[t.name],'strict':False})
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
    except Exception as e:
        print(json.dumps({'stopped_exception':type(e).__name__,'request_count':len(captured)}))
wire={t.get('name'):t for t in captured[0]['tools']}
print(json.dumps({'wire':[{'name':name,'type':wire[name]['type'],'strict':wire[name].get('strict','OMITTED'),'parameters_equal':wire[name].get('parameters')==parameters[name],'has_defs':'$defs' in wire[name].get('parameters',{})} for name in names],'other_strict':wire['unchanged_existing_shape'].get('strict','OMITTED'),'parallel_tool_calls':captured[0].get('parallel_tool_calls'),'store':captured[0].get('store'),'tool_executed':False,'network':'httpx.MockTransport only'},ensure_ascii=False))
