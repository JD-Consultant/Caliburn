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

from app.job_analysis.domain import (
    OpenIssue,
    OpksProposalStatus,
    Task,
    TaskId,
    TaskState,
)

from .opks_context import proposal_references_task
from .opks_digest import ScheduledOpks, compute_analysis_input_digest
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
    blocked_by_proposal = frozenset(
        proposal.entity_id
        for proposal in state.opks_proposals
        if proposal.status in BLOCKING_PROPOSAL_STATUSES
    )

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
        if any(
            proposal.entity_id in blocked_by_proposal
            and proposal_references_task(
                proposal,
                selected_task_id=entry.task_id,
                selected_indicator_ids=_indicator_ids_for(state, entry.task_id),
            )
            for proposal in state.opks_proposals
        ):
            continue
        candidates.append(
            ScheduledOpks(
                task_id=entry.task_id,
                analysis_input_digest=compute_analysis_input_digest(task),
            )
        )
    return tuple(candidates)


def _is_analysable(task: Task) -> bool:
    return (
        task.state is TaskState.ACTIVE
        and bool(task.effective_employee_support_links)
    )


def _indicator_ids_for(state: JobAnalysisState, task_id: TaskId) -> frozenset[str]:
    from app.job_analysis.domain import OpksEntityKind

    return frozenset(
        item.entity_id
        for item in state.current_opks.items
        if item.entity_kind is OpksEntityKind.INDICATOR and task_id in item.task_refs
    )
