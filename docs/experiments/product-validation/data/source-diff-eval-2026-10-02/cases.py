"""Fixed synthetic source-review cases; expected answers never enter visible inputs."""

from copy import deepcopy

PROTECTED_TEXT = "每月底本人複點高價品，再由倉庫主管確認差異。"
FACTS = {
    "frequency": "每月",
    "actor": "本人",
    "approver": "倉庫主管",
    "deadline": "結束當日",
    "scope": "一般存貨定期盤點",
}


def source_body(facts: dict[str, str]) -> str:
    """Purposeful unmodified work context, not repeated padding or hidden gold."""
    return f"""# 一般存貨的盤點與差異追查

## 工作範圍
適用範圍：{facts["scope"]}。
本情境不包含高價品月底專案；兩種盤點的交接與責任須分開理解。
員工將核准的盤點清單和倉位紀錄作為起點，不自行擴大盤點範圍。
盤點當日若仍有收貨，先辨認入帳時間，再比對實際收貨與系統截點。
尚在運送中的物料不因系統出現訂單就列為已入庫存貨。

## 執行頻率
頻率：{facts["frequency"]}。
排程由倉庫主管與現場確認，臨時插入的盤查與定期作業分開記錄。
同一批曾重複核對幾次，不代表平常就有相同次數的固定要求。

## 接收資料
本人取得盤點表、前次未結差異及當期入出庫紀錄。
品號一致但批號不同時分列，不能只以品名相近合併數量。
遇到缺少移轉單據，先標記資料不足，向提供單據的窗口查詢。
同事口述可作查詢線索，正式差異表仍要寫明可查回的資料。

## 現場複點
複點執行者：{facts["actor"]}。
本人负责核對、追查、整理差異，不因參與溝通就代表搬運或採購。
已確認是單位換算差異時，保留換算口徑，不逕自改動原始單據。
系統數量與現場不一致時，先分清漏登、時間差與真正短缺。

## 差異分析
本人按品號追查當期收貨、領用、退料與移轉紀錄。
若同一筆移轉被兩邊重複登記，先列明兩筆紀錄的關係。
遇到原因尚不確定的差異，保留待查原因與所缺資料，不寫成已查明。
先前批次的差異若仍未結案，延續原追查線索而不是重新建立同名案件。

## 權限
庫存調整核准者：{facts["approver"]}。
本人提出差異證據與處理建議，沒有核准補貨或採購的權限。
核准完成後，系統帳務由被授權的同事依正式紀錄處理。
調整前後的資料需能回查，但本人不負責制定公司會計政策。

## 交付
差異資料交付期限：{facts["deadline"]}。
交付內容包括差異品項、目前原因、查核過的資料及尚缺證據。
接收者需能區分已釐清與待釐清項目，不能把空白解讀成零差異。
缺資料時可以先交已確認部分，但須標明其範圍與未完原因。

## 知識與判斷
需理解庫存單位、批號、進出帳截點及單據前後關係。
使用試算表是核對資料的方法，不把單一軟體名稱視為工作目的。
重要的是定位差異與說明依據，而不是把每次排序篩選各寫成一個任務。
新人常把時間差當成遺失，故交接時須說明資料的時間範圍。

## 例外與未確認範圍
受管制品的特殊保管流程不在這次訪談的已確認範圍。
員工沒有說明年度盤點的頻率與角色，不以本情境自行外推。
盤點結果可能用於採購討論，但提出資料不代表決定採購數量。
此情境只支援上述工作範圍，不代表該員工所有工作都已訪談完成。
"""


def make_cases() -> list[dict]:
    """Six fixed cases; two carry a child source whose changed fact controls review."""
    result = []
    definitions = [
        ("frequency", {"frequency": "每季"}, "revise", "align", False),
        (
            "actor_scope",
            {"actor": "現場同事", "frequency": "每日"},
            "revise",
            "align",
            False,
        ),
        ("chain_only", {"approver": "營運主管"}, "revise", "align", True),
        ("removed", {}, "ask", "keep_pending", False),
        ("same_text", {}, "keep", "align", False),
        ("unknown", {"deadline": "未確認"}, "revise", "keep_pending", False),
    ]
    for name, changes, decision, reference_action, child_changed in definitions:
        old_facts = dict(FACTS)
        if name == "actor_scope":
            old_facts["frequency"] = "每日"
        new_facts = old_facts | changes
        old_body = source_body(old_facts)
        new_body = source_body(new_facts)
        if name == "unknown":
            new_body += "\n員工已撤回原本的當日要求；新期限仍需再向主管確認，不可宣稱來源核對已完成。\n"
        root_old = {
            "title": "一般存貨盤點與差異追查",
            "description": "一般存貨的頻率、複點分工、核准權限及交付要求；不含高價品月底專案。",
            "body": old_body,
            "interview_sequences": [2, 4],
            "source_titles": [],
        }
        root_new = deepcopy(root_old)
        root_new["body"] = new_body
        if changes:
            root_new["interview_sequences"] = [2, 4, 8]
        old_sources = [root_old]
        new_sources = [root_new]
        if child_changed:
            child_old = root_old
            child_new = root_new
            child_old["title"] = child_new["title"] = "一般存貨盤點現場情境"
            root_old = {
                "title": "一般存貨盤點與差異追查",
                "description": "整理一般存貨的查核責任；具體分工與期限以所引用情境為依據。",
                "body": "# 一般存貨盤點責任\n本人核對盤點資料、追查差異並交付有據的資料。\n具體頻率、複點分工、核准者及期限詳見直接情境依據。\n高價品月底專案是另一項工作，不受本次變更影響。\n",
                "interview_sequences": [],
                "source_titles": [child_old["title"]],
            }
            root_new = deepcopy(root_old)
            old_sources = [root_old, child_old]
            new_sources = [root_new, child_new]
        if name == "removed":
            new_sources = []
        result.append(
            {
                "case_id": name,
                "jd_facts": old_facts,
                "protected_task": PROTECTED_TEXT,
                "old_sources": old_sources,
                "new_sources": new_sources,
                "expected": {
                    "facts": old_facts if name == "removed" else new_facts,
                    "decision": decision,
                    "reference_action": reference_action,
                    "protected_task": PROTECTED_TEXT,
                },
            }
        )
    return result
