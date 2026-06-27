"""T1 infra + T2 /ai/recommend-ks (D28). FakeLlm + stub indexer — no API key needed."""
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.api.routes.ai import get_llm
from app.api.routes.documents import get_knowledge
from app.config import settings
from app.database import get_db
from app.graph_v3.llm import OpenRouterLlm
from app.main import app
from app.models import JobProfile, User
from app.services.knowledge.models import CitableItem, CompetencyPool, SourceRef
from tests.conftest_graph import FakeLlm


class StubKnowledge:
    """Minimal KnowledgeClient for /ai/*: only competencies is exercised here."""

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
        knowledge=[
            CitableItem(code="K01", name="標準知識", sources=src),
            CitableItem(code="K02", name="法規知識", sources=src),
        ],
        skills=[CitableItem(code="S01", name="分析技能", sources=src)],
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


async def _mk_profile_with_task(db_session, cat_id="cat-1", code="T1.1"):
    u = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(u)
    await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師", job_summary="做事", selected_ocs_codes=["OC1"])
    db_session.add(p)
    await db_session.flush()
    return p


def _doc_with_task(cat_id="cat-1", code="T1.1"):
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
                            "provenance": {"ocs_code": "OC1", "task_code": code},
                        }
                    ],
                }
            ]
        },
        "ocs_attitude": {"attitudes": []},
    }


# ---- T1 infra ----

def test_get_llm_none_without_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    assert get_llm() is None


def test_get_llm_builds_openrouter_with_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test")
    assert isinstance(get_llm(), OpenRouterLlm)


def test_ai_router_mounted():
    assert "/api/v1/ai/recommend-ks" in app.openapi()["paths"]


# ---- T2 /ai/recommend-ks ----

@pytest.mark.asyncio
async def test_recommend_ks_no_note_returns_full_catalog(client):
    p = await _mk_profile_with_task(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: FakeLlm(json={"knowledge": [], "skills": []})
    r = await client.post("/api/v1/ai/recommend-ks", json={"profile_id": str(p.id), "task_key": "T1.1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [k["code"] for k in body["knowledge"]] == ["K01", "K02"]
    assert [s["code"] for s in body["skills"]] == ["S01"]
    assert all(k["source"] == "catalog" for k in body["knowledge"])
    assert all("reason" not in k for k in body["knowledge"])


@pytest.mark.asyncio
async def test_recommend_ks_with_note_filters_and_adds_reason(client):
    p = await _mk_profile_with_task(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: FakeLlm(
        json={"knowledge": [{"code": "K01", "reason": "與描述高度相關"}], "skills": []}
    )
    r = await client.post(
        "/api/v1/ai/recommend-ks",
        json={"profile_id": str(p.id), "task_key": "T1.1", "note": "我主要做標準蒐集"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [k["code"] for k in body["knowledge"]] == ["K01"]
    assert body["knowledge"][0]["reason"] == "與描述高度相關"
    assert body["knowledge"][0]["source"] == "catalog"
    assert body["skills"] == []


@pytest.mark.asyncio
async def test_recommend_ks_no_llm_degrades_to_catalog(client):
    p = await _mk_profile_with_task(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post(
        "/api/v1/ai/recommend-ks",
        json={"profile_id": str(p.id), "task_key": "T1.1", "note": "有描述但沒有 LLM"},
    )
    assert r.status_code == 200, r.text
    assert [k["code"] for k in r.json()["knowledge"]] == ["K01", "K02"]


@pytest.mark.asyncio
async def test_recommend_ks_indexer_down_returns_empty(client):
    p = await _mk_profile_with_task(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail=True)
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post("/api/v1/ai/recommend-ks", json={"profile_id": str(p.id), "task_key": "T1.1"})
    assert r.status_code == 200, r.text
    assert r.json() == {"knowledge": [], "skills": []}


@pytest.mark.asyncio
async def test_recommend_ks_task_not_found_404(client):
    p = await _mk_profile_with_task(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_with_task())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge()
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post("/api/v1/ai/recommend-ks", json={"profile_id": str(p.id), "task_key": "T9.9"})
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_recommend_ks_missing_fields_400(client):
    p = await _mk_profile_with_task(client._db)
    r = await client.post("/api/v1/ai/recommend-ks", json={"profile_id": str(p.id)})
    assert r.status_code == 400, r.text
