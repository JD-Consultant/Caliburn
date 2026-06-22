"""D29: GET /profile/{ocs_code} profile-metadata projection."""
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint


def _profile_point():
    return FakePoint(payload={
        "chunk_level": "profile", "ocs_code": "OC1",
        "job_title": "AIoT應用工程師",
        # ocs_name.job_category_name 常為 null → 標題職類名空；所屬職類別在 category（多值）
        "job_category": None,
        "job_category_codes": ["MPM", "INM"], "job_category_names": ["製造/生產管理", "資訊科技"],
        "industry_codes": ["K62", "C26"], "industry_names": ["電腦程式設計", "電子零組件製造"],
        "occupation_codes": ["2152", "3513"], "occupation_names": ["電子工程師", "電腦網路技術員"],
        "job_description": "AIoT 系統整合與應用",
        "ocs_level": 4,
        "all_a_pairs": [{"code": "A01", "name": "多元思考"}],
        "prerequisites": ["理工相關科系畢業"], "supplements": [],
    })


def test_get_profile_projects_metadata():
    fake = FakeQdrant(scroll_pages=[([_profile_point()], None)])
    out = service.get_profile(fake, "ocs_v3", ocs_code="OC1")
    assert out["ocs_code"] == "OC1"
    assert out["job_title"] == "AIoT應用工程師"
    assert out["job_category_name"] == ""  # ocs_name.job_category_name was null
    # 所屬職類別 = 多值 {code,name}（與職業/行業並列）
    assert out["job_categories"] == [
        {"code": "MPM", "name": "製造/生產管理"},
        {"code": "INM", "name": "資訊科技"},
    ]
    assert out["occupations"] == [
        {"code": "2152", "name": "電子工程師"},
        {"code": "3513", "name": "電腦網路技術員"},
    ]
    assert out["industries"][0] == {"code": "K62", "name": "電腦程式設計"}
    assert out["job_description"] == "AIoT 系統整合與應用"
    assert out["ocs_level"] == 4
    assert out["attitudes"] == [{"code": "A01", "name": "多元思考"}]
    assert out["prerequisites"] == ["理工相關科系畢業"]
    assert out["supplements"] == []


def test_get_profile_missing_returns_none():
    fake = FakeQdrant(scroll_pages=[([], None)])
    assert service.get_profile(fake, "ocs_v3", ocs_code="NOPE") is None


def test_get_profile_tolerates_missing_codes():
    # pre-reingest payloads may lack job_category_* / mismatched code|name lengths
    pt = FakePoint(payload={
        "chunk_level": "profile", "ocs_code": "OC2", "job_title": "JT",
        "job_category": "標題職類名",  # ocs_name.job_category_name present
        # no job_category_codes/names at all (old payload)
        "industry_names": ["行業A", "行業B"],  # names without codes
        "occupation_codes": ["O1"], "occupation_names": [],  # code without name
    })
    out = service.get_profile(FakeQdrant(scroll_pages=[([pt], None)]), "ocs_v3", ocs_code="OC2")
    assert out["job_category_name"] == "標題職類名"
    assert out["job_categories"] == []
    assert out["industries"] == [{"code": "", "name": "行業A"}, {"code": "", "name": "行業B"}]
    assert out["occupations"] == [{"code": "O1", "name": ""}]
    assert out["ocs_level"] is None
    assert out["attitudes"] == [] and out["prerequisites"] == []
