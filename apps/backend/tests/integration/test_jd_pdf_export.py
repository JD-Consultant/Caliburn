"""真 PostgreSQL scoped 匯出：先釋放讀取連線，列印不改任何 JD 內容。"""

from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.pool import QueuePool

from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.presentation.api.routes.export import (
    build_export_router,
)
from tests.integration.content_scenarios import JD
from tests.integration.content_support import content_rows, seed_root


def test_saved_jd_export_releases_read_connection_and_enforces_workspace_scope(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    before = content_rows(pg_engine)
    calls = []

    class Renderer:
        async def render_html(self, body_html: str) -> bytes:
            assert isinstance(pg_engine.pool, QueuePool)
            assert pg_engine.pool.checkedout() == 0
            assert "職責一" in body_html
            assert "任務一" in body_html
            assert "知識一" in body_html
            assert "技能一" in body_html
            assert "JD 合成測試" not in body_html
            calls.append(body_html)
            return b"%PDF-verified-snapshot"

    app = FastAPI()
    app.include_router(
        build_export_router(
            queries=SqlAlchemyJobDescriptionQueries(pg_engine), renderer=Renderer()
        )
    )
    with TestClient(app) as client:
        saved = client.get(
            f"/workspaces/{jd_workspace_id}/job-descriptions/{JD}/export.pdf"
        )
        assert saved.status_code == 200, saved.text
        assert saved.content == b"%PDF-verified-snapshot"
        wrong_workspace = client.get(
            f"/workspaces/{uuid4()}/job-descriptions/{JD}/export.pdf"
        )
        assert wrong_workspace.status_code == 404
    assert len(calls) == 1
    assert content_rows(pg_engine) == before
