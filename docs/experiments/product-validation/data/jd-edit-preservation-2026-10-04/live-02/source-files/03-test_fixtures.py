"""Check isolation and preservation, not whether prompt text sounds correct."""

import json
from pathlib import Path

from fixtures import UNDERSTANDING, context_for_case

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "memory-reading-boundaries-2026-10-04/live-01"


def load_inputs():
    material = json.loads((BASELINE / "materials.json").read_text(encoding="utf-8"))
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
    return material, cases


def test_model_receives_one_scoped_task_and_no_grading_answers():
    material, cases = load_inputs()
    for case in cases:
        window = context_for_case(material, case)
        data = json.loads(window[0]["content"])
        assert len(data["jd_draft"]["work_tasks"]) == 1
        assert (
            data["jd_draft"]["work_tasks"][0]["fields"][0]["target_ref"]
            == f"{case['task_id']}.description"
        )
        assert "criteria" not in data
        assert "initial_overrides" not in data
        assert (
            data["preloaded_work_understanding"] == material["objects"][UNDERSTANDING]
        )
        assert window[1] == {"role": "user", "content": case["prompt"]}


def test_each_case_is_fresh_and_does_not_change_original_sources():
    material, cases = load_inputs()
    before = json.dumps(material, ensure_ascii=False, sort_keys=True)
    first = context_for_case(material, cases[0])
    first[0]["content"] = "changed by another cell"
    assert context_for_case(material, cases[0])[0]["content"] != first[0]["content"]
    assert json.dumps(material, ensure_ascii=False, sort_keys=True) == before


def test_dedup_fixture_has_correct_division_and_explicit_time_and_statuses():
    material, cases = load_inputs()
    case = next(case for case in cases if case["case_id"] == "deduplication")
    task = json.loads(context_for_case(material, case)[0]["content"])["jd_draft"][
        "work_tasks"
    ][0]
    fields = {field["target_ref"]: field["text"] for field in task["fields"]}
    assert "品質" in fields["task_2.description"]
    assert "報廢待核准" in fields["task_2.outcome_2"]
    assert "09:10" in fields["task_2.requirement_1"]


def test_numeric_probe_does_not_include_unrelated_intentional_errors():
    material, cases = load_inputs()
    case = next(case for case in cases if case["case_id"] == "numeric_boundaries")
    task = json.loads(context_for_case(material, case)[0]["content"])["jd_draft"][
        "work_tasks"
    ][0]
    fields = {field["target_ref"]: field["text"] for field in task["fields"]}
    assert "task_1.requirement_6" not in fields
    assert "task_1.requirement_10" not in fields
    assert "5%" in fields["task_1.requirement_3"]
    assert "安全疑慮" in fields["task_1.requirement_4"]
