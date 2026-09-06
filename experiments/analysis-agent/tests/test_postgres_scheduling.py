"""Task4 recovery against real PostgreSQL clients, only external HTTP is fake."""
import json

import pytest

from analysis_agent.publication import PublicationUncertain
from test_postgres_service import pg_service
from test_scheduling import notify, dispatcher, ProcessLost
from test_consolidation import call, done
from test_extraction import body


@pytest.mark.parametrize('phase,expected_calls', [
    ('notification_only', 2), ('b1_saved', 1), ('b2_tool_saved', 1),
    ('memory_prepared', 0), ('publication_reply', 0),
])
def test_pg_background_rebuild_resumes_exact_saved_stage(pg_service, monkeypatch, phase, expected_calls):
    opened, owned = pg_service
    with opened() as (service, sent, replies):
        doc = service.create_document('背景接續-' + phase)['id']
        owned.append(doc)
        notify(service, doc, replies)
        worker = dispatcher(service)
        b1, b2 = worker._workflows(doc)
        if phase == 'b1_saved':
            monkeypatch.setattr(b2, 'start', lambda: (_ for _ in ()).throw(ProcessLost()))
            replies.append(body())
        elif phase == 'b2_tool_saved':
            actual_send = service.model.http_client.send
            calls = 0
            def interrupted_send(request, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:  # B1, B2 read tool, then process loss before next response
                    raise ProcessLost()
                return actual_send(request, **kwargs)
            monkeypatch.setattr(service.model.http_client, 'send', interrupted_send)
            replies.extend([body(), call('ls', path='/memory/')])
        elif phase == 'memory_prepared':
            monkeypatch.setattr(b2.publication, 'prepare', lambda *a, **kw: (_ for _ in ()).throw(ProcessLost()))
            replies.extend([body(), done()])
        elif phase == 'publication_reply':
            publish = b2.publication.publish
            def fail_reply(request):
                publish(request)
                raise PublicationUncertain('commit response lost')
            monkeypatch.setattr(b2.publication, 'publish', fail_reply)
            replies.extend([body(), done()])
        if phase in {'b1_saved', 'b2_tool_saved', 'memory_prepared'}:
            with pytest.raises(ProcessLost):
                worker.tick()
        elif phase == 'publication_reply':
            worker.tick()
        original_messages = service.messages(doc)
    with opened() as (service, sent, replies):
        worker = dispatcher(service)
        if phase == 'notification_only':
            replies.append(body())
        if expected_calls:
            replies.append(done())
        worker.tick()
        assert worker.status(doc)['status'] == 'idle'
        assert len(sent) == expected_calls
        b1, b2 = worker._workflows(doc)
        assert b2.publication.current().revision == 1
        assert service.messages(doc) == original_messages
        assert len(b1.graph.get_state(b1.config).values['files']) == 1
        assert b2.publication.artifacts.read_text(b1.graph.get_state(b1.config).values['files'][0]['summary_path'])
        if phase == 'b2_tool_saved':
            assert any(i.get('type') == 'function_call_output' for i in json.loads(sent[0].content)['input'])
        worker.tick()
        assert len(sent) == expected_calls


def test_pg_blocked_error_remains_blocked_after_rebuilding_all_clients(pg_service):
    opened, owned = pg_service
    with opened() as (service, sent, replies):
        doc = service.create_document('持久失敗')['id']
        owned.append(doc)
        notify(service, doc, replies)
        bad = body()
        bad['status'] = 'incomplete'
        replies.append(bad)
        dispatcher(service).tick()
    with opened() as (service, sent, replies):
        worker = dispatcher(service)
        worker.tick()
        assert not sent
        assert worker.status(doc)['status'] == 'blocked'
        assert len(service.messages(doc)) == 2
        assert worker.notice(doc)
