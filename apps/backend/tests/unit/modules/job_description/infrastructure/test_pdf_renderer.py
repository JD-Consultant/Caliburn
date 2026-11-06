"""工作執行緒資格在真正收尾前不釋放，不把缺字型當成空 PDF 成功。"""

import asyncio
import importlib
import importlib.util
from pathlib import Path
from threading import Event

import pytest

from caliburn.modules.job_description.application.exporting import PdfRenderError


def renderer_type() -> type:
    name = "caliburn.modules.job_description.infrastructure.pdf_renderer"
    assert importlib.util.find_spec(name) is not None, "尚未提供有界PDF列印"
    module = importlib.import_module(name)
    assert isinstance(module.PdfRenderer, type)
    return module.PdfRenderer


def test_missing_font_is_explicit_and_renderer_closes() -> None:
    renderer = renderer_type()(font_path=Path("missing-test-font.ttf"))

    async def run() -> None:
        try:
            with pytest.raises(PdfRenderError, match="pdf_font_unavailable"):
                await renderer.render_html("<h1>中文</h1>")
        finally:
            await renderer.aclose()
        with pytest.raises(PdfRenderError, match="pdf_renderer_busy"):
            await renderer.render_html("<h1>已關閉</h1>")

    asyncio.run(run())


def test_cancelled_caller_cannot_admit_second_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    renderer = renderer_type()(font_path=Path("worker-test-unused.ttf"))
    release = Event()

    async def run() -> None:
        started = asyncio.Event()
        loop = asyncio.get_running_loop()

        def blocked_worker(body_html: str) -> bytes:
            loop.call_soon_threadsafe(started.set)
            if not release.wait(5):
                raise AssertionError("測試工作執行緒未被釋放")
            return b"%PDF-test"

        monkeypatch.setattr(renderer, "_render_in_thread", blocked_worker)
        first = asyncio.create_task(renderer.render_html("<h1>第一份</h1>"))
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            with pytest.raises(PdfRenderError, match="pdf_renderer_busy"):
                await renderer.render_html("<h1>第二份</h1>")
        finally:
            release.set()
            await renderer.aclose()

    asyncio.run(run())
