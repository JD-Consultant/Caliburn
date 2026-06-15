import httpx
import pytest
import respx

from app.services.knowledge.http_client import HttpIndexerClient

BASE = "http://idx.test"


@pytest.fixture
def client():
    return HttpIndexerClient(base_url=BASE, api_key="", timeout_s=5.0)


@respx.mock
async def test_search_calls_endpoint_and_parses(client):
    route = respx.post(f"{BASE}/search").mock(return_value=httpx.Response(
        200, json={"mode": "hybrid", "hits": [{"id": "p1", "score": 0.8,
                   "chunk_level": "task", "ocs_code": "OC1", "task_title": "t"}]}))
    r = await client.search("hello", top_k=5)
    assert route.called
    assert r.hits[0].id == "p1"


@respx.mock
async def test_pairs_uses_path_param(client):
    respx.get(f"{BASE}/profile/OC1/pairs").mock(return_value=httpx.Response(
        200, json={"ocs_code": "OC1", "knowledge": [{"code": "K01", "name": "k"}],
                   "skills": [], "attitudes": [], "outputs": [],
                   "prerequisites": [], "supplements": []}))
    r = await client.pairs("OC1")
    assert r.knowledge[0].code == "K01"


@respx.mock
async def test_tasks_by_id_posts_ids(client):
    respx.post(f"{BASE}/tasks/by-id").mock(return_value=httpx.Response(
        200, json={"tasks": [{"id": "x", "task_id": "T1.1", "task_title": "t",
                   "competency_level": 3}]}))
    r = await client.tasks_by_id(["x"])
    assert r.tasks[0].competency_level == 3
