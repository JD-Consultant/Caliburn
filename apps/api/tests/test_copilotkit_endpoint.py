from fastapi.testclient import TestClient

from app.copilotkit_app import app


def test_healthz():
    with TestClient(app) as c:
        assert c.get("/healthz").json()["status"] == "ok"


def test_copilotkit_route_mounted():
    paths = [getattr(r, "path", "") for r in app.routes]
    assert any("/copilotkit" in p for p in paths), f"no /copilotkit route in {paths}"
