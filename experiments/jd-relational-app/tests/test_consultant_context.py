"""Native graph/middleware checks with fixed replies; no provider or fake DB PASS."""

import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx2
import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from jd_relational.consultant_context import (
    ConsultantContext, ConsultantContextError, ConsultantState, JdNoticeMiddleware,
    build_consultant_node, read_closed_model_view,
)
from jd_relational.notice_history import NoticeBoundary, NoticeEvent, NoticeMaterial
from jd_relational.references import ReferenceCodec
from jd_relational.runtime_checkpoints import build_document_graph


@pytest.fixture(autouse=True)
def no_remote_tracing(monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING', 'false')
    monkeypatch.setenv('LANGCHAIN_TRACING_V2', 'false')


class FixedModel(BaseChatModel):
    replies: list[AIMessage]
    requests: list = []

    @property
    def _llm_type(self): return "fixed-offline-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests.append(deepcopy(messages))
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


class MaterialReader:
    """Only model context unit material. Real PG is in test_notice_history."""
    def __init__(self, material): self.material = material; self.calls = []
    def read(self, document, baseline, *, limit):
        self.calls.append((document, baseline, limit))
        value = self.material
        if baseline == value.head:
            return NoticeMaterial(document, baseline, value.head, (), 0, 0, 0)
        return value


def setup():
    document, dataset, run = (str(uuid4()) for _ in range(3))
    b, h = NoticeBoundary(uuid4(), 1), NoticeBoundary(uuid4(), 3)
    between = uuid4()
    events = (NoticeEvent(uuid4(), between, 2, h.revision_id, 3, "manual", "jd_set_text"),
        NoticeEvent(uuid4(), b.revision_id, 1, between, 2, "manual", "jd_set_text"))
    material = NoticeMaterial(document, None, h, events, 2, 0, 0)
    reader = MaterialReader(material)
    context = ConsultantContext(dataset, document, run, reader, ReferenceCodec(b'x'*32, dataset), material)
    reply = AIMessage(id='fixed-reply-'+str(uuid4()), content='我會依目前已保存的工作內容繼續。',
        response_metadata={'stop_reason':'end_turn', 'model_name':'synthetic'},
        usage_metadata={'input_tokens':20,'output_tokens':10,'total_tokens':30})
    return context, reply


def graph(model, saver):
    child = create_agent(model, tools=[], system_prompt='可信的合成顧問指引',
        middleware=[JdNoticeMiddleware()], state_schema=ConsultantState, context_schema=ConsultantContext)
    return build_document_graph(child, saver)


@pytest.mark.parametrize('asynchronous', [False, True])
def test_actual_model_request_and_closed_root_preserve_original_conversation(asynchronous):
    context, reply = setup()
    model = FixedModel(replies=[reply]); saver = InMemorySaver(); root = graph(model, saver)
    human = HumanMessage(id='original-employee', content='原話不可變。把「每週」更正為「每月」。')
    before = deepcopy(human.model_dump())
    config = {'configurable':{'thread_id':context.document_id}}
    if asynchronous:
        result = asyncio.run(root.ainvoke({'messages':[human]}, config,
            context=context, durability='sync'))
    else:
        result = root.invoke({'messages':[human]}, config, context=context, durability='sync')
    view = read_closed_model_view(root, document_id=context.document_id,
        dataset_id=context.dataset_id, run_id=context.run_id)
    assert view.revision_number == 3 and view.response_message_id == reply.id
    assert result['messages'][0].model_dump() == before
    assert [m.type for m in result['messages']] == ['human', 'ai']
    assert result['messages'][1].usage_metadata == reply.usage_metadata
    assert len(model.requests) == 1
    assert isinstance(model.requests[0][0], SystemMessage)
    notice = json.loads(model.requests[0][0].content[-1]['text'])
    assert notice['turn_start']['manual_change_count'] == 2
    assert notice['turn_start']['content_included'] is False
    assert human.content not in view.notice_json
    assert model.requests[0][1].model_dump() == before
    # Reconstruct the native root on the same Saver and only read: no new model.
    reopened = graph(FixedModel(replies=[]), saver)
    assert read_closed_model_view(reopened, document_id=context.document_id,
        dataset_id=context.dataset_id, run_id=context.run_id) == view


@pytest.mark.parametrize('stop', ['max_tokens', 'pause_turn', None])
def test_incomplete_reply_does_not_publish_notification_boundary(stop):
    context, reply = setup(); reply.response_metadata['stop_reason'] = stop
    model = FixedModel(replies=[reply]); root = graph(model, InMemorySaver())
    config = {'configurable':{'thread_id':context.document_id}}
    with pytest.raises(ConsultantContextError, match='incomplete_consultant_response'):
        root.invoke({'messages':[HumanMessage(content='synthetic')]}, config, context=context, durability='sync')
    assert len(model.requests) == 1
    with pytest.raises(ConsultantContextError, match='consultant_checkpoint_unconfirmed'):
        read_closed_model_view(root, document_id=context.document_id, dataset_id=context.dataset_id, run_id=context.run_id)


def test_wrong_scope_stops_before_model_and_corrupt_notice_is_rejected():
    context, reply = setup(); model = FixedModel(replies=[reply]); root = graph(model, InMemorySaver())
    with pytest.raises(ConsultantContextError, match='invalid_model_view'):
        root.invoke({'messages':[HumanMessage(content='x')], 'jd_model_view':{'document_id':str(uuid4())}},
            {'configurable':{'thread_id':context.document_id}}, context=context, durability='sync')
    assert not model.requests


@pytest.mark.parametrize('asynchronous', [False, True])
def test_graph_thread_must_match_document_before_read_or_model(asynchronous):
    context, reply = setup(); model = FixedModel(replies=[reply]); root = graph(model, InMemorySaver())
    config = {'configurable': {'thread_id': str(uuid4())}}
    with pytest.raises(ConsultantContextError, match='consultant_thread_mismatch'):
        if asynchronous:
            asyncio.run(root.ainvoke({'messages': [HumanMessage(content='x')]}, config,
                context=context, durability='sync'))
        else:
            root.invoke({'messages': [HumanMessage(content='x')]}, config,
                context=context, durability='sync')
    assert not context.history.calls and not model.requests


@pytest.mark.parametrize('after_write', [False, True])
def test_root_checkpoint_ack_loss_is_read_only_and_never_replays_model(after_write):
    class FailingSaver(InMemorySaver):
        armed = True
        def put(self, config, checkpoint, metadata, versions):
            if self.armed and config['configurable'].get('checkpoint_ns','') == '' and metadata.get('step') == 1:
                self.armed = False
                if after_write: super().put(config, checkpoint, metadata, versions)
                raise OSError('synthetic root checkpoint failure')
            return super().put(config, checkpoint, metadata, versions)
    context, reply = setup(); model = FixedModel(replies=[reply]); root = graph(model, FailingSaver())
    with pytest.raises(OSError):
        root.invoke({'messages':[HumanMessage(content='synthetic')]},
            {'configurable':{'thread_id':context.document_id}}, context=context, durability='sync')
    if after_write:
        assert read_closed_model_view(root, document_id=context.document_id,
            dataset_id=context.dataset_id, run_id=context.run_id).response_message_id == reply.id
    else:
        with pytest.raises(ConsultantContextError, match='consultant_checkpoint_unconfirmed'):
            read_closed_model_view(root, document_id=context.document_id,
                dataset_id=context.dataset_id, run_id=context.run_id)
    assert len(model.requests) == 1


def test_latest_pending_values_are_not_used_as_closed_checkpoint():
    context, _ = setup()
    class Graph:
        calls = []
        def get_state(self, config, **kwargs):
            self.calls.append(config)
            if len(self.calls) == 1:
                return SimpleNamespace(config={'configurable':{'thread_id':context.document_id,'checkpoint_id':'fixed'}}, values={'jd_model_view':'overlay'})
            return SimpleNamespace(next=(), tasks=(object(),), interrupts=(), values={})
    fake = Graph()
    with pytest.raises(ConsultantContextError, match='consultant_checkpoint_unconfirmed'):
        read_closed_model_view(fake, document_id=context.document_id, dataset_id=context.dataset_id, run_id=context.run_id)
    assert fake.calls[1]['configurable']['checkpoint_id'] == 'fixed'


def test_tool_loop_keeps_initial_manual_notice_and_advances_response_boundary():
    context, final_reply = setup()
    initial = context.turn_notice
    first_reply = AIMessage(id='fixed-tool-reply', content='',
        tool_calls=[{'name': 'synthetic_change', 'args': {}, 'id': 'call-one', 'type': 'tool_call'}],
        response_metadata={'stop_reason': 'tool_use'})

    @tool
    def synthetic_change() -> str:
        """Advance synthetic history material; this does not write a JD."""
        head = NoticeBoundary(uuid4(), 4)
        event = NoticeEvent(uuid4(), initial.head.revision_id, 3, head.revision_id, 4,
            'ai', 'jd_set_text')
        context.history.material = NoticeMaterial(context.document_id, initial.head, head,
            (event,), 0, 1, 0)
        return 'synthetic result'

    model = FixedModel(replies=[first_reply, final_reply])
    child = create_agent(model, tools=[synthetic_change], system_prompt='synthetic',
        middleware=[JdNoticeMiddleware()], state_schema=ConsultantState, context_schema=ConsultantContext)
    root = build_document_graph(child, InMemorySaver())
    result = root.invoke({'messages': [HumanMessage(content='請繼續')]},
        {'configurable': {'thread_id': context.document_id}}, context=context, durability='sync')
    notices = [json.loads(messages[0].content[-1]['text']) for messages in model.requests]
    assert len(notices) == 2
    assert notices[0]['turn_start'] == notices[1]['turn_start']
    assert notices[1]['turn_start']['manual_change_count'] == 2
    assert notices[1]['since_previous_response']['baseline_revision_number'] == 3
    assert notices[1]['since_previous_response']['ai_change_count'] == 1
    assert [m.type for m in result['messages']] == ['human', 'ai', 'tool', 'ai']
    assert result['messages'][2].tool_call_id == 'call-one'
    assert read_closed_model_view(root, document_id=context.document_id,
        dataset_id=context.dataset_id, run_id=context.run_id).revision_number == 4


@pytest.mark.parametrize('corruption', ['notice_digest', 'response_digest', 'document', 'checkpoint'])
def test_closed_observer_rejects_mismatched_saved_evidence(corruption):
    context, reply = setup(); root = graph(FixedModel(replies=[reply]), InMemorySaver())
    root.invoke({'messages': [HumanMessage(content='synthetic')]},
        {'configurable': {'thread_id': context.document_id}}, context=context, durability='sync')
    latest = root.get_state({'configurable': {'thread_id': context.document_id}}, subgraphs=True)
    pinned = root.get_state(latest.config, subgraphs=True)
    values = deepcopy(pinned.values); config = deepcopy(pinned.config)
    if corruption == 'checkpoint':
        config['configurable']['checkpoint_id'] = 'different'
    elif corruption == 'document':
        values['jd_model_view']['document_id'] = str(uuid4())
    else:
        values['jd_model_view'][corruption] = '0' * 64
    damaged = pinned._replace(values=values, config=config)
    class Graph:
        calls = 0
        def get_state(self, *args, **kwargs):
            self.calls += 1
            return latest if self.calls == 1 else damaged
    with pytest.raises(ConsultantContextError):
        read_closed_model_view(Graph(), document_id=context.document_id,
            dataset_id=context.dataset_id, run_id=context.run_id)


def test_factory_sdk_tool_round_trip_keeps_native_blocks_and_real_result(monkeypatch):
    from jd_relational.consultant_model import create_consultant_model
    from test_consultant_model import SyncBody, events

    context, _ = setup(); requests = []; bodies = []; executions = []

    @tool
    def jd_read(target: str) -> str:
        """Return synthetic read material for adapter integration only."""
        executions.append(target)
        return '{"synthetic_read_result":true}'

    def receive(request):
        assert request.url.host == 'api.anthropic.com' and len(requests) < 2
        requests.append(json.loads(request.content))
        chunks = events(kind='thinking_tool' if len(requests) == 1 else 'text')
        # Distinct provider messages; actual native AIMessage IDs are not assumed.
        chunks = [chunk.replace(b'msg_synthetic', f'msg_synthetic_{len(requests)}'.encode()) for chunk in chunks]
        body = SyncBody(chunks); bodies.append(body)
        return httpx2.Response(200, headers={'content-type': 'text/event-stream'}, stream=body)

    with httpx2.Client(transport=httpx2.MockTransport(receive), trust_env=False) as client:
        monkeypatch.setattr('langchain_anthropic.chat_models._get_default_httpx_client', lambda **kwargs: client)
        model = create_consultant_model(model_name='synthetic', api_key='synthetic-no-key', timeout=5, max_tokens=64)
        root = build_document_graph(build_consultant_node(model, tools=[jd_read], guidance='synthetic'), InMemorySaver())
        result = root.invoke({'messages': [HumanMessage(content='合成原話')]},
            {'configurable': {'thread_id': context.document_id}}, context=context, durability='sync')
    assert executions == ['synthetic'] and len(requests) == 2 and all(b.closed for b in bodies)
    assert all(r['tool_choice']['disable_parallel_tool_use'] is True for r in requests)
    assert [m.type for m in result['messages']] == ['human', 'ai', 'tool', 'ai']
    assert result['messages'][2].tool_call_id == 'toolu_synthetic'
    assistant_wire = requests[1]['messages'][1]['content']
    assert next(b for b in assistant_wire if b['type'] == 'thinking')['signature'] == 'synthetic-signature'
    assert next(b for b in assistant_wire if b['type'] == 'tool_use')['id'] == 'toolu_synthetic'
    tool_wire = requests[1]['messages'][2]['content'][0]
    assert tool_wire['type'] == 'tool_result' and tool_wire['tool_use_id'] == 'toolu_synthetic'
    assert tool_wire['content'] == '{"synthetic_read_result":true}'
    view = read_closed_model_view(root, document_id=context.document_id,
        dataset_id=context.dataset_id, run_id=context.run_id)
    assert view.response_message_id == result['messages'][-1].id
