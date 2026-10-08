"""Bounded Chromium printing outside the database event loop."""

import asyncio
import base64
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from threading import BoundedSemaphore

from playwright.async_api import Browser, async_playwright
from playwright.async_api import Error as PlaywrightError


class PdfRenderError(RuntimeError):
    """A safe public code; renderer diagnostics must not expose document contents."""


_PRINT_CSS = """
@page { size: A4; margin: 17mm 17mm 20mm; }
body { font-family: CaliburnPrint; color: #182c3b; font-size: 10.5pt; line-height: 1.55; }
h1 { font-size: 23pt; color: #154b58; border-bottom: 2px solid #154b58; padding-bottom: 10px; }
h2 { font-size: 14pt; margin: 20px 0 7px; border-bottom: 1px solid #c7d9dc; }
h3 { font-size: 12pt; margin: 15px 0 5px; }
h4 { font-size: 11pt; margin: 12px 0 4px; }
h5 { font-size: 10.5pt; margin: 8px 0 3px; color: #285769; }
h1,h2,h3,h4,h5 { break-after: avoid; }
p,li { white-space: pre-wrap; overflow-wrap: anywhere; orphans: 3; widows: 3; }
p { margin: 4px 0 9px; } ul { padding-left: 22px; margin: 3px 0 8px; }
"""


class PdfRenderer:
    def __init__(self, *, font_path: Path, executable_path: Path | None = None) -> None:
        self.font_path = font_path
        self.executable_path = executable_path
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="caliburn-pdf")
        self._slot = BoundedSemaphore(1)
        self._closed = False

    async def render_html(self, body_html: str) -> bytes:
        """Print trusted template HTML; callers must escape all untrusted JD text first.

        One render at a time, no hidden queue. Cancellation/timeout does not release the
        slot until the worker has closed its own browser. A caller never cancels a
        Playwright operation on another loop.
        """
        if self._closed or not self._slot.acquire(blocking=False):
            raise PdfRenderError("pdf_renderer_busy")
        future = self._executor.submit(self._render_in_thread, body_html)
        future.add_done_callback(lambda _: self._slot.release())
        wrapped = asyncio.wrap_future(future)
        # Observe a late worker failure even when the HTTP client has disconnected.
        wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        try:
            return await asyncio.wait_for(asyncio.shield(wrapped), timeout=60)
        except TimeoutError as error:
            raise PdfRenderError("pdf_render_timeout") from error

    async def aclose(self) -> None:
        self._closed = True
        await asyncio.to_thread(self._executor.shutdown, wait=True, cancel_futures=False)

    def _render_in_thread(self, body_html: str) -> bytes:
        try:
            font = self.font_path.read_bytes()
        except OSError as error:
            raise PdfRenderError("pdf_font_unavailable") from error
        if not font or len(font) > 40_000_000:
            raise PdfRenderError("pdf_font_unavailable")
        factory = asyncio.ProactorEventLoop if sys.platform == "win32" else asyncio.new_event_loop
        with asyncio.Runner(loop_factory=factory) as runner:
            return runner.run(self._print(body_html, font))

    async def _print(self, body_html: str, font: bytes) -> bytes:
        encoded = base64.b64encode(font).decode("ascii")
        document = (
            '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
            "style-src 'unsafe-inline'; font-src data:; script-src 'none'\">"
            "<title>職務說明書</title><style>"
            "@font-face {font-family: CaliburnPrint; src: url(data:font/ttf;base64,"
            + encoded
            + "); font-weight: 100 900;}"
            + _PRINT_CSS
            + "</style></head><body>"
            + body_html
            + "</body></html>"
        )
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    executable_path=self.executable_path, headless=True, timeout=30_000
                )
                close_deadline = asyncio.create_task(_close_at_deadline(browser))
                try:
                    context = await browser.new_context(
                        java_script_enabled=False, offline=True, service_workers="block"
                    )
                    await context.route("**/*", lambda route: route.abort())
                    page = await context.new_page()
                    page.set_default_timeout(30_000)
                    await page.set_content(document, wait_until="load", timeout=30_000)
                    loaded = await page.evaluate(
                        "async () => { await document.fonts.ready; "
                        "return [...document.fonts].some(f => f.status === 'loaded'); }"
                    )
                    if not loaded:
                        raise PdfRenderError("pdf_font_unavailable")
                    result = await page.pdf(
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                        display_header_footer=True,
                        header_template="<span></span>",
                        footer_template=(
                            '<div style="font-size:8px;width:100%;text-align:center;color:#667;">'
                            '<span class="pageNumber"></span> / '
                            '<span class="totalPages"></span></div>'
                        ),
                        tagged=True,
                        outline=True,
                    )
                finally:
                    try:
                        await browser.close()
                    finally:
                        close_deadline.cancel()
                        with suppress(asyncio.CancelledError):
                            await close_deadline
        except (PlaywrightError, OSError) as error:
            raise PdfRenderError("pdf_render_failed") from error
        if not result.startswith(b"%PDF-"):
            raise PdfRenderError("pdf_render_failed")
        return result


async def _close_at_deadline(browser: Browser) -> None:
    """Close owned browser rather than cancel an in-flight Playwright operation."""
    await asyncio.sleep(50)
    await browser.close()
