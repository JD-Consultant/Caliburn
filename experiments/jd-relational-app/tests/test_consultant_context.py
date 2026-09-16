"""Native graph/middleware checks with fixed replies; no provider or fake DB PASS."""

import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
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
        response_metadata={'stop_reason':'end_turn', 'status': 'completed',
                           'model_name':'synthetic'},
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
    context, reply = setup(); reply.response_metadata.update(
        {'stop_reason': stop, 'status': 'incomplete'})
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
        response_metadata={'stop_reason': 'tool_use', 'status': 'completed'})

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


def test_factory_sdk_tool_round_trip_keeps_native_calls_and_real_result():
    from jd_relational.consultant_model import OPENROUTER_HEADERS, create_consultant_model
    from support.openrouter_replies import reply

    context, _ = setup(); requests = []; executions = []

    @tool
    def jd_read(target: str) -> str:
        """Return synthetic read material for adapter integration only."""
        executions.append(target)
        return '{"synthetic_read_result":true}'

    def receive(request):
        assert request.url.host == 'openrouter.ai' and len(requests) < 2
        requests.append(json.loads(request.content))
        body = (reply('first', 'jd_read', {'target': 'synthetic'}) if len(requests) == 1
                else reply('second', text='完整合成回覆'))
        return httpx.Response(200, json=body, request=request)

    client = httpx.Client(transport=httpx.MockTransport(receive), trust_env=False,
                          headers=OPENROUTER_HEADERS)
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(receive), trust_env=False,
                                     headers=OPENROUTER_HEADERS)
    try:
        model = create_consultant_model(api_key='synthetic-no-key', http_client=client,
            async_http_client=async_client, request_timeout=5, max_output_tokens=64)
        root = build_document_graph(build_consultant_node(model, tools=[jd_read], guidance='synthetic'), InMemorySaver())
        result = root.invoke({'messages': [HumanMessage(content='合成原話')]},
            {'configurable': {'thread_id': context.document_id}}, context=context, durability='sync')
    finally:
        client.close()
        asyncio.run(async_client.aclose())
    assert executions == ['synthetic'] and len(requests) == 2
    assert all(r['parallel_tool_calls'] is False for r in requests)
    assert [m.type for m in result['messages']] == ['human', 'ai', 'tool', 'ai']
    assert result['messages'][2].tool_call_id == 'call_first'
    assistant_wire = requests[1]['messages'][2]
    assert assistant_wire['tool_calls'][0]['id'] == 'call_first'
    tool_wire = requests[1]['messages'][3]
    assert tool_wire['role'] == 'tool' and tool_wire['tool_call_id'] == 'call_first'
    assert tool_wire['content'] == '{"synthetic_read_result":true}'
    view = read_closed_model_view(root, document_id=context.document_id,
        dataset_id=context.dataset_id, run_id=context.run_id)
    assert view.response_message_id == result['messages'][-1].id


def test_factory_context_seam_changes_only_the_model_request():
    """A can accept a supported request view without trimming its Saver state.

    This does not choose the unresolved production transport.  The synthetic
    middleware stands in for whichever supported adapter the Owner later
    selects and proves that the graph seam itself is request-only.
    """
    from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
    from jd_relational.consultant_model import OPENROUTER_HEADERS, create_consultant_model
    from support.openrouter_replies import reply

    context, _ = setup()
    projected = []
    requests = []

    @wrap_model_call
    def latest_message_only(request: ModelRequest, handler) -> ModelResponse:
        projected.append([message.model_copy(deep=True) for message in request.messages])
        return handler(request.override(messages=[request.messages[-1].model_copy(deep=True)]))

    def receive(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=reply('context-seam', text='已收到最新訊息。'),
                              request=request)

    transport = httpx.MockTransport(receive)
    client = httpx.Client(transport=transport, trust_env=False, headers=OPENROUTER_HEADERS)
    async_client = httpx.AsyncClient(
        transport=transport, trust_env=False, headers=OPENROUTER_HEADERS)
    try:
        model = create_consultant_model(
            api_key='synthetic-no-key', http_client=client,
            async_http_client=async_client, request_timeout=5, max_output_tokens=64)
        child = build_consultant_node(
            model, tools=[], guidance='synthetic', context_middleware=latest_message_only)
        root = build_document_graph(child, InMemorySaver())
        earlier = HumanMessage(id='earlier', content='較早但仍需完整保存的原話。')
        earlier_reply = AIMessage(id='earlier-reply', content='較早回覆。')
        current = HumanMessage(id='current', content='這次只送最新訊息。')
        result = root.invoke(
            {'messages': [earlier, earlier_reply, current]},
            {'configurable': {'thread_id': context.document_id}},
            context=context,
            durability='sync',
        )
    finally:
        client.close()
        asyncio.run(async_client.aclose())

    assert [[message.id for message in messages] for messages in projected] == [
        ['earlier', 'earlier-reply', 'current']
    ]
    assert [message['role'] for message in requests[0]['messages']] == ['system', 'user']
    assert requests[0]['messages'][-1]['content'] == '這次只送最新訊息。'
    assert '較早但仍需完整保存的原話。' not in json.dumps(requests[0], ensure_ascii=False)
    assert [message.id for message in result['messages'][:3]] == [
        'earlier', 'earlier-reply', 'current'
    ]


def test_context_compaction_counts_the_fully_projected_request():
    from langchain.agents.middleware import AgentMiddleware
    from jd_relational.consultant_model import OPENROUTER_HEADERS, create_consultant_model
    from jd_relational.continuation_compaction import (
        CompactionProfile,
        ContinuationCompactionMiddleware,
    )
    from support.openrouter_replies import reply

    context, _ = setup()
    counted = []

    class InnerContext(AgentMiddleware):
        def wrap_model_call(self, request, handler):
            content = request.system_message.content
            blocks = ([{'type': 'text', 'text': content}]
                      if isinstance(content, str) else list(content))
            blocks.append({'type': 'text', 'text': 'inner-skills-and-background-context'})
            return handler(request.override(system_message=SystemMessage(content=blocks)))

    def count(request, view):
        counted.append(deepcopy(request.system_message.content))
        return 0

    def receive(request):
        return httpx.Response(200, json=reply('projected', text='完整合成回覆'),
                              request=request)

    transport = httpx.MockTransport(receive)
    client = httpx.Client(transport=transport, trust_env=False, headers=OPENROUTER_HEADERS)
    async_client = httpx.AsyncClient(
        transport=transport, trust_env=False, headers=OPENROUTER_HEADERS)
    try:
        model = create_consultant_model(
            api_key='synthetic-no-key', http_client=client,
            async_http_client=async_client, request_timeout=5, max_output_tokens=64)
        compaction = ContinuationCompactionMiddleware(
            summary_model=model,
            profile=CompactionProfile(trigger_input_tokens=100, keep_messages=1),
            token_counter=count,
        )
        child = build_consultant_node(
            model,
            tools=[],
            guidance='synthetic',
            context_middleware=compaction,
            extra_middleware=[InnerContext()],
        )
        root = build_document_graph(child, InMemorySaver())
        root.invoke(
            {'messages': [HumanMessage(id='current', content='目前問題。')]},
            {'configurable': {'thread_id': context.document_id}},
            context=context,
            durability='sync',
        )
    finally:
        client.close()
        asyncio.run(async_client.aclose())

    assert len(counted) == 1
    rendered = json.dumps(counted[0], ensure_ascii=False)
    assert 'jd_change_notice' in rendered
    assert 'inner-skills-and-background-context' in rendered


def test_a_compaction_and_jd_notice_commands_are_saved_together():
    from jd_relational.consultant_model import (
        CONSULTANT_MODEL,
        OPENROUTER_HEADERS,
        OPENROUTER_PROVIDER,
        create_consultant_model,
    )
    from jd_relational.continuation_compaction import (
        CompactionProfile,
        ContinuationCompaction,
        ContinuationCompactionMiddleware,
    )
    from support.openrouter_replies import reply

    context, _ = setup()
    payloads = []
    observed_model_replies = []

    class Capture(BaseCallbackHandler):
        def on_llm_end(self, response, **kwargs):
            observed_model_replies.append(response.generations[0][0].message)

    @tool
    def synthetic_jd_read(target: str) -> str:
        """Expose one harmless business tool to the main request only."""
        return target

    def receive(request):
        payloads.append(json.loads(request.content))
        response = (reply('summary', text='舊訪談已確認案例 A；目前要處理最新更正。')
                    if len(payloads) == 1
                    else reply('main', text='我會先確認最新更正。'))
        return httpx.Response(200, json=response, request=request)

    transport = httpx.MockTransport(receive)
    client = httpx.Client(transport=transport, trust_env=False, headers=OPENROUTER_HEADERS)
    async_client = httpx.AsyncClient(
        transport=transport, trust_env=False, headers=OPENROUTER_HEADERS)
    try:
        model = create_consultant_model(
            api_key='synthetic-no-key', http_client=client,
            async_http_client=async_client, request_timeout=5, max_output_tokens=64)
        compaction = ContinuationCompactionMiddleware(
            summary_model=model,
            profile=CompactionProfile(trigger_input_tokens=1, keep_messages=1),
            token_counter=lambda request, view: 100,
        )
        child = build_consultant_node(
            model, tools=[synthetic_jd_read], guidance='synthetic',
            context_middleware=compaction)
        root = build_document_graph(child, InMemorySaver())
        earlier = HumanMessage(id='earlier', content='案例 A 是每週巡檢。')
        earlier_reply = AIMessage(id='earlier-reply', content='已記錄案例 A。')
        current = HumanMessage(id='current', content='最新更正：其實是每月。')
        originals = [deepcopy(message.model_dump())
                     for message in (earlier, earlier_reply, current)]
        result = root.invoke(
            {'messages': [earlier, earlier_reply, current]},
            {
                'configurable': {'thread_id': context.document_id},
                'callbacks': [Capture()],
            },
            context=context,
            durability='sync',
        )
    finally:
        client.close()
        asyncio.run(async_client.aclose())

    assert len(payloads) == 2
    assert payloads[0]['max_tokens'] == 2048
    assert [payload['model'] for payload in payloads] == [CONSULTANT_MODEL] * 2
    assert [payload['provider'] for payload in payloads] == [
        {
            'only': [OPENROUTER_PROVIDER],
            'order': [OPENROUTER_PROVIDER],
            'allow_fallbacks': False,
            'require_parameters': True,
        }
    ] * 2
    assert 'tools' not in payloads[0]
    assert payloads[1]['tools'][0]['function']['name'] == 'synthetic_jd_read'
    # The nested summary call inherits the graph callback context, so the extra
    # paid call cannot disappear from runtime usage instrumentation.
    assert [message.text for message in observed_model_replies] == [
        '舊訪談已確認案例 A；目前要處理最新更正。',
        '我會先確認最新更正。',
    ]
    expected_usage = {
        'input_tokens': 20,
        'output_tokens': 10,
        'total_tokens': 30,
    }
    assert all(message.usage_metadata == expected_usage
               for message in observed_model_replies)
    assert all(message.response_metadata['provider'] == 'OpenAI'
               for message in observed_model_replies)
    main_messages = payloads[1]['messages']
    assert [message['role'] for message in main_messages] == ['system', 'assistant', 'user']
    assert '對話延續摘要' in main_messages[1]['content']
    assert main_messages[2]['content'] == '最新更正：其實是每月。'
    assert [message.model_dump() for message in result['messages'][:3]] == originals
    saved = ContinuationCompaction.model_validate(
        result['continuation_compaction'], strict=True)
    assert saved.covered_through_message_id == 'earlier-reply'
    checkpoint = root.get_state(
        {'configurable': {'thread_id': context.document_id}}, subgraphs=True)
    checkpoint_saved = ContinuationCompaction.model_validate(
        checkpoint.values['continuation_compaction'], strict=True)
    assert checkpoint_saved == saved
    view = read_closed_model_view(
        root,
        document_id=context.document_id,
        dataset_id=context.dataset_id,
        run_id=context.run_id,
    )
    assert view.response_message_id == result['messages'][-1].id


def test_a_taken_back_turn_is_named_in_the_notice_and_nothing_else_is():
    """The next turn must be able to tell "taken back" from an ordinary edit."""
    from jd_relational.consultant_context import NOTICE_INSTRUCTION, _material_notice
    from jd_relational.notice_history import NoticeBoundary, NoticeEvent, NoticeMaterial
    from jd_relational.references import ReferenceCodec
    codec = ReferenceCodec(b"x" * 32, str(uuid4()))
    document, run = str(uuid4()), str(uuid4())
    head = NoticeBoundary(uuid4(), 3)
    undo = NoticeEvent(uuid4(), uuid4(), 2, head.revision_id, 3, "manual", "undo_ai_turn", run)
    edit = NoticeEvent(uuid4(), uuid4(), 1, uuid4(), 2, "ai", "jd_set_text")
    notice = _material_notice(NoticeMaterial(document, None, head, (undo, edit), 1, 1, 0), codec)
    assert notice["events"][0]["took_back_an_ai_turn"] is True
    assert "took_back_an_ai_turn" not in notice["events"][1], "an ordinary edit took nothing back"
    # A marker, never the run identity: every identity here is signed.
    assert run not in json.dumps(notice, ensure_ascii=False)
    assert "took_back_an_ai_turn" in NOTICE_INSTRUCTION
    assert "訪談" in NOTICE_INSTRUCTION and "工作理解" in NOTICE_INSTRUCTION
