"""Controlled gaps over frozen synthetic exports; never product edits."""

import json
from copy import deepcopy

UNDERSTANDING = "work_understanding:庫存與物流行政的作業核對、追蹤與支援"
RECEIVING = "work_situation:到貨驗收、ERP 登錄與收貨異常追蹤"


def build_material(baseline):
    material = deepcopy(baseline)
    understanding = material["objects"][UNDERSTANDING]
    situation = material["objects"][RECEIVING]
    removed = {
        "removed_from_understanding": [
            "兩個工作日未獲回覆提醒採購，第四個工作日仍無進展則回報主管。",
            "曾有一品號經資料窗口確認一箱為 12 件，本人留存換算依據後登錄；此換算只適用該品號，不推用其他商品。",
        ],
        "removed_from_situation": [
            "- 曾有某批商品採購單寫「箱」、送貨單寫「件」；資料窗口確認該品號一箱 12 件後，本人保留換算依據再登錄。12 件僅適用該品號包裝，不可推用於其他商品。\n"
        ],
    }
    for sentence in removed["removed_from_understanding"]:
        understanding["body"] = replace_once(understanding["body"], sentence, "")
    understanding["body"] = replace_once(
        understanding["body"], "兩／四工作日提醒升級規則", "提醒升級規則"
    )
    for sentence in removed["removed_from_situation"]:
        situation["body"] = replace_once(situation["body"], sentence, "")
    overrides = {
        "task_1.requirement_3": "驗收不良比例以每批實際驗收件數為分母，超過 5% 時提報倉儲主管；剛好 5% 不因比例規則提報。有安全疑慮仍須隔離並通知主管。",
        "task_1.requirement_6": "收貨異常通知採購後，由採購自行追蹤，不另設定提醒與升級。",
        "task_1.requirement_10": "所有商品都以一箱 10 件換算並登錄 ERP，不需逐品號查證。",
        "task_2.description": material["slots"]["task_2.description"].replace(
            "每週一 08:35", "每週一 08:50"
        ),
        "task_2.requirement_1": "週一 08:50、週二至週五 08:35 開始核對退貨，每個工作日仍於 09:10 前交退貨差異表給客服；此時限不套用進貨驗收。",
    }
    for task in material["jd_draft"]["work_tasks"]:
        for field in task["fields"]:
            target = field["target_ref"]
            if target in overrides:
                field["text"] = overrides[target]
                material["slots"][target] = field["text"]
    removed["neutralized_secondary_mention"] = "兩／四工作日提醒升級規則 → 提醒升級規則"
    removed["jd_overrides"] = {
        target: {"before": baseline["slots"][target], "after": value}
        for target, value in overrides.items()
    }
    return material, removed


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Frozen fixture no longer has one exact source fragment")
    return text.replace(old, new, 1)


def context_for_case(material, template, case):
    data = json.loads(template[0]["content"])
    task_id = case["task_id"]
    tasks = [
        deepcopy(task)
        for task in material["jd_draft"]["work_tasks"]
        if task["fields"][0]["target_ref"] == f"{task_id}.description"
    ]
    if len(tasks) != 1:
        raise ValueError("Expected one complete task")
    data["jd_draft"] = {"work_tasks": tasks}
    data["work_situation_map"] = material["maps"]["work_situation"]
    data["work_understanding_map"] = material["maps"]["work_understanding"]
    return [
        {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
        {"role": "user", "content": case["prompt"]},
    ]
