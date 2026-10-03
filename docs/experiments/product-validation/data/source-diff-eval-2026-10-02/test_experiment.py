"""Scorer and comparison preflight; no API, database, or product state changes."""

from copy import deepcopy

from cases import make_cases
from experiment import public_items, score, source_diff, visible_input


def test_gold_and_every_individual_fault_are_detected():
    for case in make_cases():
        correct = deepcopy(case["expected"])
        assert all(score(case, correct).values())
        for field in correct["facts"]:
            wrong = deepcopy(correct)
            wrong["facts"][field] = "wrong"
            assert sum(score(case, wrong).values()) == 7
        for field in ("decision", "reference_action", "protected_task"):
            wrong = deepcopy(correct)
            wrong[field] = "wrong"
            assert sum(score(case, wrong).values()) == 7


def test_visible_arms_never_contain_oracle_and_diff_covers_edge_cases():
    for case in make_cases():
        for arm in ("full", "diff"):
            rendered = visible_input(case, arm)[0]["content"]
            assert '"expected"' not in rendered
            assert '"decision"' not in rendered
        difference = source_diff(case)
        assert "未解除待核對" in difference
        if case["case_id"] == "chain_only":
            assert "直接情境依據" in difference
            assert "營運主管" in difference
        if case["case_id"] == "same_text":
            assert "來源修訂已更新" in difference
        if case["case_id"] == "removed":
            assert "不按同名替代" in difference


def test_native_reasoning_is_not_written_to_public_trace():
    items = [
        {
            "type": "reasoning",
            "id": "rs",
            "encrypted_content": "SECRET",
            "content": "RAW",
        },
        {"role": "user", "content": "synthetic"},
    ]
    safe = public_items(items)
    assert "SECRET" not in str(safe)
    assert "RAW" not in str(safe)
    assert safe[1] == items[1]
    assert items[0]["encrypted_content"] == "SECRET"
