"""Preservation audit rejects corruption rather than reusing saved success flags."""

import hashlib

import pytest

from verify_results import compare_values, read_cache_prefix, verify_row


def test_prefix_allows_later_append_but_rejects_short_or_changed_data(tmp_path):
    original = b'{"text_sha256":"a"}\n'
    path = tmp_path / "cache.jsonl"
    path.write_bytes(original + b'{"text_sha256":"b"}\n')
    digest = hashlib.sha256(original).hexdigest()
    assert list(read_cache_prefix(path, len(original), digest)) == ["a"]
    path.write_bytes(original[:-1])
    with pytest.raises(ValueError):
        read_cache_prefix(path, len(original), digest)
    path.write_bytes(original.replace(b'"a"', b'"z"'))
    with pytest.raises(ValueError):
        read_cache_prefix(path, len(original), digest)


def test_numeric_summary_tampering_is_not_tolerated():
    compare_values({"hit_5": 1, "ndcg_10": 0.5}, {"hit_5": 1, "ndcg_10": 0.5})
    with pytest.raises(ValueError):
        compare_values({"hit_5": 1, "ndcg_10": 0.5}, {"hit_5": 1, "ndcg_10": 0.6})


def test_row_audit_rejects_score_tamper_and_grade_change():
    case = {"grades": {"a": 3}}
    row = {"grades": {"a": 3}, "ranking": [{"id": "a", "score": 0.9}]}
    assert verify_row(row, case, [("a", 0.9)])
    with pytest.raises(ValueError):
        verify_row(row, case, [("a", 0.8)])
    with pytest.raises(ValueError):
        verify_row(row, {"grades": {"a": 2}}, [("a", 0.9)])


def test_row_audit_rejects_saved_ranking_truncation():
    case = {"grades": {"a": 3}}
    row = {"grades": case["grades"], "ranking": [{"id": "a", "score": 0.9}]}
    with pytest.raises(ValueError):
        verify_row(row, case, [("a", 0.9), ("b", 0.8)])
