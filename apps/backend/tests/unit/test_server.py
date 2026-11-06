"""正式服務入口須使用 PostgreSQL async driver 支援的事件迴圈。"""

import asyncio
import runpy
import sys

import pytest

from caliburn.server import create_server


def test_server_cli_passes_explicit_bind_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import uvicorn

    received: list[tuple[str, int]] = []

    def run(server: uvicorn.Server) -> None:
        received.append((server.config.host, server.config.port))

    monkeypatch.setattr(uvicorn.Server, "run", run)
    monkeypatch.setattr(
        sys, "argv", ["caliburn.server", "--host", "0.0.0.0", "--port", "8102"]
    )
    monkeypatch.delitem(sys.modules, "caliburn.server")
    runpy.run_module("caliburn.server", run_name="__main__")
    assert received == [("0.0.0.0", 8102)]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 事件迴圈相容性")
def test_windows_server_uses_selector_event_loop() -> None:
    """正式啟動配置須可直接建立相容 Psycopg 的 Selector loop。"""
    config = create_server().config
    factory = config.get_loop_factory()
    assert factory is not None
    loop = factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()
