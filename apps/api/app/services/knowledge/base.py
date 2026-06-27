"""KnowledgeClient 介面：節點依賴此 Protocol，不依賴 HTTP 細節。
日後換 transport（如 MCP）= 換 adapter，節點不動。"""
from typing import Protocol

from app.services.knowledge.models import (
    CompetencyPool,
    OccupationDetail,
    OccupationSearchResponse,
    OccupationTasks,
    TaskSearchResponse,
)


class KnowledgeClient(Protocol):
    async def search_occupations(self, query: str, *, top_k: int = 10) -> OccupationSearchResponse: ...

    async def search_tasks(self, query: str, *, top_k: int = 10) -> TaskSearchResponse: ...

    async def occupation(self, ocs_code: str) -> OccupationDetail: ...

    async def competencies(self, ocs_code: str) -> CompetencyPool: ...

    async def occupation_tasks(self, ocs_code: str) -> OccupationTasks: ...

    async def healthz(self) -> bool: ...
