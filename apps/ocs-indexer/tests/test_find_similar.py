# tests/test_find_similar.py
from jd_ocs_indexer.api import service

def _t(i, code, name, vec):
    return {"id": i, "ocs_code": "OC%s" % i[-1], "task_code": code, "task_name": name, "vector": vec}

def test_pairwise_candidates_above_threshold_only():
    a = _t("idA", "T1.1", "撰寫測試報告", [1.0, 0.0])
    b = _t("idB", "T2.2", "編寫測試報告書", [0.99, 0.14])   # ~cos 0.99 with a
    c = _t("idC", "T3.3", "完全不同", [0.0, 1.0])           # ~cos 0.0 with a
    pairs = service._pairwise_candidates([a, b, c], threshold=0.85)
    assert len(pairs) == 1
    p = pairs[0]
    assert {p["a"]["task_code"], p["b"]["task_code"]} == {"T1.1", "T2.2"}
    assert p["a"]["urn"].startswith("ocs:") and p["score"] >= 0.85

def test_pairwise_excludes_self_and_dedups_direction():
    a = _t("idA", "T1.1", "x", [1.0, 0.0])
    b = _t("idB", "T2.2", "y", [1.0, 0.0])   # identical -> cos 1.0
    pairs = service._pairwise_candidates([a, b], threshold=0.85)
    assert len(pairs) == 1   # one undirected pair, no self-pairs
