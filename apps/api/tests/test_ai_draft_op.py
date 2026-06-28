"""T3 /ai/draft-op (D28). FakeLlm + stub indexer — no API key needed."""
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.api.routes.ai import get_llm
from app.api.routes.documents import get_knowledge
from app.database import get_db
from app.main import app
from app.models import JobProfile, User
from app.core.knowledge_dto import CitableItem, CompetencyPool, SourceRef
from tests.conftest_graph import FakeLlm


class StubKnowledge:
    """Minimal KnowledgeClient for /ai/draft-op: only competencies is exercised."""

    def __init__(self, pool=None, fail=False):
        self.pool = pool
        self.fail = fail
        self.calls = []

    async def competencies(self, ocs_code):
        self.calls.append(ocs_code)
        if self.fail:
            raise RuntimeError("indexer down")
        return self.pool or CompetencyPool(ocs_code=ocs_code)


def _pool(task_code="T1.1"):
    src = [SourceRef(task_code=task_code)]
    return CompetencyPool(
        ocs_code="OC1",
        outputs=[
            CitableItem(code="O01", name="月報表", sources=src),
            CitableItem(code="O02", name="分析摘要", sources=src),
        ],
        indicators=[
            CitableItem(code="P01", text="蒐集資料並彙整", sources=src),
            CitableItem(code="P02", text="撰寫分析報告", sources=src),
        ],
    )


@pytest_asyncio.fixture
async def client(db_session):
    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://t", follow_redirects=True
    ) as ac:
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


def _doc_with_task(code="T1.1", provenance=None):
    return {
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "u",
                    "tasks": [
                        {
                            "task_codes": [{"code": code, "name": "蒐集標準"}],
                            "competency_blocks": [{"outputs": [], "indicators": [],
                                                   "knowledge": [], "skills": []}],
                            "provenance": {"ocs_code": "OC1", "task_code": code}
                            if provenance is None else provenance,
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": []},
    }


@pytest.mark.asyncio
async def test_draft_op_no_note_returns_full_catalog(client):
    p = await _mk_profile(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: FakeLlm(json={"outputs": [], "indicators": []})
    r = await client.post("/api/v1/ai/draft-op", json={"profile_id": str(p.id), "task_key": "T1.1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [o["name"] for o in body["outputs"]] == ["月報表", "分析摘要"]
    assert [i["text"] for i in body["indicators"]] == ["蒐集資料並彙整", "撰寫分析報告"]
    assert all(o["source"] == "catalog" for o in body["outputs"])
    assert all(i["source"] == "catalog" for i in body["indicators"])


@pytest.mark.asyncio
async def test_draft_op_with_note_returns_ai_drafts(client):
    p = await _mk_profile(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: FakeLlm(
        json={"outputs": ["客製產出"], "indicators": ["客製指標"]}
    )
    r = await client.post(
        "/api/v1/ai/draft-op",
        json={"profile_id": str(p.id), "task_key": "T1.1", "note": "我主要做標準蒐集"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [o["name"] for o in body["outputs"]] == ["客製產出"]
    assert [i["text"] for i in body["indicators"]] == ["客製指標"]
    assert all(o["source"] == "ai" for o in body["outputs"])
    assert all(i["source"] == "ai" for i in body["indicators"])


@pytest.mark.asyncio
async def test_draft_op_no_llm_degrades_to_catalog(client):
    p = await _mk_profile(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post(
        "/api/v1/ai/draft-op",
        json={"profile_id": str(p.id), "task_key": "T1.1", "note": "有描述但沒有 LLM"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [o["name"] for o in body["outputs"]] == ["月報表", "分析摘要"]
    assert all(o["source"] == "catalog" for o in body["outputs"])


@pytest.mark.asyncio
async def test_draft_op_indexer_down_returns_empty(client):
    p = await _mk_profile(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail=True)
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post("/api/v1/ai/draft-op", json={"profile_id": str(p.id), "task_key": "T1.1"})
    assert r.status_code == 200, r.text
    assert r.json() == {"outputs": [], "indicators": []}


@pytest.mark.asyncio
async def test_draft_op_task_not_found_404(client):
    p = await _mk_profile(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge()
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post("/api/v1/ai/draft-op", json={"profile_id": str(p.id), "task_key": "T9.9"})
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_draft_op_missing_fields_400(client):
    p = await _mk_profile(client._db)
    r = await client.post("/api/v1/ai/draft-op", json={"profile_id": str(p.id)})
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_draft_op_thin_task_returns_empty(client):
    p = await _mk_profile(client._db)
    await client.patch(
        f"/api/v1/job-profiles/{p.id}/document",
        json=_doc_with_task(provenance={}),
    )
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post("/api/v1/ai/draft-op", json={"profile_id": str(p.id), "task_key": "T1.1"})
    assert r.status_code == 200, r.text
    assert r.json() == {"outputs": [], "indicators": []}
