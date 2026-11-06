"""獨立審查：逾時回呼不釋放仍在工作的 renderer 名額。"""

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from threading import Event

import pytest

from caliburn.modules.job_description.application.exporting import PdfRenderError
from caliburn.modules.job_description.infrastructure.pdf_renderer import PdfRenderer


def test_caller_timeout_keeps_slot_until_worker_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    renderer = PdfRenderer(font_path=Path("unused-review-font.ttf"))
    release = Event()
    started = Event()
    original_wait_for = asyncio.wait_for

    async def short_wait_for(awaitable: Awaitable[bytes], *, timeout: int) -> bytes:
        assert timeout == 60
        return await original_wait_for(awaitable, timeout=0.1)

    def delayed_worker(body_html: str) -> bytes:
        started.set()
        if not release.wait(5):
            raise AssertionError("審查測試未釋放自有 worker")
        return b"%PDF-review"

    monkeypatch.setattr(renderer, "_render_in_thread", delayed_worker)
    monkeypatch.setattr(asyncio, "wait_for", short_wait_for)

    async def run() -> None:
        try:
            with pytest.raises(PdfRenderError, match="pdf_render_timeout"):
                await renderer.render_html("<h1>測試</h1>")
            assert started.is_set()
            with pytest.raises(PdfRenderError, match="pdf_renderer_busy"):
                await renderer.render_html("<h1>第二份</h1>")
        finally:
            release.set()
            await renderer.aclose()
        with pytest.raises(PdfRenderError, match="pdf_renderer_busy"):
            await renderer.render_html("<h1>已關閉</h1>")

    asyncio.run(run())
