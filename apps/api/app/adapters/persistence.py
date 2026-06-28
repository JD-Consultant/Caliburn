"""業務表的 write-through persistence（document-centric, D25）。

ProfileRepo: set_selected_ocs — UPDATE job_profiles.selected_ocs_codes。
DocRepo: save — INSERT document_versions，版本遞增。"""
import logging
from uuid import UUID

logger = logging.getLogger("jobintel")

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentVersion, JobProfile


def compute_completion(content: dict) -> float:
    """OCS 文件填充率：header 與 A 各算一格，每 task 4 格(O/P/K/S)。

    分子 filled = 1(header) + (1 if A) + Σ 每 task 已填格數；
    分母 total  = 4*num_tasks + 1(A) + 1(header)。回傳 filled/total ∈ [0,1]。"""
    units = (content.get("ocs_content") or {}).get("ocu_units") or []
    num_tasks = 0
    filled = 1  # header
    for unit in units:
        for task in (unit.get("tasks") or []):
            num_tasks += 1
            blocks = task.get("competency_blocks") or []
            block = blocks[0] if blocks else {}
            for key in ("outputs", "indicators", "knowledge", "skills"):
                if block.get(key):
                    filled += 1
    if (content.get("ocs_attitude") or {}).get("attitudes"):
        filled += 1
    total = 4 * num_tasks + 1 + 1  # A + header
    return filled / total


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

    async def save(self, job_profile_id: UUID, content: dict) -> dict:
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

    async def _latest_row(self, job_profile_id: UUID) -> DocumentVersion | None:
        return (await self.s.execute(
            select(DocumentVersion)
            .where(DocumentVersion.job_profile_id == job_profile_id)
            .order_by(DocumentVersion.version.desc())
        )).scalars().first()

    async def upsert_draft(self, job_profile_id: UUID, content: dict) -> dict:
        """最新列若為 draft → 原地更新 content（版本不變）；否則 INSERT 新 draft。"""
        row = await self._latest_row(job_profile_id)
        if row is not None and row.status == "draft":
            row.content = content
        else:
            row = DocumentVersion(job_profile_id=job_profile_id,
                                  version=(row.version if row else 0) + 1,
                                  content=content, status="draft")
            self.s.add(row)
        await self.s.flush()
        return self._to_dict(row)

    async def finalize(self, job_profile_id: UUID, content: dict | None = None) -> dict:
        """INSERT 新 final 列（版本遞增）；無任何文件則 raise ValueError。"""
        row = await self._latest_row(job_profile_id)
        if row is None:
            raise ValueError("no document to finalize")
        final = DocumentVersion(job_profile_id=job_profile_id,
                                version=row.version + 1,
                                content=content if content is not None else row.content,
                                status="final")
        self.s.add(final)
        await self.s.flush()
        return self._to_dict(final)

    async def status_of(self, job_profile_id: UUID) -> tuple[str, float]:
        row = await self._latest_row(job_profile_id)
        if row is None:
            return ("none", 0.0)
        return (row.status, compute_completion(row.content))

    @staticmethod
    def _to_dict(r: DocumentVersion) -> dict:
        return {"id": str(r.id), "version": r.version,
                "content": r.content, "status": r.status}


class DbPersist:
    """正式環境的 PersistPort：用一個 AsyncSession 寫業務表。"""
    def __init__(self, session: AsyncSession):
        self.s = session

    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None:
        await ProfileRepo(self.s).set_selected_ocs(job_profile_id, codes)

    async def save_document(self, job_profile_id: UUID, content: dict) -> dict:
        return await DocRepo(self.s).save(job_profile_id, content)


class LiveDbPersist:
    """Live serving 的 PersistPort：每操作開一短命 session、委派、各自 commit
    （write-through，D16）。deps 在 app 啟動一次性注入、無 per-request scope，故用 factory。"""

    def __init__(self, session_factory):
        self._sf = session_factory

    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None:
        async with self._sf() as s:
            await ProfileRepo(s).set_selected_ocs(job_profile_id, codes)
            await s.commit()

    async def save_document(self, job_profile_id: UUID, content: dict) -> dict:
        async with self._sf() as s:
            doc = await DocRepo(s).save(job_profile_id, content)
            await s.commit()
            return doc
