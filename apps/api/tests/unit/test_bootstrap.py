"""Offline startup has no model-key, database or legacy dotenv dependency."""

import pytest
from fastapi.testclient import TestClient

from caliburn.bootstrap import create_app


def test_health_and_openapi_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        schema = client.get("/openapi.json").json()
        assert (
            schema["components"]["schemas"]["HealthStatus"]["properties"]["status"]["const"] == "ok"
        )
