"""T6 /ai/clarify (D28). FakeLlm — no indexer, no DB, no API key needed."""
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
async def test_clarify_no_llm_returns_null(client):
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post("/api/v1/ai/clarify", json={"task": "蒐集標準", "note": "做事"})
    assert r.status_code == 200, r.text
    assert r.json() == {"question": None}


@pytest.mark.asyncio
async def test_clarify_llm_returns_question(client):
    app.dependency_overrides[get_llm] = lambda: FakeLlm(json={"question": "你蒐集的是哪一類標準？"})
    r = await client.post("/api/v1/ai/clarify", json={"task": "蒐集標準", "note": "做事"})
    assert r.status_code == 200, r.text
    assert r.json() == {"question": "你蒐集的是哪一類標準？"}


@pytest.mark.asyncio
async def test_clarify_llm_returns_null_question(client):
    app.dependency_overrides[get_llm] = lambda: FakeLlm(json={"question": None})
    r = await client.post("/api/v1/ai/clarify", json={"task": "蒐集標準", "note": "已很完整的說明"})
    assert r.status_code == 200, r.text
    assert r.json() == {"question": None}


@pytest.mark.asyncio
async def test_clarify_llm_junk_returns_null(client):
    app.dependency_overrides[get_llm] = lambda: FakeLlm(json=["nope"])
    r = await client.post("/api/v1/ai/clarify", json={"task": "蒐集標準", "note": "做事"})
    assert r.status_code == 200, r.text
    assert r.json() == {"question": None}
