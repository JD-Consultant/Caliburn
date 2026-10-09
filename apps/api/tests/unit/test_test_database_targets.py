"""Test entry points reject ambiguous or redirected targets before any connection."""

import os
import runpy
import sys
from pathlib import Path

import psycopg
import pytest

from caliburn.adapters.database_settings import require_isolated_test_database
from caliburn.settings import DatabaseSettings, Settings
from tests.fixtures import scripted_backend


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/caliburn?application_name=audit_test",
        "postgresql://203.0.113.10/synthetic_test",
        "postgresql://localhost/synthetic_test?hostaddr=203.0.113.10",
    ],
)
def test_scripted_backend_rejects_unsafe_target_before_creating_app(monkeypatch, url):
    settings = Settings(database=DatabaseSettings(url=url))
    monkeypatch.setattr(Settings, "from_environment", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["scripted-backend"])

    def unexpected_app(*args, **kwargs):
        pytest.fail("Unsafe target reached App construction")

    monkeypatch.setattr(scripted_backend, "create_scripted_app", unexpected_app)
    with pytest.raises(SystemExit) as stopped:
        scripted_backend.main()
    assert stopped.value.code == 2


@pytest.mark.parametrize("redirect", ["url", "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"])
def test_postgres_fixture_rejects_redirection_before_connect(monkeypatch, redirect):
    url = "postgresql://localhost/synthetic_test"
    if redirect == "url":
        url += "?hostaddr=203.0.113.10"
    else:
        monkeypatch.setenv(redirect, "redirect-not-allowed")
    monkeypatch.setenv("CALIBURN_TEST_DATABASE_URL", url)

    def unexpected_connect(*args, **kwargs):
        pytest.fail("Unsafe target reached PostgreSQL connection")

    monkeypatch.setattr(psycopg, "connect", unexpected_connect)
    namespace = runpy.run_path(str(Path(__file__).parents[1] / "integration/conftest.py"))
    fixture = namespace["empty_database_settings"].__wrapped__()
    with pytest.raises(ValueError, match="redirect"):
        next(fixture)


def test_fixture_probe_never_uses_existing_database_environment(monkeypatch):
    monkeypatch.delenv("CALIBURN_TEST_DATABASE_URL", raising=False)
    namespace = runpy.run_path(str(Path(__file__).parents[1] / "integration/conftest.py"))
    with pytest.raises(pytest.skip.Exception):
        next(namespace["empty_database_settings"].__wrapped__())
    assert "CALIBURN_TEST_DATABASE_URL" not in os.environ


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://localhost/synthetic_test",
        "postgresql://127.0.0.1:55467/synthetic_test?application_name=audit",
        "postgresql://[::1]/synthetic_test",
        "host=127.0.0.1 dbname=synthetic_test options='-c search_path=t01_synthetic'",
    ],
)
def test_test_target_accepts_explicit_loopback_namespaces(dsn):
    require_isolated_test_database(dsn, environment={})


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://localhost/caliburn?application_name=audit_test",
        "postgresql://203.0.113.10/synthetic_test",
        "postgresql:///synthetic_test",
        "host=localhost,203.0.113.10 dbname=synthetic_test",
        "postgresql://localhost/synthetic_test?service=other",
        "postgresql://localhost/synthetic_test?hostaddr=127.0.0.1",
        "host=localhost dbname=synthetic_test unexpected=synthetic_secret",
    ],
)
def test_test_target_rejects_ambiguous_locations_without_exposing_dsn(dsn):
    with pytest.raises(ValueError) as rejected:
        require_isolated_test_database(dsn, environment={})
    assert dsn not in str(rejected.value)
    assert "synthetic_secret" not in str(rejected.value)
