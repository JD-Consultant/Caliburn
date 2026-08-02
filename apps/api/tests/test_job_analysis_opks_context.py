"""OPKS v1 的最小、高訊號 Context Packet。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.job_analysis.application import (
    OpksGroundingUnavailable,
    build_opks_context_packet,
    render_opks_context_packet,
)
from app.job_analysis.domain import (
    CurrentJdOpks,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    OpksProposalStatus,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)


NOW = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


def source(kind: SourceKind, source_id: str) -> SourceRef:
    return SourceRef(kind=kind, id=source_id)


def evidence(
    text: str = "我每週彙整營運週報",
    *,
    source_id: str = "turn-1",
) -> OpksEvidenceLink:
    return OpksEvidenceLink(
        source_ref=source(SourceKind.EMPLOYEE_TURN, source_id),
        quote=text,
    )


def task(*support_links: SupportLink) -> Task:
    return Task(
        task_id="task-selected",
        statement="彙整營運週報，提供主管追蹤營運狀況",
        action="彙整",
        object="營運週報",
        purpose_result="提供主管追蹤營運狀況",
        support_links=support_links,
    )


def item(
    entity_id: str,
    kind: OpksEntityKind,
    text: str,
    *,
    task_refs: tuple[str, ...] = (),
    indicator_refs: tuple[str, ...] = (),
) -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=kind,
        text=text,
        task_refs=task_refs,
        indicator_refs=indicator_refs,
        evidence_links=(evidence(),),
    )


def proposal(
    proposal_id: str,
    after: OpksItem,
    *,
    status: OpksProposalStatus = OpksProposalStatus.PENDING,
) -> OpksProposal:
    return OpksProposal(
        proposal_id=proposal_id,
        operation_id=f"operation-{proposal_id}",
        entity_id=after.entity_id,
        entity_kind=after.entity_kind,
        action=OpksProposalAction.ADD,
        after=after,
        status=status,
        rejection_reason="員工認為不是必要知識"
        if status is OpksProposalStatus.REJECTED
        else None,
        base_authority_generation=1,
        created_at=NOW,
        resolved_at=NOW if status is OpksProposalStatus.REJECTED else None,
    )


def selected_task() -> Task:
    old_ref = source(SourceKind.EMPLOYEE_TURN, "turn-old")
    correction_ref = source(SourceKind.EMPLOYEE_TURN, "turn-current")
    return task(
        SupportLink(
            source_ref=old_ref,
            quote="我每天整理所有報表",
            superseded_by=correction_ref,
        ),
        SupportLink(
            source_ref=correction_ref,
            quote="我每週彙整營運週報",
            question_turn_id="question-1",
        ),
        SupportLink(source_ref=source(SourceKind.DIRECT_EDIT, "edit-1")),
        SupportLink(
            source_ref=source(SourceKind.PROPOSAL_DECISION, "decision-1")
        ),
    )


def test_packet_projects_only_the_selected_task_and_relevant_opks_authority():
    output = item(
        "output-selected",
        OpksEntityKind.OUTPUT,
        "營運週報",
        task_refs=("task-selected",),
    )
    unrelated_output = item(
        "output-other",
        OpksEntityKind.OUTPUT,
        "排班表",
        task_refs=("task-other",),
    )
    indicator = item(
        "indicator-selected",
        OpksEntityKind.INDICATOR,
        "依約定時程完成週報",
        task_refs=("task-selected",),
    )
    knowledge = item(
        "knowledge-shared",
        OpksEntityKind.KNOWLEDGE,
        "營運指標定義",
        task_refs=("task-other",),
    )
    skill = item(
        "skill-unlinked",
        OpksEntityKind.SKILL,
        "資料彙整",
    )
    attitude = item(
        "attitude-hidden",
        OpksEntityKind.ATTITUDE,
        "細心",
    )
    relevant_pending = proposal(
        "proposal-relevant",
        item(
            "knowledge-new",
            OpksEntityKind.KNOWLEDGE,
            "門市營運指標",
            task_refs=("task-selected",),
        ),
    )
    relevant_rejected = proposal(
        "proposal-rejected",
        item(
            "skill-rejected",
            OpksEntityKind.SKILL,
            "統計建模",
            task_refs=("task-selected",),
        ),
        status=OpksProposalStatus.REJECTED,
    )
    unrelated_pending = proposal(
        "proposal-unrelated",
        item(
            "knowledge-other",
            OpksEntityKind.KNOWLEDGE,
            "排班規則",
            task_refs=("task-other",),
        ),
    )

    packet = build_opks_context_packet(
        selected_task=selected_task(),
        current_opks=CurrentJdOpks(
            items=(
                output,
                unrelated_output,
                indicator,
                knowledge,
                skill,
                attitude,
            )
        ),
        proposals=(relevant_pending, relevant_rejected, unrelated_pending),
    )

    assert packet.selected_task.task.task_id == "task-selected"
    assert [view.source_kind for view in packet.evidence] == [
        SourceKind.EMPLOYEE_TURN,
        SourceKind.DIRECT_EDIT,
    ]
    assert packet.item_view(OpksEntityKind.OUTPUT, 1).item == output
    assert packet.item_view(OpksEntityKind.INDICATOR, 1).item == indicator
    assert packet.item_view(OpksEntityKind.KNOWLEDGE, 1).item == knowledge
    assert packet.item_view(OpksEntityKind.SKILL, 1).item == skill
    assert packet.items_for(OpksEntityKind.ATTITUDE) == ()
    assert [view.proposal.proposal_id for view in packet.proposals] == [
        "proposal-relevant",
        "proposal-rejected",
    ]

    rendered = render_opks_context_packet(packet)
    assert rendered == render_opks_context_packet(packet)
    assert "彙整營運週報，提供主管追蹤營運狀況" in rendered
    assert "我每週彙整營運週報" in rendered
    assert "員工直接編輯" in rendered
    assert "營運週報" in rendered
    assert "營運指標定義" in rendered
    assert "資料彙整" in rendered
    assert "未連到選定工作；另連 1 個工作／0 個指標" in rendered
    assert "未連到選定工作；另連 0 個工作／0 個指標" in rendered
    assert "待決提案（尚未成立）" in rendered
    assert "已拒絕提案（避免重提）" in rendered

    for hidden in (
        "task-selected",
        "task-other",
        "turn-current",
        "edit-1",
        "proposal-relevant",
        "proposal-rejected",
        "排班表",
        "排班規則",
        "細心",
        "我每天整理所有報表",
    ):
        assert hidden not in rendered


def test_packet_refuses_to_call_the_model_without_effective_employee_grounding():
    with pytest.raises(OpksGroundingUnavailable):
        build_opks_context_packet(
            selected_task=task(
                SupportLink(
                    source_ref=source(SourceKind.PROPOSAL_DECISION, "decision-1")
                )
            ),
            current_opks=CurrentJdOpks(),
        )
