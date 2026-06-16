from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobProfile
from app.services.knowledge.base import KnowledgeClient
from app.services.persistence import TaskRepo


class PersistPort(Protocol):
    async def set_selected_ocs(self, job_profile_id: UUID, ocs_code: str) -> None: ...
    async def flush_tasks(self, job_profile_id: UUID, tasks: list[dict]) -> None: ...


class DbPersist:
    """正式環境的 PersistPort：用一個 AsyncSession 寫業務表。"""
    def __init__(self, session: AsyncSession):
        self.s = session

    async def set_selected_ocs(self, job_profile_id: UUID, ocs_code: str) -> None:
        prof = await self.s.get(JobProfile, job_profile_id)
        if prof:
            prof.selected_ocs_code = ocs_code
        await self.s.flush()

    async def flush_tasks(self, job_profile_id: UUID, tasks: list[dict]) -> None:
        await TaskRepo(self.s).flush(job_profile_id, tasks)


@dataclass
class Deps:
    knowledge: KnowledgeClient
    persist: PersistPort
