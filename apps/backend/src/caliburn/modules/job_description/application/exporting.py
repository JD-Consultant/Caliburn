"""釋放完整 scoped JD 的讀取資源後，才執行 PDF 列印。"""

import asyncio
from typing import Literal, Protocol
from uuid import UUID

from caliburn.modules.job_description.application.export_projection import (
    project_jd_export_html,
)
from caliburn.modules.job_description.application.queries import (
    JobDescriptionQueries,
    get_job_description,
)

type PdfFailureCode = Literal[
    "pdf_renderer_busy",
    "pdf_render_timeout",
    "pdf_font_unavailable",
    "pdf_render_failed",
]


class PdfRenderError(RuntimeError):
    """安全公開代碼；不得將 JD 內容放進錯誤或一般日誌。"""

    def __init__(self, code: PdfFailureCode) -> None:
        self.code = code
        super().__init__(code)


class HtmlPdfRenderer(Protocol):
    async def render_html(self, body_html: str) -> bytes:
        """只列印已 escape 的可信格式，不持有業務交易。"""
        ...


async def export_job_description(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    queries: JobDescriptionQueries,
    renderer: HtmlPdfRenderer,
) -> bytes:
    snapshot = await asyncio.to_thread(
        get_job_description,
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        queries=queries,
    )
    return await renderer.render_html(project_jd_export_html(snapshot))
