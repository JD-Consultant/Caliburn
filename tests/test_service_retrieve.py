from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint


def test_retrieve_tasks_projects_full_payload_with_id():
    pts = [FakePoint(id="pt-1", payload={
        "chunk_level": "task", "ocs_code": "OC1", "unit_id": "U1", "unit_title": "U",
        "task_id": "T1.1", "task_title": "任務一", "competency_level": 3,
        "activity_examples": ["a1", "a2"],
        "k_pairs": [{"code": "K01", "name": "k1"}], "s_pairs": [{"code": "S01", "name": "s1"}],
        "output_pairs": [{"code": "O01", "name": "o1"}],
    })]
    out = service.retrieve_tasks(FakeQdrant(retrieve_points=pts), "ocs_v3", ids=["pt-1"])
    t = out["tasks"][0]
    assert t["id"] == "pt-1" and t["ocs_code"] == "OC1"
    assert t["unit_id"] == "U1" and t["task_id"] == "T1.1" and t["task_title"] == "任務一"
    assert t["competency_level"] == 3 and t["activity_examples"] == ["a1", "a2"]
    assert t["k_pairs"] == [{"code": "K01", "name": "k1"}]
    assert t["s_pairs"] == [{"code": "S01", "name": "s1"}]
    assert t["output_pairs"] == [{"code": "O01", "name": "o1"}]


def test_retrieve_tasks_empty_when_none_found():
    assert service.retrieve_tasks(FakeQdrant(retrieve_points=[]), "ocs_v3", ids=["nope"]) == {"tasks": []}
