"""明示啟用真 Chromium：從 Selector caller 列印完整中文短／長 JD。"""

import asyncio
import os
import unicodedata
from io import BytesIO
from pathlib import Path

import pdfplumber
import pytest

from caliburn.modules.job_description.application.export_projection import (
    project_jd_export_html,
)
from caliburn.modules.job_description.infrastructure.pdf_renderer import PdfRenderer
from tests.unit.modules.job_description.application.test_export import document


@pytest.mark.parametrize("paragraph_count", [1, 80])
def test_actual_chromium_preserves_chinese_content_across_pages(
    paragraph_count: int,
) -> None:
    font = os.environ.get("CALIBURN_TEST_PDF_FONT")
    if font is None:
        pytest.skip("Set CALIBURN_TEST_PDF_FONT for actual Chromium rendering")
    pytest.importorskip("playwright")
    executable = os.environ.get("CALIBURN_TEST_PDF_CHROMIUM")
    snapshot = document()
    task = snapshot.tasks[0].model_copy(
        update={
            "description": "\n".join(
                f"步驟 {index}：依需求確認設備狀態，記錄異常與判斷，與維修組協調修正。"
                for index in range(paragraph_count)
            )
            + "\n最後內容：全部工作與界線均已保留。"
        }
    )
    snapshot = snapshot.model_copy(
        update={"job_title": "設備維護員", "tasks": (task, *snapshot.tasks[1:])}
    )

    async def render() -> bytes:
        renderer = PdfRenderer(
            font_path=Path(font),
            executable_path=Path(executable) if executable else None,
        )
        try:
            return await renderer.render_html(project_jd_export_html(snapshot))
        finally:
            await renderer.aclose()

    pdf = asyncio.run(render(), loop_factory=asyncio.SelectorEventLoop)
    assert pdf.startswith(b"%PDF-")
    with pdfplumber.open(BytesIO(pdf)) as parsed:
        # Chromium 字型子集可把同形字對映至相容部首；僅正規化抽取比對，不改 PDF。
        text = unicodedata.normalize(
            "NFKC", "\n".join(page.extract_text() or "" for page in parsed.pages)
        )
        assert "設備維護員" in text
        assert "全部工作與界線均已保留" in text
        assert "基準職能級別" in text
        assert "故障診斷" in text
        assert "qualification" in text
        assert "citation" not in text
        if paragraph_count > 1:
            assert len(parsed.pages) >= 3
    output = os.environ.get("CALIBURN_TEST_PDF_OUTPUT")
    if output is not None:
        directory = Path(output)
        directory.mkdir(parents=True, exist_ok=True)
        (
            directory / f"jd-{'short' if paragraph_count == 1 else 'long'}.pdf"
        ).write_bytes(pdf)
