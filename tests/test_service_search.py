from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint, StubEmbedder


def test_search_projects_task_hit_with_id():
    pt = FakePoint(id="pt-1", score=0.9, payload={
        "chunk_level": "task", "ocs_code": "OC1", "unit_id": "U1", "unit_title": "U",
        "task_id": "T1.1", "task_title": "任務一", "competency_level": 3,
        "activity_examples": ["a1"], "k_pairs": [{"code": "K01", "name": "k"}],
        "s_pairs": [], "output_pairs": [{"code": "O01", "name": "o"}],
    })
    fake = FakeQdrant(query_points=[pt])
    out = service.search(fake, StubEmbedder(), "ocs_v3", query="x", hybrid=False, top_k=5)
    assert out["mode"] == "dense"
    h = out["hits"][0]
    assert h["id"] == "pt-1" and h["task_id"] == "T1.1" and h["competency_level"] == 3
    assert h["activity_examples"] == ["a1"] and h["output_pairs"] == [{"code": "O01", "name": "o"}]
    assert "snippet" not in h and "task_titles" not in h


def test_search_projects_profile_hit():
    pt = FakePoint(id="pf-1", score=0.8, payload={
        "chunk_level": "profile", "ocs_code": "OC1", "job_title": "JT",
        "job_description": "desc", "is_current": True, "ocs_level": 4,
    })
    out = service.search(FakeQdrant(query_points=[pt]), StubEmbedder(), "ocs_v3", query="x", hybrid=True)
    h = out["hits"][0]
    assert h["chunk_level"] == "profile" and h["job_title"] == "JT" and h["job_description"] == "desc"
