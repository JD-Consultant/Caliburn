# tests/test_competencies.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint

_PROFILE = {"chunk_level": "profile", "ocs_code": "OC1", "ocs_name": {"occupation_name": "JT"},
            "attitudes": [{"code": "A01", "name": "主動"}]}
_T1 = {"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT", "ocu_code": "U1", "ocu_name": "單元一",
       "task_code": "T1.1", "task_name": "任務一", "competency_blocks": [
           {"competency_level": 3, "indicators": [{"code": "P1.1.1", "text": "p text"}],
            "outputs": [{"code": "O1.1.1", "name": "o1"}],
            "knowledge": [{"code": "K01", "name": "k1"}], "skills": [{"code": "S01", "name": "s1"}]}]}
_T2 = {"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT", "ocu_code": "U1", "ocu_name": "單元一",
       "task_code": "T1.2", "task_name": "任務二", "competency_blocks": [
           {"competency_level": 3, "indicators": [], "outputs": [],
            "knowledge": [{"code": "K01", "name": "k1"}], "skills": []}]}  # K01 reused -> multi-source

def test_competencies_citable_items_with_provenance():
    fake = FakeQdrant(scroll_pages=[([FakePoint(payload=_PROFILE)], None),
                                    ([FakePoint(payload=_T1), FakePoint(payload=_T2)], None)])
    out = service.get_competencies(fake, "ocs_v3", ocs_code="OC1")
    k = out["knowledge"]
    assert len(k) == 1 and k[0]["id"] == "ocs:OC1:K:K01" and k[0]["type"] == "K" and k[0]["name"] == "k1"
    # K01 appears in T1.1 and T1.2 -> two sources
    assert [s["task_code"] for s in k[0]["sources"]] == ["T1.1", "T1.2"]
    assert k[0]["sources"][0]["competency_level"] == 3
    assert out["indicators"][0]["id"] == "ocs:OC1:P:P1.1.1" and out["indicators"][0]["text"] == "p text"
    assert out["outputs"][0]["id"] == "ocs:OC1:O:O1.1.1"
    assert out["attitudes"][0]["id"] == "ocs:OC1:A:A01" and out["attitudes"][0]["sources"] == []

def test_competencies_missing_profile_returns_none():
    assert service.get_competencies(FakeQdrant(scroll_pages=[([], None)]), "c", ocs_code="X") is None
