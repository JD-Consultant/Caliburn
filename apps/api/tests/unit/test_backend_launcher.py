"""Explicit container binding must not change native launch or HTTP trust defaults."""

import runpy
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI


@pytest.mark.parametrize(
    ("arguments", "expected_host"),
    [([], "127.0.0.1"), (["--host", "0.0.0.0"], "0.0.0.0")],
)
def test_backend_binding_is_explicit_and_never_trusts_proxy_headers(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str], expected_host: str
) -> None:
    monkeypatch.setenv("CALIBURN_DATABASE_URL", "postgresql://synthetic@127.0.0.1/caliburn_test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CALIBURN_WEB_BUILD_DIRECTORY", raising=False)
    launcher = Path(__file__).parents[2] / "scripts" / "run_backend.py"
    namespace = runpy.run_path(str(launcher))
    observed: dict[str, object] = {}

    # Capture the server boundary instead of opening sockets or entering DB lifespan.
    def capture_server(app: FastAPI, **options: object) -> None:
        observed.update(options)
        observed["app"] = app

    monkeypatch.setattr(namespace["uvicorn"], "run", capture_server)
    monkeypatch.setattr(sys, "argv", [str(launcher), *arguments])
    namespace["main"]()

    assert isinstance(observed["app"], FastAPI)
    assert observed["host"] == expected_host
    assert observed["port"] == 8100
    assert observed["loop"] == "asyncio:SelectorEventLoop"
    assert observed["proxy_headers"] is False


def test_backend_rejects_arbitrary_network_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = Path(__file__).parents[2] / "scripts" / "run_backend.py"
    namespace = runpy.run_path(str(launcher))
    monkeypatch.setattr(sys, "argv", [str(launcher), "--host", "192.0.2.1"])

    with pytest.raises(SystemExit) as error:
        namespace["main"]()

    assert error.value.code == 2
