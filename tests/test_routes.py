from fastapi.testclient import TestClient
from qdrant_client.http.exceptions import UnexpectedResponse


def test_search_route_ok(make_app, make_qdrant, fake_point):
    fake = make_qdrant(query_points=[fake_point(
        id="pt-1",
        payload={"chunk_level": "task", "ocs_code": "OC1", "task_id": "T1",
                 "task_title": "t", "job_title": "JT"},
        score=0.9,
    )])
    with TestClient(make_app(fake)) as c:
        r = c.post("/search", json={"query": "hello", "hybrid": False, "top_k": 3})
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "dense"
        assert body["hits"][0]["id"] == "pt-1" and body["hits"][0]["task_id"] == "T1"


def test_search_route_empty_query_422(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant())) as c:
        r = c.post("/search", json={"query": ""})
        assert r.status_code == 422


def test_task_pool_route(make_app, make_qdrant, fake_point):
    profile = {"chunk_level": "profile", "ocs_code": "OC1", "job_title": "JT"}
    task = fake_point(id="OC1-T1", payload={
        "chunk_level": "task", "ocs_code": "OC1", "unit_id": "U1", "unit_title": "U1",
        "task_id": "T1", "task_title": "t1", "activity_examples": ["a1"],
    })
    # build_task_pool scrolls profiles first (job_title), then task points
    fake = make_qdrant(scroll_pages=[([profile], None), ([task], None)])
    with TestClient(make_app(fake)) as c:
        r = c.post("/task-pool", json={"ocs_codes": ["OC1"], "activity_examples": 1})
        assert r.status_code == 200
        t = r.json()["groups"][0]["units"][0]["tasks"][0]
        assert t["task_id"] == "T1" and t["id"] == "OC1-T1"


def test_tasks_by_id_route(make_app, make_qdrant, fake_point):
    pt = fake_point(id="pt-1", payload={
        "chunk_level": "task", "ocs_code": "OC1", "unit_id": "U1", "unit_title": "U1",
        "task_id": "T1.1", "task_title": "t1", "competency_level": 3,
        "activity_examples": ["a1"], "k_pairs": [{"code": "K01", "name": "k1"}],
        "s_pairs": [], "output_pairs": [{"code": "O01", "name": "o1"}],
    })
    with TestClient(make_app(make_qdrant(retrieve_points=[pt]))) as c:
        r = c.post("/tasks/by-id", json={"ids": ["pt-1"]})
        assert r.status_code == 200
        t = r.json()["tasks"][0]
        assert t["id"] == "pt-1" and t["task_id"] == "T1.1" and t["competency_level"] == 3
        assert t["k_pairs"] == [{"code": "K01", "name": "k1"}]
        assert t["output_pairs"] == [{"code": "O01", "name": "o1"}]


def test_tasks_by_id_empty_ids_422(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant())) as c:
        r = c.post("/tasks/by-id", json={"ids": []})
        assert r.status_code == 422


def test_pairs_route_404(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant(scroll_pages=[([], None)]))) as c:
        r = c.get("/profile/NOPE/pairs")
        assert r.status_code == 404


def test_profile_route_ok(make_app, make_qdrant, fake_point):
    profile = fake_point(payload={
        "chunk_level": "profile", "ocs_code": "OC1", "job_title": "JT",
        "job_category": "人資類", "job_category_codes": ["BHR"],
        "industry_codes": ["A"], "industry_names": ["農林漁牧業"],
        "occupation_codes": ["2422"], "occupation_names": ["人資專業人員"],
        "job_description": "desc", "ocs_level": 4,
        "all_a_pairs": [{"code": "A01", "name": "主動"}],
        "prerequisites": ["x"], "supplements": ["y"],
    })
    with TestClient(make_app(make_qdrant(scroll_pages=[([profile], None)]))) as c:
        r = c.get("/profile/OC1")
        assert r.status_code == 200
        b = r.json()
        assert b["ocs_code"] == "OC1" and b["ocs_level"] == 4
        assert b["job_category"] == {"code": "BHR", "name": "人資類"}
        assert b["industries"] == [{"code": "A", "name": "農林漁牧業"}]
        assert b["attitudes"] == [{"code": "A01", "name": "主動"}]
        assert b["prerequisites"] == ["x"] and b["supplements"] == ["y"]


def test_profile_route_404(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant(scroll_pages=[([], None)]))) as c:
        r = c.get("/profile/NOPE")
        assert r.status_code == 404


def test_healthz_route(make_app, make_qdrant):
    with TestClient(make_app(make_qdrant())) as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_stats_route(make_app, make_qdrant):
    fake = make_qdrant(counts={"__total__": 55, "profile": 5, "task": 50})
    with TestClient(make_app(fake)) as c:
        r = c.get("/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["total_points"] == 55
        assert body["by_level"] == {"profile": 5, "task": 50}


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
