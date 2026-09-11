"""R06: an admitted stop owns its final projection until shutdown may drain."""
from threading import Event, Thread
import httpx
import pytest
from test_service import service_harness


@pytest.mark.parametrize('projection_fails', [False, True])
def test_close_waits_for_stop_final_projection(tmp_path, monkeypatch, projection_fails):
    with service_harness(tmp_path) as (service, _, replies):
        document = service.create_document('停止結果')['id']
        replies.extend(httpx.ReadTimeout('offline') for _ in range(3))
        run = service.submit(document, 'first', '保留原問句')
        service.join(document)
        context = service._context(document)
        entered, release, closed = Event(), Event(), Event()
        results, errors = [], []
        original = service.get_run
        calls = 0

        def held_projection(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                entered.set()
                assert release.wait(5)
                if projection_fails:
                    raise RuntimeError('final projection unavailable')
            return original(*args)

        monkeypatch.setattr(service, 'get_run', held_projection)

        def stopping():
            try:
                results.append(service.stop(document, run['id']))
            except Exception as exc:
                errors.append(exc)

        def closing():
            try:
                service.close()
                closed.set()
            except Exception as exc:
                errors.append(exc)

        worker = Thread(target=stopping)
        closer = Thread(target=closing)
        worker.start()
        try:
            assert entered.wait(5)
            closer.start()
            assert not closed.wait(.2), 'Shutdown returned before stop projection unwound'
        finally:
            release.set()
            worker.join(10)
            if closer.ident is not None:
                closer.join(10)
        assert closed.is_set() and not worker.is_alive() and not closer.is_alive()
        assert context.close_entries == 0 and not context.closing
        if projection_fails:
            assert len(errors) == 1 and str(errors[0]) == 'final projection unavailable'
            assert results == []
        else:
            assert not errors and results[0]['status'] == 'cancelled'
