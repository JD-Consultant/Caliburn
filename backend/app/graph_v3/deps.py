from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobProfile
from app.services.knowledge.base import KnowledgeClient
from app.services.persistence import TaskRepo, KsaRepo, DocRepo


@runtime_checkable
class PersistPort(Protocol):
    async def set_selected_ocs(self, job_profile_id: UUID, ocs_code: str) -> None: ...
    async def flush_tasks(self, job_profile_id: UUID, tasks: list[dict]) -> None: ...
    async def flush_ksa(self, job_profile_id: UUID, *, by_task: dict, attitudes: list) -> None: ...
    async def save_document(self, job_profile_id: UUID, content: dict) -> dict: ...


@runtime_checkable
class LlmPort(Protocol):
    """per-role LLM 介面（D10）。role ∈ {"deep","indicator","cheap"}。"""
    async def complete_text(self, prompt: str, *, role: str = "cheap") -> str: ...
    async def complete_json(self, prompt: str, *, role: str = "cheap", default: Any = None) -> Any: ...


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

    async def flush_ksa(self, job_profile_id: UUID, *, by_task: dict, attitudes: list) -> None:
        await KsaRepo(self.s).flush(job_profile_id, by_task=by_task, attitudes=attitudes)
        await self.s.flush()

    async def save_document(self, job_profile_id: UUID, content: dict) -> dict:
        return await DocRepo(self.s).save(job_profile_id, content)


class LiveDbPersist:
    """Live serving 的 PersistPort：每操作開一短命 session、委派 DbPersist、各自 commit
    （write-through，D16）。deps 在 app 啟動一次性注入、無 per-request scope，故用 factory。"""

    def __init__(self, session_factory):
        self._sf = session_factory

    async def set_selected_ocs(self, job_profile_id: UUID, ocs_code: str) -> None:
        async with self._sf() as s:
            await DbPersist(s).set_selected_ocs(job_profile_id, ocs_code)
            await s.commit()

    async def flush_tasks(self, job_profile_id: UUID, tasks: list[dict]) -> None:
        async with self._sf() as s:
            await DbPersist(s).flush_tasks(job_profile_id, tasks)
            await s.commit()

    async def flush_ksa(self, job_profile_id: UUID, *, by_task: dict, attitudes: list) -> None:
        async with self._sf() as s:
            await KsaRepo(s).flush(job_profile_id, by_task=by_task, attitudes=attitudes)
            await s.commit()

    async def save_document(self, job_profile_id: UUID, content: dict) -> dict:
        async with self._sf() as s:
            doc = await DbPersist(s).save_document(job_profile_id, content)
            await s.commit()
            return doc


@dataclass
class Deps:
    knowledge: KnowledgeClient
    persist: PersistPort
    llm: LlmPort | None = None
