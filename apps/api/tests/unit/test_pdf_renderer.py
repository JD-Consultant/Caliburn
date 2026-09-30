"""Renderer validation is independent from database and never reports an empty success."""

import asyncio
from pathlib import Path
from threading import Event

import pytest

from caliburn.adapters.pdf_renderer import PdfRenderer, PdfRenderError


async def test_missing_font_is_explicit_and_does_not_return_pdf() -> None:
    renderer = PdfRenderer(font_path=Path("/caliburn-test-nonexistent-font.ttf"))
    try:
        with pytest.raises(PdfRenderError, match="font_unavailable"):
            await renderer.render_html("<h1>中文</h1>")
    finally:
        await renderer.aclose()


async def test_cancelled_caller_does_not_admit_a_second_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    renderer = PdfRenderer(font_path=Path("unused-in-this-worker-boundary-test.ttf"))
    started = asyncio.Event()
    release = Event()
    loop = asyncio.get_running_loop()

    def blocking_worker(body_html: str) -> bytes:
        loop.call_soon_threadsafe(started.set)
        if not release.wait(5):
            raise RuntimeError("test worker was not released")
        return b"%PDF-test"

    monkeypatch.setattr(renderer, "_render_in_thread", blocking_worker)
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
