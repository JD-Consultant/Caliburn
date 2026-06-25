from jd_ocs_indexer.models.chunk import Pair
from jd_ocs_indexer.ingestion.normalizer import (
    NormalizedBlock, NormalizedTaskGroup, NormalizedUnit, NormalizedOCS,
)
from jd_ocs_indexer.ingestion.builder import build, BuildContext


def _norm_multi_level() -> NormalizedOCS:
    """One task defined at two competency levels (e.g. AIoT T4.1 = level 3/4/5)."""
    b1 = NormalizedBlock(
        block_order=1, competency_level=2,
        k_pairs=[Pair("K01", "知識一")], s_pairs=[Pair("S01", "技能一")],
        output_pairs=[Pair("O01", "產出一")],
        evidence=[Pair("P01", "活動句一"), Pair("P02", "活動句二")],
    )
    b2 = NormalizedBlock(
        block_order=2, competency_level=3,
        k_pairs=[Pair("K02", "知識二")], s_pairs=[Pair("S02", "技能二")],
        output_pairs=[], evidence=[Pair("P03", "活動句三")],
    )
    group = NormalizedTaskGroup(
        task_orders=[1], task_ids=["T1.1"], task_titles=["任務一"],
        primary_task_key="T1.1", tasks=[Pair("T1.1", "任務一")], blocks=[b1, b2],
    )
    unit = NormalizedUnit(unit_order=1, unit_id="U1", unit_title="單元一",
                          unit_key="U1", task_groups=[group])
    return NormalizedOCS(
        ocs_code="OC1v1", ocs_code_base="OC1", job_title="JT",
        job_category=None, job_description=None, ocs_level=None,
        version="v1", version_seq=1, update_date=None, is_current=True, units=[unit],
        attitude_codes=[], attitude_terms=[], attitude_pairs=[],
        prerequisites=[], supplements=[],
    )


_CTX = BuildContext(source_file="jd-ocs/OC1v1.json", indexed_at="2026-06-14T00:00:00+00:00")


def test_multi_level_task_keeps_each_block_separate():
    """多 level 任務：每個 competency_block 各自保留 level + K/S/O/P，不攤平（decision 5）。"""
    t = [r for r in build(_norm_multi_level(), _CTX) if r.chunk_level == "task"][0]
    blocks = t.payload["competency_blocks"]
    assert [b["competency_level"] for b in blocks] == [2, 3]
    assert blocks[0]["knowledge"] == [{"code": "K01", "name": "知識一"}]
    assert blocks[0]["indicators"] == [{"code": "P01", "text": "活動句一"}, {"code": "P02", "text": "活動句二"}]
    assert blocks[0]["outputs"] == [{"code": "O01", "name": "產出一"}]
    assert blocks[1]["knowledge"] == [{"code": "K02", "name": "知識二"}]
    assert blocks[1]["outputs"] == []


def test_multi_level_embed_aggregates_indicator_texts():
    t = [r for r in build(_norm_multi_level(), _CTX) if r.chunk_level == "task"][0]
    for token in ["任務一", "活動句一", "活動句三"]:
        assert token in t.text
