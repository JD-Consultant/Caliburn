from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge.base import KnowledgeClient
from app.services.persistence import ProfileRepo, DocRepo


@runtime_checkable
class PersistPort(Protocol):
    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None: ...
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


@dataclass
class Deps:
    knowledge: KnowledgeClient
    persist: PersistPort
    llm: LlmPort | None = None
