"""Target settings cannot silently attach the retired app's database."""

import pytest
from fastapi.testclient import TestClient

from caliburn.bootstrap import create_app
from caliburn.settings import DatabaseSettings, Settings


def test_legacy_database_setting_is_not_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CALIBURN_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://legacy.invalid/old")
    assert Settings.from_environment().database is None
    with TestClient(create_app(Settings())) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/job-files").status_code == 503


@pytest.mark.parametrize("schema", ["", "unsafe; DROP TABLE t", "UPPER", "two.schema", "a" * 64])
def test_database_schema_is_a_safe_identifier(schema: str) -> None:
    with pytest.raises(ValueError, match="schema"):
        DatabaseSettings(url="postgresql://localhost/caliburn_test", schema=schema)


def test_secrets_do_not_appear_in_settings_representation() -> None:
    settings = DatabaseSettings(url="postgresql://user:private-password@localhost/caliburn_test")
    assert "private-password" not in repr(settings)


def test_non_postgresql_database_is_rejected() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        DatabaseSettings(url="sqlite://")
