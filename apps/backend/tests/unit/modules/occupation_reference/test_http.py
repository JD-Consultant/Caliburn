"""Public reference routes stay available independently of Agent configuration."""

import httpx
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

import caliburn.modules.occupation_reference.bootstrap as reference_bootstrap
from caliburn.host.app import build_app
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


def test_reference_outage_is_explicit_and_inputs_are_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic reference outage", request=request)

    monkeypatch.setattr(
        reference_bootstrap,
        "QdrantClient",
        lambda **kwargs: QdrantClient(
            **kwargs, transport=httpx.MockTransport(unavailable)
        ),
    )
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/reference_test",
    )
    with TestClient(app) as client:
        response = client.post(
            "/occupation-references:search", json={"query": "維護設備"}
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "reference_service_unavailable"
        assert client.get("/occupation-references/missing").status_code == 503
        for body in (
            {"query": "   "},
            {"query": "維護設備", "limit": 6},
            {"query": "維護設備", "top_k": 20},
        ):
            assert (
                client.post("/occupation-references:search", json=body).status_code
                == 422
            )
