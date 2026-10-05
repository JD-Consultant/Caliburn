"""Public reference HTTP contracts, separate from the legacy occupation API."""

import httpx
import pytest
from fastapi.testclient import TestClient
from jd_ocs_indexer.api.app import create_app
from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.references.errors import (
    ReferenceIndexError,
    ReferenceNotFoundError,
    ReferenceProviderError,
    ReferenceQueryError,
)
from jd_ocs_indexer.references.service import ReferenceSearch


def test_reference_search_validates_input_before_running_models(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant())) as client:
        for body in (
            {"query": "   "},
            {"query": "工作", "limit": 6},
            {"query": "工作", "top_k": 20},
        ):
            response = client.post("/occupation-references:search", json=body)
            assert response.status_code == 422, response.text


def test_reference_search_reports_unconfigured_service(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant())) as client:
        response = client.post("/occupation-references:search", json={"query": "工作"})
        assert response.status_code == 503, response.text
        assert response.json()["detail"]["code"] == "reference_service_unavailable"


@pytest.mark.parametrize(
    "error,status",
    [
        (ReferenceIndexError("private payload"), 409),
        (ReferenceProviderError("private payload"), 502),
        (ReferenceQueryError("private payload"), 422),
        (ReferenceNotFoundError("private payload"), 404),
        (httpx.ConnectError("private payload"), 503),
    ],
)
def test_reference_failures_have_distinct_status_without_sensitive_body(
    stub_embedder,
    make_qdrant,
    error,
    status,
):
    class Store:
        def validate_index(self):
            raise error

    class Ranker:
        model = "test"
        revision = "test"

    app = create_app(
        settings=load_settings(),
        client=make_qdrant(),
        embedder=stub_embedder,
        reference_search=ReferenceSearch(Store(), stub_embedder, Ranker()),
    )
    with TestClient(app) as client:
        response = client.post("/occupation-references:search", json={"query": "employee content"})
        assert response.status_code == status
        assert "private payload" not in response.text
        assert "employee content" not in response.text


def test_reference_contract_is_generated_into_openapi(make_app, make_qdrant):
    schema = make_app(make_qdrant()).openapi()
    request = schema["components"]["schemas"]["ReferenceSearchRequest"]
    assert request["additionalProperties"] is False
    assert set(request["properties"]) == {"query", "limit"}
    assert request["properties"]["limit"]["maximum"] == 5
    assert (
        schema["paths"]["/occupation-references:search"]["post"]["operationId"]
        == "search_occupation_references"
    )
