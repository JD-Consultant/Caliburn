"""Fix the formal revision before reading and printing the complete JD."""

from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import consistent_read_session
from caliburn.features.job_description import persistence, work_queries
from caliburn.features.job_description.export_projection import project_jd_export_html
from caliburn.features.job_files import queries as file_queries


class HtmlPdfRenderer(Protocol):
    async def render_html(self, body_html: str) -> bytes: ...


class JdExportWorkflow:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], renderer: HtmlPdfRenderer
    ) -> None:
        self.sessions = sessions
        self.renderer = renderer

    async def export_current(self, job_file_id: UUID) -> bytes:
        async with consistent_read_session(self.sessions) as session:
            await file_queries.read_job_file(session, job_file_id)
            document = await persistence.read_document(session, job_file_id)
            revision_id = document.current_revision_id
            profile = await persistence.read_revision(session, job_file_id, revision_id)
            work = await work_queries.read_work_at(session, job_file_id, revision_id)
        # The snapshot survives root deletion; Chromium renders after releasing the DB lease.
        return await self.renderer.render_html(project_jd_export_html(profile.profile, work))
