"""設定與資源組裝不應在啟動時偷偷建表或連線。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event

import caliburn.host.app as bootstrap
from caliburn.host.app import build_app
from caliburn.host.entrypoint import create_app
from caliburn.modules.occupation_reference.configuration import ReferenceConfiguration
from caliburn.shared.infrastructure.persistence.database import create_database_engine
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


def test_app_can_start_without_connecting_or_migrating() -> None:
    """不可達資料庫仍能建立 app 並提供 OpenAPI，表結構須另行遷移。"""
    app = build_app(
        database_url="postgresql+psycopg://localhost:1/unreachable",
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
    )
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/workspaces" in response.json()["paths"]
    assert response.json()["info"]["title"] == "Caliburn"


@pytest.mark.parametrize(
    ("method", "path", "body", "expected_location", "expected_code"),
    [
        ("POST", "/workspaces", {}, ["body", "interviewee_name"], "missing"),
        ("GET", "/workspaces/invalid", None, ["path", "workspace_id"], "value_error"),
        ("GET", "/workspaces?limit=0", None, ["query", "limit"], "greater_than_equal"),
        ("GET", "/workspaces?after=invalid", None, ["query", "after"], "value_error"),
    ],
)
def test_composed_app_preserves_workspace_validation_locations(
    method: str,
    path: str,
    body: object,
    expected_location: list[str],
    expected_code: str,
) -> None:
    """組裝根須保留 Workspace 的公開 body、path 與 query 錯誤欄位。"""
    app = build_app(
        database_url="postgresql+psycopg://localhost:1/unreachable",
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
    )
    with TestClient(app) as client:
        response = client.request(method, path, json=body)

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "invalid_request",
            "errors": [{"loc": expected_location, "code": expected_code}],
        }
    }


def test_app_factory_requires_explicit_database_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """沒有明示設定就拒絕啟動，不採舊產品或預設資料庫。"""
    monkeypatch.delenv("CALIBURN_REBUILD_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="CALIBURN_REBUILD_DATABASE_URL"):
        create_app()


def test_app_factory_requires_reference_configuration_without_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CALIBURN_REBUILD_DATABASE_URL",
        "postgresql+psycopg://localhost:1/unreachable",
    )
    monkeypatch.delenv("CALIBURN_REBUILD_AGENT_CONFIG", raising=False)
    monkeypatch.delenv("CALIBURN_REBUILD_REFERENCE_CONFIG", raising=False)
    with pytest.raises(ValueError, match="CALIBURN_REBUILD_REFERENCE_CONFIG"):
        create_app()


def test_health_reports_started_application_without_model_inference() -> None:
    app = build_app(
        database_url="postgresql+psycopg://localhost:1/unreachable",
        reference_configuration=ReferenceConfiguration(
            collection="health_test", qdrant_url="http://127.0.0.1:1"
        ),
    )
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_factory_reads_configuration_only_when_called(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """app factory 在呼叫時讀取設定，匯入模組不連線。"""
    monkeypatch.setenv(
        "CALIBURN_REBUILD_DATABASE_URL",
        "postgresql+psycopg://localhost:1/unreachable",
    )
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(
        ReferenceConfiguration(collection="factory_test").model_dump_json(),
        encoding="utf-8",
    )
    monkeypatch.setenv("CALIBURN_REBUILD_REFERENCE_CONFIG", str(reference_path))
    with TestClient(create_app()) as client:
        assert client.get("/openapi.json").status_code == 200


def test_shutdown_disposes_owned_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """關閉 app 會釋放其 Engine，生命週期由組裝根負責。"""
    engine = create_database_engine("postgresql+psycopg://localhost:1/unreachable")
    disposed: list[Engine] = []
    event.listen(engine, "engine_disposed", disposed.append)
    monkeypatch.setattr(bootstrap, "create_database_engine", lambda url: engine)
    with TestClient(
        build_app(
            database_url="unused", reference_configuration=HOST_REFERENCE_CONFIGURATION
        )
    ) as client:
        assert client.get("/openapi.json").status_code == 200
        assert disposed == []
    assert disposed == [engine]
