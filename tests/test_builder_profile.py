from jd_ocs_indexer.models.chunk import Pair
from jd_ocs_indexer.ingestion.normalizer import (
    NormalizedBlock, NormalizedTaskGroup, NormalizedUnit, NormalizedOCS,
)
from jd_ocs_indexer.ingestion.builder import build, BuildContext


def _norm() -> NormalizedOCS:
    block = NormalizedBlock(
        block_order=1, competency_level=2,
        k_pairs=[Pair("K01", "資料處理概念")], s_pairs=[Pair("S01", "Python")],
        output_pairs=[Pair("O01", "清理後資料集")], evidence=[Pair("P01", "用Python清洗資料")],
    )
    group = NormalizedTaskGroup(
        task_orders=[1], task_ids=["T1.1"], task_titles=["資料清理"],
        primary_task_key="T1.1", tasks=[Pair("T1.1", "資料清理")], blocks=[block],
    )
    unit = NormalizedUnit(unit_order=1, unit_id="U1", unit_title="資料處理",
                          unit_key="U1", task_groups=[group])
    return NormalizedOCS(
        ocs_code="OC1v2", ocs_code_base="OC1", job_title="資料分析師",
        job_category="資訊",
        job_description="負責資料分析", ocs_level=4,
        version="v2", version_seq=2, update_date="2025/12/31", is_current=True,
        units=[unit], attitude_codes=["A01"], attitude_terms=["主動積極"],
        attitude_pairs=[Pair("A01", "主動積極")],
        prerequisites=["大學以上學歷"], supplements=["須具備證照"],
        job_category_pairs=[Pair("JC1", "資訊類")],
        occupation_pairs=[Pair("OCC1", "分析師")],
        industry_pairs=[Pair("I1", "資訊業")],
    )


_CTX = BuildContext(source_file="jd-ocs/OC1v2.json", indexed_at="2026-06-14T00:00:00+00:00")


def test_profile_record_payload():
    profile = [r for r in build(_norm(), _CTX) if r.chunk_level == "profile"][0]
    p = profile.payload
    assert profile.chunk_key == "ocs:OC1v2:profile"
    assert p["chunk_level"] == "profile" and p["schema_version"] == "v4"
    assert p["ocs_code"] == "OC1v2" and p["ocs_code_base"] == "OC1"
    assert p["is_current"] is True and p["ocs_level"] == 4
    assert p["job_description"] == "負責資料分析"
    # ocs_name = source nested object (擇一; job_category_name usually null)
    assert p["ocs_name"] == {"job_category_name": "資訊", "occupation_name": "資料分析師"}
    # category 三組皆 [{code,name}]（取代平行 *_codes/*_names）
    assert p["job_categories"] == [{"code": "JC1", "name": "資訊類"}]
    assert p["occupations"] == [{"code": "OCC1", "name": "分析師"}]
    assert p["industries"] == [{"code": "I1", "name": "資訊業"}]
    assert p["attitudes"] == [{"code": "A01", "name": "主動積極"}]
    assert p["prerequisites"] == ["大學以上學歷"]
    assert p["supplements"] == ["須具備證照"]
    assert p["indexed_at"] == "2026-06-14T00:00:00+00:00"
    assert p["source_file"] == "jd-ocs/OC1v2.json"
    # dropped: version metadata, flat job_title/job_category, parallel arrays, all_a_pairs
    for gone in ("version", "version_seq", "update_date", "job_title",
                 "job_category", "job_category_codes", "occupation_codes",
                 "industry_names", "all_a_pairs"):
        assert gone not in p
    assert "text" not in p


def test_profile_embed_text_has_signal():
    profile = [r for r in build(_norm(), _CTX) if r.chunk_level == "profile"][0]
    for token in ["資料分析師", "負責資料分析", "資料清理", "Python", "資料處理概念"]:
        assert token in profile.text
