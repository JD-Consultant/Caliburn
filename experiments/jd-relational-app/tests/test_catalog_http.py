"""HTTP validation, preconditions and safe diagnostics with an in-memory port.

Transaction correctness is separately checked against actual PostgreSQL.
"""
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from jd_relational.catalog_api import CatalogServices, create_catalog_app, MERGE_PATCH
from jd_relational.catalog_service import CatalogService, CatalogError
from jd_relational.manual_runtime import ManualRuntime
from jd_relational.storage.service import CatalogRecord, StorageError
from test_manual_runtime import Checkpoints, Storage

ORIGIN = "http://127.0.0.1:3007"


class CatalogStorage(Storage):
    def __init__(self, authority):
        super().__init__(authority)
        self.records, self.creations, self.catalog_calls = {}, {}, []

    def create_document(self, key, title, *, catalog_guard):
        catalog_guard()
        self.catalog_calls.append((key, title))
        if key in self.creations:
            old, doc = self.creations[key]
            if old != title:
                raise StorageError("operation_conflict")
            return doc
        doc, now = str(uuid4()), datetime.now(timezone.utc)
        self.records[doc] = CatalogRecord(doc, title, False, 1, now, now)
        self.creations[key] = (title, doc)
        return doc

    def lookup_creation(self, key, title):
        if key not in self.creations:
            return None
        old, doc = self.creations[key]
        if old != title:
            raise StorageError("operation_conflict")
        return doc

    def catalog_document(self, document_id):
        if document_id not in self.records:
            raise StorageError("document_missing")
        return self.records[document_id]

    def list_catalog(self, *, archived, after, limit):
        return tuple(row for key, row in sorted(self.records.items())
            if (after is None or key > after) and (archived is None or row.archived == archived))[:limit]

    def update_catalog(self, doc, version, *, catalog_guard, title=None, archived=None):
        catalog_guard()
        self.catalog_calls.append((doc, version, title, archived))
        row = self.catalog_document(doc)
        if row.metadata_version != version:
            raise StorageError("metadata_changed")
        value = {"title": title} if title is not None else {"archived": archived}
        row = replace(row, **value, metadata_version=version + 1)
        self.records[doc] = row
        return row


@pytest.fixture
def app():
    runtime = ManualRuntime(Checkpoints(), CatalogStorage)
    service = CatalogService(runtime, str(uuid4()))
    @asynccontextmanager
    async def resources():
        yield CatalogServices(None, None, None, service)
    web = create_catalog_app(resources, allowed_origins=(ORIGIN,))
    try:
        with TestClient(web, base_url="http://127.0.0.1", headers={"Origin": ORIGIN}) as client:
            yield client, service, runtime, web
    finally:
        assert runtime.close(timeout=2)


def create_body(service):
    return {"dataset_id": service.dataset_id, "request_key": str(uuid4()), "title": "我的工作\n繁中😀"}


def test_empty_create_rename_archive_restore_and_original_creation(app):
    client, service, runtime, _ = app
    assert client.get("/api/documents").json() == {"dataset_id": service.dataset_id, "documents": [], "next_after": None}
    body = create_body(service)
    created = client.post("/api/documents", json=body)
    assert created.status_code == 200
    path = f"/api/documents/{created.json()['document_id']}/metadata"
    old = client.get(path)
    assert old.status_code == 200 and old.headers["cache-control"] == "no-store"
    renamed = client.patch(path, json={"title": "新列表名稱"}, headers={
        "If-Match": old.headers["etag"], "Content-Type": MERGE_PATCH})
    assert renamed.status_code == 200 and renamed.json()["title"] == "新列表名稱"
    for archived in [True, False]:
        renamed = client.patch(path, json={"archived": archived}, headers={
            "If-Match": renamed.headers["etag"], "Content-Type": MERGE_PATCH})
        assert renamed.status_code == 200 and renamed.json()["archived"] is archived
        assert len(client.get("/api/documents", params={"archived": str(archived).lower()}).json()["documents"]) == 1
    assert client.post("/api/documents", json=body).json() == created.json()
    assert client.post("/api/document-creations/lookup", json=body).json()["state"] == "found"
    assert len(runtime.storage.records) == 1


@pytest.mark.parametrize("etag", [None, '"old"', '*', 'W/"old"', '"one", "two"'])
def test_missing_stale_or_unconditional_tag_never_reaches_write(app, etag):
    client, service, runtime, _ = app
    doc = service.create(create_body(service))["document_id"]
    calls = list(runtime.storage.catalog_calls)
    headers = {"Content-Type": MERGE_PATCH}
    if etag is not None:
        headers["If-Match"] = etag
    result = client.patch(f"/api/documents/{doc}/metadata", json={"archived": True}, headers=headers)
    assert result.status_code == (428 if etag is None else 412)
    assert runtime.storage.catalog_calls == calls


@pytest.mark.parametrize("body", ['{"archived":true,"archived":false}', '{"archived":1}',
    '{"archived":null}', '{}', '{"archived":true,"title":"x"}',
    '{"metadata_version":7}', '{"title":"\\u0000"}', '{"title":"   "}'])
def test_malformed_metadata_never_reaches_write(app, body):
    client, service, runtime, _ = app
    doc = service.create(create_body(service))["document_id"]
    before = client.get(f"/api/documents/{doc}/metadata")
    calls = list(runtime.storage.catalog_calls)
    result = client.patch(f"/api/documents/{doc}/metadata", content=body, headers={
        "Content-Type": MERGE_PATCH, "If-Match": before.headers["etag"]})
    assert result.status_code == 422
    assert runtime.storage.catalog_calls == calls


def test_duplicate_if_match_and_wrong_media_type_rejected(app):
    client, service, runtime, _ = app
    doc = service.create(create_body(service))["document_id"]
    path = f"/api/documents/{doc}/metadata"
    etag = client.get(path).headers["etag"]
    calls = list(runtime.storage.catalog_calls)
    assert client.patch(path, json={"archived": True}, headers=[
        ("Content-Type", MERGE_PATCH), ("If-Match", etag), ("If-Match", etag)]).status_code == 422
    unsupported = client.patch(path, json={"archived": True}, headers={"If-Match": etag})
    assert unsupported.status_code == 415 and unsupported.headers["accept-patch"] == MERGE_PATCH
    assert runtime.storage.catalog_calls == calls


def test_dataset_change_blocks_old_create_and_etag_before_runtime(app):
    client, service, runtime, _ = app
    body = create_body(service)
    doc = service.create(body)["document_id"]
    path = f"/api/documents/{doc}/metadata"
    etag = client.get(path).headers["etag"]
    calls = list(runtime.storage.catalog_calls)
    service.dataset_id = str(uuid4())  # Simulated replacement by a fresh configured host.
    assert client.post("/api/documents", json=body).json()["code"] == "dataset_changed"
    assert client.post("/api/document-creations/lookup", json=body).json()["code"] == "dataset_changed"
    assert client.patch(path, json={"archived": True}, headers={
        "If-Match": etag, "Content-Type": MERGE_PATCH}).status_code == 412
    assert runtime.storage.catalog_calls == calls


def test_origin_gate_precedes_body_and_cors_exposes_etag(app):
    client, service, runtime, _ = app
    result = client.post("/api/documents", content="not JSON", headers={"Origin": "https://evil.invalid"})
    assert result.status_code == 403 and not runtime.storage.catalog_calls
    preflight = client.options(f"/api/documents/{uuid4()}/metadata", headers={
        "Access-Control-Request-Method": "PATCH", "Access-Control-Request-Headers": "content-type,if-match"})
    assert preflight.status_code == 200
    assert "ETag" in client.get("/api/documents").headers["access-control-expose-headers"]


def test_creation_not_found_does_not_claim_failure_and_changed_intent_rejected(app):
    client, service, runtime, _ = app
    body = create_body(service)
    result = client.post("/api/document-creations/lookup", json=body)
    assert result.status_code == 200 and result.json()["state"] == "not_found" and result.json()["document_id"] is None
    assert not runtime.storage.catalog_calls
    service.create(body)
    body["title"] = "別的建立意圖"
    assert client.post("/api/document-creations/lookup", json=body).status_code == 409


def test_driver_failure_is_safe_and_not_false_save_result(app, monkeypatch, caplog):
    client, service, runtime, _ = app
    def failure(*args, **kwargs):
        raise StorageError("create_unconfirmed")
    monkeypatch.setattr(runtime.storage, "create_document", failure)
    result = client.post("/api/documents", json=create_body(service))
    assert result.status_code == 503 and result.json()["code"] == "write_unconfirmed"
    assert result.json()["next_action"] == "retry_same_creation"
    assert "我的工作" not in caplog.text and "receipt" not in result.json()


def test_openapi_advertises_same_metadata_resource_and_strict_patch_body(app):
    schema = app[3].openapi()
    patch = schema["paths"]["/api/documents/{document_id}/metadata"]["patch"]
    assert MERGE_PATCH in patch["requestBody"]["content"]
    assert {"403", "412", "428", "503"} <= patch["responses"].keys()
    assert "application/problem+json" in patch["responses"]["412"]["content"]
