from fastapi.testclient import TestClient
from qdrant_client.http.exceptions import UnexpectedResponse


def test_search_route_ok(make_app, make_qdrant, fake_point):
    fake = make_qdrant(query_points=[fake_point(
        payload={"chunk_key": "k", "chunk_level": "profile", "ocs_code": "OC1", "job_title": "JT"},
        score=0.9,
    )])
    with TestClient(make_app(fake)) as c:
        r = c.post("/search", json={"query": "hello", "hybrid": False, "top_k": 3})
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "dense"
        assert body["hits"][0]["ocs_code"] == "OC1"


def test_search_route_empty_query_422(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant())) as c:
        r = c.post("/search", json={"query": ""})
        assert r.status_code == 422


def test_task_pool_route(make_app, make_qdrant):
    block = {
        "ocs_code": "OC1", "chunk_level": "block", "job_title": "JT", "unit_order": 1,
        "unit_id": "U1", "unit_title": "U1", "task_ids": ["T1"], "task_titles": ["t1"],
        "work_activity_terms": ["a1"],
    }
    with TestClient(make_app(make_qdrant(scroll_pages=[([block], None)]))) as c:
        r = c.post("/task-pool", json={"ocs_codes": ["OC1"], "activity_examples": 1})
        assert r.status_code == 200
        assert r.json()["groups"][0]["units"][0]["tasks"][0]["task_id"] == "T1"


def test_pairs_route_404(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant(scroll_pages=[([], None)]))) as c:
        r = c.get("/profile/NOPE/pairs")
        assert r.status_code == 404


def test_healthz_route(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant())) as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_stats_route(make_app, make_qdrant):
    fake = make_qdrant(counts={"__total__": 5, "profile": 1, "unit": 2, "block": 2})
    with TestClient(make_app(fake)) as c:
        r = c.get("/stats")
        assert r.status_code == 200
        assert r.json()["total_points"] == 5


def test_healthz_route_degraded(make_app):
    # Qdrant unreachable -> healthcheck reports degraded -> 503
    class Down:
        def get_collections(self):
            raise RuntimeError("boom")

    with TestClient(make_app(Down())) as c:
        r = c.get("/healthz")
        assert r.status_code == 503
        assert r.json()["status"] == "degraded"


def test_search_route_qdrant_unexpected_502(make_app):
    # Qdrant UnexpectedResponse from the query path -> exception handler -> 502
    class Boom:
        def query_points(self, **kw):
            raise UnexpectedResponse(status_code=500, reason_phrase="err", content=b"", headers=None)

    with TestClient(make_app(Boom())) as c:
        r = c.post("/search", json={"query": "hi", "hybrid": False})
        assert r.status_code == 502
