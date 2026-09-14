"""Bounded v2 SDK serialization evidence; MockTransport only, no tool execution.

Adapted from ../jd-contract-closure/provider-wire.py. Run with the existing
analysis-agent virtualenv; do not install packages or use a real API key.
"""

import copy
import hashlib
import json
import os
import socket
import sys
from importlib.metadata import version
from pathlib import Path

artifact_dir = Path(__file__).resolve().parent
repo = artifact_dir.parents[3]
sys.path.insert(0, str(repo / '.worktrees/analysis-only-agent/experiments/analysis-agent/src'))
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'


def reject_network(*args, **kwargs):
    raise AssertionError('This serialization probe prohibits network connections')


socket.create_connection = reject_network
socket.socket.connect = reject_network

import httpx
from langchain.agents.middleware import wrap_model_call
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent

schema_path = repo / 'docs/specs/contracts/jd-editor-v2.schema.json'
schema_bytes = schema_path.read_bytes()
schema = json.loads(schema_bytes)


class FixedTool(BaseTool):
    name: str
    description: str
    args_schema: dict

    def _run(self, **kwargs):
        raise AssertionError('No tool execution is expected')


def extract(name):
    root = copy.deepcopy(schema['$defs'][name])
    found = {}
    pending = [root]
    while pending:
        part = pending.pop()
        if isinstance(part, dict):
            ref = part.get('$ref', '')
            if ref.startswith('#/$defs/'):
                key = ref.rsplit('/', 1)[1]
                if key not in found:
                    found[key] = copy.deepcopy(schema['$defs'][key])
                    pending.append(found[key])
            pending.extend(v for k, v in part.items() if k != '$ref')
        elif isinstance(part, list):
            pending.extend(part)
    if found:
        root['$defs'] = found
    return root


names = {'jd_read': 'JdReadModelInput', 'jd_edit': 'JdEditModelInput', 'jd_change_read': 'JdChangeReadModelInput'}
parameters = {name: extract(defname) for name, defname in names.items()}
jd = [FixedTool(name=name, description=schema['$defs'][names[name]]['description'], args_schema=parameters[name]) for name in names]
other = FixedTool(name='unchanged_existing_shape', description='Non-JD control tool; not executed.', args_schema={'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text']})
converted = {t.name: convert_to_openai_tool(t) for t in jd}


@wrap_model_call
def fixed_jd_projection(request, handler):
    projected = []
    for tool in request.tools:
        if any(tool is original for original in jd):
            projected.append({'type': 'function', 'name': tool.name, 'description': tool.description, 'parameters': parameters[tool.name], 'strict': False})
        else:
            projected.append(tool)
    return handler(request.override(tools=projected))


captured = []


def respond(request):
    captured.append(json.loads(request.content))
    return httpx.Response(400, json={'error': {'message': 'fixed offline serialization stop', 'type': 'invalid_request_error'}})


stopped_exception = None
stopped_detail = None
with httpx.Client(transport=httpx.MockTransport(respond)) as client:
    model = build_model(model='gpt-5.6-luna', api_key='offline-fixed', base_url='http://offline.invalid/v1', http_client=client)
    agent = build_agent(model=model, checkpointer=None, instructions='fixed serialization only', tools=[*jd, other], middleware=[fixed_jd_projection])
    try:
        agent.invoke({'messages': [HumanMessage('fixed serialization', id='offline-input')]})
    except Exception as error:
        stopped_exception = type(error).__name__
        stopped_detail = str(error)

assert stopped_exception == 'OpenAIInvalidRequestError', (stopped_exception, stopped_detail, len(captured))
assert len(captured) == 1, 'Exactly one local mock request expected'
wire = {tool.get('name'): tool for tool in captured[0]['tools']}
assert all(wire[name]['parameters'] == parameters[name] for name in names)
assert all(wire[name]['description'] == schema['$defs'][names[name]]['description'] for name in names)
assert all(wire[name]['strict'] is False for name in names)
assert 'strict' not in wire['unchanged_existing_shape']
assert captured[0]['parallel_tool_calls'] is False and captured[0]['store'] is False
edit = wire['jd_edit']['parameters']
defs = edit['$defs']
assert set(edit['properties']) == {'commands'}
assert not {'id', 'attributes', 'knowledge_refs', 'skill_refs', 'knowledge_ids', 'skill_ids'} & set(defs['JdNewElement']['properties'])
assert {'knowledge_refs', 'skill_refs'} <= set(defs['JdEditableProperties']['properties'])
assert not {'knowledge_ids', 'skill_ids', 'attributes'} & set(defs['JdEditableProperties']['properties'])
assert {'knowledge_refs', 'skill_refs'} <= set(defs['JdUnsettableProperty']['enum'])
assert not {'knowledge_ids', 'skill_ids'} & set(defs['JdUnsettableProperty']['enum'])
assert 'JdResolvedEditableProperties' not in defs
assert {'jd_outcomes', 'jd_requirements', 'jd_knowledge', 'jd_skill'} <= set(defs['JdElementType']['enum'])
task_rule = next(rule for rule in defs['JdNewElement']['allOf'] if rule.get('if', {}).get('properties', {}).get('type', {}).get('const') == 'jd_task')
assert task_rule['then']['properties']['children']['minItems'] == 3
for kind in ['jd_outcomes', 'jd_requirements']:
    rule = next(rule for rule in task_rule['then']['properties']['children']['allOf'] if rule['contains'].get('properties', {}).get('type', {}).get('const') == kind)
    assert rule['minContains'] == rule['maxContains'] == 1
for field in ['knowledge_refs', 'skill_refs']:
    assert any(rule['not']['properties']['set']['required'] == [field] and rule['not']['properties']['unset']['contains']['const'] == field for rule in defs['JdPropertyUpdateConstraint']['allOf'])
assert all(term in wire['jd_read']['description'] for term in ['knowledge_refs', 'skill_refs', 'used_by_task_refs'])
assert 'First create items without links' in wire['jd_edit']['description']
assert schema_path.read_bytes() == schema_bytes, 'Schema changed during this probe'

captured_path = artifact_dir / 'provider-wire-v2-captured.json'
captured_path.write_text(json.dumps(captured[0], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
result = {
    'schema': str(schema_path.relative_to(repo)),
    'schema_sha256': hashlib.sha256(schema_bytes).hexdigest(),
    'schema_defs': len(schema['$defs']),
    'versions': {name: version(name) for name in ['langchain', 'langchain-core', 'langchain-openai', 'openai']},
    'base_tool_conversion': {name: {'original_refs': json.dumps(parameters[name]).count('"$ref"'), 'converted_refs': json.dumps(tool['function']['parameters']).count('"$ref"'), 'has_defs': '$defs' in tool['function']['parameters']} for name, tool in converted.items()},
    'wire': [{'name': name, 'parameters_equal': wire[name]['parameters'] == parameters[name], 'description_equal': wire[name]['description'] == schema['$defs'][names[name]]['description'], 'strict': wire[name]['strict'], 'has_defs': '$defs' in wire[name]['parameters']} for name in names],
    'v2_checks': {'commands_only': True, 'new_ids_links_attributes_absent': True, 'model_refs_set_unset_present': True, 'resolved_ids_absent': True, 'exact_two_task_groups_present': True, 'knowledge_skill_types_present': True, 'set_unset_constraints_present': True, 'read_projection_description_present': True, 'first_creation_description_present': True},
    'control_tool_strict': 'OMITTED',
    'parallel_tool_calls': captured[0]['parallel_tool_calls'],
    'store': captured[0]['store'],
    'stopped_exception': stopped_exception,
    'mock_request_count': len(captured),
    'network_requests': 0,
    'tool_executions': 0,
    'probe_history': 'The first two invocations each captured one local mock request and failed a probe assertion expecting BadRequestError. The second added diagnostics and identified the fixed SDK wrapper OpenAIInvalidRequestError for the intentional HTTP 400. The third invocation corrected the assertion and passed; this is a probe assertion correction, not a tool-contract change. All three invocations used MockTransport with no network or tool execution.',
    'captured_request': captured_path.name,
    'limitations': ['SDK serialization only; no real provider acceptance or natural model quality', 'No ToolNode execution, JD read result production, native transform, or database access', 'ReadTarget result shape is not a model-input definition; its handling is mentioned in the transmitted official tool description']
}
(artifact_dir / 'provider-wire-v2-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
