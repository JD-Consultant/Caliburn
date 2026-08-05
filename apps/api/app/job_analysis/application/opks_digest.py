"""`analysis_input_digest`:一個 Task 的 OPKS 分析輸入指紋(ADR 0054 決定 7、12–14)。

digest 是**付費邊界**:相同 digest 代表分析輸入沒變,不再自動重跑。因此納入與排除
都是契約——

- **納入**:Task 的六個語意欄位,與當前有效且**實際投影給 specialist** 的員工依據。
- **排除 `CurrentJdOpks` 與 `OpksProposal` 狀態**:納入會造成「接受 Proposal →
  寫入 `OpksItem` → digest 變 → 再分析」的 ping-pong(決定 13)。
- **排除 `rejection_reason`**:`OpksProposalDecisionPayload` 強制 REJECTED 必須帶
  reason,每次拒絕都必然產生新文字,進 digest 就是付費 reject loop(決定 14)。
  拒絕回饋只作為下次分析的 rejection memory,既不是 Evidence 也不是觸發器。

這三條排除在這裡是**簽章層事實**:函式只收一個 `Task`,呼叫端沒有東西可以多傳。
"""

from __future__ import annotations

import hashlib
import json

from app.job_analysis.domain import DomainModel, Identifier, NonEmptyText, Task, TaskId


class ScheduledOpks(DomainModel):
    """主回合 receipt 凍結的唯一 child(決定 7–8)。

    child operation ID 由這兩個值推導,**不重複持久化**——多存一份 ID 就多一個
    會與推導結果不一致的真相。
    """

    task_id: TaskId
    analysis_input_digest: NonEmptyText


def scheduled_opks_operation_id(scheduled: ScheduledOpks) -> Identifier:
    return f"opks:auto:{scheduled.task_id}:{scheduled.analysis_input_digest}"


def compute_analysis_input_digest(task: Task) -> str:
    """決定性、跨行程穩定的分析輸入指紋。

    用 canonical JSON + SHA-256,**不用內建 `hash()`** ——PYTHONHASHSEED 每個行程
    不同,會讓同一個輸入在重開後算出不同 digest,於是同一筆分析付兩次錢。
    """

    payload = {
        "statement": task.statement,
        "action": task.action,
        "object": task.object,
        "purpose_result": task.purpose_result,
        "context": task.context,
        "enablers": [
            {"kind": enabler.kind.value, "name": enabler.name}
            for enabler in task.enablers
        ],
        "evidence": [
            {
                "kind": link.source_ref.kind.value,
                "id": link.source_ref.id,
                "quote": link.quote,
            }
            for link in task.effective_employee_support_links
        ],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
