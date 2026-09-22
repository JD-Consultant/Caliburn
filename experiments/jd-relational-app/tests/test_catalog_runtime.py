"""Catalog admission with real thread ownership; persistence/OS are explicit fakes."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextvars import copy_context
from threading import Event
from uuid import uuid4

import pytest

from jd_relational.manual_runtime import ManualRuntime, RuntimeFailure
from jd_relational.storage.service import StorageError
from test_manual_runtime import Checkpoints, Storage, intent
from test_startup_recovery import PreviousHost


class CatalogStorage(Storage):
    def __init__(self, authority):
        super().__init__(authority)
        self.catalog_calls, self.catalog_commits = [], []
        self.catalog_hook = lambda key, guard: None
        self.created = {}
        self.record = object()

    def document_ids(self, *, after=None, limit=100):
        return ()

    def _catalog(self, key, guard):
        guard()  # Before transaction entry.
        self.catalog_calls.append(key)
        self.catalog_hook(key, guard)
        guard()  # Again after the simulated row locks, before mutation.
        self.catalog_commits.append(key)

    def create_document(self, request_key, title, *, catalog_guard=None):
        self._catalog(("create", request_key), catalog_guard)
        return self.created.setdefault(request_key, str(uuid4()))

    def update_catalog(self, document_id, metadata_version, *, title=None, archived=None,
                       catalog_guard):
        self._catalog(document_id, catalog_guard)
        return self.record


@pytest.fixture
def catalog():
    checkpoints, lease = Checkpoints(), PreviousHost()
    owner = ManualRuntime(checkpoints, CatalogStorage, previous_host=lease)
    yield owner, checkpoints, owner.storage, lease
    owner.storage.release.set()
    assert owner.close(timeout=3)


def invoke(owner, mode, key):
    if mode == "create":
        return owner.create_document(key, "合成文件")
    return owner.update_catalog(key, 1, title="重新命名", archived=False)


def key_for(mode):
    return uuid4() if mode == "create" else str(uuid4())


@pytest.mark.parametrize("mode", ["create", "update"])
def test_catalog_requires_complete_startup_then_returns_storage_result(catalog, mode):
    owner, checkpoints, storage, _ = catalog
    key = key_for(mode)
    with pytest.raises(RuntimeFailure, match="^startup_pending$"):
        invoke(owner, mode, key)
    assert storage.catalog_calls == []
    owner.finish_startup()
    result = invoke(owner, mode, key)
    if mode == "create":
        assert result == storage.created[key]
    else:
        assert result is storage.record
    assert not checkpoints.pending and checkpoints.closed == []
    assert storage.executed == storage.recovered == []


@pytest.mark.parametrize("mode", ["create", "update"])
def test_invalid_host_before_admission_starts_no_catalog_io(catalog, mode):
    owner, _, storage, lease = catalog
    owner.finish_startup()
    lease.valid = False
    with pytest.raises(RuntimeFailure, match="^host_not_valid$"):
        invoke(owner, mode, key_for(mode))
    assert storage.catalog_calls == []


@pytest.mark.parametrize("mode", ["create", "update"])
def test_host_is_rechecked_after_catalog_row_locks(catalog, mode):
    owner, _, storage, lease = catalog
    owner.finish_startup()
    storage.catalog_hook = lambda key, guard: setattr(lease, "valid", False)
    with pytest.raises(RuntimeFailure, match="^host_not_valid$"):
        invoke(owner, mode, key_for(mode))
    assert len(storage.catalog_calls) == 1 and storage.catalog_commits == []


@pytest.mark.parametrize("failure", ["pending", "busy", "unavailable"])
def test_metadata_never_bypasses_native_pending_or_failed_saver(catalog, failure):
    owner, checkpoints, storage, _ = catalog
    owner.finish_startup()
    value = intent()
    if failure == "pending":
        checkpoints.pending[value.document_id] = value.identity
    else:
        def broken(_):
            raise RuntimeFailure("document_busy" if failure == "busy" else "private saver contents")
        checkpoints.read = broken
    expected = "checkpoint_unavailable" if failure == "unavailable" else "document_busy"
    with pytest.raises(RuntimeFailure, match=f"^{expected}$") as failed:
        owner.update_catalog(value.document_id, 1, archived=True)
    if failure != "pending":
        assert failed.value.__suppress_context__
    assert not storage.catalog_calls and storage.recovered == []


def test_metadata_keeps_local_unsettled_cleanup_gate_even_if_pending_disappeared(catalog):
    owner, checkpoints, storage, _ = catalog
    owner.finish_startup()
    checkpoints.close_error = True
    value = intent()
    assert not owner.submit(value).wait(2).checkpoint_closed
    checkpoints.pending.clear()
    with pytest.raises(RuntimeFailure, match="^document_busy$"):
        owner.update_catalog(value.document_id, 1, archived=True)
    assert storage.catalog_calls == [] and storage.recovered == []


@pytest.mark.parametrize("second_kind", ["update", "submit"])
def test_same_document_catalog_holds_slot_until_storage_call_exits(catalog, second_kind):
    owner, _, storage, _ = catalog
    owner.finish_startup()
    document, entered, release, trying = str(uuid4()), Event(), Event(), Event()
    def slow(key, guard):
        if not entered.is_set():
            entered.set()
            assert release.wait(3)
    storage.catalog_hook = slow
    def second():
        trying.set()
        return (owner.update_catalog(document, 2, archived=True) if second_kind == "update"
                else owner.submit(intent(document)))
    with ThreadPoolExecutor(max_workers=2) as callers:
        first = callers.submit(owner.update_catalog, document, 1, title="第一個")
        try:
            assert entered.wait(1)
            following = callers.submit(second)
            assert trying.wait(1)
            with pytest.raises(FutureTimeout):
                following.result(0.03)
            assert storage.catalog_commits == [] and storage.executed == []
        finally:
            release.set()
        assert first.result(2) is storage.record
        result = following.result(2)
        if second_kind == "submit":
            assert result.wait(2).checkpoint_closed


@pytest.mark.parametrize("mode,same_key", [("update", False), ("create", False), ("create", True)])
def test_catalog_keys_are_independent_but_creation_retry_uses_same_slot(catalog, mode, same_key):
    owner, _, storage, _ = catalog
    owner.finish_startup()
    first_key = key_for(mode)
    second_key = first_key if same_key else key_for(mode)
    entered, release = Event(), Event()
    actual_first = ("create", first_key) if mode == "create" else first_key
    def slow(key, guard):
        if key == actual_first and not entered.is_set():
            entered.set()
            assert release.wait(3)
    storage.catalog_hook = slow
    with ThreadPoolExecutor(max_workers=2) as callers:
        first = callers.submit(invoke, owner, mode, first_key)
        try:
            assert entered.wait(1)
            second = callers.submit(invoke, owner, mode, second_key)
            if same_key:
                with pytest.raises(FutureTimeout):
                    second.result(0.03)
            else:
                assert second.result(1) is not None
        finally:
            release.set()
        first_result, second_result = first.result(2), second.result(2)
        if same_key:
            assert first_result == second_result


@pytest.mark.parametrize("mode", ["create", "update"])
def test_close_timeout_retains_catalog_io_and_already_admitted_guard(catalog, mode):
    owner, _, storage, _ = catalog
    owner.finish_startup()
    entered, release = Event(), Event()
    def slow(key, guard):
        entered.set()
        assert release.wait(3)
    storage.catalog_hook = slow
    with ThreadPoolExecutor(max_workers=1) as callers:
        original = callers.submit(invoke, owner, mode, key_for(mode))
        try:
            assert entered.wait(1)
            assert not owner.close(timeout=0.02)
            with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
                invoke(owner, mode, key_for(mode))
        finally:
            release.set()
        assert original.result(2) is not None
    assert len(storage.catalog_commits) == 1 and owner.close(timeout=1)


def test_copied_context_cannot_borrow_catalog_authority_in_other_thread_or_after_call(catalog):
    owner, _, storage, _ = catalog
    owner.finish_startup()
    document, captured = str(uuid4()), []
    def inspect(key, guard):
        captured.append(copy_context())
        with pytest.raises(RuntimeFailure, match="^writer_not_valid$"):
            owner.require_catalog(str(uuid4()))
        with ThreadPoolExecutor(max_workers=1) as foreign:
            attempt = foreign.submit(copy_context().run, owner.require_catalog, key)
            with pytest.raises(RuntimeFailure, match="^writer_not_valid$"):
                attempt.result(1)
    storage.catalog_hook = inspect
    owner.update_catalog(document, 1, archived=True)
    with pytest.raises(RuntimeFailure, match="^writer_not_valid$"):
        captured[0].run(owner.require_catalog, document)
    with pytest.raises(RuntimeFailure, match="^writer_not_valid$"):
        owner.require_catalog(document)


def test_catalog_context_is_revoked_after_storage_failure_without_replaying(catalog):
    owner, _, storage, _ = catalog
    owner.finish_startup()
    document, captured = str(uuid4()), []
    def failed(key, guard):
        captured.append(copy_context())
        raise StorageError("metadata_conflict")
    storage.catalog_hook = failed
    with pytest.raises(StorageError, match="^metadata_conflict$"):
        owner.update_catalog(document, 1, archived=True)
    with pytest.raises(RuntimeFailure, match="^writer_not_valid$"):
        captured[0].run(owner.require_catalog, document)
    assert len(storage.catalog_calls) == 1 and storage.catalog_commits == []


@pytest.mark.parametrize("phase", ["storage", "saver"])
def test_reentrant_close_cannot_claim_the_active_catalog_call_drained(catalog, phase):
    owner, checkpoints, storage, _ = catalog
    owner.finish_startup()
    def closing(*_):
        assert not owner.close(timeout=0), "active call was not drained"
    if phase == "storage":
        storage.catalog_hook = closing
        owner.create_document(uuid4(), "合成文件")
    else:
        checkpoints.read = closing
        owner.update_catalog(str(uuid4()), 1, title="合成文件")
    assert owner.close(timeout=1)


@pytest.mark.parametrize("document,version,fields", [
    ("bad", 1, {"title": "a"}), ("AAAAAAAA-AAAA-4AAA-AAAA-AAAAAAAAAAAA", 1, {"title": "a"}),
    (str(uuid4()), True, {"title": "a"}), (str(uuid4()), 0, {"title": "a"}),
    (str(uuid4()), 1, {"archived": 0}), (str(uuid4()), 1, {"title": 42}),
    (str(uuid4()), 1, {}),
])
def test_bad_catalog_inputs_never_acquire_saver_or_storage_authority(catalog, document, version, fields):
    owner, _, storage, _ = catalog
    owner.finish_startup()
    with pytest.raises(RuntimeFailure, match="^invalid_input$"):
        owner.update_catalog(document, version, **fields)
    assert storage.catalog_calls == []


@pytest.mark.parametrize("request_key,title", [("not-a-uuid", "a"), (str(uuid4()), "a"), (uuid4(), None)])
def test_creation_requires_uuid_request_identity_and_text(catalog, request_key, title):
    owner, _, storage, _ = catalog
    owner.finish_startup()
    with pytest.raises(RuntimeFailure, match="^invalid_input$"):
        owner.create_document(request_key, title)
    assert storage.catalog_calls == []
