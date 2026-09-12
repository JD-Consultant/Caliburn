"""Actual catalog transactions over isolated PostgreSQL; synthetic authority."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os
from uuid import uuid4

import pytest

from test_storage_postgres import engine
from test_storage_service import store, current, change
from jd_relational.storage.service import StorageError

pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


def allow():
    pass  # This file tests SQL; actual ownership is tested in catalog runtime.


def test_catalog_changes_leave_jd_and_history_intact(store, current):
    latest, _, _ = change(store, current, "jd_set_text", {
        "target_field_ref": "profile.job_title", "text": "實際職稱", "basis_refs": []})
    row = store.catalog_document(current.document_id)
    renamed = store.update_catalog(row.document_id, row.metadata_version,
        title="列表上的名稱", catalog_guard=allow)
    assert renamed.title == "列表上的名稱" and renamed.metadata_version == 2
    archived = store.update_catalog(row.document_id, 2, archived=True, catalog_guard=allow)
    assert archived.archived and archived.metadata_version == 3
    restored = store.update_catalog(row.document_id, 3, archived=False, catalog_guard=allow)
    assert not restored.archived and restored.metadata_version == 4
    loaded = store.read_current(row.document_id)
    assert loaded.snapshot == latest.snapshot and loaded.revision_id == latest.revision_id
    assert loaded.domain["profile"]["job_title"] == "實際職稱"


def test_stale_update_cannot_revert_later_change_even_if_value_matches(store, current):
    doc = current.document_id
    store.update_catalog(doc, 1, title="新名稱", catalog_guard=allow)
    for title in (current.title, "新名稱"):
        with pytest.raises(StorageError, match="^metadata_changed$"):
            store.update_catalog(doc, 1, title=title, catalog_guard=allow)
    assert store.catalog_document(doc).title == "新名稱"


def test_concurrent_same_version_has_only_one_winner(store, current):
    def update(title):
        try:
            return store.update_catalog(current.document_id, 1, title=title, catalog_guard=allow).title
        except StorageError as error:
            return error.code
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(update, ["一", "二"]))
    assert results.count("metadata_changed") == 1
    assert store.catalog_document(current.document_id).metadata_version == 2


def test_repeated_create_after_rename_archive_retains_original_identity(store):
    key = uuid4()
    doc = store.create_document(key, "原名稱", catalog_guard=allow)
    store.update_catalog(doc, 1, title="新名稱", catalog_guard=allow)
    store.update_catalog(doc, 2, archived=True, catalog_guard=allow)
    assert store.create_document(key, "原名稱", catalog_guard=allow) == doc
    assert store.lookup_creation(key, "原名稱") == doc
    with pytest.raises(StorageError, match="^operation_conflict$"):
        store.create_document(key, "改過的意圖", catalog_guard=allow)
    assert store.catalog_document(doc).archived


def test_no_change_preserves_metadata_version_and_updated_at(store, current):
    original = store.catalog_document(current.document_id)
    assert store.update_catalog(original.document_id, 1, title=original.title, catalog_guard=allow) == original
    assert store.update_catalog(original.document_id, 1, archived=False, catalog_guard=allow) == original


def test_failed_guard_after_lock_rolls_back_and_no_false_success(store, current):
    calls = []
    def guard():
        calls.append(True)
        if len(calls) == 2:
            raise ValueError("private host failure")
    with pytest.raises(StorageError, match="^catalog_unconfirmed$"):
        store.update_catalog(current.document_id, 1, archived=True, catalog_guard=guard)
    assert len(calls) == 2 and not store.catalog_document(current.document_id).archived


def test_commit_reply_lost_requires_read_not_rollback_or_blind_retry(store, current, monkeypatch):
    real = store._connection
    @contextmanager
    def lost(*, readonly=False):
        with real(readonly=readonly) as conn:
            yield conn
        if not readonly:
            raise RuntimeError("synthetic lost commit acknowledgement")
    monkeypatch.setattr(store, "_connection", lost)
    with pytest.raises(StorageError, match="^catalog_unconfirmed$"):
        store.update_catalog(current.document_id, 1, archived=True, catalog_guard=allow)
    row = store.catalog_document(current.document_id)
    assert row.archived and row.metadata_version == 2
    with pytest.raises(StorageError, match="^metadata_changed$"):
        store.update_catalog(current.document_id, 1, archived=True, catalog_guard=allow)


def test_list_pages_filter_and_preserve_duplicate_titles_without_loading_content(store):
    docs = sorted(store.create_document(uuid4(), "同名合成文件") for _ in range(3))
    store.update_catalog(docs[1], 1, archived=True, catalog_guard=allow)
    def collect(archived):
        result, after = [], docs[0]
        while True:
            page = store.list_catalog(archived=archived, after=after, limit=100)
            result.extend(page)
            if len(page) < 100 or page[-1].document_id > docs[-1]:
                return result
            after = page[-1].document_id
    active, archive = collect(False), collect(True)
    assert docs[1] not in {row.document_id for row in active}
    assert docs[1] in {row.document_id for row in archive}
    first = store.list_catalog(archived=None, after=docs[0], limit=1)
    assert len(first) == 1 and first[0].document_id > docs[0]


@pytest.mark.parametrize("arguments", [dict(), {"title": "a", "archived": True},
    {"title": " "}, {"title": "\x00"}, {"archived": 1}])
def test_catalog_invalid_changes_never_touch_metadata(store, current, arguments):
    with pytest.raises(StorageError, match="^invalid_input$"):
        store.update_catalog(current.document_id, 1, catalog_guard=allow, **arguments)
    assert store.catalog_document(current.document_id).metadata_version == 1
