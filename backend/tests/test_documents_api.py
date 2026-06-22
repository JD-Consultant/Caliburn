"""REST document endpoints (D27 T3): GET/PATCH/finalize + ksa-pool + list doc_status.

Transaction isolation: override get_db to yield the test's transaction-bound
db_session WITHOUT committing, so every ASGI request shares one rolled-back tx.
"""
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.api.routes.documents import get_knowledge
from app.database import get_db
from app.main import app
from app.models import JobProfile, User
from app.services import ocs_doc
from app.services.knowledge.models import (
    Hit,
    Pair,
    Pairs,
    PoolGroup,
    PoolTask,
    PoolUnit,
    SearchResult,
    TaskPool,
)


class StubKnowledge:
    def __init__(self, pairs_map=None, fail=False, pool=None, hits=None):
        self.pairs_map, self.fail, self.pool = pairs_map or {}, fail, pool
        self.hits = hits or []

    async def pairs(self, ocs_code):
        if self.fail:
            raise RuntimeError("indexer down")
        return self.pairs_map.get(ocs_code, Pairs())

    async def task_pool(self, ocs_codes, *, activity_examples=3):
        if self.fail:
            raise RuntimeError("indexer down")
        return self.pool if self.pool is not None else TaskPool()

    async def search(self, query, *, level=None, hybrid=True, top_k=10):
        if self.fail:
            raise RuntimeError("indexer down")
        return SearchResult(hits=self.hits)


def _mk_pool():
    return TaskPool(
        groups=[
            PoolGroup(
                ocs_code="OC1",
                job_title="x",
                units=[
                    PoolUnit(
                        unit_id="T1",
                        unit_title="u1",
                        tasks=[
                            PoolTask(id="1", task_id="T1.1", task_title="蒐集標準"),
                            PoolTask(id="2", task_id="T1.2", task_title="分析趨勢"),
                        ],
                    )
                ],
            )
        ]
    )


@pytest_asyncio.fixture
async def client(db_session):
    async def _db():
        yield db_session  # shared session; NO commit → fixture rolls back

    app.dependency_overrides[get_db] = _db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://t", follow_redirects=True
    ) as ac:
        ac._db = db_session
        yield ac
    app.dependency_overrides.clear()


async def _mk_profile(db_session, codes=None):
    u = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(u)
    await db_session.flush()
    p = JobProfile(
        user_id=u.id,
        job_title="工程師",
        job_summary="做事",
        selected_ocs_codes=codes or [],
    )
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_get_document_no_doc_returns_skeleton(client):
    p = await _mk_profile(client._db)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/document")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "none"
    assert body["version"] == 0
    assert body["content"]["ocs_content"]["ocu_units"] == []


@pytest.mark.asyncio
async def test_patch_then_get_roundtrips(client):
    p = await _mk_profile(client._db)
    doc = {
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "tasks": [
                        {
                            "task_codes": [{"code": "T1.1", "name": "t"}],
                            "competency_blocks": [],
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": []},
    }
    r = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["version"] == 1

    r2 = await client.get(f"/api/v1/job-profiles/{p.id}/document")
    assert r2.status_code == 200
    assert r2.json()["content"] == doc


@pytest.mark.asyncio
async def test_patch_twice_no_version_bump(client):
    p = await _mk_profile(client._db)
    doc = {"ocs_content": {"ocu_units": []}, "ocs_attitude": {"attitudes": []}}
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    assert r1.json()["version"] == 1
    r2 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    assert r2.json()["version"] == 1


@pytest.mark.asyncio
async def test_finalize_success(client):
    p = await _mk_profile(client._db)
    skel = ocs_doc.skeleton(
        {"ocs_code": "OC1", "job_title": "x"},
        [{"task_name": "t", "unit_id": "T1", "unit_title": "u",
          "indexer_ref": {"task_id": "T1.1"}}],
    )
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=skel)
    assert r1.json()["version"] == 1
    r = await client.post(f"/api/v1/job-profiles/{p.id}/document/finalize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "final"
    assert body["version"] == 2


@pytest.mark.asyncio
async def test_finalize_invalid_returns_422(client):
    p = await _mk_profile(client._db)
    doc = {
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "tasks": [
                        {
                            "task_codes": [],
                            "competency_blocks": [],
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": []},
    }
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    r = await client.post(f"/api/v1/job-profiles/{p.id}/document/finalize")
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail["errors"]


@pytest.mark.asyncio
async def test_finalize_no_document_returns_400(client):
    p = await _mk_profile(client._db)
    r = await client.post(f"/api/v1/job-profiles/{p.id}/document/finalize")
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_export_returns_clean_ocs_json(client):
    p = await _mk_profile(client._db)
    skel = ocs_doc.skeleton({"ocs_code": "OC1", "job_title": "x"},
                            [{"task_name": "t", "unit_id": "T1", "unit_title": "u",
                              "indexer_ref": {"task_id": "T1.1"}}])
    skel["_pool"] = {"knowledge": [], "skills": [], "attitudes": []}
    skel["ocs_content"]["ocu_units"][0]["_uid"] = "u-x"
    skel["ocs_content"]["ocu_units"][0]["tasks"][0]["_notes"] = "工作筆記原文"
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=skel)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/document/export")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "_pool" not in body
    assert "_uid" not in body["ocs_content"]["ocu_units"][0]
    assert "_notes" not in body["ocs_content"]["ocu_units"][0]["tasks"][0]
    assert set(["version_info", "ocs_profile", "ocs_content", "ocs_attitude", "notes"]).issubset(body)


@pytest.mark.asyncio
async def test_export_no_document_returns_400(client):
    p = await _mk_profile(client._db)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/document/export")
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_ksa_pool_happy(client):
    p = await _mk_profile(client._db, codes=["OC1"])
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(
        {
            "OC1": Pairs(
                knowledge=[Pair(code="K01", name="a")],
                skills=[Pair(code="S01", name="b")],
                attitudes=[Pair(code="A01", name="c")],
            )
        }
    )
    r = await client.get(f"/api/v1/job-profiles/{p.id}/ksa-pool")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["knowledge"][0]["code"] == "K01"
    assert body["skills"][0]["code"] == "S01"
    assert body["attitudes"][0]["code"] == "A01"


@pytest.mark.asyncio
async def test_ocs_search_dedupes_by_code(client):
    p = await _mk_profile(client._db)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(
        hits=[
            Hit(id="1", ocs_code="OC1", job_title="AIoT 應用工程師"),
            Hit(id="2", ocs_code="OC1", job_title="dup chunk"),
            Hit(id="3", ocs_code="OC2", job_title="資料工程師"),
        ]
    )
    r = await client.get(f"/api/v1/job-profiles/{p.id}/ocs-search?q=AIoT")
    assert r.status_code == 200, r.text
    hits = r.json()["hits"]
    assert [h["ocs_code"] for h in hits] == ["OC1", "OC2"]
    assert hits[0]["job_title"] == "AIoT 應用工程師"


@pytest.mark.asyncio
async def test_ocs_search_blank_query_empty(client):
    p = await _mk_profile(client._db)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(
        hits=[Hit(id="1", ocs_code="OC1", job_title="x")]
    )
    r = await client.get(f"/api/v1/job-profiles/{p.id}/ocs-search?q=   ")
    assert r.status_code == 200, r.text
    assert r.json()["hits"] == []


@pytest.mark.asyncio
async def test_ocs_search_indexer_down_502(client):
    p = await _mk_profile(client._db)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail=True)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/ocs-search?q=AIoT")
    assert r.status_code == 502, r.text


@pytest.mark.asyncio
async def test_ksa_pool_indexer_down(client):
    p = await _mk_profile(client._db, codes=["OC1"])
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail=True)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/ksa-pool")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["knowledge"] == []
    assert body["skills"] == []
    assert body["attitudes"] == []


@pytest.mark.asyncio
async def test_list_doc_status(client):
    p = await _mk_profile(client._db)
    r = await client.get(f"/api/v1/job-profiles?user_id={p.user_id}")
    assert r.status_code == 200, r.text
    items = r.json()
    entry = next(i for i in items if i["id"] == str(p.id))
    assert entry["doc_status"] == "none"
    assert entry["completion"] == 0.0

    doc = {
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "tasks": [
                        {
                            "task_codes": [{"code": "T1.1", "name": "t"}],
                            "competency_blocks": [
                                {"outputs": ["o"], "indicators": [],
                                 "knowledge": [], "skills": []}
                            ],
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": []},
    }
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    r2 = await client.get(f"/api/v1/job-profiles?user_id={p.user_id}")
    entry2 = next(i for i in r2.json() if i["id"] == str(p.id))
    assert entry2["doc_status"] == "draft"
    assert entry2["completion"] > 0


def _picked(unit_title="u1"):
    return [
        {"ocs_code": "OC1", "unit_id": "T1", "unit_title": unit_title,
         "occupation_name": "AIoT", "task_id": "T1.1", "task_name": "蒐集標準", "id": "uuid-1"},
        {"ocs_code": "OC1", "unit_id": "T1", "unit_title": unit_title,
         "occupation_name": "AIoT", "task_id": "T1.2", "task_name": "分析趨勢", "id": "uuid-2"},
    ]


@pytest.mark.asyncio
async def test_set_occupations(client, db_session):
    p = await _mk_profile(client._db)
    r = await client.post(
        f"/api/v1/job-profiles/{p.id}/occupations", json={"ocs_codes": ["OC1", "OC2"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["ocs_codes"] == ["OC1", "OC2"]
    await db_session.refresh(p)
    assert p.selected_ocs_codes == ["OC1", "OC2"]


@pytest.mark.asyncio
async def test_set_occupations_refreshes_stale_draft_header(client):
    # repro: an empty draft (no ocs_code) exists before 選職類 → occupations must
    # refresh the draft header so 選任務 (FE gates on ocs_code) becomes enabled.
    p = await _mk_profile(client._db)
    await client.patch(
        f"/api/v1/job-profiles/{p.id}/document",
        json={"ocs_content": {"ocu_units": []}, "ocs_profile": {"ocs_code": ""}},
    )
    r = await client.post(
        f"/api/v1/job-profiles/{p.id}/occupations", json={"ocs_codes": ["OC1"]}
    )
    assert r.status_code == 200, r.text
    g = await client.get(f"/api/v1/job-profiles/{p.id}/document")
    assert g.json()["content"]["ocs_profile"]["ocs_code"] == "OC1"


@pytest.mark.asyncio
async def test_set_occupations_empty_400(client):
    p = await _mk_profile(client._db)
    r = await client.post(
        f"/api/v1/job-profiles/{p.id}/occupations", json={"ocs_codes": []}
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_task_candidates_grouped(client):
    p = await _mk_profile(client._db, codes=["OC1"])
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(pool=_mk_pool())
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-candidates")
    assert r.status_code == 200, r.text
    groups = r.json()["groups"]
    assert groups[0]["ocs_code"] == "OC1"
    units = groups[0]["units"]
    assert units[0]["unit_id"] == "T1"
    assert [t["task_id"] for t in units[0]["tasks"]] == ["T1.1", "T1.2"]
    assert [t["id"] for t in units[0]["tasks"]] == ["1", "2"]


@pytest.mark.asyncio
async def test_task_candidates_no_codes_empty(client):
    p = await _mk_profile(client._db)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(pool=_mk_pool())
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-candidates")
    assert r.status_code == 200, r.text
    assert r.json()["groups"] == []


@pytest.mark.asyncio
async def test_task_candidates_indexer_down_502(client):
    p = await _mk_profile(client._db, codes=["OC1"])
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail=True)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-candidates")
    assert r.status_code == 502, r.text


@pytest.mark.asyncio
async def test_build_tasks_happy(client):
    p = await _mk_profile(client._db, codes=["OC1"])
    r = await client.post(
        f"/api/v1/job-profiles/{p.id}/build-tasks", json={"picked": _picked()}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "draft" and body["version"] == 1
    units = body["content"]["ocs_content"]["ocu_units"]
    assert len(units) == 1
    assert units[0]["ocu_code"] == "T1" and units[0]["ocu_name"] == "u1"
    tasks = units[0]["tasks"]
    assert [t["task_codes"][0]["code"] for t in tasks] == ["T1.1", "T1.2"]
    assert tasks[0]["provenance"] == {"ocs_code": "OC1", "task_id": "T1.1", "id": "uuid-1"}
    assert tasks[0]["competency_blocks"][0]["knowledge"] == []


@pytest.mark.asyncio
async def test_build_tasks_cherry_pick_blank_unit_name(client):
    p = await _mk_profile(client._db, codes=["OC1"])
    r = await client.post(
        f"/api/v1/job-profiles/{p.id}/build-tasks", json={"picked": _picked(unit_title="")}
    )
    assert r.status_code == 200, r.text
    units = r.json()["content"]["ocs_content"]["ocu_units"]
    assert units[0]["ocu_name"] == ""  # 留白讓使用者自填


@pytest.mark.asyncio
async def test_build_tasks_preserves_filled_on_rebuild(client):
    p = await _mk_profile(client._db, codes=["OC1"])
    await client.post(
        f"/api/v1/job-profiles/{p.id}/build-tasks", json={"picked": _picked()}
    )
    # fill T1.1's knowledge via PATCH
    g = await client.get(f"/api/v1/job-profiles/{p.id}/document")
    doc = g.json()["content"]
    doc["ocs_content"]["ocu_units"][0]["tasks"][0]["competency_blocks"][0]["knowledge"] = [
        {"code": "K1", "name": "k"}
    ]
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    # rebuild with same picks → filled cell preserved by provenance
    r = await client.post(
        f"/api/v1/job-profiles/{p.id}/build-tasks", json={"picked": _picked()}
    )
    tasks = r.json()["content"]["ocs_content"]["ocu_units"][0]["tasks"]
    assert tasks[0]["competency_blocks"][0]["knowledge"] == [{"code": "K1", "name": "k"}]


@pytest.mark.asyncio
async def test_build_tasks_additive_adds_without_removing(client):
    p = await _mk_profile(client._db, codes=["OC1"])
    # first build: only T1.1
    r1 = await client.post(
        f"/api/v1/job-profiles/{p.id}/build-tasks", json={"picked": [_picked()[0]]}
    )
    u1 = r1.json()["content"]["ocs_content"]["ocu_units"]
    assert [t["task_codes"][0]["code"] for t in u1[0]["tasks"]] == ["T1.1"]
    # second build: only T1.2 → additive: keeps T1.1, adds T1.2 into same unit
    r2 = await client.post(
        f"/api/v1/job-profiles/{p.id}/build-tasks", json={"picked": [_picked()[1]]}
    )
    units = r2.json()["content"]["ocs_content"]["ocu_units"]
    assert len(units) == 1  # merged into the same 職責 (same ocs_code+unit_id)
    assert [t["task_codes"][0]["code"] for t in units[0]["tasks"]] == ["T1.1", "T1.2"]


@pytest.mark.asyncio
async def test_build_tasks_missing_profile_404(client):
    r = await client.post(
        f"/api/v1/job-profiles/{uuid4()}/build-tasks", json={"picked": _picked()}
    )
    assert r.status_code == 404, r.text
