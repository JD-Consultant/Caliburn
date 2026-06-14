from jd_ocs_indexer.models.chunk import Pair
from jd_ocs_indexer.ingestion.normalizer import (
    NormalizedBlock, NormalizedTaskGroup, NormalizedUnit, NormalizedOCS,
)
from jd_ocs_indexer.ingestion.builder import build, BuildContext


def _norm_two_tasks() -> NormalizedOCS:
    block = NormalizedBlock(
        block_order=1, competency_level=3,
        k_pairs=[Pair("K01", "知識一")], s_pairs=[Pair("S01", "技能一")],
        output_pairs=[Pair("O01", "產出一")],
        evidence=[Pair("P01", "活動一"), Pair("P02", "活動二"), Pair("P03", "活動三"), Pair("P04", "活動四")],
    )
    multi = NormalizedTaskGroup(
        task_orders=[1, 2], task_ids=["T1.1", "T1.2"], task_titles=["任務一", "任務二"],
        primary_task_key="T1.1",
        tasks=[Pair("T1.1", "任務一"), Pair("T1.2", "任務二")], blocks=[block],
    )
    blockless = NormalizedTaskGroup(
        task_orders=[3], task_ids=["T1.3"], task_titles=["任務三"],
        primary_task_key="T1.3", tasks=[Pair("T1.3", "任務三")], blocks=[],
    )
    unit = NormalizedUnit(unit_order=1, unit_id="U1", unit_title="單元一",
                          unit_key="U1", task_groups=[multi, blockless])
    return NormalizedOCS(
        ocs_code="OC1v1", ocs_code_base="OC1", job_title="JT",
        job_category=None, job_category_codes=[], industry_codes=[], industry_names=[],
        occupation_codes=[], occupation_names=[], job_description=None, ocs_level=None,
        version="v1", version_seq=1, update_date=None, is_current=True, units=[unit],
        attitude_codes=[], attitude_terms=[], attitude_pairs=[],
        prerequisites=[], supplements=[],
    )


_CTX = BuildContext(source_file="jd-ocs/OC1v1.json", indexed_at="2026-06-14T00:00:00+00:00")


def test_one_task_record_per_task_id():
    tasks = [r for r in build(_norm_two_tasks(), _CTX) if r.chunk_level == "task"]
    assert sorted(r.payload["task_id"] for r in tasks) == ["T1.1", "T1.2", "T1.3"]


def test_task_record_payload_and_examples():
    t11 = [r for r in build(_norm_two_tasks(), _CTX) if r.payload.get("task_id") == "T1.1"][0]
    p = t11.payload
    assert t11.chunk_key == "ocs:OC1v1:unit:U1:task:T1.1"
    assert p["chunk_level"] == "task" and p["ocs_code"] == "OC1v1"
    assert p["unit_id"] == "U1" and p["unit_title"] == "單元一"
    assert p["task_id"] == "T1.1" and p["task_title"] == "任務一"
    assert p["k_pairs"] == [{"code": "K01", "name": "知識一"}]
    assert p["s_pairs"] == [{"code": "S01", "name": "技能一"}]
    assert p["output_pairs"] == [{"code": "O01", "name": "產出一"}]
    assert p["competency_level"] == 3
    assert p["activity_examples"] == ["活動一", "活動二", "活動三"]
    assert "text" not in p
    assert "任務一" in t11.text and "活動一" in t11.text


def test_block_less_task_record():
    t13 = [r for r in build(_norm_two_tasks(), _CTX) if r.payload.get("task_id") == "T1.3"][0]
    assert t13.payload["k_pairs"] == [] and t13.payload["activity_examples"] == []
    assert t13.payload["competency_level"] is None
