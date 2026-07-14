"""T11(ADR 0030):Source Score——已知造假案例必須正確扣分(程式算,零 LLM)。"""
from evals.source_score import source_score

TURNS = {3: "我們每兩週跑一次回歸,工具主要是 Postman 跟自己寫的 pytest 腳本"}
REF = {"ocs:X:K:K01"}


def _doc():
    return {"ocs_content": {"ocu_units": [{"_uid": "u1", "tasks": [{
        "_tid": "t1",
        "task_codes": [{"code": "T1.1", "name": "回歸測試"}],
        "competency_blocks": [{
            "knowledge": [
                # ① 好:官方 ref + 逐字 quote
                {"code": "K01", "name": "測試知識", "_id": "k1",
                 "_pending": {"op": "add", "by": "ai", "turn_id": 3,
                              "src": {"ref_urn": "ocs:X:K:K01",
                                      "quote": {"turn_id": 3, "text": "每兩週跑一次回歸"}}}},
                # ② 造假 quote:他沒說過這句
                {"code": None, "name": "捏造知識", "_id": "k2",
                 "_pending": {"op": "add", "by": "ai", "turn_id": 3,
                              "src": {"quote": {"turn_id": 3, "text": "我有 ISTQB 證照"}}}},
                # ③ 偽 ref:不在參考集合(即使無 quote 也不得過)
                {"code": None, "name": "偽官方", "_id": "k3",
                 "_pending": {"op": "add", "by": "ai", "turn_id": 3,
                              "src": {"ref_urn": "ocs:X:K:K99"}}}]}],
        "details": {"tools": "Postman",
                    "_pending": {"tools": {"op": "mod", "by": "ai", "turn_id": 3,
                                           "src": {"quote": {"turn_id": 3,
                                                             "text": "工具主要是 Postman"}}}}},
    }]}]}}


def test_source_score_penalizes_fabrication():
    r = source_score(_doc(), turns=TURNS, ref_codes=REF)
    assert r["total"] == 4 and r["passed"] == 2
    assert r["score"] == 0.5
    bad = {d["path"].split(".")[-1]: d["reason"] for d in r["details"] if not d["ok"]}
    assert any("quote 未驗證" in v for v in bad.values())
    assert any("ref 不在參考集合" in v for v in bad.values())


def test_source_score_counts_accepted_events():
    accepted = [
        {"doc_path": "p1", "op_meta": {"src": {"quote": {"turn_id": 3,
                                                         "text": "pytest 腳本"}}}},
        {"doc_path": "p2", "op_meta": {}},               # 無出處紀錄 → 扣分
    ]
    r = source_score({}, turns=TURNS, ref_codes=REF, accepted=accepted)
    assert r["total"] == 2 and r["passed"] == 1


def test_source_score_empty_doc_is_perfect():
    assert source_score({}, turns={}, ref_codes=set())["score"] == 1.0
