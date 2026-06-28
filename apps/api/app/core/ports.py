"""Ports (hexagonal inside ring): Protocols the application/graph depend on.

Adapters in app/adapters/ implement these; nothing here imports adapters,
graph_v3, or fastapi. See docs/specs/2026-06-28-api-hexagonal-untangle-research.md.
"""
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from app.core.knowledge_dto import (
    CompetencyPool,
    OccupationDetail,
    OccupationSearchResponse,
    OccupationTasks,
    TaskSearchResponse,
)


class KnowledgePort(Protocol):
    async def search_occupations(self, query: str, *, top_k: int = 10) -> OccupationSearchResponse: ...

    async def search_tasks(self, query: str, *, top_k: int = 10) -> TaskSearchResponse: ...

    async def occupation(self, ocs_code: str) -> OccupationDetail: ...

    async def competencies(self, ocs_code: str) -> CompetencyPool: ...

    async def occupation_tasks(self, ocs_code: str) -> OccupationTasks: ...

    async def healthz(self) -> bool: ...


@runtime_checkable
class PersistPort(Protocol):
    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None: ...
    async def save_document(self, job_profile_id: UUID, content: dict) -> dict: ...


@runtime_checkable
class LlmPort(Protocol):
    """per-role LLM 介面（D10）。role ∈ {"deep","indicator","cheap"}。"""
    async def complete_text(self, prompt: str, *, role: str = "cheap") -> str: ...
    async def complete_json(self, prompt: str, *, role: str = "cheap", default: Any = None) -> Any: ...


KnowledgeClient = KnowledgePort  # back-compat alias (node call sites unchanged)
