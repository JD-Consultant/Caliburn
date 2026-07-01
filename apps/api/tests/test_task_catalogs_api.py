"""階段1 批次 task-catalogs 端點：每個 ocs_code 只撈一次池、依 task_key 切片。"""
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.api.routes.documents import get_knowledge
from app.database import get_db
from app.main import app
from app.models import JobProfile, User
from app.core.knowledge_dto import CitableItem, CompetencyPool, SourceRef


class StubKnowledge:
    def __init__(self, pool=None, fail=False):
        self.pool = pool
        self.fail = fail
        self.calls = []

    async def competencies(self, ocs_code):
        self.calls.append(ocs_code)
        if self.fail:
            raise RuntimeError("indexer down")
        return self.pool or CompetencyPool(ocs_code=ocs_code)


def _pool_two_tasks():
    """OC1 池含 T1.1(K01,S01,O1,P1) 與 T1.2(K02)。"""
    return CompetencyPool(
        ocs_code="OC1",
        knowledge=[
            CitableItem(code="K01", name="標準知識", sources=[SourceRef(task_code="T1.1", competency_level=3)]),
            CitableItem(code="K02", name="法規知識", sources=[SourceRef(task_code="T1.2")]),
        ],
        skills=[CitableItem(code="S01", name="分析技能", sources=[SourceRef(task_code="T1.1")])],
        outputs=[CitableItem(code="O1", name="標準清單", sources=[SourceRef(task_code="T1.1")])],
        indicators=[CitableItem(code="P1", text="完成蒐集", sources=[SourceRef(task_code="T1.1")])],
    )


def _doc_two_tasks_same_ocs():
    def task(code, name):
        return {
            "task_codes": [{"code": code, "name": name}],
            "competency_blocks": [{"outputs": [], "indicators": [], "knowledge": [], "skills": []}],
            "provenance": {"ocs_code": "OC1", "task_code": code},
        }
    return {
        "ocs_content": {"ocu_units": [{"ocu_code": "T1", "ocu_name": "u",
                                       "tasks": [task("T1.1", "蒐集標準"), task("T1.2", "彙整法規")]}]},
        "ocs_attitude": {"attitudes": []},
    }


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


async def _mk_profile(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(u)
    await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師", job_summary="做事", selected_ocs_codes=["OC1"])
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_task_catalogs_batches_pool_once_per_ocs_code(client):
    p = await _mk_profile(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_two_tasks_same_ocs())
    stub = StubKnowledge(_pool_two_tasks())
    app.dependency_overrides[get_knowledge] = lambda: stub
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-catalogs")
    assert r.status_code == 200, r.text
    cats = r.json()["catalogs"]
    assert set(cats) == {"T1.1", "T1.2"}
    assert [k["code"] for k in cats["T1.1"]["knowledge"]] == ["K01"]
    assert [s["code"] for s in cats["T1.1"]["skills"]] == ["S01"]
    assert [o["code"] for o in cats["T1.1"]["outputs"]] == ["O1"]
    assert [i["code"] for i in cats["T1.1"]["indicators"]] == ["P1"]
    assert cats["T1.1"]["competency_level"] == 3
    assert [k["code"] for k in cats["T1.2"]["knowledge"]] == ["K02"]
    # 核心:同一 ocs_code 的池只撈一次(兩任務不重撈)
    assert stub.calls == ["OC1"]


@pytest.mark.asyncio
async def test_task_catalogs_skips_custom_tasks(client):
    p = await _mk_profile(client._db)
    doc = _doc_two_tasks_same_ocs()
    doc["ocs_content"]["ocu_units"][0]["tasks"].append({
        "task_codes": [{"code": "T1.3", "name": "自訂"}],
        "competency_blocks": [{"outputs": [], "indicators": [], "knowledge": [], "skills": []}],
        "provenance": {"ocs_code": "", "task_code": ""},
    })
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool_two_tasks())
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-catalogs")
    assert r.status_code == 200, r.text
    assert "T1.3" not in r.json()["catalogs"]


@pytest.mark.asyncio
async def test_task_catalogs_indexer_down_degrades_empty(client):
    p = await _mk_profile(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_two_tasks_same_ocs())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail=True)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-catalogs")
    assert r.status_code == 200, r.text
    # enrichment 降級：仍 200 但標 meta.partial=true（ADR 0018）
    assert r.json() == {"catalogs": {}, "meta": {"partial": True}}


@pytest.mark.asyncio
async def test_task_catalogs_no_document_empty(client):
    p = await _mk_profile(client._db)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool_two_tasks())
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-catalogs")
    assert r.status_code == 200, r.text
    # 沒任務 → 沒撈池 → 非降級
    assert r.json() == {"catalogs": {}, "meta": {"partial": False}}
