"""Foreign startup ownership with real Futures and explicit fake OS/SQL ports.

This does not prove native Windows death, PostgreSQL behavior or model execution.
"""

from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import replace
from threading import Event

import pytest

from jd_relational.manual_runtime import ManualRuntime, RuntimeFailure
from jd_relational.storage.receipts import WriteObservation
from test_foreground_runtime import ai_intent, run_identity
from test_manual_runtime import Checkpoints, observation, intent
from test_startup_recovery import CatalogStorage, PreviousHost


class RestartCheckpoints(Checkpoints):
    def __init__(self):
        super().__init__()
        self.busy, self.reads = set(), []

    def read(self, document):
        self.reads.append(document)
        if document in self.busy:
            raise RuntimeFailure("document_busy")
        return super().read(document)


class RestartStorage(CatalogStorage):
    def __init__(self, authority):
        super().__init__(authority)
        self.archived = set()
        self.contexts = []
        self.return_unknown = False

    def reconcile_stopped(self, identity):
        self.authority.require_stopped(identity)
        self.recovered.append(identity)
        self.contexts.append(copy_context())
        self.started.set()
        assert self.release.wait(3), "Release the test-owned recovery worker."
        self.authority.require_stopped(identity)
        if self.return_unknown:
            return WriteObservation(identity.document_id, identity.operation_id, None, "unknown")
        result = self.receipts.get(identity.operation_id)
        if result is None:
            result = observation(identity, "save_failed")
            result = replace(result, receipt=replace(result.receipt, origin=identity.origin, ai_run_id=identity.ai_run_id))
            self.receipts[identity.operation_id] = result
        return result


@pytest.fixture
def restart():
    checkpoints, lease = RestartCheckpoints(), PreviousHost()
    owner = ManualRuntime(checkpoints, RestartStorage, previous_host=lease, max_workers=1)
    yield owner, checkpoints, owner.storage, lease
    lease.valid = True
    owner.storage.release.set()
    owner.storage.return_unknown = False
    checkpoints.busy.clear()
    for slot in tuple(owner._slots.values()):
        foreground = slot.foreground
        if foreground is not None and not foreground.closed:
            if slot.entry is not None:
                slot.entry.attempt.handle.wait(3)
            if slot.entry is not None:
                owner.recover_foreground(foreground.permit, slot.entry.identity, lambda _: None, timeout=3)
            owner.finish_foreground(foreground.permit, lambda: None)
    assert owner.close(timeout=3)


def pending(restart):
    owner, checkpoints, storage, _ = restart
    identity = run_identity()
    storage.documents.append(identity.document_id)
    checkpoints.busy.add(identity.document_id)
    return identity


def close_original(owner, checkpoints, handle):
    def confirm():
        checkpoints.busy.discard(handle.permit.identity.document_id)
    owner.finish_foreground(handle.permit, confirm)


def test_only_scan_can_adopt_original_and_foreign_can_never_execute(restart):
    owner, checkpoints, storage, lease = restart
    identity, handles, checked = pending(restart), [], []
    value = ai_intent(identity)

    def recover(document, timeout):
        assert document == identity.document_id and timeout == 0.5 and not owner.ready
        first = owner.adopt_previous_foreground(identity, checked.append)
        assert owner.adopt_previous_foreground(identity, checked.append) is first
        handles.append(first)
        assert first._entry.future is None and first.wait(0).error == "foreground_interrupted"
        assert first._entry.previous_host is lease
        with pytest.raises(RuntimeFailure, match="^writer_not_valid$"):
            owner.execute_foreground(first.permit, value, lambda _: pytest.fail("foreign write"))
        observed = owner.recover_foreground(first.permit, value.identity, lambda _: None, timeout=timeout)
        assert observed.observation.confirmed and observed.observation.status == "save_failed"
        assert not observed.checkpoint_closed
        close_original(owner, checkpoints, first)
        return 1

    owner.claim_foreground_coordinator(startup_recover=recover)
    assert owner.finish_startup(timeout=0.5) == 1 and owner.ready
    assert checked == [identity, identity] and storage.recovered == [value.identity] and not storage.executed
    assert checkpoints.reads == [identity.document_id] and not checkpoints.closed
    assert owner.finish_startup() == 0
    with pytest.raises(RuntimeFailure, match="^startup_recovery_required$"):
        owner.adopt_previous_foreground(identity, lambda _: None)


def test_adoption_without_previous_host_or_scan_cannot_be_forged_by_failed_future(monkeypatch):
    owner = ManualRuntime(RestartCheckpoints(), RestartStorage)
    try:
        identity = run_identity()
        fake = Future(); fake.set_exception(RuntimeError("synthetic failure"))
        monkeypatch.setattr(owner._foreground_pool, "submit", lambda *_: fake)
        handle = owner.start_foreground(identity, lambda _: pytest.fail("not dispatched"))
        with pytest.raises(RuntimeFailure, match="^startup_recovery_required$"):
            owner.adopt_previous_foreground(identity, lambda _: None)
        assert fake.done() and not owner.storage.recovered
        owner.finish_foreground(handle.permit, lambda: None)
    finally:
        assert owner.close(timeout=1)


def test_previous_host_alone_and_copied_scan_context_are_not_admission(restart):
    owner, checkpoints, storage, _ = restart
    first, second = pending(restart), pending(restart)
    storage.documents.sort()
    runs = {value.document_id: value for value in (first, second)}
    captured = []
    with pytest.raises(RuntimeFailure, match="^startup_recovery_required$"):
        owner.adopt_previous_foreground(first, lambda _: None)

    def recover(document, _):
        identity = runs[document]
        with ThreadPoolExecutor(max_workers=1) as other:
            context = copy_context()
            future = other.submit(context.run, owner.adopt_previous_foreground, identity, lambda _: None)
            with pytest.raises(RuntimeFailure, match="^startup_recovery_required$"):
                future.result(1)
        if captured:
            context, previous = captured[0]
            with pytest.raises(RuntimeFailure, match="^startup_recovery_required$"):
                context.run(owner.adopt_previous_foreground, previous, lambda _: None)
        captured.append((copy_context(), identity))
        handle = owner.adopt_previous_foreground(identity, lambda _: None)
        close_original(owner, checkpoints, handle)
        return 1

    owner.claim_foreground_coordinator(startup_recover=recover)
    assert owner.finish_startup() == 2
    context, previous = captured[0]
    with pytest.raises(RuntimeFailure, match="^startup_recovery_required$"):
        context.run(owner.adopt_previous_foreground, previous, lambda _: None)


@pytest.mark.parametrize("fault", ["raise", "boolean", "digest"])
def test_unverified_record_or_changed_identity_keeps_startup_blocked(restart, fault):
    owner, checkpoints, storage, _ = restart
    identity = pending(restart)

    def recover(document, timeout):
        if fault == "digest":
            owner.adopt_previous_foreground(identity, lambda _: None)
            owner.adopt_previous_foreground(replace(identity, request_digest="b" * 64), lambda _: None)
        else:
            def confirm(_):
                if fault == "raise":
                    raise RuntimeError("synthetic private record")
                return True
            owner.adopt_previous_foreground(identity, confirm)
        return 1

    owner.claim_foreground_coordinator(startup_recover=recover)
    with pytest.raises(RuntimeFailure) as error:
        owner.finish_startup()
    assert str(error.value) in {"checkpoint_unavailable", "operation_conflict"}
    assert "private" not in str(error.value) and not owner.ready
    assert owner.status(identity.document_id).write_blocked
    assert not storage.recovered and not storage.executed


@pytest.mark.parametrize("result", [None, True, -1, 2, "1"])
def test_callback_count_is_strict_and_cannot_open_startup(restart, result):
    owner, _, storage, _ = restart
    storage.documents = [run_identity().document_id]
    owner.claim_foreground_coordinator(startup_recover=lambda *_: result)
    with pytest.raises(RuntimeFailure, match="^checkpoint_unavailable$"):
        owner.finish_startup()
    assert not owner.ready


def test_callback_cannot_replace_manual_idle_check_or_leave_foreground_open(restart):
    owner, checkpoints, _, _ = restart
    identity = pending(restart)
    mode = ["busy"]

    def recover(document, timeout):
        if mode[0] == "open":
            owner.adopt_previous_foreground(identity, lambda _: None)
            checkpoints.busy.clear()  # Misbehaving coordinator cannot conceal live owner state.
        return 0

    owner.claim_foreground_coordinator(startup_recover=recover)
    with pytest.raises(RuntimeFailure, match="^document_busy$"):
        owner.finish_startup()
    mode[0] = "open"
    with pytest.raises(RuntimeFailure, match="^startup_recovery_pending$"):
        owner.finish_startup()
    assert checkpoints.reads == [identity.document_id, identity.document_id] and not owner.ready


def test_timeout_retry_reuses_original_foreign_handle_and_unfinished_sql_attempt(restart):
    owner, checkpoints, storage, _ = restart
    identity, handles = pending(restart), []
    value = ai_intent(identity)
    storage.release.clear()

    def recover(document, timeout):
        handle = owner.adopt_previous_foreground(identity, lambda _: None)
        handles.append(handle)
        observed = owner.recover_foreground(handle.permit, value.identity, lambda _: None, timeout=timeout)
        assert observed.observation.confirmed
        close_original(owner, checkpoints, handle)
        return 1

    owner.claim_foreground_coordinator(startup_recover=recover)
    try:
        with pytest.raises(RuntimeFailure, match="^startup_recovery_pending$"):
            owner.finish_startup(timeout=0.01)
        assert storage.started.wait(1)
        attempt = owner._slots[identity.document_id].entry.attempt
        with pytest.raises(RuntimeFailure, match="^writer_not_stopped$"):
            owner.finish_startup(timeout=0.01)
        assert owner._slots[identity.document_id].entry.attempt is attempt
        assert handles[0] is handles[1] and storage.recovered == [value.identity]
        assert not owner.ready
    finally:
        storage.release.set()
    assert attempt.handle.wait(2).observation.confirmed
    assert owner.finish_startup() == 1 and owner.ready
    assert handles[-1] is handles[0] and not storage.executed
    # A completed original receipt may be looked up again, never re-executed.
    assert storage.recovered == [value.identity, value.identity]


def test_all_documents_including_archived_get_callback_before_final_ready(restart):
    owner, checkpoints, storage, _ = restart
    runs = [pending(restart) for _ in range(102)]
    by_doc = {value.document_id: value for value in runs}
    storage.archived.add(runs[-1].document_id)
    seen = []
    def recover(document, timeout):
        assert not owner.ready
        seen.append(document)
        handle = owner.adopt_previous_foreground(by_doc[document], lambda _: None)
        close_original(owner, checkpoints, handle)
        return 1
    owner.claim_foreground_coordinator(startup_recover=recover)
    assert owner.finish_startup() == 102
    assert seen == sorted(by_doc) and storage.archived.issubset(seen)
    assert checkpoints.reads == seen and not storage.recovered


def test_lease_loss_blocks_foreign_recovery_and_finish_then_allows_exact_retry(restart):
    owner, checkpoints, storage, lease = restart
    identity = pending(restart)
    value = ai_intent(identity)
    seen = []
    def recover(document, timeout):
        handle = owner.adopt_previous_foreground(identity, lambda _: None)
        seen.append(handle)
        if len(seen) > 1:
            assert handle is seen[0]
            close_original(owner, checkpoints, handle)
            return 1
        lease.valid = False
        for operation in (lambda: owner.recover_foreground(handle.permit, value.identity, lambda _: None),
                          lambda: owner.finish_foreground(handle.permit, lambda: pytest.fail("invalid lease"))):
            with pytest.raises(RuntimeFailure, match="^host_not_valid$"):
                operation()
        raise RuntimeError("synthetic lease failure")
    owner.claim_foreground_coordinator(startup_recover=recover)
    with pytest.raises(RuntimeFailure, match="^checkpoint_unavailable$"):
        owner.finish_startup()
    assert not owner.ready and not seen[0]._entry.closed and not storage.recovered
    lease.valid = True
    assert owner.finish_startup() == 1 and owner.ready


def test_close_budget_includes_startup_callback_and_reentrant_close(restart):
    owner, _, storage, _ = restart
    storage.documents = [run_identity().document_id]
    entered, release = Event(), Event()
    def recover(document, timeout):
        entered.set()
        assert owner.close(timeout=0) is False
        assert release.wait(2)
        return 0
    owner.claim_foreground_coordinator(startup_recover=recover)
    with ThreadPoolExecutor(max_workers=1) as caller:
        starting = caller.submit(owner.finish_startup)
        try:
            assert entered.wait(1)
            assert owner.close(timeout=0.01) is False
            with pytest.raises(RuntimeFailure, match="^startup_busy$"):
                owner.claim_foreground_coordinator(startup_recover=lambda *_: 0)
        finally:
            release.set()
        with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
            starting.result(2)
    assert not owner.ready


def test_single_coordinator_claim_validates_callback_without_consuming_claim(restart):
    owner, _, _, _ = restart
    with pytest.raises(RuntimeFailure, match="^invalid_input$"):
        owner.claim_foreground_coordinator(startup_recover=True)
    owner.claim_foreground_coordinator(startup_recover=lambda *_: 0)
    with pytest.raises(RuntimeFailure, match="^foreground_coordinator_already_configured$"):
        owner.claim_foreground_coordinator()


def test_startup_callback_does_not_replace_existing_manual_recovery(restart):
    owner, checkpoints, storage, _ = restart
    value, seen = intent(), []
    checkpoints.pending[value.document_id] = value.identity
    storage.documents.append(value.document_id)
    def inspect(document, timeout):
        seen.append(document)
        return 0
    owner.claim_foreground_coordinator(startup_recover=inspect)
    assert owner.finish_startup() == 1 and owner.ready
    assert seen == [value.document_id] and storage.recovered == [value.identity]
    assert checkpoints.closed == [value.identity]


def test_lease_is_checked_again_after_confirmation_before_marking_closed(restart):
    owner, checkpoints, _, lease = restart
    identity = pending(restart)
    def recover(document, timeout):
        handle = owner.adopt_previous_foreground(identity, lambda _: None)
        def invalidated():
            lease.valid = False
        with pytest.raises(RuntimeFailure, match="^host_not_valid$"):
            owner.finish_foreground(handle.permit, invalidated)
        assert not handle._entry.closed
        lease.valid = True
        close_original(owner, checkpoints, handle)
        return 1
    owner.claim_foreground_coordinator(startup_recover=recover)
    assert owner.finish_startup() == 1 and owner.ready


def test_foreign_sql_rechecks_lease_after_wait_before_confirming_result(restart):
    owner, checkpoints, storage, lease = restart
    identity = pending(restart)
    value = ai_intent(identity)
    storage.release.clear()
    def recover(document, timeout):
        handle = owner.adopt_previous_foreground(identity, lambda _: None)
        result = owner.recover_foreground(handle.permit, value.identity, lambda _: None, timeout=timeout)
        if result.observation is None or not result.observation.confirmed:
            raise RuntimeFailure("startup_recovery_pending")
        close_original(owner, checkpoints, handle)
        return 1
    owner.claim_foreground_coordinator(startup_recover=recover)
    with ThreadPoolExecutor(max_workers=1) as caller:
        starting = caller.submit(owner.finish_startup)
        try:
            assert storage.started.wait(1)
            lease.valid = False
        finally:
            storage.release.set()
        with pytest.raises(RuntimeFailure, match="^startup_recovery_pending$"):
            starting.result(2)
    assert not owner.ready and not storage.receipts
    lease.valid = True
    assert owner.finish_startup() == 1 and len(storage.recovered) == 2


def test_foreign_recovery_old_context_cannot_outlive_or_borrow_current_attempt(restart):
    owner, checkpoints, storage, _ = restart
    identity = pending(restart)
    value = ai_intent(identity)
    storage.return_unknown = True
    def recover(document, timeout):
        handle = owner.adopt_previous_foreground(identity, lambda _: None)
        result = owner.recover_foreground(handle.permit, value.identity, lambda _: None, timeout=timeout)
        if not result.observation.confirmed:
            raise RuntimeFailure("startup_recovery_pending")
        close_original(owner, checkpoints, handle)
        return 1
    owner.claim_foreground_coordinator(startup_recover=recover)
    with pytest.raises(RuntimeFailure, match="^startup_recovery_pending$"):
        owner.finish_startup()
    previous = storage.contexts[0]
    # The same actual one-worker pool thread is reused after its Future is done.
    late = owner._pool.submit(previous.run, owner.require_stopped, value.identity)
    with pytest.raises(RuntimeFailure, match="^writer_not_stopped$"):
        late.result(1)
    storage.return_unknown = False
    original = storage.reconcile_stopped
    def retry(given):
        with pytest.raises(RuntimeFailure, match="^writer_not_stopped$"):
            previous.run(owner.require_stopped, given)
        return original(given)
    storage.reconcile_stopped = retry
    assert owner.finish_startup() == 1 and owner.ready
    assert storage.recovered == [value.identity, value.identity]
