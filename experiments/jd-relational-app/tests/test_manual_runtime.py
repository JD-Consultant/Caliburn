"""Real managed threads; synthetic persistence, not PostgreSQL or OS proof."""

from dataclasses import replace
from datetime import datetime, timezone
from threading import Event, get_ident
from uuid import uuid4

import pytest

from jd_relational.domain import CommandContext, Ref
from jd_relational.intents import bind_edit
from jd_relational.manual_runtime import ManualRuntime, RuntimeFailure
from jd_relational.storage.receipts import SavedOperation, WriteObservation, body_for
from jd_relational.storage.service import StorageError


def intent(document=None, *, operation=None, text="保存真實工作"):
    doc, base = document or str(uuid4()), uuid4()
    context = CommandContext(doc, str(base), {"purpose": Ref(doc, str(base), "profile", field="purpose")}, {}, lambda: str(uuid4()))
    return bind_edit(operation_id=operation or uuid4(), origin="manual", ai_run_id=None,
        context=context, command={"tool": "jd_set_text", "arguments": {
            "target_field_ref": "purpose", "text": text, "basis_refs": []}})


def observation(identity, status="committed"):
    return WriteObservation(identity.document_id, identity.operation_id, SavedOperation(
        identity.document_id, identity.operation_id, identity.request_digest, "manual", None,
        identity.base_revision_id, uuid4() if status == "committed" else None,
        status, body_for(identity.command_kind, status), datetime.now(timezone.utc)))


class Checkpoints:
    def __init__(self):
        self.pending = {}
        self.admit_error = self.close_error = False
        self.closed = []

    def read(self, document):
        return self.pending.get(document)

    def admit(self, identity):
        self.pending[identity.document_id] = identity
        if self.admit_error:
            raise RuntimeError("synthetic private saver details")

    def close(self, identity):
        if self.close_error:
            raise RuntimeError("synthetic private saver details")
        assert self.pending.get(identity.document_id) == identity
        del self.pending[identity.document_id]
        self.closed.append(identity)


class Storage:
    def __init__(self, authority):
        self.authority = authority
        self.receipts = {}
        self.executed = []
        self.recovered = []
        self.started = Event()
        self.release = Event()
        self.release.set()
        self.unknown = False
        self.failure = False

    def lookup(self, identity):
        result = self.receipts.get(identity.operation_id)
        if result and result.receipt.request_digest != identity.request_digest:
            raise StorageError("operation_conflict")
        return result

    def execute(self, value):
        self.authority.require_bound(value)
        self.executed.append((value.identity, get_ident()))
        self.started.set()
        assert self.release.wait(3), "test must release its own writer"
        self.authority.require_bound(value)
        result = observation(value.identity, "save_failed" if self.failure else "committed")
        self.receipts[value.operation_id] = result
        return WriteObservation(value.document_id, value.operation_id, None, "unknown") if self.unknown else result

    def reconcile_stopped(self, identity):
        self.authority.require_stopped(identity)
        self.recovered.append(identity)
        return self.receipts.get(identity.operation_id) or observation(identity, "save_failed")


@pytest.fixture
def runtime():
    checkpoint = Checkpoints()
    owner = ManualRuntime(checkpoint, Storage, max_workers=2)
    yield owner, checkpoint, owner.storage
    owner.storage.release.set()
    assert owner.close(timeout=3)


def test_managed_worker_saves_then_confirms_checkpoint_cleanup(runtime):
    owner, checkpoints, storage = runtime
    value = intent()
    result = owner.submit(value).wait(3)
    assert result.observation.confirmed and result.checkpoint_closed
    assert result.error is None and storage.executed[0][1] != get_ident()
    assert checkpoints.closed == [value.identity]
    assert not owner.status(value.document_id).write_blocked
    assert owner.submit(value).wait(3).observation == result.observation
    assert len(storage.executed) == 1


def test_recovery_for_old_operation_cannot_recover_new_pending(runtime):
    owner, checkpoint, storage = runtime
    old = intent()
    assert owner.submit(old).wait(3).checkpoint_closed
    new = intent(old.document_id)
    checkpoint.close_error = True
    assert not owner.submit(new).wait(3).checkpoint_closed
    with pytest.raises(RuntimeFailure, match="operation_conflict"):
        owner.recover(old.document_id, expected_operation_id=old.operation_id)
    assert checkpoint.pending[old.document_id] == new.identity
    assert storage.recovered == []
    checkpoint.close_error = False
    assert owner.recover(new.document_id, expected_operation_id=new.operation_id).checkpoint_closed


def test_same_pending_operation_with_different_intent_is_conflict(runtime):
    owner, checkpoint, storage = runtime
    storage.release.clear()
    value = intent()
    owner.submit(value)
    assert storage.started.wait(2)
    changed = bind_edit(value.operation_id, "manual", None,
        {"tool": "jd_set_text", "arguments": {
            "target_field_ref": "purpose", "text": "different", "basis_refs": []}}, value.context)
    with pytest.raises(RuntimeFailure, match="operation_conflict"):
        owner.submit(changed)
    assert checkpoint.pending[value.document_id] == value.identity


def test_original_receipt_remains_observable_while_later_operation_runs(runtime):
    owner, checkpoint, storage = runtime
    old = intent()
    original = owner.submit(old).wait(3)
    storage.release.clear()
    new = intent(old.document_id)
    owner.submit(new)
    repeated = owner.submit(old).wait(0.1)
    assert repeated.observation == original.observation
    assert checkpoint.pending[old.document_id] == new.identity
    assert owner.status(old.document_id).write_blocked


def test_same_document_wait_timeout_is_not_cancellation_or_stopped_proof(runtime):
    owner, checkpoints, storage = runtime
    storage.release.clear()
    value = intent()
    handle = owner.submit(value)
    assert storage.started.wait(2)
    assert owner.submit(value) is handle
    with pytest.raises(TimeoutError):
        handle.wait(0.01)
    with pytest.raises(RuntimeFailure, match="writer_not_stopped"):
        owner.recover(value.document_id)
    with pytest.raises(RuntimeFailure, match="document_busy"):
        owner.submit(intent(value.document_id))
    assert checkpoints.pending[value.document_id] == value.identity
    storage.release.set()
    assert handle.wait(3).observation.confirmed


def test_other_document_is_not_held_by_first_documents_checkpoint_io(runtime):
    owner, checkpoints, storage = runtime
    one, two = intent(), intent()
    entered, release = Event(), Event()
    original = checkpoints.admit
    def slow(identity):
        if identity.document_id == one.document_id:
            entered.set()
            assert release.wait(3)
        original(identity)
    checkpoints.admit = slow
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as caller:
        first = caller.submit(owner.submit, one)
        try:
            assert entered.wait(2)
            assert owner.submit(two).wait(2).checkpoint_closed
        finally:
            release.set()
        assert first.result(2).wait(2).checkpoint_closed


def test_unknown_keeps_gate_until_explicit_original_receipt_recovery(runtime):
    owner, checkpoints, storage = runtime
    value = intent()
    storage.unknown = True
    result = owner.submit(value).wait(3)
    assert not result.observation.confirmed and not result.checkpoint_closed
    assert checkpoints.pending[value.document_id] == value.identity
    assert not storage.recovered
    recovered = owner.recover(value.document_id)
    assert recovered.observation == storage.receipts[value.operation_id]
    assert recovered.checkpoint_closed and len(storage.executed) == 1


def test_terminal_failure_is_not_left_permanently_pending(runtime):
    owner, checkpoints, storage = runtime
    storage.failure = True
    result = owner.submit(intent()).wait(3)
    assert result.observation.confirmed and result.observation.status == "save_failed"
    assert result.checkpoint_closed and not checkpoints.pending


def test_unconfirmed_admission_never_starts_sql_and_can_only_close_failure(runtime):
    owner, checkpoints, storage = runtime
    value = intent()
    checkpoints.admit_error = True
    result = owner.submit(value).wait(2)
    assert result.error == "checkpoint_unavailable"
    assert not storage.executed and not result.checkpoint_closed
    recovered = owner.recover(value.document_id)
    assert recovered.observation.status == "save_failed" and recovered.checkpoint_closed
    assert storage.recovered == [value.identity] and not storage.executed


def test_committed_receipt_survives_checkpoint_close_failure(runtime):
    owner, checkpoints, storage = runtime
    value = intent()
    checkpoints.close_error = True
    saved = owner.submit(value).wait(3)
    assert saved.observation.confirmed and not saved.checkpoint_closed
    assert saved.error == "checkpoint_unavailable"
    checkpoints.close_error = False
    result = owner.recover(value.document_id)
    assert result.observation == saved.observation and result.checkpoint_closed
    assert len(storage.executed) == 1


def test_reopened_owner_does_not_invent_death_of_a_foreign_pending_writer(runtime):
    _, checkpoints, _ = runtime
    value = intent()
    checkpoints.pending[value.document_id] = value.identity
    owner = ManualRuntime(checkpoints, Storage)
    try:
        with pytest.raises(RuntimeFailure, match="writer_not_stopped"):
            owner.recover(value.document_id)
        with pytest.raises(RuntimeFailure, match="document_busy"):
            owner.submit(value)
        assert not owner.storage.executed and not owner.storage.recovered
    finally:
        assert owner.close(timeout=2)


def test_calling_storage_outside_managed_worker_cannot_borrow_its_authority(runtime):
    owner, _, storage = runtime
    value = intent()
    storage.release.clear()
    handle = owner.submit(value)
    assert storage.started.wait(2)
    try:
        with pytest.raises(RuntimeFailure, match="writer_not_valid"):
            storage.execute(value)
    finally:
        storage.release.set()
    assert handle.wait(3).checkpoint_closed


def test_known_operation_conflict_does_not_publish_new_pending(runtime):
    owner, checkpoints, storage = runtime
    original = intent()
    owner.submit(original).wait(3)
    different = intent(original.document_id, operation=original.operation_id, text="另一個意圖")
    with pytest.raises(RuntimeFailure, match="operation_conflict"):
        owner.submit(different)
    assert not checkpoints.pending and len(storage.executed) == 1


def test_shutdown_timeout_keeps_running_writer_and_stops_admission(runtime):
    owner, _, storage = runtime
    storage.release.clear()
    value = intent()
    handle = owner.submit(value)
    assert storage.started.wait(2)
    assert not owner.close(timeout=0.01)
    with pytest.raises(RuntimeFailure, match="runtime_closed"):
        owner.submit(intent())
    storage.release.set()
    assert handle.wait(3).checkpoint_closed
    assert owner.close(timeout=2)


def test_shutdown_deadline_also_covers_admission_checkpoint_io(runtime):
    owner, checkpoints, _ = runtime
    entered, release = Event(), Event()
    original = checkpoints.admit
    def slow(identity):
        entered.set()
        assert release.wait(2)
        original(identity)
    checkpoints.admit = slow
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as caller:
        request = caller.submit(owner.submit, intent())
        try:
            assert entered.wait(1)
            assert not owner.close(timeout=0.01)
        finally:
            release.set()
        assert request.result(2).wait(2).checkpoint_closed


def test_worker_base_exception_settles_without_leaking_or_replaying(runtime, caplog):
    owner, checkpoints, storage = runtime
    value = intent()
    def stopped(value):
        storage.authority.require_bound(value)
        raise SystemExit("synthetic private worker detail")
    storage.execute = stopped
    result = owner.submit(value).wait(1)
    assert result.error == "writer_failed" and not result.checkpoint_closed
    assert checkpoints.pending[value.document_id] == value.identity
    assert "synthetic private worker detail" not in caplog.text
    recovered = owner.recover(value.document_id)
    assert recovered.observation.status == "save_failed" and recovered.checkpoint_closed


def test_worker_cleanup_base_exception_preserves_saved_result(runtime, caplog):
    owner, checkpoints, _ = runtime
    value = intent()
    original_close = checkpoints.close
    def stopped(identity):
        raise SystemExit("synthetic private cleanup detail")
    checkpoints.close = stopped
    result = owner.submit(value).wait(1)
    assert result.observation.confirmed and not result.checkpoint_closed
    assert result.error == "checkpoint_unavailable"
    assert "synthetic private cleanup detail" not in caplog.text
    checkpoints.close = original_close
    recovered = owner.recover(value.document_id)
    assert recovered.observation == result.observation and recovered.checkpoint_closed


def test_inline_cleanup_main_thread_interrupt_settles_then_propagates(runtime, monkeypatch):
    from concurrent.futures import Future
    owner, checkpoints, _ = runtime
    value = intent()
    checkpoints.close_error = True
    saved = owner.submit(value).wait(1)
    assert saved.observation.confirmed and not saved.checkpoint_closed
    original_close = checkpoints.close
    def interrupted(identity):
        raise KeyboardInterrupt()
    def already_done(*args):
        future = Future()
        future.set_result(saved.observation)
        return future  # Native add_done_callback now executes in this thread.
    checkpoints.close = interrupted
    with monkeypatch.context() as patch:
        patch.setattr(owner._pool, "submit", already_done)
        with pytest.raises(KeyboardInterrupt):
            owner.recover(value.document_id)
    assert not owner.status(value.document_id).running
    assert owner.status(value.document_id).write_blocked
    checkpoints.close = original_close
    checkpoints.close_error = False
    assert owner.recover(value.document_id).checkpoint_closed


def test_admission_interrupt_propagates_with_known_unsubmitted_attempt(runtime):
    owner, checkpoints, storage = runtime
    value = intent()
    original_admit = checkpoints.admit
    def interrupted(identity):
        original_admit(identity)
        raise KeyboardInterrupt()
    checkpoints.admit = interrupted
    with pytest.raises(KeyboardInterrupt):
        owner.submit(value)
    assert not owner.status(value.document_id).running
    assert owner.status(value.document_id).write_blocked
    assert not storage.executed
    recovered = owner.recover(value.document_id)
    assert recovered.observation.status == "save_failed" and recovered.checkpoint_closed
