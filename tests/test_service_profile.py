"""D29: GET /profile/{ocs_code} profile-metadata projection."""
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint


def _profile_point():
    return FakePoint(payload={
        "chunk_level": "profile", "ocs_code": "OC1",
        "job_title": "農業人力資源管理師",
        "job_category": "人力資源類", "job_category_codes": ["BHR"],
        "industry_codes": ["A"], "industry_names": ["農林漁牧業"],
        "occupation_codes": ["2422"], "occupation_names": ["人力資源專業人員"],
        "job_description": "規劃並執行人力資源管理",
        "ocs_level": 4,
        "all_a_pairs": [{"code": "A01", "name": "主動積極"}],
        "prerequisites": ["大學以上學歷"], "supplements": ["須具備證照"],
    })


def test_get_profile_projects_metadata():
    fake = FakeQdrant(scroll_pages=[([_profile_point()], None)])
    out = service.get_profile(fake, "ocs_v3", ocs_code="OC1")
    assert out["ocs_code"] == "OC1"
    assert out["job_title"] == "農業人力資源管理師"
    assert out["job_category"] == {"code": "BHR", "name": "人力資源類"}
    assert out["occupations"] == [{"code": "2422", "name": "人力資源專業人員"}]
    assert out["industries"] == [{"code": "A", "name": "農林漁牧業"}]
    assert out["job_description"] == "規劃並執行人力資源管理"
    assert out["ocs_level"] == 4
    assert out["attitudes"] == [{"code": "A01", "name": "主動積極"}]
    assert out["prerequisites"] == ["大學以上學歷"]
    assert out["supplements"] == ["須具備證照"]


def test_get_profile_missing_returns_none():
    fake = FakeQdrant(scroll_pages=[([], None)])
    assert service.get_profile(fake, "ocs_v3", ocs_code="NOPE") is None


def test_get_profile_tolerates_missing_codes():
    # pre-reingest payloads may lack job_category_codes / mismatched code|name lengths
    pt = FakePoint(payload={
        "chunk_level": "profile", "ocs_code": "OC2", "job_title": "JT",
        "job_category": "類別名",  # no job_category_codes
        "industry_names": ["行業A", "行業B"],  # names without codes
        "occupation_codes": ["O1"], "occupation_names": [],  # code without name
    })
    out = service.get_profile(FakeQdrant(scroll_pages=[([pt], None)]), "ocs_v3", ocs_code="OC2")
    assert out["job_category"] == {"code": "", "name": "類別名"}
    assert out["industries"] == [{"code": "", "name": "行業A"}, {"code": "", "name": "行業B"}]
    assert out["occupations"] == [{"code": "O1", "name": ""}]
    assert out["ocs_level"] is None
    assert out["attitudes"] == [] and out["prerequisites"] == []
