"""In-process real ASGI routing, generated DTOs and native middleware."""

from contextlib import asynccontextmanager
import json
import logging
from threading import get_ident
import traceback
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from jd_relational.query_api import QueryServices, create_query_app
from jd_relational.reads import ReadError
from jd_relational.generated.reads import ReadInput
from test_reads import reader, codec, complete_domain

DOCUMENT = str(uuid4())
PATH = f"/api/documents/{DOCUMENT}/jd/read"
BODY = {"view": "current", "target_ref": None, "cursor": None}


class NoChanges:
    def read(self, *args):
        raise AssertionError("A current read must not call change reader")


class NoCurrent:
    def read(self, *args):
        raise AssertionError("A change or preview read must not call the current reader")


def app_for(reads, changes=None, observed=None):
    @asynccontextmanager
    async def resources():
        if observed is not None:
            observed.append("startup")
        try:
            yield QueryServices(reads, changes or NoChanges())
        finally:
            if observed is not None:
                observed.append("shutdown")

    return create_query_app(resources, allowed_origins=("http://localhost:3000",))


@pytest.fixture
def app(codec):
    value = complete_domain()
    value["document_id"] = DOCUMENT
    reads, _ = reader(value, codec, 12000)
    return app_for(reads)


def test_generated_current_read_and_lifespan(codec):
    observed = []
    value = complete_domain()
    value["document_id"] = DOCUMENT
    reads, _ = reader(value, codec)
    with TestClient(app_for(reads, observed=observed), base_url="http://127.0.0.1") as client:
        result = client.post(PATH, json=BODY)
        assert result.status_code == 200
        assert result.json()["view"] == "current"
        assert result.headers["cache-control"] == "no-store"
        assert result.headers["x-request-id"]
        assert len(result.content) <= 12000
        assert observed == ["startup"]
    assert observed == ["startup", "shutdown"]


@pytest.mark.parametrize(
    "content,headers",
    [
        ('{"view":"current","target_ref":null}', {"content-type": "application/json"}),
        (
            '{"view":"current","view":"current","target_ref":null,"cursor":null}',
            {"content-type": "application/json"},
        ),
        ('{"private":"raw-interview-SENTINEL"', {"content-type": "application/json"}),
        (json.dumps(BODY), {"content-type": "text/plain"}),
        (json.dumps(BODY), {}),
        (
            json.dumps({**BODY, "extra": "raw-interview-SENTINEL"}),
            {"content-type": "application/json"},
        ),
    ],
)
def test_input_failures_are_fixed_and_private(app, content, headers, caplog):
    with TestClient(app, base_url="http://127.0.0.1") as client:
        with caplog.at_level(logging.DEBUG):
            result = client.post(PATH, content=content, headers=headers)
    assert result.status_code == 422
    assert result.headers["content-type"].startswith("application/problem+json")
    assert result.json()["jd_read_error"]["code"] == "invalid_input"
    assert "raw-interview-SENTINEL" not in result.text + caplog.text
    assert "jd_result" not in result.json()


@pytest.mark.parametrize(
    "code,status",
    [("invalid_ref", 422), ("stale_view", 409), ("target_missing", 404), ("read_failed", 500)],
)
def test_read_errors_keep_correct_http_semantics(code, status):
    class Broken:
        def read(self, *args):
            raise ReadError(code)

    with TestClient(app_for(Broken()), base_url="http://127.0.0.1") as client:
        result = client.post(PATH, json=BODY, headers={"origin": "http://localhost:3000"})
    assert result.status_code == status
    assert result.json()["jd_read_error"]["code"] == code
    assert result.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_internal_failure_is_not_reraised_or_logged_with_private_data(caplog):
    class Broken:
        def read(self, *args):
            raise RuntimeError("raw-interview-SENTINEL")

    # TestClient's default raise_server_exceptions=True exposes any reraised cause.
    with TestClient(app_for(Broken()), base_url="http://127.0.0.1") as client:
        with caplog.at_level(logging.INFO, logger="caliburn.jd.http"):
            result = client.post(PATH, json=BODY)
    assert result.status_code == 500
    assert result.json()["jd_read_error"]["code"] == "read_failed"
    assert "raw-interview-SENTINEL" not in result.text + caplog.text
    records = [r for r in caplog.records if r.name == "caliburn.jd.http"]
    assert records and all(r.exc_info is None for r in records)


def test_invalid_response_is_internal_failure():
    class Broken:
        def read(self, *args):
            return {"records": ["raw-interview-SENTINEL"]}

    with TestClient(app_for(Broken()), base_url="http://127.0.0.1") as client:
        result = client.post(PATH, json=BODY)
    assert result.status_code == 500 and "SENTINEL" not in result.text


def test_native_body_limit_applies_to_chunked_and_known_length(app):
    with TestClient(app, base_url="http://127.0.0.1") as client:
        for content in ("x" * 17000, iter([b"x" * 9000, b"x" * 9000])):
            result = client.post(
                PATH, content=content, headers={"content-type": "application/json"}
            )
            assert result.status_code == 413
            assert result.headers["cache-control"] == "no-store"
            assert len(result.content) < 200


def test_host_and_cors_are_explicit_and_no_mutation_routes(app):
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.post(PATH, json=BODY, headers={"host": "evil.example"}).status_code == 400
        trusted = client.post(PATH, json=BODY, headers={"origin": "http://localhost:3000"})
        assert trusted.headers["access-control-allow-origin"] == "http://localhost:3000"
        untrusted = client.post(PATH, json=BODY, headers={"origin": "https://evil.example"})
        assert "access-control-allow-origin" not in untrusted.headers
        assert client.post(f"/api/documents/{DOCUMENT}/jd/edit", json={}).status_code == 404
        assert client.post("/api/documents", json={}).status_code == 404


def test_openapi_uses_generated_read_types(app):
    schema = app.openapi()
    operation = schema["paths"]["/api/documents/{document_id}/jd/read"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ReadInput"
    )
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ReadPage"
    )
    assert schema["components"]["schemas"]["ReadInput"] == ReadInput.model_json_schema()
    for status in ("404", "409", "422", "500"):
        content = operation["responses"][status]["content"]
        assert set(content) == {"application/problem+json"}
        assert content["application/problem+json"]["schema"]["$ref"].endswith("/QueryProblem")


def test_database_reader_runs_outside_the_asgi_loop(codec):
    threads = {}
    value = complete_domain()
    value["document_id"] = DOCUMENT
    reads, _ = reader(value, codec)

    class ObservedReader:
        def read(self, *args):
            threads["reader"] = get_ident()
            return reads.read(*args)

    @asynccontextmanager
    async def resources():
        threads["loop"] = get_ident()
        yield QueryServices(ObservedReader(), NoChanges())

    with TestClient(create_query_app(resources), base_url="http://127.0.0.1") as client:
        assert client.post(PATH, json=BODY).status_code == 200
    assert threads["reader"] != threads["loop"]


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://evil.example",
        "http://localhost/path",
        "http://user:password@localhost",
        "http://localhost:*",
        "null",
    ],
)
def test_host_rejects_nonlocal_or_ambiguous_origin_configuration(origin):
    @asynccontextmanager
    async def resources():
        raise AssertionError("invalid configuration must not acquire resources")
        yield

    with pytest.raises(ValueError, match="explicit_local_origins_required"):
        create_query_app(resources, allowed_origins=(origin,))


@pytest.mark.parametrize("phase", ["startup", "shutdown"])
def test_resource_failure_keeps_native_cleanup_without_private_cause(phase, caplog):
    private = "SyntheticPrivateFactory" + "Sentinel"
    observed = []

    @asynccontextmanager
    async def resources():
        try:
            if phase == "startup":
                raise RuntimeError(private)
            yield QueryServices(NoChanges(), NoChanges())
            raise RuntimeError(private)
        finally:
            observed.append("cleanup")

    app = create_query_app(resources)
    with pytest.raises(RuntimeError, match=f"jd_query_{phase}_failed") as captured:
        with TestClient(app, base_url="http://127.0.0.1"):
            assert phase == "shutdown"
    rendered = "".join(traceback.format_exception(captured.value))
    assert private not in rendered + caplog.text
    assert observed == ["cleanup"]
    assert not hasattr(app.state, "jd_queries")


def test_diagnostic_sink_failure_does_not_replace_success(app, monkeypatch):
    def broken_sink(*args, **kwargs):
        raise RuntimeError("private-log-sink-error")

    monkeypatch.setattr("jd_relational.query_api.LOG.log", broken_sink)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        result = client.post(PATH, json=BODY)
    assert result.status_code == 200
    assert result.json()["view"] == "current"


class PreviewOnly:
    """Records the arguments the preview route actually forwards."""

    def __init__(self):
        self.calls = []

    def read(self, *args):
        raise AssertionError("A restore preview must not call the saved-change reader")

    def preview_restore(self, document_id, arguments):
        self.calls.append((document_id, arguments))
        return {"format_version": 2, "view": "restore_preview", "access": "current",
                "base_revision_ref": "head-ref", "target_revision_ref": "target-ref",
                "records": [], "start_index": 0, "total_records": 0, "total_changes": 0,
                "has_more": False, "next_cursor": None, "oversized_unit": False}


def test_the_preview_route_forwards_the_reparsed_arguments_and_writes_nothing():
    """A preview is a read: it reaches the preview reader and nothing else."""
    changes = PreviewOnly()
    path = f"/api/documents/{DOCUMENT}/jd/restore/preview"
    with TestClient(app_for(NoCurrent(), changes), base_url="http://127.0.0.1") as client:
        response = client.post(path, json={"target_revision_ref": "target-ref", "cursor": None})
    assert response.status_code == 200
    assert response.json()["view"] == "restore_preview"
    assert changes.calls == [(DOCUMENT, {"target_revision_ref": "target-ref", "cursor": None})]


def test_the_preview_route_refuses_a_body_that_is_not_its_own_shape():
    """Its shape is generated, so an extra or missing key never reaches the reader."""
    changes = PreviewOnly()
    path = f"/api/documents/{DOCUMENT}/jd/restore/preview"
    with TestClient(app_for(NoCurrent(), changes), base_url="http://127.0.0.1") as client:
        assert client.post(path, json={"target_revision_ref": "target-ref"}).status_code == 422
        assert client.post(path, json={"target_revision_ref": "t", "cursor": None,
                                       "document_id": "App owns this"}).status_code == 422
    assert changes.calls == []
