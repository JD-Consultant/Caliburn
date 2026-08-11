from types import SimpleNamespace
from jd_ocs_indexer.validation.smoke_query import _to_hit, Hit


def test_to_hit_carries_id_not_chunk_key():
    p = SimpleNamespace(id="pt-1", payload={"chunk_level": "task", "ocs_code": "OC1", "job_title": "JT"}, score=0.9)
    h = _to_hit(p)
    assert h.id == "pt-1"
    assert h.chunk_level == "task" and h.ocs_code == "OC1"
    assert not hasattr(h, "chunk_key")


def test_filter_by_ks_code_is_removed():
    import jd_ocs_indexer.validation.smoke_query as sq
    assert not hasattr(sq, "filter_by_ks_code")
