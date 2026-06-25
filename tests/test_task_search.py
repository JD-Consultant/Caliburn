# tests/test_task_search.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint, StubEmbedder

def test_search_tasks_returns_identity_only():
    hit = FakePoint(payload={"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT",
                             "ocu_code": "U1", "ocu_name": "單元一",
                             "task_code": "T1.1", "task_name": "任務一",
                             "competency_blocks": [{"knowledge": [{"code": "K01", "name": "k"}]}]}, score=0.7)
    out = service.search_tasks(FakeQdrant(query_points=[hit]), StubEmbedder(), "c", query="任務")
    h = out["hits"][0]
    assert h["task_code"] == "T1.1" and h["urn"] == "ocs:OC1:T:T1.1" and h["score"] == 0.7
    assert h["ocu_code"] == "U1" and h["ocs_name"] == "JT"
    assert "competency_blocks" not in h   # identity only
