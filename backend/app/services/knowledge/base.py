"""KnowledgeClient 介面：節點依賴此 Protocol，不依賴 HTTP 細節。
日後換 transport（如 MCP）= 換 adapter，節點不動。"""
from typing import Protocol

from app.services.knowledge.models import (
    Pairs,
    ProfileMeta,
    SearchResult,
    TaskPool,
    TasksByIdResult,
)


class KnowledgeClient(Protocol):
    async def search(self, query: str, *, level: str | None = None,
                     hybrid: bool = True, top_k: int = 10) -> SearchResult: ...

    async def task_pool(self, ocs_codes: list[str], *,
                        activity_examples: int = 3) -> TaskPool: ...

    async def pairs(self, ocs_code: str) -> Pairs: ...

    async def profile(self, ocs_code: str) -> ProfileMeta: ...

    async def tasks_by_id(self, ids: list[str]) -> TasksByIdResult: ...

    async def healthz(self) -> bool: ...
