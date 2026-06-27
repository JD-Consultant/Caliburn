# tests/test_task_batch_get.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint

_T = {"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT", "ocu_code": "U1", "ocu_name": "單元一",
      "task_code": "T1.1", "task_name": "任務一", "competency_blocks": [
          {"competency_level": 3, "indicators": [{"code": "P01", "text": "pt"}],
           "outputs": [], "knowledge": [{"code": "K01", "name": "k1"}], "skills": [{"code": "S01", "name": "s1"}]}]}

def test_batch_get_returns_blocks_and_urn():
    fake = FakeQdrant(retrieve_points=[FakePoint(payload=_T, id="pid1")])
    out = service.batch_get_tasks(fake, "ocs_v3", ids=["pid1"])
    t = out["tasks"][0]
    assert t["id"] == "pid1" and t["urn"] == "ocs:OC1:T:T1.1"
    assert t["ocu_code"] == "U1" and t["task_code"] == "T1.1" and t["ocs_name"] == "JT"
    assert t["competency_blocks"][0]["knowledge"] == [{"code": "K01", "name": "k1"}]
    assert t["competency_blocks"][0]["indicators"] == [{"code": "P01", "text": "pt"}]
