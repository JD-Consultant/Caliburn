"""Pair contamination or wrong-time facts would invalidate the comparison."""

from cases import build_cases


def test_pair_workspaces_are_detached_and_context_matches():
    cases = build_cases()
    for case in cases:
        first, second = case["workspace"], case["workspace_copy"]
        assert first.snapshot() == second.snapshot()
        first.objects.clear()
        assert second.objects
        assert case["context"] == case["context_copy"]


def test_known_correction_has_new_sources_but_old_understanding():
    case = build_cases()[0]
    current = case["workspace"]
    assert "48 小時" in current.objects["object_1"]["body"]
    assert "24 小時" in current.objects["object_6"]["body"]
    assert current.read_through == 14
    assert all(seq <= 14 for seq in current.objects["object_1"]["references"])


def test_warehouse_keeps_roles_numbers_and_unrelated_work():
    case = next(case for case in build_cases() if case["id"] == "warehouse-correction")
    objects = case["workspace"].objects
    assert "超過 8%" in objects["object_1"]["body"]
    assert "5%" in objects["object_4"]["body"]
    assert "17:30" in objects["object_2"]["body"]
    assert "倉儲主管核准" in objects["object_2"]["body"]
    assert "帳務專員" in objects["object_2"]["body"]
    assert "月末" in objects["object_5"]["body"]


def test_narrow_question_changes_only_question_not_source():
    full, narrow = build_cases()[-2:]
    assert full["workspace"].snapshot() == narrow["workspace"].snapshot()
    assert "幾點" in narrow["context"]["question"]
    assert full["context"]["question"] != narrow["context"]["question"]
    assert "grading" not in narrow["context"]
