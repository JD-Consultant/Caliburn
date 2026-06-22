"""D29 V1: header-metadata aggregation (pure function, no DB/HTTP)."""
from app.services import header_meta
from app.services.knowledge.models import Pair, ProfileMeta


def _meta(code, **kw):
    return ProfileMeta(ocs_code=code, **kw)


def test_aggregate_dedupes_by_code_and_tracks_sources():
    metas = [
        _meta("OC1", job_title="人資專員",
              job_category=Pair(code="BHR", name="人資類"),
              occupations=[Pair(code="2422", name="人資專業人員")],
              industries=[Pair(code="A", name="農林漁牧業")],
              attitudes=[Pair(code="A01", name="主動")],
              prerequisites=["大學以上"], supplements=["須證照"],
              job_description="desc1", ocs_level=4),
        _meta("OC2", job_title="人資主管",
              job_category=Pair(code="BHR", name="人資類"),          # dup code BHR
              occupations=[Pair(code="1120", name="高階主管")],
              industries=[Pair(code="A", name="農林漁牧業"),         # dup A
                          Pair(code="N", name="支援服務業")],
              attitudes=[Pair(code="A01", name="主動")],             # dup A01
              prerequisites=["大學以上"], ocs_level=5),
    ]
    out = header_meta.aggregate(metas, primary_code="OC1")

    # dedupe by code, first-seen order
    assert [x["code"] for x in out["job_categories"]] == ["BHR"]
    assert out["job_categories"][0]["sources"] == ["OC1", "OC2"]
    assert [x["code"] for x in out["occupations"]] == ["2422", "1120"]
    assert [x["code"] for x in out["industries"]] == ["A", "N"]
    assert out["industries"][0]["sources"] == ["OC1", "OC2"]   # A from both
    assert out["industries"][1]["sources"] == ["OC2"]          # N only OC2
    assert [x["code"] for x in out["attitudes"]] == ["A01"]
    # notes union dedupe by text
    assert [x["text"] for x in out["prerequisites"]] == ["大學以上"]
    assert out["prerequisites"][0]["sources"] == ["OC1", "OC2"]
    assert [x["text"] for x in out["supplements"]] == ["須證照"]


def test_primary_defaults_to_primary_code():
    metas = [
        _meta("OC1", job_title="專員", job_category=Pair(code="B", name="乙"),
              job_description="d1", ocs_level=3),
        _meta("OC2", job_title="主管", job_description="d2", ocs_level=5),
    ]
    out = header_meta.aggregate(metas, primary_code="OC2")
    assert out["primary"]["ocs_code"] == "OC2"
    assert out["primary"]["occupation_name"] == "主管"
    assert out["primary"]["job_description"] == "d2"
    assert out["primary"]["ocs_level"] == 5
    # switcher options list all selected, each carrying its bound job_category_name
    assert [o["ocs_code"] for o in out["primary_options"]] == ["OC1", "OC2"]
    assert out["primary_options"][0]["job_category_name"] == "乙"


def test_empty_is_safe():
    out = header_meta.aggregate([], primary_code="")
    assert out["primary"]["ocs_code"] == "" and out["primary"]["ocs_level"] is None
    assert out["occupations"] == [] and out["attitudes"] == []


def test_code_empty_falls_back_to_name_dedupe():
    metas = [
        _meta("OC1", industries=[Pair(code="", name="自訂行業")]),
        _meta("OC2", industries=[Pair(code="", name="自訂行業")]),  # same name, no code
    ]
    out = header_meta.aggregate(metas, primary_code="OC1")
    assert [x["name"] for x in out["industries"]] == ["自訂行業"]
    assert out["industries"][0]["sources"] == ["OC1", "OC2"]
