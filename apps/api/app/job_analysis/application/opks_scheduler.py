"""OPKS pre-gate:哪些 Task 現在值得花一次分析(ADR 0054 決定 2–6)。

**這是 application 的純函式,不是模型 routing。** 主顧問繼續擁有唯一聊天室與唯一
active question;OPKS 是有邊界的 specialist。純函式的紀律沿用 0052 決定 1 把
readiness 放在純函式的同一條線。

**pre-gate 只擋明顯過早,不宣稱資料完整。** 兩條加嚴是被明令禁止的:

- `purpose_result` 不得列為硬條件——0052 決定 15 說工作產出可合法缺省,
  meaningful outcome 可隱含於 `action + object`。
- 不得以引文數、字數或涵蓋度加強——機械條件的誠實極限是「≥1 筆有效 SupportLink」,
  再往上就是 0052 決定 6 禁止的完成百分比換皮(決定 5)。

**「無相同 digest 的終端 receipt」這一條不在這裡。** 它要讀 journal,放進來就毀了
純函式。分兩層:這裡回傳已排序、含 digest 的候選,application 端再逐一
`journal.get(scheduled_opks_operation_id(candidate))`,取第一個沒有 receipt 的。
`journal.get()` 因此就是完整答案,不需要新 query port。
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from app.core.domain import (
    OpenIssue,
    OpksProposalStatus,
    Task,
    TaskId,
    TaskState,
)
from app.job_analysis.llm import (
    NextQuestionTargetKind,
    TaskAnalysisResult,
    TaskChangeKind,
)

from .context import TaskAnalysisPacket
from .opks_context import proposal_references_task
from .opks_digest import (
    ScheduledOpks,
    compute_analysis_input_digest,
    scheduled_opks_operation_id,
)
from .persistence import JobAnalysisUnitOfWork
from .transition import JobAnalysisState


BLOCKING_PROPOSAL_STATUSES = frozenset(
    {OpksProposalStatus.PENDING, OpksProposalStatus.DEFERRED}
)


def _issue_blocks(issue: OpenIssue, task_id: TaskId) -> bool:
    """這筆 active issue 指向這個 Task 嗎。

    只認 `subject_task_id`(OPKS gap)與 `reconciliation_task_id`(待對齊)——那是
    資料模型能表達的全部。一般 open issue 沒有 Task 指標,用文字比對去猜它在講哪個
    Task 是 0054 明令不做的事,所以這裡誠實地擋不住那一類。
    """

    if not issue.is_active:
        return False
    return task_id in {issue.subject_task_id, issue.reconciliation_task_id}


def eligible_opks_candidates(
    state: JobAnalysisState,
    *,
    question_task_ids: frozenset[TaskId] = frozenset(),
) -> tuple[ScheduledOpks, ...]:
    """回傳可分析的候選,依 Current JD `display_order` 排序(決定 6)。

    `question_task_ids` 是本輪 `next_question` 指向的 Task——員工不該同時被主顧問
    與 OPKS 問同一件事。解析 question target 需要 packet,屬呼叫端的工作。

    排序決定性且 reload 一致:`immediate_task_ids` 只活在 `TransitionResult`、
    replay 不保留,因此必須從 current state 重算。員工可隨時結束訪談,順序**會**
    影響最終覆蓋。
    """

    open_issues = state.work_model.open_issues
    candidates: list[ScheduledOpks] = []
    # `current_jd` 的 state invariant 已保證依 (display_order, task_id) 排序。
    for entry in state.current_jd:
        task = state.work_model.task_by_id(entry.task_id)
        if task is None or not _is_analysable(task):
            continue
        if entry.task_id in question_task_ids:
            continue
        if any(_issue_blocks(issue, entry.task_id) for issue in open_issues):
            continue
        if _has_blocking_proposal(state, entry.task_id):
            continue
        candidates.append(
            ScheduledOpks(
                task_id=entry.task_id,
                analysis_input_digest=compute_analysis_input_digest(task),
            )
        )
    return tuple(candidates)


class OpksTaskStatus(StrEnum):
    """一個 Task 的 OPKS 現況,只有三個可說的值(ADR 0054 決定 36)。

    這三個標籤存在的理由是**不宣稱完整**;因此每一個都必須是當下可查證的事實,
    不是「接下來會分析」這種意圖宣告。判不出來就**不提示**——ADR 0052 決定 6:
    「只有依現行官方規則能確定的缺漏才發聲;無法確定的一律不提示。」

    措辭受 0052 決定 7 約束(不得用「不完整」「不合格」「未通過」);中文字串住 Web,
    這裡只給固定 code——0052 決定 2:契約描述形狀,不描述政策。
    """

    AWAITING_ANSWER = "awaiting_employee_answer"
    PROPOSALS_READY = "proposals_ready"
    NOT_READY = "not_ready_for_analysis"


def opks_task_status(
    state: JobAnalysisState,
    task_id: TaskId,
) -> OpksTaskStatus | None:
    """純函式(0052 決定 1);Web 直接呈現結果,不自行重算(0052 決定 3)。

    **缺口優先於待審提案。** 兩者同時存在是常態(決定 18 的 item-level 部分發布),
    這時只說「已可提出建議」會讓員工以為這個工作已經談完了——那正是 `不宣稱完整`
    要擋的事。
    """

    if any(
        issue.is_active
        and issue.opks_axis is not None
        and issue.subject_task_id == task_id
        for issue in state.work_model.open_issues
    ):
        return OpksTaskStatus.AWAITING_ANSWER
    if _has_blocking_proposal(state, task_id):
        return OpksTaskStatus.PROPOSALS_READY
    if not any(
        candidate.task_id == task_id for candidate in eligible_opks_candidates(state)
    ):
        return OpksTaskStatus.NOT_READY
    # 資料夠、沒缺口、沒待審提案:可能還沒分析,也可能已經分析完且都處理掉了。
    # 兩者都無法從現況區分,依 0052 決定 6 一律不提示。
    return None


async def select_scheduled_opks(
    uow: JobAnalysisUnitOfWork,
    *,
    document_id: UUID,
    state: JobAnalysisState,
    question_task_ids: frozenset[TaskId] = frozenset(),
) -> ScheduledOpks | None:
    """挑出這一輪要排定的唯一 child,或 `None`。

    這是 pre-gate 的第二層:純函式給出排序好的候選,這裡對每個候選問
    `journal.get()`「這個輸入分析過了嗎」。**四種 outcome 都是終端 receipt**
    (決定 29),存在即跳過;abandon 不寫 receipt 所以不擋(決定 10)。
    """

    for candidate in eligible_opks_candidates(
        state,
        question_task_ids=question_task_ids,
    ):
        receipt = await uow.journal.get(
            document_id,
            scheduled_opks_operation_id(candidate),
        )
        if receipt is None:
            return candidate
    return None


def question_target_task_ids(
    *,
    result: TaskAnalysisResult,
    packet: TaskAnalysisPacket,
    operation_id: str,
) -> frozenset[TaskId]:
    """本輪 `next_question` 問到了哪些 Task。

    員工不該在同一輪同時被主顧問與 OPKS 問同一件事(決定 3 的最後一條)。兩種 target
    都要解:`existing_open_issue` 走 packet ordinal 找回 issue 的 Task 指標;
    `new_signal` 走該筆 signal 的 Task ordinal,**並算進本輪才鑄出來的 ID**——剛加進
    Current JD 的 Task 當輪就可能 eligible,漏掉它就會問兩題。
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


def _has_blocking_proposal(state: JobAnalysisState, task_id: TaskId) -> bool:
    """這個 Task 有待員工決定的 OPKS 提案嗎。

    pre-gate 與狀態呈現共用同一個判準:兩邊各寫一次,員工就會看到「已可提出建議」
    卻同時被系統再分析一次。
    """

    indicator_ids = _indicator_ids_for(state, task_id)
    return any(
        proposal.status in BLOCKING_PROPOSAL_STATUSES
        and proposal_references_task(
            proposal,
            selected_task_id=task_id,
            selected_indicator_ids=indicator_ids,
        )
        for proposal in state.opks_proposals
    )


def _is_analysable(task: Task) -> bool:
    return (
        task.state is TaskState.ACTIVE
        and bool(task.effective_employee_support_links)
    )


def _indicator_ids_for(state: JobAnalysisState, task_id: TaskId) -> frozenset[str]:
    from app.core.domain import OpksEntityKind

    return frozenset(
        item.entity_id
        for item in state.current_opks.items
        if item.entity_kind is OpksEntityKind.INDICATOR and task_id in item.task_refs
    )
