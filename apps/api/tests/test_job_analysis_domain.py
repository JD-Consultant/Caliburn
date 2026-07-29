"""T1:`app/job_analysis/domain` 的凍結形狀(研究稿 §9、§10)。

測試對著凍結文件寫,不是對著實作寫:enum 值域逐字比對、必填/可空、§10.5 的
`edited_jd_after` 四條硬規則、lineage 不成環。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.job_analysis.domain import (
    ALLOWED_STATUS_TRANSITIONS,
    TERMINAL_STATUSES,
    CurrentWorkModel,
    Enabler,
    EnablerKind,
    ExcludedSignal,
    ExclusionReason,
    JdEntry,
    MergeTarget,
    OpenIssue,
    OpenIssueKind,
    Proposal,
    ProposalAction,
    ProposalStatus,
    Retirement,
    RetirementKind,
    RetirementReason,
    RevisionRequestResolution,
    SingleTaskTarget,
    SourceAnchor,
    SourceKind,
    SourceRef,
    SplitTarget,
    StagedTask,
    StagedTaskLineage,
    StagedWorkModelDelta,
    SupportLink,
    Task,
    TaskFields,
    TaskState,
    is_allowed_transition,
    validate_edited_jd_after,
)


# ── helpers ─────────────────────────────────────────────────────────────────


def employee_ref(turn_id: str = "turn-3") -> SourceRef:
    return SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=turn_id)


def support(turn_id: str = "turn-3", **overrides) -> SupportLink:
    return SupportLink(
        source_ref=employee_ref(turn_id), quote="我每週要出一份週報", **overrides
    )


def make_task(task_id: str = "task-1", **overrides) -> Task:
    base = {
        "statement": "每週彙整營運週報並送交主管",
        "action": "彙整",
        "object": "營運週報",
        "support_links": (support(),),
    }
    base.update(overrides)
    return Task(task_id=task_id, **base)


def jd(*pairs: tuple[str, str | None]) -> tuple[JdEntry, ...]:
    return tuple(JdEntry(task_id=task_id, content=content) for task_id, content in pairs)


def merged_retirement() -> Retirement:
    return Retirement(kind=RetirementKind.MERGED, source_ref=employee_ref())


def merged_task(task_id: str, into: str) -> Task:
    return make_task(task_id, merged_into=into, retirement=merged_retirement())


def withdraw_delta(task_id: str = "task-1") -> StagedWorkModelDelta:
    return StagedWorkModelDelta(
        lineage_changes=(
            StagedTaskLineage(
                task_id=task_id,
                retirement=Retirement(
                    kind=RetirementKind.WITHDRAWN,
                    reason=RetirementReason.EMPLOYEE_DENIED,
                    source_ref=employee_ref(),
                ),
            ),
        )
    )


def merge_delta(
    members: tuple[str, ...] = ("task-1", "task-2"), new_task_id: str = "task-9"
) -> StagedWorkModelDelta:
    return StagedWorkModelDelta(
        lineage_changes=tuple(
            StagedTaskLineage(
                task_id=member,
                retirement=merged_retirement(),
                merged_into=new_task_id,
            )
            for member in members
        ),
        new_tasks=(
            StagedTask(
                task_id=new_task_id,
                fields=TaskFields(
                    statement="合併後的工作", action="彙整", object="營運週報"
                ),
                support_links=(support(),),
            ),
        ),
    )


# ── enum 值域(逐字對照凍結文件)────────────────────────────────────────────


def test_frozen_enum_value_domains():
    assert {member.value for member in SourceKind} == {
        "employee_turn",
        "direct_edit",
        "proposal_decision",
    }
    assert {member.value for member in EnablerKind} == {
        "tool_system",
        "method",
        "knowledge",
        "skill",
        "other",
    }
    assert {member.value for member in RetirementKind} == {
        "withdrawn",
        "merged",
        "split",
    }
    assert {member.value for member in RetirementReason} == {
        "other_person",
        "past_work",
        "one_off",
        "enabler_or_step",
        "employee_denied",
    }
    assert {member.value for member in OpenIssueKind} == {
        "責任邊界不明",
        "證據不足",
        "矛盾未解",
        "task_boundary_uncertain",
    }
    assert {member.value for member in ExclusionReason} == {
        "他人工作",
        "過去工作",
        "一次性支援",
        "工具或步驟",
        "員工否認",
    }
    assert {member.value for member in ProposalAction} == {
        "add",
        "revise",
        "withdraw",
        "merge",
        "split",
    }
    assert {member.value for member in ProposalStatus} == {
        "pending",
        "deferred",
        "accepted",
        "edited",
        "rejected",
        "revision_requested",
        "stale",
    }


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SourceRef(kind="employee_edit", id="x"),
        lambda: Enabler(kind="tooling", name="Excel"),
        lambda: OpenIssue(
            id="i1", kind="不明", summary="s", source_anchors=(SourceAnchor(source_ref=employee_ref()),)
        ),
        lambda: ExcludedSignal(
            id="e1",
            reason="他人的工作",
            summary="s",
            source_anchors=(SourceAnchor(source_ref=employee_ref()),),
        ),
    ],
)
def test_values_outside_the_enum_domain_are_rejected(factory):
    with pytest.raises(ValidationError):
        factory()


def test_domain_values_are_immutable_and_reject_unknown_fields():
    task = make_task()
    with pytest.raises(ValidationError):
        task.statement = "改一下"
    with pytest.raises(ValidationError):
        Task(
            task_id="task-1",
            statement="s",
            action="a",
            object="o",
            support_links=(support(),),
            confidence=0.9,
        )


# ── SourceAnchor／SupportLink(§9.1、§9.5)──────────────────────────────────


def test_employee_turn_anchor_requires_a_quote():
    with pytest.raises(ValidationError, match="requires a quote"):
        SourceAnchor(source_ref=employee_ref())


@pytest.mark.parametrize("kind", [SourceKind.DIRECT_EDIT, SourceKind.PROPOSAL_DECISION])
def test_non_employee_anchors_may_omit_the_quote(kind):
    anchor = SourceAnchor(source_ref=SourceRef(kind=kind, id="x"))
    assert anchor.quote is None


def test_support_link_is_effective_until_superseded():
    link = support()
    assert link.is_effective
    superseded = support(superseded_by=employee_ref("turn-9"))
    assert not superseded.is_effective


# ── Retirement／Task(§9.1、§9.2、§9.5)─────────────────────────────────────


def test_withdrawn_retirement_requires_a_reason():
    with pytest.raises(ValidationError, match="requires a reason"):
        Retirement(kind=RetirementKind.WITHDRAWN, source_ref=employee_ref())


@pytest.mark.parametrize("kind", [RetirementKind.MERGED, RetirementKind.SPLIT])
def test_only_withdrawn_retirement_carries_a_reason(kind):
    with pytest.raises(ValidationError, match="must not carry a reason"):
        Retirement(
            kind=kind,
            reason=RetirementReason.PAST_WORK,
            source_ref=employee_ref(),
        )


def test_merged_retirement_requires_merged_into():
    with pytest.raises(ValidationError, match="requires merged_into"):
        make_task(
            retirement=Retirement(kind=RetirementKind.MERGED, source_ref=employee_ref())
        )


def test_active_task_requires_one_effective_support_link():
    with pytest.raises(ValidationError, match="effective support link"):
        make_task(support_links=())
    with pytest.raises(ValidationError, match="effective support link"):
        make_task(support_links=(support(superseded_by=employee_ref("turn-9")),))


def test_retired_or_reconciling_tasks_may_have_no_effective_support():
    """§9.5 的原子性三出口:最後一條依據失效時,Task 必須同時走進其中一個出口。"""
    retired = make_task(
        support_links=(support(superseded_by=employee_ref("turn-9")),),
        retirement=Retirement(
            kind=RetirementKind.WITHDRAWN,
            reason=RetirementReason.EMPLOYEE_DENIED,
            source_ref=employee_ref("turn-9"),
        ),
    )
    assert retired.state is TaskState.RETIRED
    reconciling = make_task(
        support_links=(support(superseded_by=employee_ref("turn-9")),),
        pending_reconciliation=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-2"),
    )
    assert reconciling.state is TaskState.PENDING_RECONCILIATION
    assert make_task().state is TaskState.ACTIVE


def test_retired_task_may_not_also_be_pending_reconciliation():
    """並存時推導狀態只會顯示 retired,那筆等著對齊的員工編輯就靜默消失。"""
    with pytest.raises(ValidationError, match="not also be pending reconciliation"):
        make_task(
            support_links=(support(superseded_by=employee_ref("turn-9")),),
            pending_reconciliation=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-2"),
            retirement=Retirement(
                kind=RetirementKind.WITHDRAWN,
                reason=RetirementReason.ONE_OFF,
                source_ref=employee_ref("turn-9"),
            ),
        )


def test_merged_into_requires_a_merged_retirement():
    """`active` 卻帶 `merged_into` = 已併入別人還留在線上,同一件事會被提兩次。"""
    with pytest.raises(ValidationError, match="merged_into requires a merged retirement"):
        make_task(merged_into="task-9")
    with pytest.raises(ValidationError, match="merged_into requires a merged retirement"):
        make_task(
            merged_into="task-9",
            support_links=(support(superseded_by=employee_ref("turn-9")),),
            retirement=Retirement(
                kind=RetirementKind.WITHDRAWN,
                reason=RetirementReason.ONE_OFF,
                source_ref=employee_ref("turn-9"),
            ),
        )


def test_optional_semantic_fields_default_to_none():
    task = make_task()
    assert task.purpose_result is None
    assert task.context is None
    assert task.deliverable_hint is None
    assert task.success_criterion_hint is None
    assert task.enablers == ()


@pytest.mark.parametrize("missing", ["statement", "action", "object"])
def test_task_core_fields_are_required(missing):
    payload = {
        "task_id": "task-1",
        "statement": "s",
        "action": "a",
        "object": "o",
        "support_links": (support(),),
    }
    payload.pop(missing)
    with pytest.raises(ValidationError):
        Task(**payload)


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_text_is_not_a_value(blank):
    with pytest.raises(ValidationError):
        make_task(statement=blank)


# ── lineage(§9.5)──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "overrides",
    [
        {"merged_into": "task-1", "retirement": merged_retirement()},
        {"split_from": "task-1"},
    ],
)
def test_task_lineage_may_not_point_at_itself(overrides):
    with pytest.raises(ValidationError, match="itself"):
        make_task(**overrides)


def test_lineage_targets_must_exist_in_the_work_model():
    with pytest.raises(ValidationError, match="does not exist"):
        CurrentWorkModel(tasks=(make_task(split_from="task-missing"),))


def test_two_task_lineage_cycle_is_rejected():
    with pytest.raises(ValidationError, match="lineage cycle"):
        CurrentWorkModel(
            tasks=(merged_task("task-1", "task-2"), merged_task("task-2", "task-1"))
        )


def test_longer_lineage_cycle_across_both_edge_kinds_is_rejected():
    first = merged_task("task-1", "task-2")
    second = make_task("task-2", split_from="task-3")
    third = merged_task("task-3", "task-1")
    with pytest.raises(ValidationError, match="lineage cycle"):
        CurrentWorkModel(tasks=(first, second, third))


def test_acyclic_lineage_chain_is_accepted():
    survivor = make_task("task-3")
    merged = merged_task("task-1", "task-3")
    child = make_task("task-2", split_from="task-3")
    model = CurrentWorkModel(tasks=(merged, child, survivor))
    assert model.task_by_id("task-1") is merged
    assert model.task_by_id("task-nope") is None


def test_duplicate_identifiers_are_rejected():
    with pytest.raises(ValidationError, match="duplicate task id"):
        CurrentWorkModel(tasks=(make_task("task-1"), make_task("task-1")))


# ── open issues／excluded signals(§9.1、§9.5)───────────────────────────────


def test_open_issue_requires_at_least_one_anchor():
    with pytest.raises(ValidationError, match="at least one source anchor"):
        OpenIssue(
            id="issue-1",
            kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
            summary="無法判斷頻率",
            source_anchors=(),
        )


def test_unresolved_contradiction_requires_two_anchors():
    anchors = (SourceAnchor(source_ref=employee_ref(), quote="我負責結帳"),)
    with pytest.raises(ValidationError, match="at least two source anchors"):
        OpenIssue(
            id="issue-1",
            kind=OpenIssueKind.UNRESOLVED_CONTRADICTION,
            summary="前後說法不一致",
            source_anchors=anchors,
        )
    issue = OpenIssue(
        id="issue-1",
        kind=OpenIssueKind.UNRESOLVED_CONTRADICTION,
        summary="前後說法不一致",
        source_anchors=(
            *anchors,
            SourceAnchor(source_ref=employee_ref("turn-7"), quote="結帳是同事做的"),
        ),
    )
    assert issue.last_asked_turn_id is None


def test_excluded_signal_requires_an_anchor():
    with pytest.raises(ValidationError, match="at least one source anchor"):
        ExcludedSignal(
            id="ex-1",
            reason=ExclusionReason.OTHER_PERSON_WORK,
            summary="那是主管做的",
            source_anchors=(),
        )


# ── Proposal target(§10.2)──────────────────────────────────────────────────


def test_merge_target_requires_two_distinct_members():
    with pytest.raises(ValidationError, match="at least two member"):
        MergeTarget(new_task_id="task-9", member_task_ids=("task-1",))
    with pytest.raises(ValidationError, match="distinct"):
        MergeTarget(new_task_id="task-9", member_task_ids=("task-1", "task-1"))
    with pytest.raises(ValidationError, match="differ from its members"):
        MergeTarget(new_task_id="task-1", member_task_ids=("task-1", "task-2"))


def test_split_target_requires_two_children_that_exclude_the_parent():
    with pytest.raises(ValidationError, match="at least two children"):
        SplitTarget(parent_task_id="task-1", child_task_ids=("task-2",))
    with pytest.raises(ValidationError, match="not be one of its children"):
        SplitTarget(parent_task_id="task-1", child_task_ids=("task-1", "task-2"))


def test_affected_task_ids_follow_the_action_table():
    single = SingleTaskTarget(action=ProposalAction.REVISE, task_id="task-1")
    assert single.affected_task_ids == ("task-1",)
    merge = MergeTarget(new_task_id="task-9", member_task_ids=("task-1", "task-2"))
    assert merge.affected_task_ids == ("task-9", "task-1", "task-2")
    split = SplitTarget(parent_task_id="task-1", child_task_ids=("task-8", "task-9"))
    assert split.affected_task_ids == ("task-1", "task-8", "task-9")


# ── Proposal(§10.1、§10.3、§10.4)──────────────────────────────────────────


def add_proposal(**overrides) -> Proposal:
    base = {
        "proposal_id": "prop-1",
        "target": SingleTaskTarget(action=ProposalAction.ADD, task_id="task-1"),
        "jd_before": jd(("task-1", None)),
        "jd_after": jd(("task-1", "每週彙整營運週報")),
    }
    base.update(overrides)
    return Proposal(**base)


def test_jd_snapshots_must_cover_exactly_the_affected_tasks():
    with pytest.raises(ValidationError, match="jd_after must cover exactly"):
        add_proposal(jd_after=jd(("task-1", "x"), ("task-2", "y")))
    with pytest.raises(ValidationError, match="jd_before must cover exactly"):
        add_proposal(jd_before=())


def test_jd_entries_must_be_unique_and_sorted():
    with pytest.raises(ValidationError, match="duplicate task ids"):
        add_proposal(jd_after=jd(("task-1", "x"), ("task-1", "y")))
    merge_target = MergeTarget(new_task_id="task-9", member_task_ids=("task-1", "task-2"))
    with pytest.raises(ValidationError, match="must be sorted"):
        Proposal(
            proposal_id="prop-2",
            target=merge_target,
            jd_before=jd(("task-2", "b"), ("task-1", "a"), ("task-9", None)),
            jd_after=jd(("task-1", None), ("task-2", None), ("task-9", "合併後")),
        )


def test_withdraw_proposal_removes_a_task_that_is_in_the_jd():
    target = SingleTaskTarget(action=ProposalAction.WITHDRAW, task_id="task-1")
    with pytest.raises(ValidationError, match="requires the task to be in the JD"):
        Proposal(
            proposal_id="prop-1",
            target=target,
            jd_before=jd(("task-1", None)),
            jd_after=jd(("task-1", None)),
        )
    with pytest.raises(ValidationError, match="must remove the task from the JD"):
        Proposal(
            proposal_id="prop-1",
            target=target,
            jd_before=jd(("task-1", "舊文字")),
            jd_after=jd(("task-1", "新文字")),
        )


def test_staged_delta_is_only_for_cross_layer_topology():
    with pytest.raises(ValidationError, match="must not carry a staged work model delta"):
        add_proposal(staged_work_model_delta=merge_delta())

    merge = Proposal(
        proposal_id="prop-2",
        target=MergeTarget(new_task_id="task-9", member_task_ids=("task-1", "task-2")),
        jd_before=jd(("task-1", "a"), ("task-2", "b"), ("task-9", None)),
        jd_after=jd(("task-1", None), ("task-2", None), ("task-9", "合併後")),
        staged_work_model_delta=merge_delta(),
    )
    assert merge.action is ProposalAction.MERGE
    assert merge.affected_task_ids == ("task-9", "task-1", "task-2")


@pytest.mark.parametrize(
    ("target", "jd_before", "jd_after"),
    [
        (
            MergeTarget(new_task_id="task-9", member_task_ids=("task-1", "task-2")),
            jd(("task-1", "a"), ("task-2", "b"), ("task-9", None)),
            jd(("task-1", None), ("task-2", None), ("task-9", "合併後")),
        ),
        (
            SplitTarget(parent_task_id="task-1", child_task_ids=("task-8", "task-9")),
            jd(("task-1", "a"), ("task-8", None), ("task-9", None)),
            jd(("task-1", None), ("task-8", "子一"), ("task-9", "子二")),
        ),
        (
            SingleTaskTarget(action=ProposalAction.WITHDRAW, task_id="task-1"),
            jd(("task-1", "a")),
            jd(("task-1", None)),
        ),
    ],
)
def test_cross_layer_topology_proposals_require_a_staged_delta(
    target, jd_before, jd_after
):
    """§9.6／§10.4:`accepted`／`edited` 要兩層原子套用,少了 delta 就只改得動 JD——
    Task 從 JD 消失,Work Model 裡卻還 active 且毫髮無傷。"""
    with pytest.raises(ValidationError, match="requires a staged work model delta"):
        Proposal(
            proposal_id="prop-2",
            target=target,
            jd_before=jd_before,
            jd_after=jd_after,
        )


def test_empty_staged_delta_is_rejected():
    with pytest.raises(ValidationError, match="must not be empty"):
        StagedWorkModelDelta()


# ── §10.5 `edited` 的四條硬規則 ─────────────────────────────────────────────


def edited_proposal(edited: tuple[JdEntry, ...], **overrides) -> Proposal:
    return add_proposal(
        status=ProposalStatus.EDITED, edited_jd_after=edited, **overrides
    )


def test_edited_may_only_rewrite_the_text_of_a_non_null_entry():
    proposal = edited_proposal(jd(("task-1", "員工自己改的文字")))
    assert proposal.edited_jd_after == jd(("task-1", "員工自己改的文字"))


def test_edited_key_set_must_equal_jd_after():
    with pytest.raises(ValidationError, match="exactly the jd_after task ids"):
        edited_proposal(jd(("task-1", "x"), ("task-2", "y")))
    with pytest.raises(ValidationError, match="exactly the jd_after task ids"):
        edited_proposal(())


def test_edited_may_not_move_a_null_position():
    """第 2、3 條:null／非 null 位置必須相同,因此只有非 null 的內容能被改。"""
    with pytest.raises(ValidationError, match="keep the null position"):
        edited_proposal(jd(("task-1", None)))

    withdraw = {
        "target": SingleTaskTarget(action=ProposalAction.WITHDRAW, task_id="task-1"),
        "jd_before": jd(("task-1", "舊文字")),
        "jd_after": jd(("task-1", None)),
        "staged_work_model_delta": withdraw_delta(),
    }
    with pytest.raises(ValidationError, match="keep the null position"):
        edited_proposal(jd(("task-1", "員工想留著")), **withdraw)


def test_edited_payload_cannot_express_topology():
    """第 4 條:payload 只是 `{task_id -> content}`;要改 topology 只能改 key 集合,
    而那條路已經被第 1 條擋死——型別上沒有 action／target／成員可以填。"""
    assert set(JdEntry.model_fields) == {"task_id", "content"}
    merge_after = jd(("task-1", None), ("task-2", None), ("task-9", "合併後"))
    with pytest.raises(ValueError, match="exactly the jd_after task ids"):
        validate_edited_jd_after(
            merge_after, jd(("task-1", None), ("task-9", "只留一個成員"))
        )


def test_edited_status_and_payload_imply_each_other():
    with pytest.raises(ValidationError, match="requires edited_jd_after"):
        add_proposal(status=ProposalStatus.EDITED)
    with pytest.raises(ValidationError, match="edited status only"):
        add_proposal(
            status=ProposalStatus.ACCEPTED, edited_jd_after=jd(("task-1", "x"))
        )


# ── 其餘 payload × status(§10.1)────────────────────────────────────────────


def test_rejection_reason_belongs_to_rejected_only():
    assert add_proposal(status=ProposalStatus.REJECTED, rejection_reason="不是我的工作")
    assert add_proposal(status=ProposalStatus.REJECTED).rejection_reason is None
    with pytest.raises(ValidationError, match="rejected status only"):
        add_proposal(status=ProposalStatus.DEFERRED, rejection_reason="不是我的工作")


def test_stale_requires_an_employee_visible_reason():
    with pytest.raises(ValidationError, match="requires an employee-visible reason"):
        add_proposal(status=ProposalStatus.STALE)
    with pytest.raises(ValidationError, match="stale reason belongs"):
        add_proposal(status=ProposalStatus.PENDING, stale_reason="JD 已被改過")
    assert add_proposal(status=ProposalStatus.STALE, stale_reason="JD 已被改過")


def test_revision_request_requires_an_exclusion_from_its_own_members():
    merge_target = MergeTarget(new_task_id="task-9", member_task_ids=("task-1", "task-2"))
    merge_jd = {
        "jd_before": jd(("task-1", "a"), ("task-2", "b"), ("task-9", None)),
        "jd_after": jd(("task-1", None), ("task-2", None), ("task-9", "合併後")),
        "staged_work_model_delta": merge_delta(),
    }
    with pytest.raises(ValidationError, match="requires at least one exclusion"):
        Proposal(
            proposal_id="prop-2",
            target=merge_target,
            status=ProposalStatus.REVISION_REQUESTED,
            **merge_jd,
        )
    with pytest.raises(ValidationError, match="unknown excluded members"):
        Proposal(
            proposal_id="prop-2",
            target=merge_target,
            status=ProposalStatus.REVISION_REQUESTED,
            excluded_member_task_ids=("task-7",),
            **merge_jd,
        )
    with pytest.raises(ValidationError, match="apply to split proposals only"):
        Proposal(
            proposal_id="prop-2",
            target=merge_target,
            status=ProposalStatus.REVISION_REQUESTED,
            excluded_child_refs=("task-1",),
            **merge_jd,
        )
    accepted = Proposal(
        proposal_id="prop-2",
        target=merge_target,
        status=ProposalStatus.REVISION_REQUESTED,
        excluded_member_task_ids=("task-2",),
        **merge_jd,
    )
    assert accepted.excluded_member_task_ids == ("task-2",)


def test_exclusion_lists_belong_to_revision_requested_only():
    with pytest.raises(ValidationError, match="revision_requested status only"):
        Proposal(
            proposal_id="prop-2",
            target=MergeTarget(
                new_task_id="task-9", member_task_ids=("task-1", "task-2")
            ),
            status=ProposalStatus.PENDING,
            excluded_member_task_ids=("task-2",),
            jd_before=jd(("task-1", "a"), ("task-2", "b"), ("task-9", None)),
            jd_after=jd(("task-1", None), ("task-2", None), ("task-9", "合併後")),
            staged_work_model_delta=merge_delta(),
        )


def test_revision_resolution_is_exclusive_and_status_scoped():
    with pytest.raises(ValidationError, match="not both"):
        RevisionRequestResolution(
            replacement_proposal_id="prop-3",
            closed_without_replacement_reason="已不需要改 JD",
        )
    waiting = RevisionRequestResolution()
    assert waiting.replacement_proposal_id is None
    assert waiting.closed_without_replacement_reason is None
    with pytest.raises(ValidationError, match="revision_requested status only"):
        add_proposal(
            status=ProposalStatus.DEFERRED,
            revision_resolution=RevisionRequestResolution(replacement_proposal_id="p3"),
        )


# ── 狀態機(§10.1)──────────────────────────────────────────────────────────


def test_status_transitions_match_the_frozen_state_machine():
    non_terminal = {
        ProposalStatus.ACCEPTED,
        ProposalStatus.EDITED,
        ProposalStatus.REJECTED,
        ProposalStatus.REVISION_REQUESTED,
        ProposalStatus.STALE,
    }
    assert ALLOWED_STATUS_TRANSITIONS[ProposalStatus.PENDING] == (
        non_terminal | {ProposalStatus.DEFERRED}
    )
    assert ALLOWED_STATUS_TRANSITIONS[ProposalStatus.DEFERRED] == non_terminal
    assert TERMINAL_STATUSES == non_terminal
    assert is_allowed_transition(ProposalStatus.PENDING, ProposalStatus.DEFERRED)
    assert not is_allowed_transition(ProposalStatus.DEFERRED, ProposalStatus.PENDING)


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATUSES))
def test_terminal_proposals_never_become_stale(terminal):
    assert not is_allowed_transition(terminal, ProposalStatus.STALE)
    assert ALLOWED_STATUS_TRANSITIONS[terminal] == frozenset()
