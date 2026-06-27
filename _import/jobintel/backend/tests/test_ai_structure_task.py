"""T5 /ai/structure-task (D28). FakeLlm — no indexer, no DB, no API key needed."""
import httpx
import pytest
import pytest_asyncio

from app.api.routes.ai import get_llm
from app.database import get_db
from app.main import app
from tests.conftest_graph import FakeLlm


@pytest_asyncio.fixture
async def client(db_session):
    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://t", follow_redirects=True
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_structure_task_no_llm_echoes_description(client):
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post("/api/v1/ai/structure-task", json={"description": "  幫忙整理資料  "})
    assert r.status_code == 200, r.text
    assert r.json() == {"task_name": "幫忙整理資料", "unit_suggestion": ""}


@pytest.mark.asyncio
async def test_structure_task_llm_returns_structured(client):
    app.dependency_overrides[get_llm] = lambda: FakeLlm(
        json={"task_name": "資料蒐集與彙整", "unit_suggestion": "資料管理職責"}
    )
    r = await client.post(
        "/api/v1/ai/structure-task", json={"description": "幫忙整理資料", "ocs_codes": ["OC1"]}
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"task_name": "資料蒐集與彙整", "unit_suggestion": "資料管理職責"}


@pytest.mark.asyncio
async def test_structure_task_llm_junk_falls_back(client):
    app.dependency_overrides[get_llm] = lambda: FakeLlm(json=["not", "a", "dict"])
    r = await client.post("/api/v1/ai/structure-task", json={"description": "幫忙整理資料"})
    assert r.status_code == 200, r.text
    assert r.json() == {"task_name": "幫忙整理資料", "unit_suggestion": ""}


@pytest.mark.asyncio
async def test_structure_task_blank_description_400(client):
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post("/api/v1/ai/structure-task", json={"description": "   "})
    assert r.status_code == 400, r.text
