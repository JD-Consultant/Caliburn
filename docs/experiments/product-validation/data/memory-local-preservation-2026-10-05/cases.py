"""Build detached paired cases; never modify historical experiment evidence."""

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "memory-layered-value-2026-10-05"
sys.path.insert(0, str(HERE.parent / "memory-structure-incremental-2026-10-05"))
from protocol import context, reader_context
from workspace import SITUATION, UNDERSTANDING, Workspace


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def paired_case(
    identity: str, role: str, workspace: Workspace, reference: dict
) -> dict:
    return {
        "id": identity,
        "role": role,
        "workspace": workspace,
        "workspace_copy": Workspace.restore(
            "two_layer", list(workspace.messages.values()), workspace.snapshot()
        ),
        "context": reference,
        "context_copy": deepcopy(reference),
    }


def warehouse() -> tuple[Workspace, Workspace]:
    """New synthetic domain, with a seeded stale comparison like the observed bug."""
    texts = [
        "甲倉我每天盤點，帳實數量差異超過 5% 才回報主管，先複盤並填差異單；不是我改 ERP。",
        "乙倉我每天 17:30 核對客戶退貨單與實收品，檢查分類並記錄；不能判定的列待判定，不算可用庫存。庫存異動由誰核准還沒確認，核准後由帳務專員改 ERP，不是我改。乙沒有提供差異百分比門檻。",
        "甲倉盤點資料我每個月末歸檔一次，保留差異單與主管回覆。",
        "甲倉剛才 5% 說錯了，是超過 8% 才回報。乙倉的異動核准人確認是倉儲主管，核准後仍由帳務專員改 ERP，其餘不變。",
    ]
    messages = [
        {"interview_sequence": index, "role": "user", "text": text}
        for index, text in enumerate(texts, 1)
    ]
    before = Workspace("two_layer", messages)
    before.read_through = 3
    count_body = "甲倉每天盤點；本人複盤並填差異單，帳實數量差異超過 5% 才回報主管，不自行異動 ERP。每個月末將差異單與主管回覆歸檔一次。"
    returns_body = "乙倉每天 17:30 由本人核對退貨單與實收品，檢查分類並記錄；無法判定的列待判定，不計可用庫存。異動核准人尚未確認；核准後由帳務專員異動 ERP，不由本人異動。乙倉差異百分比門檻尚未提供。"
    objects = [
        ("甲倉盤點與歸檔", "盤點差異回報及月末歸檔。", count_body, SITUATION, [1, 3]),
        (
            "乙倉退貨核對",
            "每天定時核對、分類與庫存異動分工。",
            returns_body,
            SITUATION,
            [2],
        ),
        (
            "甲倉盤點差異回報",
            "本人複盤、填單並依百分比門檻回報。",
            "甲倉每天盤點，本人複盤填差異單；帳實數量差異超過 5% 才回報主管，不自行異動 ERP。",
            UNDERSTANDING,
            ["object_1"],
        ),
        (
            "乙倉退貨核對與異動交接",
            "退貨核對、待判定狀態與核准交接；不套甲倉門檻。",
            returns_body + "甲倉超過 5% 的回報門檻不適用乙倉。",
            UNDERSTANDING,
            ["object_2"],
        ),
        (
            "甲倉盤點資料歸檔",
            "每月歸檔差異單及主管回覆。",
            "本人在每個月末將甲倉差異單與主管回覆歸檔一次。",
            UNDERSTANDING,
            ["object_1"],
        ),
    ]
    before.objects = {
        f"object_{index}": {
            "title": title,
            "description": description,
            "body": body,
            "layer": layer,
            "references": refs,
        }
        for index, (title, description, body, layer, refs) in enumerate(objects, 1)
    }
    before.next_id = 6
    current = Workspace.restore("two_layer", messages, before.snapshot())
    current.read_through = 4
    current.objects["object_1"]["body"] = count_body.replace("5%", "8%")
    current.objects["object_1"]["references"].append(4)
    current.objects["object_2"]["body"] = returns_body.replace(
        "異動核准人尚未確認", "異動由倉儲主管核准"
    )
    current.objects["object_2"]["references"].append(4)
    return before, current


def build_cases() -> list[dict]:
    previous = PREVIOUS / "live-01"
    material = load(previous / "materials.json")
    messages = material["messages"]
    initial = Workspace.restore(
        "two_layer", messages, load(previous / "workspace-initial-b2.json")
    )
    current = Workspace.restore(
        "two_layer", messages, load(previous / "workspace-corrections-b1.json")
    )
    correction = paired_case(
        "website-correction",
        "b2",
        current,
        context(current, "b2", {}, initial.views(SITUATION)),
    )
    read = Workspace.restore(
        "two_layer", messages, load(previous / "workspace-corrections-b2.json")
    )
    question = next(
        probe["question"]
        for probe in material["probes"]
        if probe["probe_id"] == "maintenance"
    )
    full = paired_case("website-task", "reader", read, reader_context(read, question))
    old_warehouse, new_warehouse = warehouse()
    warehouse_correction = paired_case(
        "warehouse-correction",
        "b2",
        new_warehouse,
        context(new_warehouse, "b2", {}, old_warehouse.views(SITUATION)),
    )
    # Both reader arms use the same manually prepared source-aligned snapshot,
    # not either B2 arm's output: this isolates A's instruction change.
    ready = Workspace.restore(
        "two_layer", list(new_warehouse.messages.values()), new_warehouse.snapshot()
    )
    ready.objects["object_3"]["body"] = ready.objects["object_3"]["body"].replace(
        "5%", "8%"
    )
    ready.objects["object_4"]["body"] = ready.objects["object_2"]["body"]
    full_warehouse = paired_case(
        "warehouse-task",
        "reader",
        ready,
        reader_context(
            ready,
            "請將乙倉退貨處理整理成一項完整 JD 任務，說明本人的工作與相關分工，保留必要條件；未知另列。",
        ),
    )
    narrow = Workspace.restore(
        "two_layer", list(ready.messages.values()), ready.snapshot()
    )
    detail = paired_case(
        "warehouse-detail",
        "reader",
        narrow,
        reader_context(
            narrow, "乙倉每天幾點核對退貨？只整理這個時點，不需要整份工作流程。"
        ),
    )
    return [correction, full, warehouse_correction, full_warehouse, detail]
