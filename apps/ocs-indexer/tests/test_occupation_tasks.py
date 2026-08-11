# tests/test_occupation_tasks.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint

_PROFILE = {"chunk_level": "profile", "ocs_code": "OC1", "ocs_name": {"occupation_name": "JT"}}
def _task(tc, tn):
    return {"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT",
            "ocu_code": "U1", "ocu_name": "單元一", "task_code": tc, "task_name": tn,
            "competency_blocks": []}

def test_occupation_tasks_grouped_by_unit():
    fake = FakeQdrant(scroll_pages=[([FakePoint(payload=_PROFILE)], None),
                                    ([FakePoint(payload=_task("T1.2", "二")), FakePoint(payload=_task("T1.1", "一"))], None)])
    out = service.get_occupation_tasks(fake, "ocs_v3", ocs_code="OC1")
    assert out["ocs_code"] == "OC1" and out["ocs_name"] == "JT"
    unit = out["units"][0]
    assert unit["ocu_code"] == "U1" and unit["urn"] == "ocs:OC1:U:U1"
    assert [t["task_code"] for t in unit["tasks"]] == ["T1.1", "T1.2"]   # sorted
    assert unit["tasks"][0]["urn"] == "ocs:OC1:T:T1.1"
