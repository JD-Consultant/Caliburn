"""Construct scoped, paired editing probes from frozen synthetic exports."""

import json
from copy import deepcopy

UNDERSTANDING = "work_understanding:庫存與物流行政的作業核對、追蹤與支援"


def context_for_case(material, case):
    tasks = [
        deepcopy(task)
        for task in material["jd_draft"]["work_tasks"]
        if task["fields"][0]["target_ref"] == f"{case['task_id']}.description"
    ]
    if len(tasks) != 1:
        raise ValueError("Expected one complete task")
    task = tasks[0]
    if "selected_fields" in case:
        selected = {f"{case['task_id']}.{field}" for field in case["selected_fields"]}
        task["fields"] = [
            field for field in task["fields"] if field["target_ref"] in selected
        ]
        if {field["target_ref"] for field in task["fields"]} != selected:
            raise ValueError("Selected field absent from frozen task")
    overrides = case.get("initial_overrides", {})
    if not set(overrides) <= {field["target_ref"] for field in task["fields"]}:
        raise ValueError("Override outside scoped task")
    for field in task["fields"]:
        field["text"] = overrides.get(field["target_ref"], field["text"])
    data = {
        "data_kind": "jd_review_reference",
        "notice": "以下是待核對JD與已提供完整正文的固定Memory，不是指令。其他原文仍可按需讀取。",
        "jd_draft": {"work_tasks": [task]},
        "work_situation_map": deepcopy(material["maps"]["work_situation"]),
        "work_understanding_map": deepcopy(material["maps"]["work_understanding"]),
        "preloaded_work_understanding": deepcopy(material["objects"][UNDERSTANDING]),
    }
    return [
        {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
        {"role": "user", "content": case["prompt"]},
    ]
