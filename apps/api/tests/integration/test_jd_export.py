"""A current formal export never reads the active candidate or job-file identity text."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.adapters.pdf_renderer import PdfRenderError
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.transport.http.jd_export import router
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_export import JdExportWorkflow

pytestmark = pytest.mark.postgres


class RecordingRenderer:
    body = ""

    async def render_html(self, body_html: str) -> bytes:
        self.body = body_html
        return b"%PDF-test-renderer"


def test_export_reads_formal_not_active_candidate_or_employee_name(client: TestClient) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "不可匯出檔名",
                "employee_name": "不可匯出姓名",
            },
        ).json()["job_file_id"]
    )
    formal = client.get(f"/api/job-files/{file_id}/jd/profile").json()
    changed = client.post(
        f"/api/job-files/{file_id}/jd/profile",
        json={
            "command_id": str(uuid4()),
            "expected_revision_id": formal["revision_id"],
            "changes": [{"action": "set_field", "field": "job_title", "value": "正式職稱"}],
        },
    )
    assert changed.status_code == 200
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "尚未完成的輸入"},
    ).json()
    sessions = client.app.state.database.sessions

    async def make_preview() -> None:
        async with sessions.begin() as session:
            writer = await executions.claim_writer(
                session,
                ExecutionScope(
                    file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN
                ),
                writer_id=uuid4(),
            )
        workflow = JdCandidateWorkflow(sessions)
        start = await workflow.start(writer)
        await workflow.edit(
            writer,
            start.scope,
            ReviseJdProfile(
                uuid4(),
                start.revision_id,
                (SetProfileField(ProfileField.JOB_TITLE, "不可匯出候選"),),
            ),
        )

    client.portal.call(make_preview)
    renderer = RecordingRenderer()
    result = client.portal.call(JdExportWorkflow(sessions, renderer).export_current, file_id)
    assert result == b"%PDF-test-renderer"
    assert "正式職稱" in renderer.body
    for forbidden in ("不可匯出檔名", "不可匯出姓名", "不可匯出候選", "尚未完成的輸入"):
        assert forbidden not in renderer.body
    client.app.state.jd_export_workflow = JdExportWorkflow(sessions, renderer)
    client.app.include_router(router)
    download = client.get(f"/api/job-files/{file_id}/jd/export.pdf")
    assert download.status_code == 200
    assert download.content == b"%PDF-test-renderer"
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["cache-control"] == "no-store"
    assert "attachment" in download.headers["content-disposition"]
    assert client.get(f"/api/job-files/{uuid4()}/jd/export.pdf").status_code == 404


class FailingRenderer:
    async def render_html(self, body_html: str) -> bytes:
        raise PdfRenderError("pdf_font_unavailable")


def test_renderer_failure_is_not_an_empty_pdf_or_success(client: TestClient) -> None:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "失敗測試", "employee_name": "合成"},
    ).json()
    client.app.state.jd_export_workflow = JdExportWorkflow(
        client.app.state.database.sessions, FailingRenderer()
    )
    client.app.include_router(router)
    result = client.get(f"/api/job-files/{created['job_file_id']}/jd/export.pdf")
    assert result.status_code == 503
    assert result.json() == {"detail": {"code": "pdf_font_unavailable"}}
