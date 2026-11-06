"""下載提供完整 PDF 或明確失敗；不可把缺設定或列印失敗回成200。"""

import importlib
import importlib.util
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from caliburn.modules.job_description.application.exporting import (
    PdfFailureCode,
    PdfRenderError,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from tests.unit.modules.job_description.application.test_export import document


class Queries:
    def __init__(self) -> None:
        self.snapshot = document().model_copy(
            update={"job_description_id": UUID(int=42)}
        )

    def get_job_description(
        self, *, workspace_id: UUID, job_description_id: UUID
    ) -> JobDescriptionResult | None:
        snapshot = self.snapshot
        return (
            snapshot
            if (workspace_id, job_description_id)
            == (snapshot.workspace_id, snapshot.job_description_id)
            else None
        )


class Renderer:
    def __init__(self, error: PdfFailureCode | None = None) -> None:
        self.error = error
        self.html: str | None = None

    async def render_html(self, body_html: str) -> bytes:
        self.html = body_html
        if self.error is not None:
            raise PdfRenderError(self.error)
        return b"%PDF-test-renderer"


def client(renderer: Renderer | None) -> TestClient:
    name = "caliburn.modules.job_description.presentation.api.routes.export"
    assert importlib.util.find_spec(name) is not None, "尚未提供PDF下載路由"
    router = importlib.import_module(name).build_export_router(
        queries=Queries(), renderer=renderer
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_pdf_download_has_binary_contract_and_safe_headers() -> None:
    renderer = Renderer()
    with client(renderer) as connection:
        response = connection.get(
            f"/workspaces/{UUID(int=41)}/job-descriptions/{UUID(int=42)}/export.pdf"
        )
        assert response.status_code == 200
        assert response.content == b"%PDF-test-renderer"
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="job-description.pdf"'
        )
        assert renderer.html is not None
        assert "檢查設備" in renderer.html
        response = connection.get(
            f"/workspaces/{UUID(int=99)}/job-descriptions/{UUID(int=42)}/export.pdf"
        )
        assert response.status_code == 404


@pytest.mark.parametrize(
    ("error", "status"),
    [
        ("pdf_renderer_busy", 503),
        ("pdf_render_timeout", 504),
        ("pdf_font_unavailable", 503),
        ("pdf_render_failed", 503),
    ],
)
def test_renderer_failure_returns_safe_code(error: PdfFailureCode, status: int) -> None:
    with client(Renderer(error)) as connection:
        response = connection.get(
            f"/workspaces/{UUID(int=41)}/job-descriptions/{UUID(int=42)}/export.pdf"
        )
    assert response.status_code == status
    assert response.json() == {"detail": {"code": error}}


def test_unconfigured_export_is_explicitly_unavailable() -> None:
    with client(None) as connection:
        response = connection.get(
            f"/workspaces/{UUID(int=41)}/job-descriptions/{UUID(int=42)}/export.pdf"
        )
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "pdf_export_unavailable"}}
