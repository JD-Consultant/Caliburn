"""Approved CT25 contract at the SDK boundary, not natural model selection.

The fixed HTTP responses only let the real middleware/SDK assemble requests.
The independently reviewed fixture catches missing/duplicated/misrouted prompt
blocks or tool contracts; it cannot establish that Luna chooses the right tool.
"""
import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path
import re

from langchain_core.messages import HumanMessage
from langgraph.store.memory import InMemoryStore

from analysis_agent import api
from analysis_agent.conversation import build_conversation
from analysis_agent.live_memory import MemorySession
from analysis_agent.skills import SkillAssets, analysis_skills
from test_consolidation import call, done
from test_live_memory import h, system_wire
from test_service import service_harness


def application_instructions():
    # Read the real composition literal without opening API clients, keys or PG.
    tree = ast.parse(inspect.getsource(inspect.unwrap(api.open_service)))
    factory = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name) and node.func.id == 'AnalysisService')
    value = next(k.value for k in factory.keywords if k.arg == 'instructions')
    assert isinstance(value, ast.Name) and value.id == 'ADVISOR_INSTRUCTIONS'
    return api.ADVISOR_INSTRUCTIONS


def assert_reviewed_contract(payloads, *, revision, guide):
    fixture = Path(__file__).resolve().parents[3] / 'docs/specs/evidence/2026-09-08-ct25-memory-prompt-candidate.json'
    expected = json.loads(fixture.read_text(encoding='utf-8'))
    # CT41 reviewed delta; preserve the CT25 historical evidence unchanged.
    # This checks SDK prompt routing, NOT whether the model obeys the text.
    delta = json.loads((Path(__file__).parent / 'fixtures/ct41-memory-action-delta.json').read_text(encoding='utf-8'))
    matches = 0
    for item in expected['system']:
        for block in item['content']:
            matches += block['text'].count(delta['before'])
            block['text'] = block['text'].replace(delta['before'], delta['after'])
    assert matches == 1
    read_delta = json.loads((Path(__file__).parent / 'fixtures/ct43-memory-read-delta.json').read_text(encoding='utf-8'))
    matches = 0
    for item in expected['system']:
        for block in item['content']:
            matches += block['text'].count(read_delta['before'])
            block['text'] = block['text'].replace(read_delta['before'], read_delta['after'])
    assert matches == 1
    # Reviewed CT48 shared patch-description delta, not a regenerated snapshot.
    # The preserved historical fixture continues checking every other field.
    patch_delta = json.loads((Path(__file__).parent / 'fixtures/ct48-patch-guidance-delta.json').read_text(encoding='utf-8'))
    repair = next(tool for tool in expected['tools'] if tool['name'] == 'repair_memory')
    assert repair['description'].count(patch_delta['before']) == 1
    repair['description'] = repair['description'].replace(patch_delta['before'], patch_delta['after'])
    # Task6 only changes main JD capability and adds on-demand method metadata.
    # Keep the independently reviewed historical Memory contract unchanged.
    jd_delta = json.loads((Path(__file__).parent / 'fixtures/jd-task6-prompt-delta.json').read_text(encoding='utf-8'))
    for replacement in jd_delta['replacements']:
        matches = 0
        for item in expected['system']:
            for block in item['content']:
                matches += block['text'].count(replacement['before'])
                block['text'] = block['text'].replace(replacement['before'], replacement['after'])
        assert matches == 1
    for payload in payloads:
        system = deepcopy(system_wire(payload))
        for block in system[0]['content']:
            block['text'] = block['text'].replace(
                f"Initial guide publication revision: {revision}",
                'Initial guide publication revision: {{initial_memory_revision}}').replace(
                guide, '{{initial_memory_guide}}')
            block['text'] = re.sub(r'(?<=Current input reference \(copy only if useful\): )conversation:\S+',
                                   '{{current_input_reference}}', block['text'])
        assert system == expected['system']
        assert payload['tools'] == expected['tools']
        assert payload['parallel_tool_calls'] is False
        assert 'tool_choice' not in payload


def test_actual_sdk_request_matches_reviewed_contract_through_tool_followup(h):
    assets = SkillAssets()
    memory = MemorySession(h.pub, h.source, skill_assets=assets)
    graph = build_conversation(model=h.model, checkpointer=h.saver,
        instructions=application_instructions(), tools=memory.tools,
        middleware=[analysis_skills(assets), memory])
    h.source.graph = graph
    initial = h.pub.current()
    initial_guide = h.artifacts.guide(initial.memory)
    h.replies.extend([call('read_file', file_path='/memory/knowledge.md'), done()])
    graph.invoke({'messages': [HumanMessage('更正為處長核准。', id='ct22-wire')]},
                 h.config, durability='sync')
    assert len(h.sent) == 2
    assert_reviewed_contract(h.sent, revision=initial.revision, guide=initial_guide)
    # Read-only fixture response cannot silently publish or enqueue background.
    assert h.pub.current().revision == 1
    assert h.source.pending_consolidation_turns() == []


def test_service_initial_memory_request_matches_reviewed_contract(tmp_path):
    # Exercise AnalysisService._context, including the normal Memory and Skills
    # composition. The official Store is present even before first publication.
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        service.instructions = application_instructions()
        document = service.create_document('新訪談提示接線')['id']
        context = service._context(document)
        context.memory.publication.setup()
        service.enable_background(max_recoveries=2)
        replies.extend([call('read_file', file_path='/skills/work-scope-interview/SKILL.md'), done()])
        run = service.submit(document, 'ct22-service', '我會依照客戶需求製作網站。')
        service.join(document)
        assert service.get_run(document, run['id'])['status'] == 'completed'
        assert len(sent) == 2
        assert_reviewed_contract([json.loads(request.content) for request in sent],
                                 revision=0, guide='No memory has been published yet.')
        assert context.memory.publication.current() is None
        assert context.reader.pending_consolidation_turns() == []


def test_service_default_budget_can_complete_multisource_read(tmp_path):
    """Real service default routing; natural retrieval evidence lives in CT49."""
    with service_harness(tmp_path, store=InMemoryStore(),
                         max_model_steps=None, max_tool_calls=None) as (service, sent, replies):
        doc = service.create_document('多來源回查額度')['id']
        service._context(doc).memory.publication.setup()
        # Fourteen real read operations plus an answer. This fixture is not a
        # recommendation to repeatedly read the same file in a real interview.
        replies.extend([call('read_file', file_path='/skills/work-scope-interview/SKILL.md') for _ in range(14)])
        replies.append(done())
        run = service.submit(doc, 'multi-source-budget', '核對多份訪談的原句。')
        service.join(doc)
        state = service.get_run(doc, run['id'])
        context = service._context(doc)
        snapshot = context.graph.get_state(context.config, subgraphs=True)
        assert state['status'] == 'completed', (state['error_code'], str(snapshot.tasks), len(sent))
        assert len(sent) == 15
