"""An isolated UI has an explicit local origin, never a forged proxy header."""

import pytest
from fastapi.testclient import TestClient

from caliburn.bootstrap import create_app
from caliburn.settings import Settings


@pytest.fixture
def offline_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CALIBURN_DATABASE_URL",
        "OPENAI_API_KEY",
        "CALIBURN_PDF_FONT_PATH",
        "CALIBURN_DEV_ORIGIN",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.usefixtures("offline_environment")
@pytest.mark.parametrize(
    "origin",
    ["http://127.0.0.1:5174", "http://localhost:5174", "http://[::1]:5174"],
)
def test_configured_dev_origin_is_exact_and_instance_local(
    monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    monkeypatch.setenv("CALIBURN_DEV_ORIGIN", origin)
    app = create_app(Settings.from_environment())

    @app.post("/probe")
    async def probe() -> dict[str, bool]:
        return {"accepted": True}

    with TestClient(app, base_url="http://127.0.0.1:8100") as client:
        response = client.post("/probe", headers={"Origin": origin}, json={})
        assert response.status_code == 200
        assert response.json() == {"accepted": True}
        assert (
            client.post("/probe", headers={"Origin": "http://127.0.0.1:9999"}, json={}).status_code
            == 403
        )
        assert (
            client.post(
                "/probe",
                headers={"Origin": origin, "Sec-Fetch-Site": "cross-site"},
                json={},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/probe", headers={"Origin": origin, "Host": "evil.example"}, json={}
            ).status_code
            == 400
        )
        assert (
            client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"}).status_code
            == 200
        )

    with TestClient(create_app(Settings()), base_url="http://127.0.0.1:8100") as client:
        assert client.get("/api/health", headers={"Origin": origin}).status_code == 403


@pytest.mark.usefixtures("offline_environment")
@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "null",
        "",
        "https://evil.example",
        "http://0.0.0.0:5174",
        "http://127.0.0.1:5174/",
        "http://user@localhost:5174",
        "http://localhost:5174?x=1",
        "http://localhost:5174#x",
        "http://localhost:0",
        "http://localhost:65536",
        "http://localhost:5174,http://localhost:5175",
    ],
)
def test_invalid_dev_origin_fails_before_serving(
    monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    monkeypatch.setenv("CALIBURN_DEV_ORIGIN", origin)
    with pytest.raises(ValueError, match="origin"):
        Settings.from_environment()


@pytest.mark.usefixtures("offline_environment")
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_default_http_port_uses_browser_serialized_origin(
    monkeypatch: pytest.MonkeyPatch, host: str
) -> None:
    monkeypatch.setenv("CALIBURN_DEV_ORIGIN", f"http://{host}:80")
    with TestClient(
        create_app(Settings.from_environment()), base_url="http://127.0.0.1:8100"
    ) as client:
        assert client.get("/api/health", headers={"Origin": f"http://{host}"}).status_code == 200
        assert client.get("/api/health", headers={"Origin": f"http://{host}:81"}).status_code == 403
