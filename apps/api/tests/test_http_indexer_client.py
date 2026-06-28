import httpx
import pytest
import respx

from app.adapters.knowledge_http import HttpIndexerClient

BASE = "http://idx.test"


@pytest.fixture
def client():
    return HttpIndexerClient(base_url=BASE, api_key="", timeout_s=5.0)


@respx.mock
async def test_search_occupations_calls_endpoint(client):
    route = respx.post(f"{BASE}/occupations/search").mock(return_value=httpx.Response(
        200, json={"hits": [{"ocs_code": "OC1", "urn": "ocs:OC1", "ocs_name": "JT",
                             "job_description": "d", "ocs_level": 4, "score": 0.8}]}))
    r = await client.search_occupations("hello", top_k=5)
    assert route.called and r.hits[0].ocs_code == "OC1" and r.hits[0].score == 0.8


@respx.mock
async def test_search_tasks_calls_endpoint(client):
    route = respx.post(f"{BASE}/tasks/search").mock(return_value=httpx.Response(
        200, json={"hits": [{"ocs_code": "OC1", "ocs_name": "JT", "ocu_code": "U1",
                             "ocu_name": "單元一", "task_code": "T1.1", "task_name": "任務一",
                             "urn": "ocs:OC1:T:T1.1", "score": 0.9}]}))
    r = await client.search_tasks("q", top_k=5)
    assert route.called
    hit = r.hits[0]
    assert hit.ocs_code == "OC1" and hit.task_code == "T1.1" and hit.task_name == "任務一"
    assert hit.urn == "ocs:OC1:T:T1.1" and hit.score == 0.9


@respx.mock
async def test_occupation_uses_path_param(client):
    respx.get(f"{BASE}/occupations/OC1").mock(return_value=httpx.Response(
        200, json={"ocs_code": "OC1", "urn": "ocs:OC1",
                   "ocs_name": {"occupation_name": "JT"}, "job_categories": [],
                   "occupations": [], "industries": [], "attitudes": [],
                   "job_description": "", "prerequisites": [], "supplements": []}))
    r = await client.occupation("OC1")
    assert r.ocs_name.occupation_name == "JT"


@respx.mock
async def test_competencies_uses_path(client):
    respx.get(f"{BASE}/occupations/OC1/competencies").mock(return_value=httpx.Response(
        200, json={"ocs_code": "OC1", "knowledge": [], "skills": [], "outputs": [],
                   "indicators": [], "attitudes": []}))
    r = await client.competencies("OC1")
    assert r.ocs_code == "OC1"


@respx.mock
async def test_occupation_tasks_uses_path(client):
    respx.get(f"{BASE}/occupations/OC1/tasks").mock(return_value=httpx.Response(
        200, json={"ocs_code": "OC1", "ocs_name": "JT", "units": [
            {"ocu_code": "U1", "ocu_name": "單元一", "urn": "ocs:OC1:U:U1",
             "tasks": [{"task_code": "T1.1", "task_name": "任務一", "urn": "ocs:OC1:T:T1.1"}]}]}))
    r = await client.occupation_tasks("OC1")
    assert r.units[0].tasks[0].task_code == "T1.1"
