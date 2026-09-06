"""Background application seams: real graph, Saver, Store, SDK; HTTP is local."""
import json
from threading import Event

import pytest
from langgraph.store.memory import InMemoryStore

from test_consolidation import call, done
from test_extraction import body
from test_service import service_harness


def notify(service, doc, replies, key='one', text='A網站為單次付款；B網站是訂閱。'):
    replies.extend([call('request_memory_consolidation'), done()])
    service.submit(doc, key, text)
    service.join(doc)


def dispatcher(service, **kwargs):
    from analysis_agent.scheduling import BackgroundDispatcher
    return BackgroundDispatcher(service, max_recoveries=1, **kwargs)


def test_notification_runs_real_b_without_repeating_published_source(tmp_path):
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        from analysis_agent.publication import Base
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('網站')['id']
        worker = dispatcher(service)
        worker.tick()
        assert not sent
        notify(service, doc, replies)
        replies.extend([body(), done()])
        worker.tick()
        memory = service._context(doc).memory
        assert memory.publication.current().revision == 1
        assert worker.status(doc)['status'] == 'idle'
        assert len(sent) == 4  # two foreground calls, extraction, consolidation
        worker.tick()
        assert len(sent) == 4
        assert not service.reader(doc).pending_consolidation_turns(memory.publication.current().processed_source)


@pytest.mark.parametrize('output_limit', [1000, 6000])
def test_background_wire_preserves_configured_output_limit(tmp_path, output_limit):
    from analysis_agent.publication import Base
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        Base.metadata.create_all(service.catalog.engine)
        service.model = service.model.model_copy(update={'max_tokens': output_limit})
        doc = service.create_document('每次回應輸出上限')['id']
        notify(service, doc, replies)
        replies.extend([body(), done()])
        worker = dispatcher(service)
        worker.tick()
        assert worker.status(doc)['status'] == 'idle'
        assert [json.loads(request.content)['max_output_tokens'] for request in sent] == [output_limit] * 4


def test_unnotified_text_stays_saved_until_explicit_fallback_threshold(tmp_path):
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        from analysis_agent.publication import Base
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('短句')['id']
        service.submit(doc, 'one', '對')
        service.join(doc)
        worker = dispatcher(service)
        worker.tick()
        assert len(sent) == 1
        assert service.messages(doc)[0]['text'] == '對'
        replies.extend([body(), done()])
        dispatcher(service, text_threshold=1).tick()
        assert len(sent) == 3


def test_failed_b_stays_blocked_across_ticks_new_input_and_rebuild(tmp_path):
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        from analysis_agent.publication import Base
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('失敗')['id']
        notify(service, doc, replies)
        bad = body()
        bad['status'] = 'incomplete'
        replies.append(bad)
        worker = dispatcher(service)
        worker.tick()
        assert worker.status(doc)['status'] == 'blocked'
        assert service._context(doc).memory.publication.current() is None
        count = len(sent)
        worker.tick()
        dispatcher(service).tick()
        assert len(sent) == count
        notify(service, doc, replies, 'two', '補充案例')
        worker.tick()
        assert len(sent) == count + 2


def test_b_is_independent_and_only_one_can_run_globally(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    entered, release = Event(), Event()
    def respond(request):
        payload = json.loads(request.content)
        if payload.get('text', {}).get('format', {}).get('type') == 'json_schema':
            entered.set()
            assert release.wait(5)
            return body()
        return done()
    with service_harness(tmp_path, store=InMemoryStore(), respond=respond) as (service, sent, replies):
        from analysis_agent.publication import Base
        Base.metadata.create_all(service.catalog.engine)
        first, second = [service.create_document(t)['id'] for t in ('一', '二')]
        for doc in (first, second):
            service.submit(doc, 'one', '工作案例')
            service.join(doc)
        worker = dispatcher(service, text_threshold=1)
        with ThreadPoolExecutor(2) as callers:
            future = callers.submit(worker.tick)
            try:
                assert entered.wait(5)
                another = callers.submit(worker.tick)
                assert another.result(timeout=2) is False
                service.submit(first, 'two', '背景未完成仍可訪談')
                service.join(first)
                assert service.messages(first)[-1]['role'] == 'assistant'
                assert sum(json.loads(r.content).get('text', {}).get('format', {}).get('type') == 'json_schema' for r in sent) == 1
            finally:
                release.set()
            future.result(timeout=5)
        assert worker.status(first)['status'] == 'idle'


def test_partial_batch_keeps_target_after_its_first_notification_is_consumed(tmp_path):
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        from analysis_agent.publication import Base
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('分批')['id']
        notify(service, doc, replies, text='甲' * 4000)
        service.submit(doc, 'two', '乙' * 4000)
        service.join(doc)
        worker = dispatcher(service, max_windows=1)
        replies.extend([body(), done()])
        worker.tick()
        assert worker.status(doc)['status'] == 'queued'
        memory = service._context(doc).memory
        assert not service.reader(doc).pending_consolidation_turns(memory.publication.current().processed_source)
        replies.extend([body(), done()])
        worker.tick()
        assert worker.status(doc)['status'] == 'idle'
        assert memory.publication.current().revision == 2
        user = next(i['content'] for i in json.loads(sent[-2].content)['input'] if i.get('role') == 'user')
        extracted_input = json.loads(user)
        assert ''.join(s['text'] for s in extracted_input['NEW_SOURCE']['segments'] if s['role'] == 'user') == '乙' * 4000


class ProcessLost(BaseException):
    """Bypass normal failure handling to leave the durable running admission."""


def test_rebuild_resumes_saved_b1_without_another_extraction(tmp_path, monkeypatch):
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        from analysis_agent.publication import Base
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('重建')['id']
        notify(service, doc, replies)
        worker = dispatcher(service)
        b1, b2 = worker._workflows(doc)
        monkeypatch.setattr(b2, 'start', lambda: (_ for _ in ()).throw(ProcessLost()))
        replies.append(body())
        with pytest.raises(ProcessLost):
            worker.tick()
        assert worker.status(doc)['status'] == 'running'
        assert not b1.graph.get_state(b1.config).next
        replies.append(done())
        rebuilt = dispatcher(service)
        rebuilt.tick()
        assert rebuilt.status(doc)['status'] == 'idle'
        assert len(sent) == 4


def test_repeated_process_loss_cannot_reset_recovery_budget(tmp_path, monkeypatch):
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        from analysis_agent.publication import Base
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('反覆重開')['id']
        notify(service, doc, replies)
        for attempt in range(2):
            worker = dispatcher(service)
            b1, b2 = worker._workflows(doc)
            monkeypatch.setattr(b2, 'start', lambda: (_ for _ in ()).throw(ProcessLost()))
            if attempt == 0:
                replies.append(body())
            with pytest.raises(ProcessLost):
                worker.tick()
        rebuilt = dispatcher(service)
        rebuilt.tick()
        assert rebuilt.status(doc) == {'status': 'blocked', 'error_code': 'recovery_limit', 'recovery_count': 1}
        assert len(sent) == 3


def test_commit_reply_loss_reconciles_without_model_or_stale_failure_notice(tmp_path, monkeypatch):
    from analysis_agent.publication import PublicationUncertain, Base
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('回覆遺失')['id']
        notify(service, doc, replies)
        worker = dispatcher(service)
        _, b2 = worker._workflows(doc)
        original = b2.publication.publish
        def lose_reply(request):
            original(request)
            raise PublicationUncertain('reply lost')
        monkeypatch.setattr(b2.publication, 'publish', lose_reply)
        replies.extend([body(), done()])
        worker.tick()
        assert worker.status(doc)['status'] == 'blocked'
        monkeypatch.setattr(b2.publication, 'publish', original)
        worker.tick()
        assert worker.status(doc)['status'] == 'idle'
        assert len(sent) == 4


def test_current_failure_is_request_context_not_conversation_and_clears_on_recovery(tmp_path):
    from analysis_agent.publication import Base
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        Base.metadata.create_all(service.catalog.engine)
        worker = service.enable_background(max_recoveries=1)
        doc = service.create_document('Context')['id']
        notify(service, doc, replies)
        bad = body()
        bad['status'] = 'incomplete'
        replies.append(bad)
        worker.tick()
        service.submit(doc, 'two', '繼續訪談')
        service.join(doc)
        payload = json.loads(sent[-1].content)
        assert '<background_memory_availability>' in json.dumps(payload)
        assert not any('background_memory_availability' in m['text'] for m in service.messages(doc))
        # Simulate an explicit maintenance recovery using the existing B APIs;
        # this does not add an employee-facing retry or consolidation endpoint.
        b1, b2 = worker._workflows(doc)
        replies.extend([body(), done()])
        b1.resume()
        b2.start()
        service.submit(doc, 'three', '整理成功後繼續')
        service.join(doc)
        assert '<background_memory_availability>' not in json.dumps(json.loads(sent[-1].content))


def test_scheduler_wakes_real_background_and_service_close_joins_it(tmp_path):
    entered, release, closed = Event(), Event(), Event()
    def respond(request):
        if json.loads(request.content).get('text', {}).get('format', {}).get('type') == 'json_schema':
            entered.set()
            assert release.wait(5)
            return body()
        return done()
    from concurrent.futures import ThreadPoolExecutor
    from analysis_agent.publication import Base
    with service_harness(tmp_path, store=InMemoryStore(), respond=respond) as (service, sent, replies):
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('真排程')['id']
        service.submit(doc, 'one', '案例')
        service.join(doc)
        service.enable_background(max_recoveries=1, text_threshold=1)
        service.start_background(poll_seconds=60)
        with ThreadPoolExecutor(1) as waiter:
            try:
                assert entered.wait(5)
                def shutdown():
                    service.close()
                    closed.set()
                future = waiter.submit(shutdown)
                assert not closed.is_set()
            finally:
                release.set()
            future.result(timeout=5)
        assert closed.is_set()
        assert service.background.status(doc)['status'] == 'idle'
        assert not service.scheduler.running
        assert len(sent) == 3


def test_blocked_document_does_not_starve_other_documents(tmp_path):
    from analysis_agent.publication import Base
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        Base.metadata.create_all(service.catalog.engine)
        docs = [service.create_document(t)['id'] for t in ('壞', '好')]
        for doc in docs:
            notify(service, doc, replies)
        worker = dispatcher(service)
        bad = body()
        bad['status'] = 'incomplete'
        replies.append(bad)
        worker.tick()
        replies.extend([body(), done()])
        worker.tick()
        assert worker.status(docs[0])['status'] == 'blocked'
        assert worker.status(docs[1])['status'] == 'idle'
        assert service._context(docs[1]).memory.publication.current().revision == 1


def test_pending_foreground_is_not_extracted_and_closed_failure_is_not_lost(tmp_path, monkeypatch):
    from analysis_agent.publication import Base
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('未完成')['id']
        with monkeypatch.context() as patch:
            patch.setattr(service, '_launch', lambda *args: (_ for _ in ()).throw(RuntimeError('before start')))
            with pytest.raises(RuntimeError):
                service.submit(doc, 'one', '尚未分析的重要短句')
        worker = dispatcher(service, text_threshold=1)
        worker.tick()
        assert not sent
        run_id = service.catalog.runs(doc)[0]['id']
        service.stop(doc, run_id)
        replies.extend([body(), done()])
        worker.tick()
        assert worker.status(doc)['status'] == 'idle'
        payload = json.loads(sent[0].content)
        assert '尚未分析的重要短句' in json.dumps(payload, ensure_ascii=False)


def test_dispatcher_cannot_start_model_after_service_shutdown(tmp_path):
    from analysis_agent.publication import Base
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        Base.metadata.create_all(service.catalog.engine)
        doc = service.create_document('停止後不可新增工作')['id']
        worker = dispatcher(service)
        notify(service, doc, replies)
        service.close()
        replies.extend([body(), done()])
        assert worker.tick() is False
        assert len(sent) == 2
