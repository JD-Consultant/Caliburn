"""matching core 純函式測試 — 假分數,不需 GPU/embedder。spec §2/§6(ADR 0022)。"""
from jd_ocs_indexer.matching import core


def test_preprocess_strips_marks_and_cjk_gaps():
    assert core.preprocess("問題解決能力【T1.1】【T1.2】") == "問題解決能力"
    assert core.preprocess("檢驗分 析能力") == "檢驗分析能力"          # CJK 字間空白刪
    assert core.preprocess("ISO 9001 品質知識") == "ISO 9001 品質知識"  # 拉丁 token/邊界空白保留
    assert core.preprocess("操作機台【註3】 ") == "操作機台"


def test_collapse_key_nfkc():
    assert core.collapse_key("品質(管理)") == core.collapse_key("品質(管理)")  # 全形=半形


def test_band_three_zones():
    pairs = [(0.96, "x", "y"), (0.85, "x", "z"), (0.5, "y", "z")]
    dup, gray = core.band(pairs, 0.95, 0.80)
    assert dup == [(0.96, "x", "y")]
    assert gray == [(0.85, "x", "z")]          # <0.80 丟棄


def _score_of(table):
    def f(x, y):
        return table.get(frozenset((x, y)))
    return f


def test_star_no_chaining():
    # A–B 0.96、B–C 0.96,但 A–C 只有 0.5 → C 不得經 B 鏈入 A 的群(SKOS 紅線)
    table = {frozenset(("A", "B")): 0.96, frozenset(("B", "C")): 0.96, frozenset(("A", "C")): 0.5}
    clusters = core.star_clusters([(0.96, "A", "B"), (0.96, "B", "C")], _score_of(table), 0.95)
    assert clusters == [("A", {"B": 0.96})]    # center=min(id);C 與中心 A 直連 0.5 → 拒入


def test_star_admits_direct_link():
    table = {frozenset(("A", "B")): 0.97, frozenset(("A", "C")): 0.96, frozenset(("B", "C")): 0.96}
    clusters = core.star_clusters([(0.97, "A", "B"), (0.96, "B", "C")], _score_of(table), 0.95)
    assert clusters == [("A", {"B": 0.97, "C": 0.96})]  # C 與中心 A 直連 0.96 → 以該分入群


def test_star_deterministic_ordering():
    # 同分對:照 (left, right) id 升序處理 → 同輸入必同輸出
    table = {frozenset(("A", "B")): 0.96, frozenset(("C", "D")): 0.96}
    c1 = core.star_clusters([(0.96, "C", "D"), (0.96, "A", "B")], _score_of(table), 0.95)
    c2 = core.star_clusters([(0.96, "A", "B"), (0.96, "C", "D")], _score_of(table), 0.95)
    assert c1 == c2 == [("A", {"B": 0.96}), ("C", {"D": 0.96})]


def test_medoid_highest_avg_tie_by_id():
    table = {frozenset(("A", "B")): 0.9, frozenset(("A", "C")): 0.9, frozenset(("B", "C")): 0.99}
    assert core.medoid_of(["A", "B", "C"], _score_of(table)) == "B"   # B 平均最高;缺分以 0 計
