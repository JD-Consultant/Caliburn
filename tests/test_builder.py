from jd_ocs_indexer.models.chunk import Pair
from jd_ocs_indexer.ingestion.normalizer import NormalizedBlock, NormalizedTaskGroup
from jd_ocs_indexer.ingestion.builder import _aggregate_group


def _group() -> NormalizedTaskGroup:
    b1 = NormalizedBlock(
        block_order=1, competency_level=2,
        k_pairs=[Pair("K01", "知識一")], s_pairs=[Pair("S01", "技能一")],
        output_pairs=[Pair("O01", "產出一")],
        evidence=[Pair("P01", "活動句一"), Pair("P02", "活動句二")],
    )
    b2 = NormalizedBlock(
        block_order=2, competency_level=3,
        k_pairs=[Pair("K01", "知識一"), Pair("K02", "知識二")],
        s_pairs=[Pair("S02", "技能二")], output_pairs=[],
        evidence=[Pair("P03", "活動句三")],
    )
    return NormalizedTaskGroup(
        task_orders=[1], task_ids=["T1.1"], task_titles=["任務一"],
        primary_task_key="T1.1", tasks=[Pair("T1.1", "任務一")], blocks=[b1, b2],
    )


def test_aggregate_group_dedups_and_collects():
    agg = _aggregate_group(_group())
    assert [(p.code, p.name) for p in agg["k_pairs"]] == [("K01", "知識一"), ("K02", "知識二")]
    assert [(p.code, p.name) for p in agg["s_pairs"]] == [("S01", "技能一"), ("S02", "技能二")]
    assert [(p.code, p.name) for p in agg["output_pairs"]] == [("O01", "產出一")]
    assert agg["activities"] == ["活動句一", "活動句二", "活動句三"]
    assert agg["competency_level"] == 3


def test_aggregate_group_block_less():
    g = NormalizedTaskGroup(
        task_orders=[1], task_ids=["T9"], task_titles=["空任務"],
        primary_task_key="T9", tasks=[Pair("T9", "空任務")], blocks=[],
    )
    agg = _aggregate_group(g)
    assert agg["k_pairs"] == [] and agg["activities"] == [] and agg["competency_level"] is None
