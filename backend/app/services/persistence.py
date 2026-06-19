"""業務表的 write-through persistence（document-centric, D25）。

ProfileRepo: set_selected_ocs — UPDATE job_profiles.selected_ocs_codes。
DocRepo: save — INSERT document_versions，版本遞增。"""
import logging
from uuid import UUID

logger = logging.getLogger("jobintel")

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentVersion, JobProfile


class ProfileRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None:
        prof = await self.s.get(JobProfile, job_profile_id)
        if prof:
            prof.selected_ocs_codes = list(codes or [])
        await self.s.flush()


class DocRepo:
    """document_versions：每次 save 版本遞增；content 為 OCS 文件 JSONB。"""

    def __init__(self, session: AsyncSession):
        self.s = session

    async def save(self, job_profile_id: UUID, content: dict, fmt: str = "json") -> dict:
        cur_max = (await self.s.execute(
            select(func.max(DocumentVersion.version))
            .where(DocumentVersion.job_profile_id == job_profile_id)
        )).scalar()
        row = DocumentVersion(job_profile_id=job_profile_id,
                              version=(cur_max or 0) + 1,
                              content=content, status="draft")
        self.s.add(row)
        await self.s.flush()
        return self._to_dict(row)

    async def latest(self, job_profile_id: UUID) -> dict | None:
        row = (await self.s.execute(
            select(DocumentVersion)
            .where(DocumentVersion.job_profile_id == job_profile_id)
            .order_by(DocumentVersion.version.desc())
        )).scalars().first()
        return self._to_dict(row) if row else None

    @staticmethod
    def _to_dict(r: DocumentVersion) -> dict:
        return {"id": str(r.id), "version": r.version,
                "content": r.content, "status": r.status}
