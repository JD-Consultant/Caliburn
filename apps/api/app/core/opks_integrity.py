"""Shared OPKS aggregate referential integrity, consumed by documents and opks.

`prune_opks_for_current_jd`／`prune_opks_gaps_for_current_jd`:Current JD 的 Task
異動(員工直接編輯、Task Proposal 決策)必須同步清理 OPKS items 與缺口,這條規則被
`documents`(Current JD 直接編輯)與 `opks`(Task Proposal 決策)兩個未來模組共同消費
(ADR 0058 規則 7)。

`ACTIVE_OPKS_PROPOSAL_STATUSES`／`stale_invalid_opks_proposals`:OPKS Proposal 的
staleness 判斷同樣被兩邊共同消費——每次寫入 Current JD 或 OPKS 之前都要重新結算現存
提案是否仍然成立。
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.domain import (
    CurrentJdOpks,
    JdTask,
    OpenIssue,
    OpksEntityKind,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    OpksProposalStatus,
)


ACTIVE_OPKS_PROPOSAL_STATUSES = frozenset(
    {OpksProposalStatus.PENDING, OpksProposalStatus.DEFERRED}
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def prune_opks_gaps_for_current_jd(
    open_issues: tuple[OpenIssue, ...],
    current_jd: tuple[JdTask, ...],
) -> tuple[OpenIssue, ...]:
    """移除指向已不在 Current JD 的 Task 的 OPKS 缺口(ADR 0054 決定 26–27)。

    `prune_opks_for_current_jd()` 只收／回 `CurrentJdOpks`,**碰不到
    `work_model.open_issues`**;缺口的清理需要這個相鄰函式,在同一個 authority
    transaction、同一批呼叫點一起做。

    **這裡是「移除」,不是寫 `terminal_resolution`。** 那個欄位的兩個值
    (`employee_unknown`／`not_applicable`)都是**員工的回答**;Task 被刪除、撤回、
    合併或拆分時員工並沒有回答任何事,借用它們等於偽造一筆不存在的回答,而那筆假
    回答會進到 packet 的「已問過、勿重問」記憶區,被主顧問與 specialist 當真。

    **merge／split 一律移除,不遷移。** 沿用既有政策「不把舊 refs 猜接到 replacement
    Task」——沒有人知道新 Task 是不是還缺同一件事。真的還缺,下次分析會自己重新提出,
    那是有依據的判斷而不是猜測。
    """

    task_ids = frozenset(task.task_id for task in current_jd)
    return tuple(
        issue
        for issue in open_issues
        if issue.opks_axis is None or issue.subject_task_id in task_ids
    )


def prune_opks_for_current_jd(
    current_opks: CurrentJdOpks,
    current_jd: tuple[JdTask, ...],
) -> CurrentJdOpks:
    """Remove invalid Task-owned items and unlink shared K/S without guessing.

    O/P belong to one Task and disappear when that Task leaves Current JD. K/S
    survive as document-level items; only references to removed Tasks and the
    Indicators removed with them are pruned. Attitude is document-level and is
    unchanged. No old reference is guessed onto a merge/split replacement.
    """

    task_ids = frozenset(task.task_id for task in current_jd)
    retained = tuple(
        item
        for item in current_opks.items
        if item.entity_kind not in {
            OpksEntityKind.OUTPUT,
            OpksEntityKind.INDICATOR,
        }
        or item.task_refs[0] in task_ids
    )
    indicator_ids = frozenset(
        item.entity_id
        for item in retained
        if item.entity_kind is OpksEntityKind.INDICATOR
    )
    normalized: list[OpksItem] = []
    for item in retained:
        if item.entity_kind in {
            OpksEntityKind.KNOWLEDGE,
            OpksEntityKind.SKILL,
        }:
            normalized.append(
                item.model_copy(
                    update={
                        "task_refs": tuple(
                            task_id
                            for task_id in item.task_refs
                            if task_id in task_ids
                        ),
                        "indicator_refs": tuple(
                            indicator_id
                            for indicator_id in item.indicator_refs
                            if indicator_id in indicator_ids
                        ),
                    }
                )
            )
        else:
            normalized.append(item)
    return CurrentJdOpks(items=tuple(normalized))


def stale_invalid_opks_proposals(
    proposals: tuple[OpksProposal, ...],
    *,
    current_opks: CurrentJdOpks,
    current_jd: tuple[JdTask, ...],
    now: datetime | None = None,
) -> tuple[OpksProposal, ...]:
    """Mark only active proposals whose stable inputs no longer hold."""

    resolved_at = now or _utcnow()
    current_task_ids = frozenset(task.task_id for task in current_jd)
    accepted = tuple(
        proposal
        for proposal in proposals
        if proposal.status
        in {OpksProposalStatus.ACCEPTED, OpksProposalStatus.EDITED}
    )
    result: list[OpksProposal] = []
    for proposal in proposals:
        if proposal.status not in ACTIVE_OPKS_PROPOSAL_STATUSES:
            result.append(proposal)
            continue

        current = current_opks.item_by_id(proposal.entity_id)
        reason: str | None = None
        if proposal.action is OpksProposalAction.ADD and current is not None:
            reason = "同一項職務內容已經建立，舊提案不再適用。"
        elif proposal.action in {
            OpksProposalAction.REVISE,
            OpksProposalAction.REMOVE,
        } and current != proposal.before:
            reason = "職務內容已由員工修改或移除，舊提案不再適用。"

        referenced = proposal.after or proposal.before
        if reason is None and referenced is not None and not set(
            referenced.task_refs
        ).issubset(current_task_ids):
            reason = "提案引用的工作已不在目前職務說明書中。"

        if reason is None and any(
            decided.entity_id == proposal.entity_id
            and decided.resolved_at is not None
            and decided.resolved_at >= proposal.created_at
            for decided in accepted
        ):
            reason = "同一項職務內容已有其他提案生效。"

        if reason is None:
            result.append(proposal)
            continue
        result.append(
            OpksProposal.model_validate(
                {
                    **proposal.model_dump(),
                    "status": OpksProposalStatus.STALE,
                    "stale_reason": reason,
                    "resolved_at": resolved_at,
                }
            )
        )
    return tuple(result)
