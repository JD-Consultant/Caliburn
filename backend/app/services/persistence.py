"""業務表的 write-through persistence（hydrate/flush）。

flush 以 (job_profile_id, task_name) 為穩定鍵做 row-level upsert：
既有 row 更新、不存在才新建、清單中消失的刪除 → 保 row id 穩定，免斷 ksa_items FK。"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompanyTask

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
