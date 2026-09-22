"""Atomic owner admission/read drain with real threads; zero DB/provider."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from jd_relational.manual_runtime import ManualRuntime, RuntimeFailure
from jd_relational.storage.service import StorageError
from test_foreground_runtime import ForegroundStorage, run_identity, ai_intent
from test_manual_runtime import Checkpoints, intent
from test_startup_recovery import PreviousHost


class AdmissionStorage(ForegroundStorage):
    def __init__(self, authority):
        super().__init__(authority)
        self.head = uuid4()
        self.archived = False
        self.head_calls = []
        self.head_hook = lambda: None

    def read_current(self, document):
        self.head_calls.append(document)
        self.head_hook()
        return SimpleNamespace(document_id=document, revision_id=self.head, archived=self.archived)


@pytest.fixture
def admission():
    checkpoint = Checkpoints()
    owner = ManualRuntime(checkpoint, AdmissionStorage, max_workers=2)
    releases = []
    yield owner, checkpoint, owner.storage, releases
    for event in releases:
        event.set()
    owner.storage.release.set()
    for slot in tuple(owner._slots.values()):
        current = slot.foreground
        if current and not current.closed:
            current.handle.wait(3)
            if slot.entry is not None:
                owner.recover_foreground(current.permit, slot.entry.identity, lambda _: None, timeout=3)
            owner.finish_foreground(current.permit, lambda: None)
    assert owner.close(timeout=3)


def admit(owner, run, work=lambda _: None, lookup=lambda: None, expected=None):
    return owner.admit_foreground(run, work, expected_revision=expected or owner.storage.head,
                                 lookup_original=lookup)


def waiting(admission, run=None):
    owner, _, _, releases = admission
    started, release = Event(), Event()
    releases.append(release)
    def work(_):
        started.set()
        assert release.wait(3)
    result = admit(owner, run or run_identity(), work)
    assert result.original is None and started.wait(1)
    return result.handle, release


@pytest.mark.parametrize("blocked", ["stale", "archived", "manual", "live_ai"])
def test_original_result_precedes_every_new_admission_precondition(admission, blocked):
    owner, checkpoint, storage, _ = admission
    run = run_identity()
    if blocked == "archived": storage.archived = True
    if blocked == "manual": checkpoint.pending[run.document_id] = intent(run.document_id).identity
    if blocked == "live_ai": waiting(admission, run_identity(run.document_id))
    storage.head_calls.clear()
    original = object()
    result = admit(owner, run, lambda _: pytest.fail("must not run"), lambda: original, uuid4())
    assert result.original is original and result.handle is None
    assert storage.head_calls == [] and not storage.executed
    checkpoint.pending.clear()


def test_same_live_handle_still_requires_coordinator_lookup_before_owner_fallback(admission):
    owner, _, storage, _ = admission
    run = run_identity()
    original_revision = storage.head
    handle, _ = waiting(admission, run)
    storage.head = uuid4()
    lookups = []
    def lookup(): lookups.append("lookup")
    result = admit(owner, run, lookup=lookup, expected=original_revision)
    assert result.handle is handle and result.original is None
    with pytest.raises(RuntimeFailure, match="^operation_conflict$"):
        admit(owner, replace(run, request_digest="b" * 64), lookup=lookup)
    assert len(storage.head_calls) == 1 and lookups == ["lookup", "lookup"]


def test_original_format_failure_precedes_same_run_owner_identity_conflict(admission):
    owner, _, _, _ = admission
    run = run_identity()
    waiting(admission, run)
    def old_format(): raise RuntimeFailure("original_run_lookup_required")
    with pytest.raises(RuntimeFailure, match="^original_run_lookup_required$"):
        admit(owner, replace(run, request_digest="b" * 64), lookup=old_format)


@pytest.mark.parametrize("failure", ["stale", "archived", "missing", "head_failure", "pending", "lookup_incomplete"])
def test_new_admission_rejections_create_no_foreground_or_work(admission, failure):
    owner, checkpoint, storage, _ = admission
    run = run_identity()
    expected, lookup, code = storage.head, lambda: None, "stale_view"
    if failure == "stale": expected = uuid4()
    elif failure == "archived": storage.archived, code = True, "document_archived"
    elif failure in {"missing", "head_failure"}:
        def broken(): raise StorageError("document_missing" if failure == "missing" else "SyntheticPrivateHead")
        storage.head_hook = broken
        code = "document_missing" if failure == "missing" else "read_failed"
    elif failure == "pending":
        checkpoint.pending[run.document_id] = intent(run.document_id).identity
        code = "document_busy"
    elif failure == "lookup_incomplete":
        def incomplete(): raise RuntimeFailure("original_run_lookup_required")
        lookup, code = incomplete, "original_run_lookup_required"
    with pytest.raises(RuntimeFailure, match=f"^{code}$"):
        admit(owner, run, lambda _: pytest.fail("rejected"), lookup, expected)
    slot = owner._slots[run.document_id]
    assert slot.foreground is None and slot.start_token is None
    assert not storage.executed and not checkpoint.closed
    checkpoint.pending.clear()


def test_head_check_to_future_attachment_has_no_same_document_writer_gap(admission):
    owner, _, storage, releases = admission
    run = run_identity()
    head_entered, head_release, work_entered, work_release = (Event() for _ in range(4))
    releases.extend([head_release, work_release])
    def head():
        head_entered.set()
        assert head_release.wait(3)
    def work(_):
        work_entered.set()
        assert work_release.wait(3)
    storage.head_hook = head
    with ThreadPoolExecutor(max_workers=2) as pool:
        starting = pool.submit(admit, owner, run, work)
        assert head_entered.wait(1)
        metadata = pool.submit(owner.update_catalog, run.document_id, 1, archived=True)
        assert not metadata.done()
        # A different document is not subject to this admission I/O lock.
        assert owner.update_catalog(str(uuid4()), 1, title="另一份") is storage.record
        head_release.set()
        result = starting.result(2)
        assert work_entered.wait(1)
        with pytest.raises(RuntimeFailure, match="^document_busy$"):
            metadata.result(2)
    assert result.handle and len(storage.catalog_calls) == 1


@pytest.mark.parametrize("stage", ["lookup", "head"])
def test_reentrant_close_cannot_close_resources_or_dispatch_after_admission_io(admission, stage):
    owner, _, storage, _ = admission
    def close_inside():
        assert owner.close(timeout=0) is False
    lookup = lambda: None
    if stage == "lookup": lookup = close_inside
    else: storage.head_hook = close_inside
    with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
        admit(owner, run_identity(), lambda _: pytest.fail("closed"), lookup)
    assert all(slot.foreground is None and slot.start_token is None for slot in owner._slots.values())


def test_executor_submit_failure_retains_known_not_started_and_safe_closure(admission, monkeypatch):
    owner, _, _, _ = admission
    def failed(*args, **kwargs): raise RuntimeError("synthetic executor closed")
    monkeypatch.setattr(owner._foreground_pool, "submit", failed)
    result = admit(owner, run_identity())
    assert result.handle.wait(0).error == "foreground_not_started"
    assert result.handle._entry.future is None
    owner.finish_foreground(result.handle.permit, lambda: None)


@pytest.mark.parametrize("gate", ["ai", "manual", "catalog"])
def test_public_read_observes_live_work_without_write_permission(admission, gate):
    owner, checkpoint, _, _ = admission
    run = run_identity()
    if gate == "ai": waiting(admission, run)
    elif gate == "manual": checkpoint.pending[run.document_id] = intent(run.document_id).identity
    else: owner._slot(run.document_id).catalog_token = object()
    def read():
        with pytest.raises(RuntimeFailure, match="^writer_not_valid$"):
            owner.require_bound(intent(run.document_id))
        return "saved original material"
    try:
        assert owner.inspect_document(run.document_id, read) == "saved original material"
    finally:
        checkpoint.pending.clear()
        owner._slots[run.document_id].catalog_token = None


def test_read_io_does_not_hold_same_document_slot_or_other_documents(admission):
    owner, _, storage, releases = admission
    entered, release = Event(), Event()
    releases.append(release)
    document = str(uuid4())
    def read():
        entered.set()
        assert release.wait(3)
        return "material"
    with ThreadPoolExecutor(max_workers=1) as pool:
        observed = pool.submit(owner.inspect_document, document, read)
        assert entered.wait(1)
        assert owner.update_catalog(document, 1, title="同文件") is storage.record
        assert owner.submit(intent()).wait(1).observation.confirmed
        release.set()
        assert observed.result(1) == "material"


def test_live_ai_can_save_while_same_document_query_is_waiting(admission):
    owner, _, storage, releases = admission
    run = run_identity()
    read_entered, read_release, write_now, written, work_release = (Event() for _ in range(5))
    releases.extend([read_release, write_now, work_release])
    def work(permit):
        assert write_now.wait(3)
        result = owner.execute_foreground(permit, ai_intent(run), lambda _: None).wait(2)
        assert result.observation.confirmed
        written.set()
        assert work_release.wait(3)
    admit(owner, run, work)
    def read():
        read_entered.set()
        assert read_release.wait(3)
    with ThreadPoolExecutor(max_workers=1) as pool:
        query = pool.submit(owner.inspect_document, run.document_id, read)
        assert read_entered.wait(1)
        write_now.set()
        assert written.wait(1) and len(storage.executed) == 1
        read_release.set()
        query.result(1)


def test_close_waits_for_real_read_completion_and_refuses_late_reads(admission):
    owner, _, _, releases = admission
    entered, release = Event(), Event()
    releases.append(release)
    def read():
        entered.set()
        assert release.wait(3)
        return "preserved"
    with ThreadPoolExecutor(max_workers=2) as pool:
        query = pool.submit(owner.inspect_document, str(uuid4()), read)
        assert entered.wait(1)
        assert owner.close(timeout=0.01) is False
        with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
            owner.inspect_document(str(uuid4()), lambda: pytest.fail("late"))
        closing = pool.submit(owner.close, timeout=2)
        assert not closing.done()
        release.set()
        assert query.result(1) == "preserved" and closing.result(1) is True


@pytest.mark.parametrize("error", [None, ValueError, KeyboardInterrupt])
def test_read_finally_drains_reentrant_close_and_all_callback_exits(admission, error):
    owner, _, _, _ = admission
    def read():
        assert owner.close(timeout=0) is False
        if error: raise error("synthetic")
        return "done"
    if error:
        with pytest.raises(error): owner.inspect_document(str(uuid4()), read)
    else:
        assert owner.inspect_document(str(uuid4()), read) == "done"
    assert owner.close(timeout=0) is True


@pytest.mark.parametrize("mode", ["startup", "host", "invalid_doc", "invalid_revision"])
def test_invalid_preconditions_start_no_read_callback_or_new_work(mode):
    lease = PreviousHost()
    owner = ManualRuntime(Checkpoints(), AdmissionStorage, previous_host=lease)
    try:
        if mode != "startup": owner.finish_startup()
        if mode == "host": lease.valid = False
        code = {"startup": "startup_pending", "host": "host_not_valid",
                "invalid_doc": "invalid_input", "invalid_revision": "invalid_input"}[mode]
        if mode == "invalid_revision":
            with pytest.raises(RuntimeFailure, match=f"^{code}$"):
                owner.admit_foreground(run_identity(), lambda _: None, expected_revision="not-uuid", lookup_original=lambda: None)
        else:
            with pytest.raises(RuntimeFailure, match=f"^{code}$"):
                owner.inspect_document("bad" if mode == "invalid_doc" else str(uuid4()),
                                       lambda: pytest.fail("not admitted"))
    finally:
        lease.valid = True
        assert owner.close(timeout=2)


def test_idle_status_read_participates_in_owner_drain(admission):
    owner, checkpoint, _, _ = admission
    def read(_):
        assert owner.close(timeout=0) is False
        return None
    checkpoint.read = read
    assert owner.status(str(uuid4())).write_blocked is False
    assert owner.close(timeout=0) is True


def test_host_loss_during_head_read_cannot_publish_a_foreground():
    lease = PreviousHost()
    owner = ManualRuntime(Checkpoints(), AdmissionStorage, previous_host=lease)
    owner.finish_startup()
    run = run_identity()
    owner.storage.head_hook = lambda: setattr(lease, "valid", False)
    try:
        with pytest.raises(RuntimeFailure, match="^host_not_valid$"):
            admit(owner, run, lambda _: pytest.fail("lost lease"))
        slot = owner._slots[run.document_id]
        assert slot.foreground is None and slot.start_token is None
    finally:
        lease.valid = True
        assert owner.close(timeout=1)


def test_lookup_interrupt_does_not_leave_a_false_live_foreground(admission):
    owner, _, storage, _ = admission
    run = run_identity()
    def interrupted(): raise KeyboardInterrupt("synthetic")
    with pytest.raises(KeyboardInterrupt):
        admit(owner, run, lookup=interrupted)
    slot = owner._slots[run.document_id]
    assert slot.foreground is None and slot.start_token is None and storage.head_calls == []


def test_start_preparation_status_is_blocked_without_rereading_saver(admission):
    owner, checkpoint, storage, _ = admission
    run = run_identity()
    def head():
        def unexpected(_): pytest.fail("start token already proves this gate is busy")
        checkpoint.read = unexpected
        state = owner.status(run.document_id)
        assert state.write_blocked and state.identity is None
    storage.head_hook = head
    assert admit(owner, run).handle
    checkpoint.read = lambda _: None


def test_status_after_close_or_before_startup_never_uses_saver():
    checkpoint, lease = Checkpoints(), PreviousHost()
    owner = ManualRuntime(checkpoint, AdmissionStorage, previous_host=lease)
    checkpoint.read = lambda _: pytest.fail("diagnostic must not open resources")
    assert owner.status(str(uuid4())).error == "startup_pending"
    assert owner.close(timeout=0)
    assert owner.status(str(uuid4())).error == "runtime_closed"
