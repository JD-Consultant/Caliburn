from evals.checks import is_valid_json, has_keys, is_zh_tw, doc_structure_ok, deep_quality_ok


def test_is_valid_json():
    assert is_valid_json('{"a":1}')
    assert not is_valid_json("not json")


def test_has_keys():
    assert has_keys({"a": 1, "b": 2}, ["a", "b"])
    assert not has_keys({"a": 1}, ["a", "b"])


def test_is_zh_tw():
    assert is_zh_tw("依點檢表逐項檢查設備")
    assert not is_zh_tw("this is english only")


def test_doc_structure_ok():
    good = {"ocs_content": {"ocu_units": [
        {"ocu_code": "T1", "ocu_name": "u", "tasks": [
            {"task_code": "T1.1", "task_name": "巡檢",
             "indicators": [{"code": "P1.1.1", "text": "x"}],
             "outputs": [{"code": "O1.1.1", "name": "點檢表"}]}]}]},
        "ocs_ksa": {"knowledge": [], "skills": [], "attitudes": []}}
    ok, reasons = doc_structure_ok(good)
    assert ok, reasons
    bad = {"ocs_content": {"ocu_units": []}, "ocs_ksa": {}}
    ok2, reasons2 = doc_structure_ok(bad)
    assert not ok2 and reasons2


def test_deep_quality_ok():
    good = {"situation": "s", "purpose": "p", "workflow_steps": ["a"], "outputs": ["o"],
            "behavior_indicators": [{"quality_score": 0.8}]}
    assert deep_quality_ok(good)
    bad = {"behavior_indicators": [{"quality_score": 0.3}]}
    assert not deep_quality_ok(bad)
    # 好分數但缺 5W2H 欄 → 不過
    missing_5w2h = {"behavior_indicators": [{"quality_score": 0.9}]}
    assert not deep_quality_ok(missing_5w2h)
