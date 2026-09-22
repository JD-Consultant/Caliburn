"""Startup coordination with managed threads; OS/DB ports are explicit fakes."""

from threading import Event

import pytest

from jd_relational.manual_runtime import ManualRuntime, RuntimeFailure
from jd_relational.storage.receipts import WriteObservation
from test_manual_runtime import Checkpoints, Storage, intent, observation


class PreviousHost:
    def __init__(self):
        self.valid, self.checked = True, 0

    def require_previous_stopped(self):
        self.checked += 1
        if not self.valid:
            raise RuntimeError("synthetic private host details")


class CatalogStorage(Storage):
    def __init__(self, authority):
        super().__init__(authority)
        self.documents = []
        self.read_error = False

    def document_ids(self, *, after=None, limit=100):
        if self.read_error:
            raise RuntimeError("synthetic private catalog details")
        return tuple(doc for doc in sorted(self.documents) if after is None or doc > after)[:limit]


@pytest.fixture
def startup():
    checkpoints, lease = Checkpoints(), PreviousHost()
    owner = ManualRuntime(checkpoints, CatalogStorage, previous_host=lease)
    yield owner, checkpoints, owner.storage, lease
    owner.storage.release.set()
    assert owner.close(timeout=3)


def pending(checkpoints, storage):
    value = intent()
    checkpoints.pending[value.document_id] = value.identity
    storage.documents.append(value.document_id)
    return value


def test_all_previous_operations_close_before_first_new_write(startup):
    owner, checkpoints, storage, lease = startup
    one, two = pending(checkpoints, storage), pending(checkpoints, storage)
    storage.receipts[two.operation_id] = observation(two.identity)
    with pytest.raises(RuntimeFailure, match="^startup_pending$"):
        owner.submit(intent())
    assert not owner.ready
    assert owner.finish_startup() == 2
    assert owner.ready and not checkpoints.pending
    assert not storage.executed and set(storage.recovered) == {one.identity, two.identity}
    assert lease.checked >= 4
    assert owner.finish_startup() == 0
    assert owner.submit(intent()).wait(2).checkpoint_closed


def test_no_pending_still_requires_successful_complete_catalog_scan(startup):
    owner, _, storage, _ = startup
    storage.documents = sorted(intent().document_id for _ in range(205))
    assert owner.finish_startup() == 0
    assert owner.ready and not storage.executed and not storage.recovered


def test_invalid_host_proof_blocks_all_recovery_and_new_work(startup):
    owner, checkpoints, storage, lease = startup
    value = pending(checkpoints, storage)
    lease.valid = False
    with pytest.raises(RuntimeFailure, match="^host_not_valid$"):
        owner.finish_startup()
    assert not owner.ready and checkpoints.pending[value.document_id] == value.identity
    assert not storage.recovered and not storage.executed
    lease.valid = True
    assert owner.finish_startup() == 1
    lease.valid = False
    with pytest.raises(RuntimeFailure, match="^host_not_valid$"):
        owner.submit(intent())


def test_catalog_read_failure_never_opens_admission(startup):
    owner, _, storage, _ = startup
    storage.read_error = True
    with pytest.raises(RuntimeFailure, match="^read_failed$"):
        owner.finish_startup()
    assert not owner.ready
    storage.read_error = False
    assert owner.finish_startup() == 0 and owner.ready


def test_confirmed_recovery_cleanup_failure_retains_original_for_explicit_retry(startup):
    owner, checkpoints, storage, _ = startup
    value = pending(checkpoints, storage)
    storage.receipts[value.operation_id] = observation(value.identity)
    checkpoints.close_error = True
    with pytest.raises(RuntimeFailure, match="^startup_recovery_pending$"):
        owner.finish_startup()
    assert not owner.ready and storage.recovered == [value.identity]
    checkpoints.close_error = False
    assert owner.finish_startup() == 1 and owner.ready
    assert storage.recovered == [value.identity] and not storage.executed


def test_foreign_no_local_future_cannot_prove_unknown_result_was_never_written(startup):
    owner, checkpoints, storage, _ = startup
    value = pending(checkpoints, storage)
    def unknown(identity):
        storage.authority.require_stopped(identity)
        return WriteObservation(identity.document_id, identity.operation_id, None, "unknown")
    storage.reconcile_stopped = unknown
    with pytest.raises(RuntimeFailure, match="^startup_recovery_pending$"):
        owner.finish_startup()
    del checkpoints.pending[value.document_id]  # Unexpected external loss, not confirmed cleanup.
    with pytest.raises(RuntimeFailure, match="^checkpoint_conflict$"):
        owner.finish_startup()
    assert not owner.ready


def test_timed_out_recovery_keeps_actual_future_and_cannot_schedule_duplicate(startup):
    owner, checkpoints, storage, _ = startup
    value = pending(checkpoints, storage)
    entered, release = Event(), Event()
    original = storage.reconcile_stopped
    calls = []
    def slow(identity):
        calls.append(identity)
        entered.set()
        assert release.wait(2)
        return original(identity)
    storage.reconcile_stopped = slow
    try:
        with pytest.raises(RuntimeFailure, match="^startup_recovery_pending$"):
            owner.finish_startup(timeout=0.01)
        assert entered.wait(1) and owner.status(value.document_id).running
        with pytest.raises(RuntimeFailure, match="^writer_not_stopped$"):
            owner.finish_startup(timeout=0.01)
        assert calls == [value.identity] and not owner.ready
    finally:
        release.set()
    assert owner._slots[value.document_id].entry.attempt.handle.wait(2).checkpoint_closed
    assert owner.finish_startup() == 0 and owner.ready


def test_close_before_startup_cannot_reopen_runtime(startup):
    owner, _, _, _ = startup
    assert owner.close(timeout=1)
    with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
        owner.finish_startup()


def test_special_native_checkpoint_blocks_startup_without_erasing_it(startup):
    owner, checkpoints, storage, _ = startup
    value = pending(checkpoints, storage)
    class Busy(Exception):
        code = "document_busy"
    original = checkpoints.read
    def busy(document):
        raise Busy("synthetic private task detail")
    checkpoints.read = busy
    with pytest.raises(RuntimeFailure, match="^document_busy$"):
        owner.finish_startup()
    assert not owner.ready and not storage.recovered
    assert checkpoints.pending[value.document_id] == value.identity
    checkpoints.read = original
    assert owner.finish_startup() == 1


def test_close_deadline_includes_startup_catalog_io(startup):
    from concurrent.futures import ThreadPoolExecutor
    owner, _, storage, _ = startup
    entered, release = Event(), Event()
    def slow(**kwargs):
        entered.set()
        assert release.wait(2)
        return ()
    storage.document_ids = slow
    with ThreadPoolExecutor(max_workers=1) as caller:
        starting = caller.submit(owner.finish_startup)
        try:
            assert entered.wait(1)
            assert not owner.close(timeout=0.01)
        finally:
            release.set()
        with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
            starting.result(2)
    assert not owner.ready and owner.close(timeout=1)
