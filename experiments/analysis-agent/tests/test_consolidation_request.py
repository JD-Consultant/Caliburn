"""Notification admission through the real Agent loop; only model HTTP is fake."""
from contextlib import contextmanager
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from analysis_agent.conversation import build_conversation, close_turn, send_input
from analysis_agent.provider import build_model
from analysis_agent.sources import ConversationReader
from test_consolidation import call, done


@contextmanager
def notification_harness(saver=None, document='notification-test', middleware=()):
    sent, replies = [], []
    provider_session = uuid4().hex

    def respond(request):
        sent.append(json.loads(request.content))
        assert replies, 'Unexpected additional model call'
        response = replies.pop(0)
        if isinstance(response, Exception):
            raise response
        response['id'] = f'resp_{provider_session}_{len(sent)}'
        for i, item in enumerate(response['output']):
            item['id'] = f'item_{provider_session}_{len(sent)}_{i}'
            if item['type'] == 'function_call':
                item['call_id'] = f'call_{provider_session}_{len(sent)}_{i}'
        return httpx.Response(200, json=response)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client).model_copy(update={'max_retries': 0})
        saver = saver if saver is not None else InMemorySaver()
        root = build_conversation(model=model, checkpointer=saver, instructions='訪談', middleware=middleware)
        yield SimpleNamespace(root=root, saver=saver, model=model, sent=sent, replies=replies,
                              reader=ConversationReader(root, document), config={'configurable': {'thread_id': document}})


def notify(h, input_id, count=1):
    h.replies.extend([*[call('request_memory_consolidation') for _ in range(count)], done()])
    return send_input(h.root, h.config, HumanMessage('我依客戶需求製作網站。', id=input_id))


def test_notice_is_durable_not_memory_completion_and_artifact_never_reaches_model():
    with notification_harness() as h:
        result = notify(h, 'z-input')
        assert result['turn_outcome']['status'] == 'completed'
        assert result['turn_outcome']['model_calls'] == 2
        assert result['turn_outcome']['tool_calls'] == 1
        notice = next(m for m in result['messages'] if isinstance(m, ToolMessage))
        assert notice.status == 'success'
        assert notice.artifact == {'kind': 'memory_consolidation_requested'}
        assert '尚未' in notice.content
        assert h.reader.pending_consolidation_turns() == [{'input_id': 'z-input', 'end_id': result['messages'][-1].id}]
        definition = next(t for t in h.sent[0]['tools'] if t['name'] == 'request_memory_consolidation')
        assert definition['parameters']['properties'] == {}
        wire = json.dumps(h.sent[1], ensure_ascii=False)
        assert 'memory_consolidation_requested' not in wire and 'artifact' not in wire
        paired = [i for i in h.sent[1]['input'] if i['type'] == 'function_call_output']
        assert len(paired) == 1 and paired[0]['call_id'] == notice.tool_call_id
        assert paired[0]['output'] == notice.content
        # There is no Memory/B component in this composition to execute or await.
        assert len(h.sent) == 2 and not h.root.get_state(h.config).next


def test_multiple_notices_coalesce_per_turn_and_cursor_uses_real_order():
    with notification_harness() as h:
        first = notify(h, 'z-input', count=2)
        old = h.reader.capture('z-input', first['messages'][-1].id)
        second = notify(h, 'a-input')  # lexical ID ordering is deliberately reversed
        assert [t['input_id'] for t in h.reader.pending_consolidation_turns()] == ['z-input', 'a-input']
        assert h.reader.pending_consolidation_turns(after_reference=old) == [
            {'input_id': 'a-input', 'end_id': second['messages'][-1].id}]
        latest = h.reader.capture('a-input', second['messages'][-1].id)
        assert h.reader.pending_consolidation_turns(after_reference=latest) == []
        # Reading/coalescing never starts a background or primary model call.
        assert len(h.sent) == 5


@pytest.mark.parametrize('fault', ['error', 'no_artifact', 'wrong_tool', 'wrong_call_id', 'no_call'])
def test_only_paired_success_of_registered_empty_notice_is_a_request(fault):
    with notification_harness() as h:
        result = notify(h, 'h1')
        notice = next(m for m in result['messages'] if isinstance(m, ToolMessage))
        caller = next(m for m in result['messages'] if isinstance(m, AIMessage) and m.tool_calls)
        if fault == 'error':
            changed = notice.model_copy(update={'status': 'error'})
        elif fault == 'no_artifact':
            changed = notice.model_copy(update={'artifact': None})
        elif fault == 'wrong_tool':
            changed = notice.model_copy(update={'name': 'some_other_tool'})
        elif fault == 'wrong_call_id':
            changed = notice.model_copy(update={'tool_call_id': 'unrelated'})
        else:
            changed = caller.model_copy(update={'tool_calls': []})
        h.root.update_state(h.config, {'messages': [changed]}, as_node='analysis')
        assert h.reader.pending_consolidation_turns() == []


def test_natural_language_and_an_unclosed_gap_cannot_release_notifications():
    with notification_harness() as h:
        h.replies.append(done())
        send_input(h.root, h.config, HumanMessage('request_memory_consolidation，請整理記憶', id='h0'))
        assert h.reader.pending_consolidation_turns() == []
        notify(h, 'h1')
        snapshot = h.root.get_state(h.config)
        # A corrupt/unresolved earlier turn cannot be skipped to admit a later one.
        bad_boundary = {**snapshot.values['closed_turns']['h0'], 'status': 'interrupted'}
        h.root.update_state(h.config, {'closed_turns': {'h0': bad_boundary}}, as_node='analysis')
        assert h.reader.pending_consolidation_turns() == []


class LoseNoticeResult(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        result = handler(request)
        if request.tool_call['name'] == 'request_memory_consolidation':
            raise RuntimeError('injected before notification result checkpoint')
        return result


class InterruptAfterSavedNotice(AgentMiddleware):
    def wrap_model_call(self, request, handler):
        last = request.messages[-1]
        if isinstance(last, ToolMessage) and last.name == 'request_memory_consolidation':
            raise RuntimeError('injected after saved notification')
        return handler(request)


@pytest.mark.parametrize('saved', [False, True])
def test_interrupted_notice_can_close_without_fabricating_success_or_blocking_next_input(saved):
    middleware = (InterruptAfterSavedNotice(),) if saved else (LoseNoticeResult(),)
    with notification_harness(middleware=middleware) as h:
        h.replies.append(call('request_memory_consolidation'))
        with pytest.raises(RuntimeError, match='injected'):
            send_input(h.root, h.config, HumanMessage('這是網站案例。', id='h1'))
        assert h.reader.pending_consolidation_turns() == []
        with pytest.raises(ValueError, match='quiescent'):
            close_turn(h.root, h.config, reason='cancelled', quiescent=False)
        closed = close_turn(h.root, h.config, reason='cancelled', quiescent=True)
        results = [m for m in closed['messages'] if isinstance(m, ToolMessage)]
        assert len(results) == 1
        assert results[0].status == ('success' if saved else 'error')
        assert bool(h.reader.pending_consolidation_turns()) == saved
        assert h.reader.extraction_windows(h.reader.capture('h1', closed['messages'][-1].id))
        h.replies.append(done())
        next_turn = send_input(h.root, h.config, HumanMessage('接著另一件工作。', id='h2'))
        assert next_turn['turn_outcome']['status'] == 'completed'
        assert [m.id for m in next_turn['messages'] if isinstance(m, HumanMessage)] == ['h1', 'h2']


def test_notice_is_not_dispatched_when_tool_budget_is_used_up():
    with notification_harness() as h:
        h.root = build_conversation(model=h.model, checkpointer=h.saver, instructions='訪談', max_tool_calls=1)
        h.reader = ConversationReader(h.root, 'notification-test')
        result = notify(h, 'h1', count=2)
        results = [m for m in result['messages'] if isinstance(m, ToolMessage)]
        assert [m.status for m in results] == ['success', 'error']
        assert result['turn_outcome']['status'] == 'limit'
        assert len(h.reader.pending_consolidation_turns()) == 1
        assert len(h.sent) == 2


def test_notification_name_cannot_be_rebound_to_an_external_effect():
    @tool('request_memory_consolidation')
    def impostor() -> str:
        """An unrelated effect must not inherit pure notification cancellation."""
        raise AssertionError('Must never run')
    with notification_harness() as h:
        with pytest.raises(ValueError, match='reserved'):
            build_conversation(model=h.model, checkpointer=h.saver, instructions='test', tools=[impostor])


def test_pending_request_cursor_must_belong_to_same_saved_conversation():
    with notification_harness() as h:
        result = notify(h, 'h1')
        ref = h.reader.capture('h1', result['messages'][-1].id)
        other = ConversationReader(h.root, 'other-document')
        with pytest.raises(ValueError, match='another document'):
            other.pending_consolidation_turns(after_reference=ref)
        with pytest.raises(ValueError, match='reference'):
            h.reader.pending_consolidation_turns(after_reference='invented')


def test_framework_ignored_extra_arguments_cannot_change_receipt_or_lose_request():
    with notification_harness() as h:
        h.replies.extend([call('request_memory_consolidation', document_id='other-document',
                              reason='must not reach receipt', job_id='invented'), done()])
        result = send_input(h.root, h.config, HumanMessage('網站案例補充。', id='h1'))
        results = [m for m in result['messages'] if isinstance(m, ToolMessage)]
        assert len(results) == 1 and results[0].status == 'success'
        assert results[0].artifact == {'kind': 'memory_consolidation_requested'}
        assert 'must not reach receipt' not in results[0].content
        assert 'other-document' not in results[0].content
        assert result['turn_outcome']['status'] == 'completed'
        assert h.reader.pending_consolidation_turns() == [{'input_id': 'h1', 'end_id': result['messages'][-1].id}]
        assert ConversationReader(h.root, 'other-document').pending_consolidation_turns() == []


def test_empty_conversation_has_no_request_and_pending_new_turn_keeps_older_request():
    with notification_harness() as h:
        assert h.reader.pending_consolidation_turns() == []
        result = notify(h, 'h1')
        h.root.update_state(h.config, {'messages': [HumanMessage('另一件事', id='h2')]}, as_node='__start__')
        assert h.reader.pending_consolidation_turns() == [
            {'input_id': 'h1', 'end_id': result['messages'][-1].id}]
