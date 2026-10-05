"""Synthetic purchasing work with distinct numbers, conditions and source positions."""

from uuid import NAMESPACE_URL, uuid5

from caliburn.contracts.generated.tools.historical_interview import (
    HistoricalInterview,
    HistoricalInterviewMessage,
)
from caliburn.contracts.generated.tools.memory_map import MemoryMap, MemoryMapItem
from caliburn.contracts.generated.tools.work_situation_view import WorkSituationView

TOPICS = (
    "一般採購月結",
    "採購申請核對",
    "供應商基本資料",
    "到貨日期追蹤",
    "採購單開立",
    "進貨差異追蹤",
    "採購付款資料",
    "價格變動彙整",
    "樣品收件核對",
    "合約有效期追蹤",
    "採購退貨核對",
    "供應商聯絡紀錄",
    "需求單位補件",
    "急件採購追蹤",
    "訂單交付核對",
    "一般採購週報",
    "供應商請款核對",
    "進貨單歸檔",
    "跨部門交接",
    "缺貨風險通知",
    "採購品項分類",
    "發票資料補件",
    "簽核退件追蹤",
    "替代品資料蒐集",
    "年度採購資料",
    "未交貨訂單檢查",
    "付款差異紀錄",
    "部門預算彙整",
    "採購資料權限",
    "供應商會議紀錄",
    "保固資料登錄",
    "詢價結果整理",
    "貨期異常回報",
    "採購報表查核",
    "年度議價資料",
    "一般採購季結",
)
FIELDS = ("frequency", "actor", "approver", "deadline", "scope", "authority")


def make_corpus() -> dict:
    messages = []
    objects = []
    cases = []
    for index, title in enumerate(TOPICS):
        first = index * 4 + 1
        frequency = f"每月{index % 4 + 1}次"
        deadline = f"下月第{index % 9 + 2}個工作日"
        scope = "國內一般採購" if index % 2 == 0 else "國外一般採購"
        approver = "採購主管" if index % 3 == 0 else "部門主管"
        old = (
            f"{title}由我處理，之前每季1次，範圍是{scope}。"
            f"由{approver}核准，我本人沒有核准權。"
            f"每次大約核對{index + 17}筆資料，先檢查申請單、採購單與到貨紀錄，"
            f"再核對單號、品項、數量及日期。單號以P{index + 101}開頭只是識別，不是版本。"
        )
        detail = []
        for item in range(1, 9):
            detail.append(
                f"作業條件{item}：處理第{item}類紀錄時，以{title}的原單據為準；"
                f"金額超過{(index + 1) * 1000 + item * 100}元只列出差異，不能自行核准。"
                f"需核對{item + 2}個欄位及附表{index + item + 1}，缺附件則通知承辦補件；"
                f"我登錄追蹤狀態，實際更動採購條件須由{approver}決定。"
            )
        update = (
            f"更正剛才{title}的頻率：目前是{frequency}，不是每季1次；"
            f"期限為{deadline}。剛才說的執行者、核准者、範圍及權限都沒有變動。"
            "每次結束會保留原單號與處理狀態，逾期項目另外列清單交核准者，"
            "不能把其他工作主題的頻率或期限套到這項工作。"
        )
        texts = [
            ("consultant", f"請說明{title}的處理範圍、頻率與核准責任。"),
            ("employee", old + "\n" + "\n".join(detail)),
            (
                "consultant",
                f"{title}目前頻率、期限有沒有更正？您的核准權與適用範圍呢？",
            ),
            ("employee", update),
        ]
        for offset, (speaker, text) in enumerate(texts):
            messages.append(
                HistoricalInterviewMessage(
                    interview_sequence=first + offset, speaker=speaker, text=text
                )
            )
        objects.append(
            WorkSituationView(
                title=title,
                description=f"本人處理{title}的資料核對、異常追蹤及責任界線，含頻率更正。",
                body=f"# {title}\n\n目前頻率：{frequency}。期限：{deadline}。執行者：本人。核准者：{approver}。"
                f"適用範圍：{scope}。權限：沒有核准權。\n\n## 作業條件\n\n"
                + "\n\n".join(detail)
                + "\n\n## 來源更正\n\n"
                + update,
                interview_references=[first + 1, first + 3],
            ).model_dump(mode="json")
        )
        if index in (0, 17, 35):
            cases.append(
                {
                    "case_id": f"context-{index + 1}",
                    "target_title": title,
                    "question": f"請核對「{title}」目前的頻率、執行者、核准者、期限、適用範圍與權限界線；用精確原文值回覆，列出共同支持全部六項結論的必要員工訪談序號，不列無關訊息。",
                    "expected": dict(
                        zip(
                            FIELDS,
                            (
                                frequency,
                                "本人",
                                approver,
                                deadline,
                                scope,
                                "沒有核准權",
                            ),
                            strict=True,
                        )
                    ),
                    "sources": [first + 1, first + 3],
                }
            )
    navigation = MemoryMap(
        items=[
            MemoryMapItem(target_title=item["title"], description=item["description"])
            for item in objects
        ]
    )
    return {
        "map": navigation.model_dump(mode="json"),
        "objects": objects,
        "interviews": HistoricalInterview(
            data_kind="historical_interview", messages=messages
        ).model_dump(mode="json"),
        "cases": cases,
    }


def make_locators(arm: str) -> dict:
    refs = {
        index: f"task_{uuid5(NAMESPACE_URL, f'caliburn-eval-task-{index}').hex}"
        if arm == "uuid"
        else f"task_{index}"
        for index in range(1, 49)
    }
    titles = {
        index: f"{TOPICS[(index - 1) % len(TOPICS)]}（{'平日' if index <= 36 else '月末'}）"
        for index in refs
    }
    # Reference IDs are a distinct kind, as in the production alias translator.
    citations = {
        index: f"citation_{uuid5(NAMESPACE_URL, f'caliburn-eval-citation-{index}').hex}"
        if arm == "uuid"
        else f"citation_{index + 48}"
        for index in range(1, 49)
    }
    return {
        "items": [
            {
                "read_ref": refs[index],
                "title": titles[index],
                "citation_ref": citations[index],
            }
            for index in refs
        ],
        "targets": {value: index for index, value in refs.items()},
        "citations": {value: index for index, value in citations.items()},
    }


def locator_cases() -> list[dict]:
    return [
        {
            "case_id": "locator-single",
            "indices": [19],
            "kind": "task",
            "question": "選取目前任務『跨部門交接（平日）』。",
        },
        {
            "case_id": "locator-order",
            "indices": [36, 2, 29],
            "kind": "task",
            "question": "依序選取：一般採購季結（平日）、採購申請核對（平日）、採購資料權限（平日）。",
        },
        {
            "case_id": "locator-similar",
            "indices": [37, 1],
            "kind": "task",
            "question": "依序選取：一般採購月結（月末）、一般採購月結（平日）；不得混同。",
        },
        {
            "case_id": "locator-history",
            "indices": [24],
            "kind": "task",
            "question": "沿用先前已選取的那一個替代品資料蒐集任務，不要改選其他任務。",
            "history": True,
        },
        {
            "case_id": "locator-citation",
            "indices": [45, 9],
            "kind": "citation",
            "question": "依序選取樣品收件核對（月末）、樣品收件核對（平日）各自目前的既存引用，不是任務定位。",
        },
        {
            "case_id": "locator-recovery",
            "indices": [11],
            "kind": "task",
            "question": "先前定位已失效；請從目前導覽重新選取採購退貨核對（平日）。",
            "recovery": True,
        },
    ]
