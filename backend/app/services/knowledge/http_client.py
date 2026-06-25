"""jd-ocs-indexer query API 的 typed HTTP client（KnowledgeClient 實作）。
日後要外部多客戶，indexer 端加 MCP surface 即可，本 client 不變。"""
import httpx

from app.services.knowledge.models import (
    CompetencyPool,
    OccupationDetail,
    OccupationSearchResponse,
    OccupationTasks,
    Pairs,
    ProfileMeta,
    SearchResult,
    TaskPool,
    TaskSearchResponse,
    TasksByIdResult,
)


class HttpIndexerClient:
    def __init__(self, base_url: str, api_key: str = "", timeout_s: float = 30.0):
        self._base = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(base_url=self._base, headers=headers, timeout=timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def search(self, query: str, *, level: str | None = None,
                     hybrid: bool = True, top_k: int = 10) -> SearchResult:
        payload: dict = {"query": query, "hybrid": hybrid, "top_k": top_k}
        if level:
            payload["level"] = level
        resp = await self._client.post("/search", json=payload)
        resp.raise_for_status()
        return SearchResult.model_validate(resp.json())

    async def task_pool(self, ocs_codes: list[str], *,
                        activity_examples: int = 3) -> TaskPool:
        resp = await self._client.post("/task-pool", json={
            "ocs_codes": ocs_codes, "activity_examples": activity_examples})
        resp.raise_for_status()
        return TaskPool.model_validate(resp.json())

    async def pairs(self, ocs_code: str) -> Pairs:
        resp = await self._client.get(f"/profile/{ocs_code}/pairs")
        resp.raise_for_status()
        return Pairs.model_validate(resp.json())

    async def profile(self, ocs_code: str) -> ProfileMeta:
        resp = await self._client.get(f"/profile/{ocs_code}")
        resp.raise_for_status()
        return ProfileMeta.model_validate(resp.json())

    async def tasks_by_id(self, ids: list[str]) -> TasksByIdResult:
        resp = await self._client.post("/tasks/by-id", json={"ids": ids})
        resp.raise_for_status()
        return TasksByIdResult.model_validate(resp.json())

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
