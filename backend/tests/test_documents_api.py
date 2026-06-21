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
from app.services.knowledge.models import Pair, Pairs


class StubKnowledge:
    def __init__(self, pairs_map=None, fail=False):
        self.pairs_map, self.fail = pairs_map or {}, fail

    async def pairs(self, ocs_code):
        if self.fail:
            raise RuntimeError("indexer down")
        return self.pairs_map.get(ocs_code, Pairs())


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
