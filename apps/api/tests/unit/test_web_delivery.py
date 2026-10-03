"""The configured build is served locally without swallowing API failures."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caliburn.bootstrap import create_app
from caliburn.settings import Settings


@pytest.fixture
def web_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in (
        "CALIBURN_DATABASE_URL",
        "OPENAI_API_KEY",
        "CALIBURN_PDF_FONT_PATH",
        "CALIBURN_DEV_ORIGIN",
    ):
        monkeypatch.delenv(name, raising=False)
    directory = tmp_path / "dist"
    directory.mkdir()
    (directory / "index.html").write_text("<html>Caliburn build</html>", encoding="utf-8")
    (directory / "assets").mkdir()
    (directory / "assets" / "app.js").write_text("export const ready = true;", encoding="utf-8")
    monkeypatch.setenv("CALIBURN_WEB_BUILD_DIRECTORY", str(directory))
    return directory


@pytest.mark.parametrize("path", ["/", "/job-files/00000000-0000-0000-0000-000000000001"])
def test_built_web_supports_initial_navigation_and_reload(web_build: Path, path: str) -> None:
    with TestClient(
        create_app(Settings.from_environment()), base_url="http://127.0.0.1:8100"
    ) as client:
        response = client.get(path, headers={"Accept": "text/html"})
        assert response.status_code == 200
        assert response.text == "<html>Caliburn build</html>"
        assert response.headers["content-type"].startswith("text/html")
        head = client.head(path, headers={"Accept": "text/html"})
        assert head.status_code == 200
        assert head.content == b""


def test_built_assets_are_served_without_api_or_spa_fallback(web_build: Path) -> None:
    with TestClient(
        create_app(Settings.from_environment()), base_url="http://127.0.0.1:8100"
    ) as client:
        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert asset.text == "export const ready = true;"
        assert "javascript" in asset.headers["content-type"]
        for path in ("/api/not-a-route", "/assets/missing.js", "/not-a-page"):
            response = client.get(path, headers={"Accept": "text/html"})
            assert response.status_code == 404
            assert response.json() == {"detail": "Not Found"}
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/job-files").status_code == 503


def test_web_fallback_is_readonly_and_keeps_local_request_protection(web_build: Path) -> None:
    with TestClient(
        create_app(Settings.from_environment()), base_url="http://127.0.0.1:8100"
    ) as client:
        assert client.post("/job-files/example", json={}).status_code == 404
        assert (
            client.get("/job-files/example", headers={"Accept": "application/json"}).status_code
            == 404
        )
        assert client.get("/", headers={"Host": "evil.example"}).status_code == 400
        assert client.get("/", headers={"Origin": "null"}).status_code == 403


def test_web_build_cannot_serve_a_file_outside_its_directory(web_build: Path) -> None:
    (web_build.parent / "private.txt").write_text("not a public asset", encoding="utf-8")
    with TestClient(
        create_app(Settings.from_environment()), base_url="http://127.0.0.1:8100"
    ) as client:
        response = client.get("/%2e%2e/private.txt")
        assert response.status_code == 404
        assert "not a public asset" not in response.text


@pytest.mark.parametrize("missing", ["directory", "index"])
def test_invalid_web_build_fails_before_serving(
    tmp_path: Path, web_build: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    directory = tmp_path / "incomplete"
    if missing == "index":
        directory.mkdir()
    monkeypatch.setenv("CALIBURN_WEB_BUILD_DIRECTORY", str(directory))
    with pytest.raises(RuntimeError, match="does not exist"):
        create_app(Settings.from_environment())


def test_web_build_requires_an_explicit_absolute_directory(
    web_build: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CALIBURN_WEB_BUILD_DIRECTORY", "../web/dist")
    with pytest.raises(ValueError, match="absolute"):
        Settings.from_environment()


def test_unconfigured_app_remains_api_only(
    web_build: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CALIBURN_WEB_BUILD_DIRECTORY")
    with TestClient(
        create_app(Settings.from_environment()), base_url="http://127.0.0.1:8100"
    ) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/health").json() == {"status": "ok"}
