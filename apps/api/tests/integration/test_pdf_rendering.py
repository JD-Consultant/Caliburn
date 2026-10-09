"""Opt-in real Chromium smoke: run from a Selector caller, with explicit local resources."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest

from caliburn.adapters.pdf_renderer import PdfRenderer
from caliburn.features.job_description.export_projection import project_jd_export_html
from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.tasks import DetailKind, TaskDetail, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision


@pytest.mark.parametrize("paragraph_count", [1, 80])
def test_chinese_short_and_long_pdf_from_selector_loop(paragraph_count: int) -> None:
    font = os.environ.get("CALIBURN_TEST_PDF_FONT")
    if font is None:
        pytest.skip("Set CALIBURN_TEST_PDF_FONT for actual Chromium rendering")
    executable = os.environ.get("CALIBURN_TEST_PDF_CHROMIUM")
    work = JdWorkRevision(
        uuid4(),
        (),
        (
            WorkTask(
                uuid4(),
                uuid4(),
                None,
                "核對網站前端交付",
                "\n".join(
                    f"步驟 {index}：依需求確認互動狀態，記錄異常與判斷，與設計師協調修正。"
                    for index in range(paragraph_count)
                ),
                (TaskDetail(uuid4(), DetailKind.OUTCOME, "最終驗證報告：全部內容均已保留。"),),
            ),
        ),
        (),
        (),
        (),
        (),
    )
    html = project_jd_export_html(
        JdProfile("前端工程師", "產品研發", "技術主管", "維護可用且清楚的介面"), work
    )

    async def render() -> bytes:
        renderer = PdfRenderer(
            font_path=Path(font), executable_path=Path(executable) if executable else None
        )
        try:
            return await renderer.render_html(html)
        finally:
            await renderer.aclose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        pdf = runner.run(render())
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 10_000
    output = os.environ.get("CALIBURN_TEST_PDF_OUTPUT")
    if output:
        target = Path(output)
        target.mkdir(parents=True, exist_ok=True)
        (target / f"jd-{'short' if paragraph_count == 1 else 'long'}.pdf").write_bytes(pdf)
