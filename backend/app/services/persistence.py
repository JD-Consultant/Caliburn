"""業務表的 write-through persistence（hydrate/flush）。

flush 以 (job_profile_id, task_name) 為穩定鍵做 row-level upsert：
既有 row 更新、不存在才新建、清單中消失的刪除 → 保 row id 穩定，免斷 ksa_items FK。"""
import logging
from uuid import UUID

logger = logging.getLogger("jobintel")

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompanyTask, DocumentVersion, KsaItem

# flush 寫回的清單欄（深問產出之外）
_TASK_FIELDS = ("task_name", "description", "category", "frequency",
                "responsibility_type", "source", "indexer_ref")


class TaskRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def hydrate(self, job_profile_id: UUID) -> list[dict]:
        rows = (await self.s.execute(
            select(CompanyTask)
            .where(CompanyTask.job_profile_id == job_profile_id)
            .order_by(CompanyTask.sort_order)
        )).scalars().all()
        return [self._to_dict(r) for r in rows]

    async def flush(self, job_profile_id: UUID, tasks: list[dict]) -> None:
        existing = {r.task_name: r for r in (await self.s.execute(
            select(CompanyTask).where(CompanyTask.job_profile_id == job_profile_id)
        )).scalars().all()}
        seen: set[str] = set()
        for i, t in enumerate(tasks):
            name = (t.get("task_name") or "").strip()
            if not name:
                continue
            seen.add(name)
            row = existing.get(name) or CompanyTask(job_profile_id=job_profile_id, task_name=name)
            for f in _TASK_FIELDS:
                if f in t:
                    setattr(row, f, t[f])
            row.sort_order = i
            if name not in existing:
                self.s.add(row)
        for name, row in existing.items():
            if name not in seen:
                await self.s.delete(row)
        await self.s.flush()

    @staticmethod
    def _to_dict(r: CompanyTask) -> dict:
        return {"id": str(r.id), "task_name": r.task_name, "description": r.description,
                "category": r.category, "frequency": r.frequency,
                "responsibility_type": r.responsibility_type, "source": r.source,
                "indexer_ref": r.indexer_ref, "sort_order": r.sort_order}


_SRC_TO_DB = {"catalog": "icap_official", "company": "company_defined"}
_DB_TO_SRC = {v: k for k, v in _SRC_TO_DB.items()}


class KsaRepo:
    """ksa_items：K/S 帶 task_id（per task）、A task_id=NULL（全域）。
    穩定鍵 (ksa_type, content, task_id) row-level upsert。"""

    def __init__(self, session: AsyncSession):
        self.s = session

    async def _task_id_map(self, job_profile_id: UUID) -> dict[str, "UUID"]:
        rows = (await self.s.execute(
            select(CompanyTask).where(CompanyTask.job_profile_id == job_profile_id)
        )).scalars().all()
        out = {}
        for r in rows:
            key = (r.indexer_ref or {}).get("task_id") or r.task_name
            if key in out:
                logger.warning("jobintel: _task_id_map duplicate key %r — overwriting", key)
            out[key] = r.id
        return out

    async def hydrate(self, job_profile_id: UUID) -> dict:
        rows = (await self.s.execute(
            select(KsaItem).where(KsaItem.job_profile_id == job_profile_id)
            .order_by(KsaItem.created_at, KsaItem.id)
        )).scalars().all()
        id_to_key = {v: k for k, v in (await self._task_id_map(job_profile_id)).items()}
        by_task: dict[str, dict] = {}
        attitudes: list[dict] = []
        bucket = {"K": "knowledge", "S": "skills"}
        for r in rows:
            item = {"id": str(r.id), "content": r.content,
                    "source": _DB_TO_SRC.get(r.source_type, "company"), "icap_ref": r.icap_ref}
            if r.ksa_type == "A":
                attitudes.append(item)
            elif r.ksa_type in bucket and r.task_id is not None:
                key = id_to_key.get(r.task_id)
                if key:
                    by_task.setdefault(key, {"knowledge": [], "skills": []})[bucket[r.ksa_type]].append(item)
        return {"by_task": by_task, "attitudes": attitudes}

    async def flush(self, job_profile_id: UUID, *, by_task: dict, attitudes: list) -> None:
        existing = {(r.ksa_type, r.content, r.task_id): r for r in (await self.s.execute(
            select(KsaItem).where(KsaItem.job_profile_id == job_profile_id)
        )).scalars().all()}
        tmap = await self._task_id_map(job_profile_id)
        seen: set = set()

        def _upsert(code: str, item: dict, task_id):
            content = (item.get("content") or "").strip()
            if not content:
                return
            key = (code, content, task_id)
            seen.add(key)
            row = existing.get(key) or KsaItem(
                job_profile_id=job_profile_id, ksa_type=code, content=content, task_id=task_id)
            row.source_type = _SRC_TO_DB.get(item.get("source", "company"), "company_defined")
            row.icap_ref = item.get("icap_ref")
            if key not in existing:
                self.s.add(row)

        for tkey, ks in (by_task or {}).items():
            tid = tmap.get(tkey)
            if tid is None:
                logger.warning("jobintel: flush skipping K/S for unresolved task key %r", tkey)
                continue
            for item in ks.get("knowledge", []):
                _upsert("K", item, tid)
            for item in ks.get("skills", []):
                _upsert("S", item, tid)
        for item in (attitudes or []):
            _upsert("A", item, None)

        for key, row in existing.items():
            if key not in seen:
                await self.s.delete(row)
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
                              version=(cur_max or 0) + 1, format=fmt,
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
        return {"id": str(r.id), "version": r.version, "format": r.format,
                "content": r.content, "status": r.status}
