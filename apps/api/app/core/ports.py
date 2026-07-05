"""Ports (hexagonal inside ring): Protocols the application/graph depend on.

Adapters in app/adapters/ implement these; nothing here imports adapters,
authoring, or fastapi. See docs/specs/2026-06-28-api-hexagonal-untangle-research.md.
"""
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from app.core.knowledge_dto import (
    CompetencyPool,
    MatchResponse,
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

    # 相似比對(ADR 0022):items = [{id, text, sources}](池 rows 原樣,api 端不強型別化)
    async def match(self, kind: str, items: list[dict]) -> MatchResponse: ...

    async def healthz(self) -> bool: ...


@runtime_checkable
class PersistPort(Protocol):
    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None: ...
    async def save_document(self, job_profile_id: UUID, content: dict) -> dict: ...


@runtime_checkable
class LlmPort(Protocol):
    """per-role LLM 介面（D10）。role ∈ {"deep","indicator","cheap","select"}。

    三句話型(ADR 0024):complete_text=自由文字(best-effort)、complete_json=提示層
    JSON(事後 parse)、select_schema=**輸出必須符合 schema/enum**(adapter 以 provider
    原生受限解碼兌現;值承重的目錄類/指令詞彙表一律走這條)。
    """
    async def complete_text(self, prompt: str, *, role: str = "cheap") -> str: ...
    async def complete_json(self, prompt: str, *, role: str = "cheap", default: Any = None) -> Any: ...
    async def select_schema(self, prompt: str, schema: dict, *,
                            role: str = "select", schema_name: str = "output") -> Any: ...


KnowledgeClient = KnowledgePort  # back-compat alias (node call sites unchanged)
