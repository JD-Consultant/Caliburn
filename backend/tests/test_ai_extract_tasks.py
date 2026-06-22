"""T4 /ai/extract-tasks (D28). FakeLlm + stub indexer (task_pool) — no API key needed."""
import httpx
import pytest
import pytest_asyncio

from app.api.routes.ai import get_llm
from app.api.routes.documents import get_knowledge
from app.database import get_db
from app.main import app
from app.services.knowledge.models import PoolGroup, PoolTask, PoolUnit, TaskPool
from tests.conftest_graph import FakeLlm


class StubKnowledge:
    """Minimal KnowledgeClient for /ai/extract-tasks: only task_pool is exercised."""

    def __init__(self, pool=None, fail=False):
        self.pool = pool or TaskPool()
        self.fail = fail
        self.calls = []

    async def task_pool(self, ocs_codes, *, activity_examples=3):
        self.calls.append(list(ocs_codes))
        if self.fail:
            raise RuntimeError("indexer down")
        return self.pool


def _pool():
    return TaskPool(
        groups=[
            PoolGroup(
                ocs_code="OC1",
                units=[
                    PoolUnit(
                        unit_id="U1",
                        tasks=[
                            PoolTask(id="cat-1", task_id="T1.1", task_title="蒐集標準"),
                            PoolTask(id="cat-2", task_id="T1.2", task_title="撰寫報告"),
                        ],
                    )
                ],
            )
        ]
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
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_extract_tasks_no_llm_returns_empty(client):
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: None
    r = await client.post(
        "/api/v1/ai/extract-tasks", json={"intake": "我做標準蒐集", "ocs_codes": ["OC1"]}
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"suggested_task_ids": [], "custom_candidates": []}


@pytest.mark.asyncio
async def test_extract_tasks_llm_keeps_known_ids_and_maps_customs(client):
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: FakeLlm(
        json={"suggested_task_ids": ["cat-1"], "custom_candidates": ["客製任務A", "客製任務B"]}
    )
    r = await client.post(
        "/api/v1/ai/extract-tasks", json={"intake": "我做標準蒐集和一些客製事務", "ocs_codes": ["OC1"]}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["suggested_task_ids"] == ["cat-1"]
    assert body["custom_candidates"] == [{"name": "客製任務A"}, {"name": "客製任務B"}]


@pytest.mark.asyncio
async def test_extract_tasks_unknown_id_is_dropped(client):
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool())
    app.dependency_overrides[get_llm] = lambda: FakeLlm(
        json={"suggested_task_ids": ["cat-2", "cat-999"], "custom_candidates": []}
    )
    r = await client.post(
        "/api/v1/ai/extract-tasks", json={"intake": "做事", "ocs_codes": ["OC1"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["suggested_task_ids"] == ["cat-2"]


@pytest.mark.asyncio
async def test_extract_tasks_indexer_down_returns_empty(client):
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail=True)
    app.dependency_overrides[get_llm] = lambda: FakeLlm(
        json={"suggested_task_ids": ["cat-1"], "custom_candidates": ["x"]}
    )
    r = await client.post(
        "/api/v1/ai/extract-tasks", json={"intake": "我做標準蒐集", "ocs_codes": ["OC1"]}
    )
    assert r.status_code == 200, r.text
    # candidates empty (indexer down) → no known ids to keep; customs still none-kept
    assert r.json()["suggested_task_ids"] == []
