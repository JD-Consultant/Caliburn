"""Behavioral counterexamples for unbiased input and published snapshot extraction."""

import json

import pytest

from support import generation_messages, published_b2


def test_generation_excludes_answer_annotations():
    case = {"case_id": "E01", "employee_messages": ["原話A", "原話B", "原話C"],
            "grades": {"SECRET_TARGET_CODE": 3}, "rationale": "SECRET_EXPECTED_TITLE"}
    messages = generation_messages(case)
    assert len(messages) == 6
    assert [row["interview_sequence"] for row in messages] == list(range(1, 7))
    assert [row["text"] for row in messages if row["speaker"] == "employee"] == case["employee_messages"]
    assert "SECRET" not in json.dumps(messages)


def test_empty_published_memory_is_explicit_abstention():
    assert published_b2({"snapshot": {}, "objects": []}) is None


@pytest.mark.parametrize("revision", ["right", "wrong"])
def test_missing_reference_and_wrong_revision_cannot_be_silently_skipped(revision):
    snapshot = {"snapshot": {}, "objects": [
        {"object_id": "b2", "layer": "work_understanding", "content": {"body": "理解"},
         "work_situation_references": [{"object_id": "a", "revision_id": "right"},
                                       {"object_id": "absent", "revision_id": "r"}]},
        {"object_id": "a", "revision_id": revision, "layer": "work_situation", "content": {"body": "原文"}}]}
    with pytest.raises(ValueError):
        published_b2(snapshot)


def test_valid_understanding_retains_unknown_and_negation():
    snapshot = {"snapshot": {}, "objects": [
        {"object_id": "b2", "layer": "work_understanding", "content": {"body": "本人沒有核准權，頻率未知。"},
         "work_situation_references": [{"object_id": "a", "revision_id": "r"}]},
        {"object_id": "a", "revision_id": "r", "layer": "work_situation", "content": {"body": "情境"}}]}
    assert published_b2(snapshot) == "本人沒有核准權，頻率未知。"
def test_empty_positive_is_a_miss_instead_of_dropped_case():
    from support import decision
    result = decision({"kind": "positive", "grades": {"expected": 3}}, [])
    assert result["hit_10"] == 0 and result["mrr"] == 0
    assert result["ndcg_10"] == 0 and result["primary_in_top10"] is False
    assert result["legacy_threshold_accepts"] is False


def test_negative_does_not_become_a_retrieval_hit_when_no_memory():
    from support import decision
    result = decision({"kind": "insufficient", "grades": {}}, [])
    assert result["hit_10"] is None
    assert result["expected_abstain"] and not result["legacy_threshold_accepts"]
