"""知識包端點測試(ADR 0021):per-code 並行、append 序、partial 降級、全掛 502。"""
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.api.routes.documents import get_knowledge
from app.database import get_db
from app.main import app
from app.models import JobProfile, User
from app.core.knowledge_dto import (
    CitableItem,
    CodeName,
    CompetencyPool,
    OccupationDetail,
    OccupationTasks,
    OcsName,
    SourceRef,
    TaskRef,
    UnitTasks,
)


class StubKnowledge:
    """兩個 code 的完整三資源 stub;fail_codes 內的 code 任一資源丟例外。"""

    def __init__(self, fail_codes=()):
        self.fail = set(fail_codes)

    def _check(self, code):
        if code in self.fail:
            raise RuntimeError("indexer down")

    async def occupation(self, ocs_code):
        self._check(ocs_code)
        return OccupationDetail(
            ocs_code=ocs_code, ocs_name=OcsName(occupation_name=f"{ocs_code}職業"),
            attitudes=[CodeName(code="A01", name=f"{ocs_code}態度")],
            prerequisites=["大學以上"], job_description="描述", ocs_level=4)

    async def occupation_tasks(self, ocs_code):
        self._check(ocs_code)
        return OccupationTasks(ocs_code=ocs_code, ocs_name=f"{ocs_code}職業", units=[
            UnitTasks(ocu_code="T1", ocu_name="維護",
                      tasks=[TaskRef(task_code="T1.1", task_name="保養")])])

    async def competencies(self, ocs_code):
        self._check(ocs_code)
        return CompetencyPool(ocs_code=ocs_code, knowledge=[
            CitableItem(code="K01", name="統計", ocs_code=ocs_code,
                        sources=[SourceRef(task_code="T1.1", competency_level=3)])])


@pytest_asyncio.fixture
async def client(db_session):
    async def _db():
        yield db_session
    app.dependency_overrides[get_db] = _db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t", follow_redirects=True) as ac:
        ac._db = db_session
        yield ac
    app.dependency_overrides.clear()


async def _mk_profile(db_session, codes):
    u = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(u)
    await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師", selected_ocs_codes=codes)
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_knowledge_happy_two_codes(client):
    p = await _mk_profile(client._db, ["OC1", "OC2"])
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge()
    r = await client.get(f"/api/v1/job-profiles/{p.id}/knowledge")
    assert r.status_code == 200, r.text
    pack = r.json()
    assert [d["ocs_code"] for d in pack["occupation_details"]] == ["OC1", "OC2"]  # 保序
    # 同名池列合併、srcs 累積(append 序)
    assert [s["ocs_code"] for s in pack["pools"]["knowledge"]["統計"]["srcs"]] == ["OC1", "OC2"]
    assert pack["pools"]["tasks"]["保養"]["srcs"] == ["ocs:OC1:T:T1.1", "ocs:OC2:T:T1.1"]
    assert pack["source_tasks"]["ocs:OC1:T:T1.1"]["k_refs"] == ["統計"]
    assert pack["meta"] == {"partial": False}


@pytest.mark.asyncio
async def test_knowledge_one_code_down_degrades_partial(client):
    p = await _mk_profile(client._db, ["OC1", "OC2"])
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail_codes=["OC2"])
    r = await client.get(f"/api/v1/job-profiles/{p.id}/knowledge")
    assert r.status_code == 200, r.text
    pack = r.json()
    assert [d["ocs_code"] for d in pack["occupation_details"]] == ["OC1"]
    assert pack["meta"] == {"partial": True}


@pytest.mark.asyncio
async def test_knowledge_all_down_502(client):
    p = await _mk_profile(client._db, ["OC1", "OC2"])
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail_codes=["OC1", "OC2"])
    r = await client.get(f"/api/v1/job-profiles/{p.id}/knowledge")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_knowledge_no_codes_empty_pack(client):
    p = await _mk_profile(client._db, [])
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge()
    r = await client.get(f"/api/v1/job-profiles/{p.id}/knowledge")
    assert r.status_code == 200, r.text
    pack = r.json()
    assert pack["occupation_details"] == [] and pack["source_tasks"] == {}
    assert all(v == {} for v in pack["pools"].values())
    assert pack["meta"] == {"partial": False}
