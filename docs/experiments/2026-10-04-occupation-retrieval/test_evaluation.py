import math

import numpy as np
import pytest

from evaluation import clean_text, ranking_check, ranking_metrics, rrf, validate_dense


def test_duplicate_candidates_do_not_inflate_relevance_or_shift_rank():
    result = ranking_metrics(["wrong", "wrong", "right", "related"],
                             {"right": 3, "related": 2})
    assert result["hit_1"] == 0
    assert result["hit_5"] == 1
    assert result["mrr"] == 0.5
    assert 0 < result["ndcg_10"] < 1


def test_perfect_graded_order_and_empty_relevance():
    assert ranking_metrics(["a", "b"], {"a": 3, "b": 2})["ndcg_10"] == 1
    assert ranking_metrics(["anything"], {})["mrr"] is None
    assert ranking_metrics(["anything"], {})["hit_5"] is None


def test_rrf_disagreement_rewards_shared_candidate_and_limits_depth():
    result = rrf([["a", "c", "b"], ["b", "c", "a"]], depth=2, constant=60)
    assert result[0][0] == "c"
    assert result[0][1] == pytest.approx(2 / 61)
    assert len(result) == 3


@pytest.mark.parametrize("vectors,count", [([[math.nan, 0]], 1),
                                           ([[0, 0]], 1), ([[1, 2]], 2)])
def test_invalid_embedding_cannot_silently_enter_scores(vectors, count):
    with pytest.raises(ValueError):
        validate_dense(vectors, count, dim=2)


def test_embedding_normalization_makes_cosine_independent_of_magnitude():
    actual = validate_dense([[3, 4]], 1, dim=2)
    np.testing.assert_allclose(actual, [[0.6, 0.8]])


def test_codes_headings_removed_but_technical_names_retained():
    assert clean_text("## 工作內容\nP1.2.3 依圖面檢查工件。\nK01 工程識圖\nS02 3D建模") == (
        "依圖面檢查工件。\n工程識圖\n3D建模")


def test_meaningful_item_heading_is_content_and_must_survive():
    assert clean_text("## K01 工程識圖\n## 尚待確認的工作\n尚未確定由本人核准。") == (
        "工程識圖\n尚待確認的工作\n尚未確定由本人核准。")


def test_engine_check_rejects_missing_reversed_and_duplicate_candidates():
    expected = [("a", 1), ("b", .8), ("c", .6)]
    assert not ranking_check(expected[:1], expected, 3)["correct"]
    assert not ranking_check(expected[::-1], expected, 3)["correct"]
    assert not ranking_check([expected[0], expected[0], expected[2]], expected, 3)["correct"]


def test_engine_check_allows_equal_score_boundary_ties():
    assert ranking_check([("a", 1), ("c", .8)], [("a", 1), ("b", .8), ("c", .8)], 2)["correct"]
