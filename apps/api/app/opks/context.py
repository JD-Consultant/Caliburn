"""OPKS v1 的最小動態 Context Packet。

這是單一 Task 的投影，不是通用 Context framework。模型只看得到可審查的 ordinal；
內部 Task、OPKS、Proposal 與來源 ID 留在 application-side mapping。
"""

from __future__ import annotations

from app.core.domain import (
    CurrentJdOpks,
    DomainModel,
    OpenIssue,
    OpenIssueTerminalResolutionKind,
    OpksEntityKind,
    OpksGapAxis,
    OpksItem,
    OpksProposal,
    OpksProposalStatus,
    SourceKind,
    SupportLink,
    Task,
)


VISIBLE_ENTITY_KINDS = (
    OpksEntityKind.OUTPUT,
    OpksEntityKind.INDICATOR,
    OpksEntityKind.KNOWLEDGE,
    OpksEntityKind.SKILL,
)
ACTIVE_OR_CONSTRAINING_PROPOSAL_STATUSES = frozenset(
    {
        OpksProposalStatus.PENDING,
        OpksProposalStatus.DEFERRED,
        OpksProposalStatus.REJECTED,
    }
)


class OpksGroundingUnavailable(ValueError):
    """選定 Task 沒有可供 OPKS 分析使用的員工來源。"""


class OpksSelectedTaskView(DomainModel):
    task: Task


class OpksEvidenceView(DomainModel):
    ordinal: int
    support_link: SupportLink

    @property
    def source_kind(self) -> SourceKind:
        return self.support_link.source_ref.kind


class OpksItemView(DomainModel):
    ordinal: int
    item: OpksItem


class OpksProposalView(DomainModel):
    proposal: OpksProposal


class OpksSettledGapView(DomainModel):
    """這個 Task 上已終結的缺口(ADR 0054 決定 20)。

    **specialist 也要看得到。** 少了這一區,員工回答「不知道」讓 digest 改變之後,
    下一次分析會對同一軸再開一次同一個缺口,員工就被重問一次已經答不出來的事。
    """

    axis: OpksGapAxis
    summary: str
    kind: OpenIssueTerminalResolutionKind


class OpksContextPacket(DomainModel):
    selected_task: OpksSelectedTaskView
    evidence: tuple[OpksEvidenceView, ...]
    outputs: tuple[OpksItemView, ...] = ()
    indicators: tuple[OpksItemView, ...] = ()
    knowledge: tuple[OpksItemView, ...] = ()
    skills: tuple[OpksItemView, ...] = ()
    proposals: tuple[OpksProposalView, ...] = ()
    settled_gaps: tuple[OpksSettledGapView, ...] = ()
    """已終結的缺口記憶;**不配發 ordinal**,specialist 不解決 issue。"""

    def items_for(self, kind: OpksEntityKind) -> tuple[OpksItemView, ...]:
        return {
            OpksEntityKind.OUTPUT: self.outputs,
            OpksEntityKind.INDICATOR: self.indicators,
            OpksEntityKind.KNOWLEDGE: self.knowledge,
            OpksEntityKind.SKILL: self.skills,
            OpksEntityKind.ATTITUDE: (),
        }[kind]

    def item_view(
        self, kind: OpksEntityKind, ordinal: int
    ) -> OpksItemView | None:
        return next(
            (view for view in self.items_for(kind) if view.ordinal == ordinal),
            None,
        )

    @property
    def read_set(self) -> tuple[Task, tuple[OpksItem, ...], tuple[OpksProposal, ...]]:
        """本輪實際投影出的 authority input；持久層可拿它做 stale 檢查。

        **`settled_gaps` 刻意不在裡面。** OPKS child 的 freshness 契約是
        `analysis_input_digest`(ADR 0054 決定 12:Task 語意欄位 ＋ 有效員工 evidence);
        終結記憶是 context,不是 authority input。放進來會製造一個與分析輸入無關的
        abandon 觸發器——別的 Task 上有人回答「不知道」,就會讓這個 child 白跑一趟。
        """

        return (
            self.selected_task.task,
            tuple(
                view.item
                for kind in VISIBLE_ENTITY_KINDS
                for view in self.items_for(kind)
            ),
            tuple(view.proposal for view in self.proposals),
        )


def _number(items: tuple[OpksItem, ...]) -> tuple[OpksItemView, ...]:
    return tuple(
        OpksItemView(ordinal=index, item=item)
        for index, item in enumerate(items, start=1)
    )


def proposal_references_task(
    proposal: OpksProposal,
    *,
    selected_task_id: str,
    selected_indicator_ids: frozenset[str],
) -> bool:
    for snapshot in (proposal.before, proposal.after, proposal.edited_after):
        if snapshot is None:
            continue
        if selected_task_id in snapshot.task_refs:
            return True
        if selected_indicator_ids.intersection(snapshot.indicator_refs):
            return True
    return False


def build_opks_context_packet(
    *,
    selected_task: Task,
    current_opks: CurrentJdOpks,
    proposals: tuple[OpksProposal, ...] = (),
    open_issues: tuple[OpenIssue, ...] = (),
) -> OpksContextPacket:
    """投影單一 Task 的 OPKS operation 所需最小現況。"""

    # 投影規則只有一個定義(`Task.effective_employee_support_links`),
    # `compute_analysis_input_digest()` 吃的是同一組——見 ADR 0054 決定 12。
    effective_employee_support = selected_task.effective_employee_support_links
    if not effective_employee_support:
        raise OpksGroundingUnavailable(
            "selected task requires effective employee evidence before OPKS generation"
        )

    selected_outputs = tuple(
        item
        for item in current_opks.items
        if item.entity_kind is OpksEntityKind.OUTPUT
        and selected_task.task_id in item.task_refs
    )
    selected_indicators = tuple(
        item
        for item in current_opks.items
        if item.entity_kind is OpksEntityKind.INDICATOR
        and selected_task.task_id in item.task_refs
    )
    selected_indicator_ids = frozenset(
        item.entity_id for item in selected_indicators
    )
    knowledge = tuple(
        item
        for item in current_opks.items
        if item.entity_kind is OpksEntityKind.KNOWLEDGE
    )
    skills = tuple(
        item
        for item in current_opks.items
        if item.entity_kind is OpksEntityKind.SKILL
    )
    relevant_proposals = tuple(
        OpksProposalView(proposal=proposal)
        for proposal in proposals
        if proposal.status in ACTIVE_OR_CONSTRAINING_PROPOSAL_STATUSES
        and proposal.entity_kind is not OpksEntityKind.ATTITUDE
        and proposal_references_task(
            proposal,
            selected_task_id=selected_task.task_id,
            selected_indicator_ids=selected_indicator_ids,
        )
    )

    settled_gaps = tuple(
        OpksSettledGapView(
            axis=issue.opks_axis,
            summary=issue.summary,
            kind=issue.terminal_resolution.kind,
        )
        for issue in open_issues
        if issue.opks_axis is not None
        and issue.subject_task_id == selected_task.task_id
        and not issue.is_active
    )

    return OpksContextPacket(
        settled_gaps=settled_gaps,
        selected_task=OpksSelectedTaskView(task=selected_task),
        evidence=tuple(
            OpksEvidenceView(ordinal=index, support_link=link)
            for index, link in enumerate(effective_employee_support, start=1)
        ),
        outputs=_number(selected_outputs),
        indicators=_number(selected_indicators),
        knowledge=_number(knowledge),
        skills=_number(skills),
        proposals=relevant_proposals,
    )


_ENTITY_LABELS = {
    OpksEntityKind.OUTPUT: "工作產出",
    OpksEntityKind.INDICATOR: "行為指標",
    OpksEntityKind.KNOWLEDGE: "知識",
    OpksEntityKind.SKILL: "技能",
}
_GAP_LABEL_KIND = {axis: OpksEntityKind(axis.value) for axis in OpksGapAxis}


def _append_items(
    lines: list[str],
    kind: OpksEntityKind,
    views: tuple[OpksItemView, ...],
    *,
    selected_task_id: str,
    selected_indicator_ids: frozenset[str],
) -> None:
    lines.append(f"## 現有{_ENTITY_LABELS[kind]}")
    if not views:
        lines.append("（目前沒有）")
        return
    for view in views:
        line = f"[{view.ordinal}] {view.item.text}"
        if kind in {OpksEntityKind.KNOWLEDGE, OpksEntityKind.SKILL}:
            linked = selected_task_id in view.item.task_refs or bool(
                selected_indicator_ids.intersection(view.item.indicator_refs)
            )
            other_tasks = sum(
                ref != selected_task_id for ref in view.item.task_refs
            )
            other_indicators = sum(
                ref not in selected_indicator_ids for ref in view.item.indicator_refs
            )
            line += (
                "（"
                + ("已連到選定工作" if linked else "未連到選定工作")
                + f"；另連 {other_tasks} 個工作／{other_indicators} 個指標）"
            )
        lines.append(line)


def render_opks_context_packet(packet: OpksContextPacket) -> str:
    """輸出給模型的文字；刻意不含任何 domain ID。"""

    task = packet.selected_task.task
    lines = [
        "# OPKS Dynamic Context",
        "## 選定工作",
        f"敘述：{task.statement}",
        f"動作：{task.action}",
        f"對象：{task.object}",
        f"目的／結果：{task.purpose_result or '（未明示）'}",
        f"條件／情境：{task.context or '（未明示）'}",
    ]
    if task.enablers:
        lines.append(
            "促成要素："
            + "、".join(f"{item.kind.value}:{item.name}" for item in task.enablers)
        )

    lines.extend(["## 員工依據"])
    for view in packet.evidence:
        link = view.support_link
        if link.source_ref.kind is SourceKind.EMPLOYEE_TURN:
            lines.append(f"[{view.ordinal}] 員工原話：{link.quote}")
        else:
            lines.append(
                f"[{view.ordinal}] 員工直接編輯（內容已反映於選定工作的目前語意）"
            )

    selected_indicator_ids = frozenset(
        view.item.entity_id for view in packet.indicators
    )
    for kind in VISIBLE_ENTITY_KINDS:
        _append_items(
            lines,
            kind,
            packet.items_for(kind),
            selected_task_id=task.task_id,
            selected_indicator_ids=selected_indicator_ids,
        )

    lines.append("## 已終結的缺口（已問過，勿重新提出）")
    if not packet.settled_gaps:
        lines.append("（目前沒有）")
    for gap in packet.settled_gaps:
        answer = {
            OpenIssueTerminalResolutionKind.EMPLOYEE_UNKNOWN: "員工表示不知道",
            OpenIssueTerminalResolutionKind.NOT_APPLICABLE: "員工表示不適用",
        }[gap.kind]
        lines.append(f"- {_ENTITY_LABELS[_GAP_LABEL_KIND[gap.axis]]}：{gap.summary} — {answer}")
    if packet.settled_gaps:
        lines.append(
            "以上缺口不要再輸出 uncertain；若這次的員工依據已足以支撐該軸，直接提出候選。"
        )

    lines.append("## 相關提案與拒絕記憶")
    if not packet.proposals:
        lines.append("（目前沒有）")
    for view in packet.proposals:
        proposal = view.proposal
        if proposal.status in {
            OpksProposalStatus.PENDING,
            OpksProposalStatus.DEFERRED,
        }:
            label = "待決提案（尚未成立）"
        else:
            label = "已拒絕提案（避免重提）"
        before = proposal.before.text if proposal.before is not None else "（無）"
        after = proposal.after.text if proposal.after is not None else "（移除）"
        line = (
            f"- {label}：{proposal.action.value} "
            f"{proposal.entity_kind.value}；原內容={before}；提議內容={after}"
        )
        if proposal.rejection_reason:
            line += f"；員工理由={proposal.rejection_reason}"
        lines.append(line)

    return "\n".join(lines) + "\n"
