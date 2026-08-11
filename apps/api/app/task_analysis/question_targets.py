"""哪些 Task 被本輪 `next_question` 問到了(T5)。

**這個函式只依賴 `task_analysis` 自己的契約**(`TaskAnalysisResult`／
`TaskAnalysisPacket`),不依賴 `app.opks` 的任何型別——它純粹是「解析這一輪主顧問
問題的 target」,回傳的 `frozenset[TaskId]` 才是跨 feature 的橋接資料,由呼叫端
(未來的 `consultation`,ADR 0058)拿去餵給 `app.opks.select_scheduled_opks()`。

歷史上這個函式與 OPKS 的 `select_scheduled_opks()` 寫在同一個檔案(pre-ADR-0058 的
`job_analysis/application/opks_scheduler.py`),但它本身從不引用 OPKS 型別;
留在 `opks_scheduler.py` 只是因為兩者被同一個呼叫端(`durable_turn.py`)一起用。
Task 5 把 `opks_scheduler.py` 拆給 `app.opks` 時,這個函式必須留在 `task_analysis`——
它是 `task_analysis` 已經擁有的 ID 配發規則(`transition._Writer`)的唯讀讀者,放進
`app.opks` 會違反 opks 只能 import core 的邊界(ADR 0058 rule 2)。
"""

from __future__ import annotations

from app.core.domain import TaskId

from .context import TaskAnalysisPacket
from .llm import NextQuestionTargetKind, TaskAnalysisResult, TaskChangeKind


def question_target_task_ids(
    *,
    result: TaskAnalysisResult,
    packet: TaskAnalysisPacket,
    operation_id: str,
) -> frozenset[TaskId]:
    """本輪 `next_question` 問到了哪些 Task。

    員工不該在同一輪同時被主顧問與 OPKS 問同一件事(ADR 0054 決定 3 的最後一條)。
    兩種 target 都要解:`existing_open_issue` 走 packet ordinal 找回 issue 的 Task
    指標;`new_signal` 走該筆 signal 的 Task ordinal,**並算進本輪才鑄出來的 ID**
    ——剛加進 Current JD 的 Task 當輪就可能 eligible,漏掉它就會問兩題。
    """

    target = result.next_question.target
    if target is None:
        return frozenset()

    if target.kind is NextQuestionTargetKind.EXISTING_OPEN_ISSUE:
        view = next(
            (
                candidate
                for candidate in packet.current_authorities.open_issues
                if candidate.ordinal == target.ordinal
            ),
            None,
        )
        if view is None:
            return frozenset()
        return frozenset(
            task_id
            for task_id in (
                view.issue.subject_task_id,
                view.issue.reconciliation_task_id,
            )
            if task_id is not None
        )

    if target.kind is not NextQuestionTargetKind.NEW_SIGNAL:
        return frozenset()
    index = target.index
    if index is None or not 0 <= index < len(result.work_signals):
        return frozenset()

    signal = result.work_signals[index]
    change = signal.task_change
    if change is None:
        return frozenset()

    ids = {
        view.task.task_id
        for ordinal in change.target_task_ordinals
        if (view := packet.task_view(ordinal)) is not None
    }
    # ID 配發規則住 `transition._Writer`;這裡照它推導,兩邊都由 operation_id + 位置
    # 決定,所以不需要 transition 回報。
    if change.change is TaskChangeKind.ADD:
        ids.add(f"{operation_id}-t{index}")
    elif change.change is TaskChangeKind.MERGE:
        ids.add(f"{operation_id}-m{index}")
    elif change.change is TaskChangeKind.SPLIT:
        ids.update(
            f"{operation_id}-s{index}-{position}"
            for position in range(len(change.split_children))
        )
    return frozenset(ids)
