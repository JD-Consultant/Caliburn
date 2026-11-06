"""正式同源 Host：API 不落入 SPA，頁面導航使用同一份靜態產物。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caliburn.host.entrypoint import create_app
from tests.reference_configuration import write_reference_configuration


@pytest.fixture
def web_dist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv(
        "CALIBURN_REBUILD_DATABASE_URL",
        "postgresql+psycopg://localhost:1/unreachable",
    )
    monkeypatch.setenv(
        "CALIBURN_REBUILD_REFERENCE_CONFIG",
        str(write_reference_configuration(tmp_path)),
    )
    monkeypatch.delenv("CALIBURN_REBUILD_AGENT_CONFIG", raising=False)
    directory = tmp_path / "dist"
    directory.mkdir()
    (directory / "index.html").write_text("<main>Caliburn SPA</main>", encoding="utf-8")
    (directory / "assets").mkdir()
    (directory / "assets/app.js").write_text("console.log('app');", encoding="utf-8")
    monkeypatch.setenv("CALIBURN_REBUILD_WEB_DIST", str(directory))
    return directory


def test_same_origin_api_and_navigation(web_dist: Path) -> None:
    with TestClient(create_app()) as client:
        health = client.get("/api/health")
        root_health = client.get("/health")
        schema = client.get("/api/openapi.json")
        home = client.get("/")
        navigation = client.get("/workspaces/example", headers={"Accept": "text/html"})
        script = client.get("/assets/app.js")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert root_health.status_code == 200
    assert root_health.json() == health.json()
    assert "/workspaces" in schema.json()["paths"]
    assert home.text == navigation.text == "<main>Caliburn SPA</main>"
    assert navigation.status_code == 200
    assert script.text == "console.log('app');"
    assert "javascript" in script.headers["content-type"]


def test_unknown_api_and_assets_never_return_spa(web_dist: Path) -> None:
    with TestClient(create_app()) as client:
        api = client.get("/api/unknown", headers={"Accept": "text/html"})
        api_root = client.get("/api", headers={"Accept": "text/html"})
        asset = client.get("/assets/missing.js", headers={"Accept": "text/html"})
        post = client.post("/workspaces/example")

    assert api.status_code == asset.status_code == 404
    assert api_root.status_code == 404
    assert api_root.history[0].status_code == 307
    assert "Caliburn SPA" not in api.text
    assert "Caliburn SPA" not in asset.text
    assert post.status_code == 405


def test_web_dist_requires_built_index(web_dist: Path) -> None:
    (web_dist / "index.html").unlink()
    with pytest.raises(ValueError, match="index.html"):
        create_app()
