"""Configured dataset admission over real ASGI, with synthetic service resources."""

from contextlib import asynccontextmanager
from copy import deepcopy
import json
import logging
from uuid import uuid4

import anyio
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
import pytest

from jd_relational.catalog_api import CatalogServices, create_catalog_app
from jd_relational.catalog_service import CatalogService
from jd_relational.configured_api import create_configured_api
from jd_relational.generated.catalog_http import CatalogUuid
from jd_relational.manual_runtime import ManualRuntime
from test_catalog_http import CatalogStorage
from test_manual_api import ManualProbe, NeverRead, PATH, RECOVER_PATH, ORIGIN
from test_manual_http_contract import save, INPUTS
from test_manual_runtime import Checkpoints


DATASET = "12345678-abcd-4abc-8abc-123456789abc"
HEADER = "X-JD-Dataset"
PRIVATE = "SyntheticPrivateDatasetRequest"


@pytest.fixture
def configured():
    runtime, manual = ManualRuntime(Checkpoints(), CatalogStorage), ManualProbe()
    catalog = CatalogService(runtime, DATASET)
    @asynccontextmanager
    async def resources():
        yield CatalogServices(NeverRead(), NeverRead(), manual, catalog)
    app = create_configured_api(resources, allowed_origins=(ORIGIN,), dataset_id=DATASET)
    try:
        with TestClient(app, base_url="http://localhost", headers={"Origin": ORIGIN}) as client:
            yield client, app, manual, runtime.storage, resources
    finally:
        assert runtime.close(timeout=2)


@pytest.mark.parametrize("headers", [[], [(HEADER, str(uuid4()))],
    [(HEADER, DATASET.upper())], [(HEADER, " " + DATASET)],
    [(HEADER, DATASET), (HEADER, DATASET)],
    [(HEADER, DATASET), (HEADER.lower(), str(uuid4()))]])
@pytest.mark.parametrize("path", [PATH, RECOVER_PATH, "/api/documents", "/api/document-creations/lookup"])
def test_missing_wrong_or_duplicate_dataset_precedes_invalid_body(configured, headers, path):
    client, _, manual, storage, _ = configured
    response = client.post(path, content=PRIVATE, headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "dataset_changed" and response.json()["next_action"] == "reread"
    assert response.headers["cache-control"] == "no-store" and response.headers["x-request-id"]
    assert PRIVATE not in response.text
    assert manual.calls == storage.catalog_calls == []


def test_origin_rejection_precedes_epoch_rejection(configured):
    client, _, manual, storage, _ = configured
    response = client.post(RECOVER_PATH, content=PRIVATE, headers={"Origin": "https://wrong.invalid"})
    assert response.status_code == 403 and response.json()["code"] == "origin_not_allowed"
    assert manual.calls == storage.catalog_calls == []


@pytest.mark.parametrize("suffix", ["read", "changes/read"])
def test_post_query_also_checks_dataset_before_reading_invalid_body(configured, suffix):
    client, _, manual, storage, _ = configured
    response = client.post(f"/api/documents/{uuid4()}/jd/{suffix}", content=PRIVATE)
    assert response.status_code == 409 and response.json()["code"] == "dataset_changed"
    assert manual.calls == storage.catalog_calls == []


def test_new_dataset_rejects_old_uuid_only_recovery_without_invoking_original_operation(configured):
    client, _, manual, _, _ = configured
    assert client.post(RECOVER_PATH, json={}, headers={HEADER: str(uuid4())}).status_code == 409
    assert manual.calls == []
    response = client.post(RECOVER_PATH, json={}, headers={HEADER: DATASET})
    assert response.status_code == 200 and response.json()["result"] == manual.result
    assert len(manual.calls) == 1 and manual.calls[0][0] == "recover"


@pytest.mark.parametrize("tool", INPUTS)
def test_same_dataset_passes_all_eight_unchanged_business_commands(configured, tool):
    client, _, manual, _, _ = configured
    envelope = save(tool)
    response = client.post(PATH, json=envelope, headers={HEADER: DATASET})
    assert response.status_code == 200 and response.json() == manual.result
    assert len(manual.calls) == 1 and manual.calls[0][2] == envelope


def test_initial_list_needs_no_dataset_and_cors_preserves_conditional_metadata(configured):
    client, _, _, _, _ = configured
    response = client.get("/api/documents")
    assert response.status_code == 200 and response.json()["dataset_id"] == DATASET
    created = client.post("/api/documents", json={"dataset_id": DATASET,
        "request_key": str(uuid4()), "title": "合成設定文件"}, headers={HEADER: DATASET})
    assert created.status_code == 200
    path = f"/api/documents/{created.json()['document_id']}/metadata"
    metadata = client.get(path)
    assert metadata.status_code == 200 and metadata.headers["ETag"]
    assert "etag" in metadata.headers["Access-Control-Expose-Headers"].lower()
    preflight = client.options(path, headers={"Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": f"Content-Type,If-Match,{HEADER}"})
    assert preflight.status_code == 200
    allowed = preflight.headers["Access-Control-Allow-Headers"].lower()
    assert "if-match" in allowed and HEADER.lower() in allowed
    changed = client.patch(path, json={"archived": True}, headers={HEADER: DATASET,
        "If-Match": metadata.headers["ETag"], "Content-Type": "application/merge-patch+json"})
    assert changed.status_code == 200 and changed.json()["archived"] is True


@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
def test_unknown_unsafe_route_rejects_before_receive_and_never_logs_input(configured, method, caplog):
    _, app, manual, storage, _ = configured
    caplog.set_level(logging.INFO, logger="caliburn.jd.http")
    sent = []
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": "/unknown/" + PRIVATE,
        "raw_path": ("/unknown/" + PRIVATE).encode(), "root_path": "", "query_string": b"",
        "client": ("127.0.0.1", 11001), "server": ("localhost", 80),
        "headers": [(b"host", b"localhost"), (b"origin", ORIGIN.encode()),
                    (b"content-type", b"application/json")]}
    async def receive():
        pytest.fail("Rejected dataset must not read request body")
    async def send(message):
        sent.append(message)
    anyio.run(app, scope, receive, send)
    assert sent[0]["status"] == 409
    body = b"".join(message.get("body", b"") for message in sent)
    assert json.loads(body)["code"] == "dataset_changed"
    assert PRIVATE not in body.decode() + caplog.text
    assert any(record.route == "unmatched" for record in caplog.records
               if record.name == "caliburn.jd.http")
    assert manual.calls == storage.catalog_calls == []


def references(value):
    if isinstance(value, dict):
        return ({value["$ref"]} if "$ref" in value else set()).union(
            *(references(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(references(item) for item in value))
    return set()


def test_openapi_declares_header_and_dataset_problem_without_replacing_prior_conflicts(configured):
    client, app, _, _, resources = configured
    original = create_catalog_app(resources, allowed_origins=(ORIGIN,)).openapi()
    schema = app.openapi()
    rejected = client.post(RECOVER_PATH, json={}).json()
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method not in {"post", "put", "patch", "delete"}:
                assert all(p.get("name") != HEADER for p in operation.get("parameters", []))
                continue
            headers = [p for p in operation["parameters"] if p.get("in") == "header" and p["name"] == HEADER]
            assert len(headers) == 1 and headers[0]["required"] is True
            assert headers[0]["schema"] == CatalogUuid.model_json_schema(mode="validation")
            problem = operation["responses"]["409"]["content"]["application/problem+json"]["schema"]
            assert "#/components/schemas/CatalogProblem" in references(problem)
            before = original["paths"][path][method]["responses"].get("409", {})
            assert references(before) <= references(problem)
            assert Draft202012Validator({**problem, "components": schema["components"]}).is_valid(rejected)
    snapshot = deepcopy(schema)
    assert app.openapi() == snapshot
    assert schema["paths"].keys() == original["paths"].keys()


@pytest.mark.parametrize("dataset", [None, "bad", uuid4(), DATASET.upper(), DATASET + " "])
def test_invalid_server_dataset_fails_before_any_resource_acquisition(dataset):
    @asynccontextmanager
    async def resources():
        pytest.fail("invalid configuration cannot open resources")
        yield
    with pytest.raises(ValueError, match="^invalid_configured_dataset$"):
        create_configured_api(resources, allowed_origins=(ORIGIN,), dataset_id=dataset)
