# tests/test_occupation_detail.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint

_PROFILE = {
    "chunk_level": "profile", "schema_version": "v4", "ocs_code": "OC1v2",
    "ocs_name": {"job_category_name": None, "occupation_name": "資料分析師"},
    "job_description": "負責資料分析", "ocs_level": 4,
    "job_categories": [{"code": "JC1", "name": "資訊類"}],
    "occupations": [{"code": "OCC1", "name": "分析師"}],
    "industries": [{"code": "I1", "name": "資訊業"}],
    "attitudes": [{"code": "A01", "name": "主動積極"}],
    "prerequisites": ["大學以上學歷"], "supplements": ["須具備證照"],
}

def test_get_occupation_projects_v4_profile():
    fake = FakeQdrant(scroll_pages=[([FakePoint(payload=_PROFILE)], None)])
    out = service.get_occupation(fake, "ocs_v3", ocs_code="OC1v2")
    assert out["ocs_code"] == "OC1v2" and out["urn"] == "ocs:OC1v2"
    assert out["ocs_name"] == {"job_category_name": None, "occupation_name": "資料分析師"}
    assert out["job_categories"] == [{"code": "JC1", "name": "資訊類"}]
    assert out["occupations"] == [{"code": "OCC1", "name": "分析師"}]
    assert out["industries"] == [{"code": "I1", "name": "資訊業"}]
    assert out["attitudes"] == [{"code": "A01", "name": "主動積極"}]
    assert out["job_description"] == "負責資料分析" and out["ocs_level"] == 4

def test_get_occupation_missing_returns_none():
    assert service.get_occupation(FakeQdrant(scroll_pages=[([], None)]), "c", ocs_code="X") is None
