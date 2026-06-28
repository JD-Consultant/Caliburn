"""jd-ocs-indexer query API 的 typed HTTP client（KnowledgeClient 實作）。
日後要外部多客戶，indexer 端加 MCP surface 即可，本 client 不變。"""
import httpx

from app.core.knowledge_dto import (
    CompetencyPool,
    OccupationDetail,
    OccupationSearchResponse,
    OccupationTasks,
    TaskSearchResponse,
)


class HttpIndexerClient:
    def __init__(self, base_url: str, api_key: str = "", timeout_s: float = 30.0):
        self._base = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(base_url=self._base, headers=headers, timeout=timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def search_occupations(self, query: str, *, top_k: int = 10) -> OccupationSearchResponse:
        resp = await self._client.post("/occupations/search", json={"query": query, "top_k": top_k})
        resp.raise_for_status()
        return OccupationSearchResponse.model_validate(resp.json())

    async def search_tasks(self, query: str, *, top_k: int = 10) -> TaskSearchResponse:
        resp = await self._client.post("/tasks/search", json={"query": query, "top_k": top_k})
        resp.raise_for_status()
        return TaskSearchResponse.model_validate(resp.json())

    async def occupation(self, ocs_code: str) -> OccupationDetail:
        resp = await self._client.get(f"/occupations/{ocs_code}")
        resp.raise_for_status()
        return OccupationDetail.model_validate(resp.json())

    async def competencies(self, ocs_code: str) -> CompetencyPool:
        resp = await self._client.get(f"/occupations/{ocs_code}/competencies")
        resp.raise_for_status()
        return CompetencyPool.model_validate(resp.json())

    async def occupation_tasks(self, ocs_code: str) -> OccupationTasks:
        resp = await self._client.get(f"/occupations/{ocs_code}/tasks")
        resp.raise_for_status()
        return OccupationTasks.model_validate(resp.json())

    async def healthz(self) -> bool:
        try:
            resp = await self._client.get("/healthz")
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            return False
