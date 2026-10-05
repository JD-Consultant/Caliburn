"""Test the controlled information boundary, not model wording or hidden order."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("boundary_fixtures", HERE / "fixtures.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
BASELINE = HERE.parent / "memory-reading-policy-2026-10-04/live-01/materials.json"


def baseline():
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def test_understanding_gap_requires_situation_but_keeps_cold_return_facts():
    material, changes = fixtures.build_material(baseline())
    body = material["objects"][fixtures.UNDERSTANDING]["body"]
    assert "兩個工作日" not in body
    assert "兩／四工作日" not in body
    assert "第四個工作日" not in body
    assert "兩個工作日" in material["objects"][fixtures.RECEIVING]["body"]
    assert "冷藏退貨另核對溫度紀錄，交品質窗口判定" in body
    assert changes["removed_from_understanding"]


def test_packaging_answer_only_exists_in_unchanged_originals():
    source = baseline()
    preserved = deepcopy(source)
    material, changes = fixtures.build_material(source)
    assert source == preserved
    assert material["messages"] == source["messages"]
    assert "一箱12件" in material["messages"][53]["text"]
    memory = json.dumps(material["objects"], ensure_ascii=False)
    assert "12 件" not in memory and "12件" not in memory
    jd = json.dumps(material["jd_draft"], ensure_ascii=False)
    assert "一箱12件" not in jd and "一箱 12 件" not in jd
    assert "所有商品都以一箱 10 件" in material["slots"]["task_1.requirement_10"]
    for task in material["jd_draft"]["work_tasks"]:
        for field in task["fields"]:
            assert field["text"] == material["slots"][field["target_ref"]]
    assert changes["removed_from_situation"]


def test_preload_contains_only_selected_task_and_no_gap_answers_or_grading():
    material, _ = fixtures.build_material(baseline())
    template_path = BASELINE.parent / "initial-corrections.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    original = deepcopy(template)
    for case_id, task_id in (
        ("complete", "task_2"),
        ("situation_gap", "task_1"),
        ("interview_gap", "task_1"),
    ):
        case = {"case_id": case_id, "prompt": "請核對這項工作。", "task_id": task_id}
        window = fixtures.context_for_case(material, template, case)
        data = json.loads(window[0]["content"])
        assert len(data["jd_draft"]["work_tasks"]) == 1
        fields = data["jd_draft"]["work_tasks"][0]["fields"]
        assert all(f["target_ref"].startswith(task_id + ".") for f in fields)
        recent = data["historical_interview"]["messages"]
        assert [m["interview_sequence"] for m in recent] == [105]
        assert (
            "12件" not in window[0]["content"] and "12 件" not in window[0]["content"]
        )
        assert "兩個工作日" not in window[0]["content"]
        assert "criteria" not in data and "fixture-changes" not in data
        assert window[-1] == {"role": "user", "content": case["prompt"]}
    assert template == original
