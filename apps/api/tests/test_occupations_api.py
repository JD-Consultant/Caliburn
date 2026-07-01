"""根層職類目錄搜尋 GET /api/v1/occupations?q=(ADR 0019)。

原 ocs-search(掛 job-profile 下)的測試搬家 + 對齊新契約:回應欄位
`occupations`(AIP-132 複數資源名)、search-only(空 q 回空)、critical 502。
不碰 DB(全域目錄、無 profile 檢查)。
"""
import httpx
import pytest
import pytest_asyncio

from app.api.deps import get_knowledge
from app.main import app
from app.core.knowledge_dto import OccupationHit, OccupationSearchResponse


class StubKnowledge:
    def __init__(self, hits=None, fail=False):
        self.hits, self.fail = hits or [], fail

    async def search_occupations(self, query, *, top_k=10):
        if self.fail:
            raise RuntimeError("indexer down")
        return OccupationSearchResponse(hits=self.hits)


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_occupations_search_dedupes_by_code(client):
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(
        hits=[
            OccupationHit(ocs_code="OC1", ocs_name="AIoT 應用工程師"),
            OccupationHit(ocs_code="OC1", ocs_name="dup chunk"),
            OccupationHit(ocs_code="OC2", ocs_name="資料工程師"),
        ]
    )
    r = await client.get("/api/v1/occupations?q=AIoT")
    assert r.status_code == 200, r.text
    occs = r.json()["occupations"]
    assert [o["ocs_code"] for o in occs] == ["OC1", "OC2"]
    assert occs[0]["ocs_name"] == "AIoT 應用工程師"


@pytest.mark.asyncio
async def test_occupations_search_blank_query_empty(client):
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(
        hits=[OccupationHit(ocs_code="OC1", ocs_name="x")]
    )
    r = await client.get("/api/v1/occupations?q=   ")
    assert r.status_code == 200, r.text
    assert r.json()["occupations"] == []


@pytest.mark.asyncio
async def test_occupations_search_missing_q_422(client):
    # search-only collection:q 為必填(indexer 無 list-all,不假裝能 List)。
    r = await client.get("/api/v1/occupations")
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_occupations_search_indexer_down_502(client):
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail=True)
    r = await client.get("/api/v1/occupations?q=AIoT")
    assert r.status_code == 502, r.text
