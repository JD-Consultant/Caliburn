"""Real Future ownership, with synthetic persistence; no provider/OS/SQL bootstrap."""

from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import replace
from threading import Event, get_ident
from uuid import uuid4

import pytest

from jd_relational.intents import bind_edit
from jd_relational.manual_runtime import ForegroundIdentity, ManualRuntime, RuntimeFailure
from jd_relational.storage.receipts import WriteObservation
from test_catalog_runtime import CatalogStorage
from test_manual_runtime import Checkpoints, intent, observation


def run_identity(document=None, *, run=None, digest="a" * 64):
    return ForegroundIdentity(document or str(uuid4()), run or str(uuid4()), digest)


def ai_intent(run, *, operation=None, text="真實工作"):
    manual = intent(run.document_id, operation=operation, text=text)
    return bind_edit(manual.operation_id, "ai", run.run_id, manual.command, manual.context)


class ForegroundStorage(CatalogStorage):
    def __init__(self, authority):
        super().__init__(authority)
        self.worker_context = None
        self.worker_thread = None

    def execute(self, value):
        self.authority.require_bound(value)
        self.executed.append((value.identity, get_ident()))
        self.worker_context, self.worker_thread = copy_context(), get_ident()
        self.started.set()
        assert self.release.wait(3), "test must release the SQL worker"
        self.authority.require_bound(value)
        result = observation(value.identity)
        result = replace(result, receipt=replace(result.receipt,
            origin=value.origin, ai_run_id=value.ai_run_id))
        self.receipts[value.operation_id] = result
        return WriteObservation(value.document_id, value.operation_id, None, "unknown") if self.unknown else result


@pytest.fixture
def foreground():
    checkpoint = Checkpoints()
    owner = ManualRuntime(checkpoint, ForegroundStorage, max_workers=1)
    release, handles = Event(), []
    yield owner, checkpoint, owner.storage, release, handles
    release.set()
    owner.storage.release.set()
    for handle in handles:
        handle.request_stop()
        handle.wait(3)
        slot = owner._slots[handle.permit.identity.document_id]
        if slot.foreground.permit is handle.permit and not slot.foreground.closed:
            if slot.entry is not None:
                owner.recover_foreground(handle.permit, slot.entry.identity, lambda _: None, timeout=3)
            owner.finish_foreground(handle.permit, lambda: None)
    assert owner.close(timeout=3)


def start_waiting(foreground, run=None):
    owner, _, _, release, handles = foreground
    started = Event()
    def work(permit):
        started.set()
        assert release.wait(3)
    handle = owner.start_foreground(run or run_identity(), work)
    handles.append(handle)
    assert started.wait(2)
    return handle


def test_pure_interview_blocks_same_document_manual_metadata_and_other_ai(foreground):
    owner, checkpoint, storage, _, _ = foreground
    handle = start_waiting(foreground)
    document = handle.permit.identity.document_id
    for call in (lambda: owner.submit(intent(document)),
                 lambda: owner.update_catalog(document, 1, archived=True),
                 lambda: owner.start_foreground(run_identity(document), lambda _: None)):
        with pytest.raises(RuntimeFailure, match="^document_busy$"):
            call()
    status = owner.status(document)
    assert status.running and status.write_blocked and status.identity is None
    assert not storage.executed and not storage.catalog_calls and not checkpoint.pending


def test_unrelated_document_and_catalog_creation_progress_during_model_wait(foreground):
    owner, _, storage, _, _ = foreground
    start_waiting(foreground)
    assert owner.submit(intent()).wait(2).observation.confirmed
    assert owner.create_document(uuid4(), "另一份")
    assert len(storage.executed) == 1


def test_same_foreground_identity_returns_original_and_changed_digest_conflicts(foreground):
    owner, _, _, release, _ = foreground
    handle = start_waiting(foreground)
    run = handle.permit.identity
    assert owner.start_foreground(run, lambda _: pytest.fail("duplicate")) is handle
    with pytest.raises(RuntimeFailure, match="^operation_conflict$"):
        owner.start_foreground(replace(run, request_digest="b" * 64), lambda _: None)
    release.set()
    assert not handle.wait(2).running
    assert owner.status(run.document_id).write_blocked
    owner.finish_foreground(handle.permit, lambda: None)
    assert owner.start_foreground(run, lambda _: pytest.fail("replay")) is handle
    assert not owner.status(run.document_id).write_blocked


@pytest.mark.parametrize("field,value", [("document_id", "wrong"), ("run_id", "wrong"),
    ("request_digest", "A" * 64), ("request_digest", "a" * 63), ("request_digest", True)])
def test_foreground_identity_rejects_invalid_scope(field, value):
    good = run_identity()
    with pytest.raises((ValueError, RuntimeFailure), match="invalid_input"):
        replace(good, **{field: value})


def test_timeout_and_stop_request_never_claim_running_callable_stopped(foreground):
    owner, _, _, release, _ = foreground
    handle = start_waiting(foreground)
    with pytest.raises(TimeoutError, match="foreground_still_running"):
        handle.wait(0.01)
    handle.request_stop()
    assert handle.permit.stop_event.is_set()
    with pytest.raises(RuntimeFailure, match="writer_not_stopped"):
        owner.finish_foreground(handle.permit, lambda: pytest.fail("too early"))
    assert not owner.close(timeout=0.01)
    assert owner.status(handle.permit.identity.document_id).running
    release.set()
    handle.wait(2)
    assert not owner.close(timeout=0.01)  # Completed is not durably closed.
    owner.finish_foreground(handle.permit, lambda: None)
    assert owner.close(timeout=2)


def test_ai_sql_uses_separate_pool_and_never_calls_manual_checkpoints(foreground):
    owner, checkpoint, storage, _, handles = foreground
    run = run_identity()
    value = ai_intent(run)
    confirmed, results, agent_threads = [], [], []
    def work(permit):
        agent_threads.append(get_ident())
        results.append(owner.execute_foreground(permit, value, confirmed.append).wait(2))
    handle = owner.start_foreground(run, work)
    handles.append(handle)
    assert handle.wait(2).error is None
    assert results[0].observation.confirmed and not results[0].checkpoint_closed
    assert confirmed == [value.identity]
    assert storage.executed[0][1] != agent_threads[0]
    assert not checkpoint.pending and not checkpoint.closed
    assert owner.status(run.document_id).write_blocked
    owner.finish_foreground(handle.permit, lambda: None)


def test_unconfirmed_sql_cannot_recover_until_actual_run_has_exited(foreground):
    owner, _, storage, release, handles = foreground
    storage.unknown = True
    run, sql_done = run_identity(), Event()
    value = ai_intent(run)
    def work(permit):
        result = owner.execute_foreground(permit, value, lambda _: None).wait(2)
        assert not result.observation.confirmed
        sql_done.set()
        assert release.wait(3)
    handle = owner.start_foreground(run, work)
    handles.append(handle)
    assert sql_done.wait(2)
    with pytest.raises(RuntimeFailure, match="writer_not_stopped"):
        owner.recover_foreground(handle.permit, value.identity, lambda _: None, timeout=0.1)
    with pytest.raises(RuntimeFailure, match="document_busy"):
        owner.recover(run.document_id)
    assert not storage.recovered
    release.set()
    handle.wait(2)
    result = owner.recover_foreground(handle.permit, value.identity, lambda _: None, timeout=2)
    assert result.observation.confirmed and not result.checkpoint_closed
    assert len(storage.executed) == 1 and storage.recovered == [value.identity]
    assert owner.status(run.document_id).write_blocked


def test_durable_binding_without_local_sql_only_gets_failure_closure(foreground):
    owner, _, storage, _, handles = foreground
    run, checked = run_identity(), []
    value = ai_intent(run)
    handle = owner.start_foreground(run, lambda _: None)
    handles.append(handle)
    handle.wait(2)
    result = owner.recover_foreground(handle.permit, value.identity, checked.append, timeout=2)
    assert result.observation.status == "save_failed" and result.observation.confirmed
    assert checked == [value.identity] and not storage.executed


def test_binding_validation_failure_dispatches_no_sql(foreground):
    owner, _, storage, _, handles = foreground
    run = run_identity()
    def work(permit):
        def unknown(_):
            raise RuntimeError("private checkpoint data")
        with pytest.raises(RuntimeFailure, match="^checkpoint_unavailable$"):
            owner.execute_foreground(permit, ai_intent(run), unknown)
    handle = owner.start_foreground(run, work)
    handles.append(handle)
    assert handle.wait(2).error is None and not storage.executed


def test_stale_permit_and_copied_sql_context_are_not_authority(foreground):
    owner, _, storage, release, handles = foreground
    run = run_identity()
    value = ai_intent(run)
    storage.release.clear()
    def work(permit):
        owner.execute_foreground(permit, value, lambda _: None).wait(3)
    handle = owner.start_foreground(run, work)
    handles.append(handle)
    assert storage.started.wait(2)
    with pytest.raises(RuntimeFailure, match="writer_not_valid"):
        storage.worker_context.run(owner.require_bound, value)
    storage.release.set()
    handle.wait(2)
    with pytest.raises(RuntimeFailure, match="writer_not_valid"):
        storage.worker_context.run(owner.require_bound, value)
    owner.finish_foreground(handle.permit, lambda: None)
    next_handle = start_waiting(foreground, run_identity(run.document_id))
    with pytest.raises(RuntimeFailure, match="writer_not_valid"):
        owner.execute_foreground(handle.permit, value, lambda _: None)
    handle.request_stop()
    assert not next_handle.permit.stop_event.is_set()
    release.set()


def test_run_failure_is_fixed_and_unclosed_run_still_blocks(foreground):
    owner, _, _, _, handles = foreground
    run = run_identity()
    def broken(_):
        raise RuntimeError("private model payload")
    handle = owner.start_foreground(run, broken)
    handles.append(handle)
    result = handle.wait(2)
    assert result.error == "foreground_failed" and result.write_blocked
    assert "private" not in repr(result)
    def no_closure():
        raise RuntimeError("private checkpoint details")
    with pytest.raises(RuntimeFailure, match="^checkpoint_unavailable$"):
        owner.finish_foreground(handle.permit, no_closure)
    assert owner.status(run.document_id).write_blocked


def test_close_waits_for_sql_even_after_agent_future_is_done(foreground):
    owner, _, storage, _, handles = foreground
    run, writes = run_identity(), []
    value = ai_intent(run)
    storage.release.clear()
    handle = owner.start_foreground(run,
        lambda permit: writes.append(owner.execute_foreground(permit, value, lambda _: None)))
    handles.append(handle)
    handle.wait(2)
    assert storage.started.wait(2)
    assert not owner.close(timeout=0.01)
    with pytest.raises(RuntimeFailure, match="writer_not_stopped"):
        owner.finish_foreground(handle.permit, lambda: pytest.fail("SQL still running"))
    storage.release.set()
    assert writes[0].wait(2).observation.confirmed
    owner.finish_foreground(handle.permit, lambda: None)
    assert owner.close(timeout=2)


def test_original_manual_receipt_is_readable_during_foreground(foreground):
    owner, _, storage, _, _ = foreground
    previous = intent()
    result = owner.submit(previous).wait(2)
    start_waiting(foreground, run_identity(previous.document_id))
    assert owner.submit(previous).wait(0.1).observation == result.observation
    assert len(storage.executed) == 1


def test_same_ai_operation_reentry_retains_original_future_and_digest(foreground):
    owner, _, storage, _, handles = foreground
    run = run_identity()
    value = ai_intent(run)
    def work(permit):
        first = owner.execute_foreground(permit, value, lambda _: None)
        assert storage.started.wait(2)
        assert owner.execute_foreground(permit, value, lambda _: pytest.fail("re-admit")) is first
        changed = bind_edit(value.operation_id, "ai", run.run_id,
            {"tool": "jd_set_text", "arguments": {
                "target_field_ref": "purpose", "text": "different", "basis_refs": []}}, value.context)
        with pytest.raises(RuntimeFailure, match="^operation_conflict$"):
            owner.execute_foreground(permit, changed, lambda _: None)
        storage.release.set()
        assert first.wait(2).observation.confirmed
    storage.release.clear()
    handle = owner.start_foreground(run, work)
    handles.append(handle)
    assert handle.wait(2).error is None and len(storage.executed) == 1


@pytest.mark.parametrize("fault", ["submit_failure", "already_done"])
def test_foreground_dispatch_failure_and_immediate_callback_are_tracked(foreground, monkeypatch, fault):
    owner, _, storage, _, handles = foreground
    def dispatch(*args):
        if fault == "submit_failure":
            raise RuntimeError("private executor detail")
        result = Future()
        result.set_exception(KeyboardInterrupt("private worker detail"))
        return result
    monkeypatch.setattr(owner._foreground_pool, "submit", dispatch)
    handle = owner.start_foreground(run_identity(), lambda _: pytest.fail("unexpected work"))
    handles.append(handle)
    assert handle.wait(0.1).error == ("foreground_not_started" if fault == "submit_failure" else "foreground_failed")
    assert owner.status(handle.permit.identity.document_id).write_blocked
    assert not storage.executed
    owner.finish_foreground(handle.permit, lambda: None)


def test_close_cannot_overtake_synchronous_foreground_admission(foreground):
    owner, checkpoint, _, release, handles = foreground
    entered, continue_read = Event(), Event()
    original = checkpoint.read
    def read(document):
        entered.set()
        assert continue_read.wait(3)
        return original(document)
    checkpoint.read = read
    with ThreadPoolExecutor(max_workers=1) as caller:
        start = caller.submit(owner.start_foreground, run_identity(), lambda _: release.wait(3))
        try:
            assert entered.wait(2)
            assert not owner.close(timeout=0.01)
        finally:
            continue_read.set()
        handle = start.result(2)
        handles.append(handle)
    assert not owner.close(timeout=0.01)
    release.set()
    handle.wait(2)
    owner.finish_foreground(handle.permit, lambda: None)
    assert owner.close(timeout=2)


def test_stop_before_next_operation_dispatches_no_write(foreground):
    owner, _, storage, _, handles = foreground
    run = run_identity()
    def work(permit):
        permit.stop_event.set()
        with pytest.raises(RuntimeFailure, match="^foreground_stopping$"):
            owner.execute_foreground(permit, ai_intent(run), lambda _: pytest.fail("cancelled admission"))
    handle = owner.start_foreground(run, work)
    handles.append(handle)
    assert handle.wait(2).error is None and not storage.executed


@pytest.mark.parametrize("confirmation", [True, False])
def test_boolean_is_not_durable_closure_evidence(foreground, confirmation):
    owner, _, _, _, handles = foreground
    handle = owner.start_foreground(run_identity(), lambda _: None)
    handles.append(handle)
    handle.wait(2)
    with pytest.raises(RuntimeFailure, match="^checkpoint_unavailable$"):
        owner.finish_foreground(handle.permit, lambda: confirmation)
    assert owner.status(handle.permit.identity.document_id).write_blocked


@pytest.mark.parametrize("pending", ["manual", "native_work", "unavailable"])
def test_foreground_start_does_not_bypass_native_checkpoint_state(foreground, pending):
    owner, checkpoint, storage, _, _ = foreground
    run = run_identity()
    if pending == "manual":
        checkpoint.pending[run.document_id] = intent(run.document_id).identity
    else:
        def blocked(_):
            raise RuntimeFailure("document_busy" if pending == "native_work" else "private saver detail")
        checkpoint.read = blocked
    with pytest.raises(RuntimeFailure, match="^(document_busy|checkpoint_unavailable)$"):
        owner.start_foreground(run, lambda _: pytest.fail("unresolved checkpoint"))
    assert not storage.executed


def test_foreign_run_and_manual_intent_cannot_use_ai_permit(foreground):
    owner, _, storage, release, handles = foreground
    run = run_identity()
    checked = []
    def work(permit):
        for value in (intent(run.document_id), ai_intent(run_identity()),
                      ai_intent(run_identity(run.document_id))):
            with pytest.raises(RuntimeFailure, match="^invalid_input$"):
                owner.execute_foreground(permit, value, checked.append)
    handle = owner.start_foreground(run, work)
    handles.append(handle)
    assert handle.wait(2).error is None
    assert not checked and not storage.executed


@pytest.mark.parametrize("origin", ["manual", "ai"])
@pytest.mark.parametrize("reuse", ["after_done", "during_next_attempt"])
def test_previous_recovery_context_cannot_authorize_late_write(origin, reuse):
    class CaptureRecovery(ForegroundStorage):
        def __init__(self, authority):
            super().__init__(authority)
            self.contexts, self.threads, self.reused = [], [], []
            self.return_unknown = True

        def reconcile_stopped(self, identity):
            self.authority.require_stopped(identity)
            if self.contexts:
                try:
                    self.contexts[0].run(self.authority.require_stopped, identity)
                    self.reused.append("authorized")
                except RuntimeFailure as error:
                    self.reused.append(error.code)
            self.contexts.append(copy_context())
            self.threads.append(get_ident())
            if self.return_unknown:
                return WriteObservation(identity.document_id, identity.operation_id, None, "unknown")
            result = observation(identity, "save_failed")
            return replace(result, receipt=replace(result.receipt,
                origin=identity.origin, ai_run_id=identity.ai_run_id))

    checkpoint = Checkpoints()
    owner = ManualRuntime(checkpoint, CaptureRecovery, max_workers=1)
    run, handle = run_identity(), None
    value = ai_intent(run) if origin == "ai" else intent(run.document_id)
    if origin == "ai":
        handle = owner.start_foreground(run, lambda _: None)
        handle.wait(2)
        recover = lambda: owner.recover_foreground(handle.permit, value.identity, lambda _: None, timeout=2)
    else:
        checkpoint.admit_error = True
        assert owner.submit(value).wait(2).error == "checkpoint_unavailable"
        recover = lambda: owner.recover(run.document_id, timeout=2)
    try:
        assert not recover().observation.confirmed
        entry = owner._slots[run.document_id].entry
        assert entry.attempt.future.done()
        if reuse == "after_done":
            def late():
                assert get_ident() == owner.storage.threads[0]
                with pytest.raises(RuntimeFailure, match="^writer_not_stopped$"):
                    owner.storage.contexts[0].run(owner.require_stopped, value.identity)
            owner._pool.submit(late).result(2)
        else:
            assert not recover().observation.confirmed
            assert owner.storage.threads[0] == owner.storage.threads[1]
            assert owner.storage.reused == ["writer_not_stopped"]
        assert not owner.storage.executed
    finally:
        owner.storage.return_unknown = False
        assert recover().observation.confirmed
        if handle is not None:
            owner.finish_foreground(handle.permit, lambda: None)
        assert owner.close(timeout=2)
