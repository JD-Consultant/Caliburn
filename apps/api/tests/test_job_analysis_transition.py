"""T6:pure transition service(研究稿 §9.5、§9.6、§10、§12.2)。

覆蓋計畫指定的六件事:JD 外 withdraw 立即 retire、JD 內 withdraw 走 Proposal、
merge 成員全不在 JD 立即套用、任一成員在 JD 建立 Proposal、`active` Task 零有效支持
時三個出口的行為、同一輪混合立即套用與 Proposal。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.job_analysis.application import (
    ConversationTurn,
    JobAnalysisState,
    TransitionOutcome,
    TurnSpeaker,
    apply_task_analysis_result,
    build_context_packet,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdEntry,
    JdTask,
    MergeTarget,
    Proposal,
    ProposalAction,
    ProposalStatus,
    RetirementKind,
    RetirementReason,
    SingleTaskTarget,
    SourceKind,
    SourceRef,
    StagedTaskLineage,
    StagedWorkModelDelta,
    SupportLink,
    Task,
    TaskFields,
    TaskState,
    jd_map,
)
from app.job_analysis.llm import (
    ExcludePayload,
    IdentityAssessment,
    IdentityRelation,
    NextQuestion,
    OpenIssuePayload,
    SignalAnchor,
    SignalDisposition,
    SplitChildPayload,
    SupportOrdinalRef,
    TaskAnalysisResult,
    TaskChangeKind,
    TaskChangePayload,
    WorkSignal,
)
from app.job_analysis.domain import ExclusionReason, OpenIssueKind, Retirement


EMPLOYEE_TEXT = "我每週要出一份營運週報,也要追蹤缺料"
TRANSCRIPT = (
    ConversationTurn(
        turn_id="turn-1", speaker=TurnSpeaker.CONSULTANT, text="說說你的一週?"
    ),
    ConversationTurn(turn_id="turn-2", speaker=TurnSpeaker.EMPLOYEE, text=EMPLOYEE_TEXT),
)


def link(turn_id: str = "turn-2", quote: str = EMPLOYEE_TEXT) -> SupportLink:
    return SupportLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=turn_id), quote=quote
    )


def task(task_id: str, statement: str) -> Task:
    return Task(
        task_id=task_id,
        statement=statement,
        action="彙整",
        object="營運週報",
        support_links=(link(),),
    )


def fields(statement: str = "每週彙整營運週報") -> TaskFields:
    return TaskFields(statement=statement, action="彙整", object="營運週報")


def jd_task(
    task_id: str,
    statement: str,
    *,
    display_order: int = 0,
) -> JdTask:
    return JdTask(
        task_id=task_id,
        statement=statement,
        display_order=display_order,
    )


def state(*, jd: tuple[JdTask, ...] = (), proposals=()) -> JobAnalysisState:
    return JobAnalysisState(
        work_model=CurrentWorkModel(
            tasks=(task("task-1", "每週彙整營運週報"), task("task-2", "每週追蹤缺料"))
        ),
        current_jd=jd,
        proposals=proposals,
    )


def anchor(quote: str = "我每週要出一份營運週報") -> SignalAnchor:
    return SignalAnchor(turn_ordinal=2, quote=quote)


def signal(**overrides) -> WorkSignal:
    base = {
        "anchors": (anchor(),),
        "identity": IdentityAssessment(relation=IdentityRelation.NO_MATCH),
        "disposition": SignalDisposition.TASK_CHANGE,
        "task_change": TaskChangePayload(
            change=TaskChangeKind.ADD, task_fields=fields("每週追蹤客訴")
        ),
    }
    base.update(overrides)
    return WorkSignal(**base)


def change_signal(change: TaskChangeKind, targets: tuple[int, ...], **overrides):
    relation = {
        TaskChangeKind.REVISE: IdentityRelation.OVERLAP,
        TaskChangeKind.MERGE: IdentityRelation.OVERLAP,
    }.get(change, IdentityRelation.DUPLICATE)
    payload = {
        "change": change,
        "target_task_ordinals": targets,
        "task_fields": None if change is TaskChangeKind.WITHDRAW else fields("合併後的工作"),
        "withdraw_reason": (
            RetirementReason.EMPLOYEE_DENIED
            if change is TaskChangeKind.WITHDRAW
            else None
        ),
    }
    payload.update(overrides.pop("payload", {}))
    return signal(
        identity=IdentityAssessment(relation=relation, target_task_ordinals=targets),
        task_change=TaskChangePayload(**payload),
        **overrides,
    )


def apply(
    *signals: WorkSignal,
    current: JobAnalysisState | None = None,
    operation_id="op-1",
    transcript=TRANSCRIPT,
    current_turn_id="turn-2",
):
    current = current or state()
    packet = build_context_packet(
        transcript=transcript,
        current_turn_id=current_turn_id,
        work_model=current.work_model,
        current_jd=current.current_jd,
        proposals=current.proposals,
    )
    result = TaskAnalysisResult(
        work_signals=signals,
        next_question=NextQuestion(text="週報交給誰?", purpose="釐清產出對象"),
    )
    return apply_task_analysis_result(
        state=current, packet=packet, result=result, operation_id=operation_id
    )


IN_JD = (jd_task("task-1", "每週彙整營運週報"),)


# ── §12.2 mapping ───────────────────────────────────────────────────────────


def test_add_creates_a_candidate_task_immediately_without_a_proposal():
    """§9.6:`add` 不碰任何既有 identity;要不要進 JD 是後續的事。"""
    outcome = apply(signal())
    assert outcome.is_applied
    assert outcome.created_proposal_ids == ()
    created = outcome.state.work_model.task_by_id("op-1-t0")
    assert created.statement == "每週追蹤客訴"
    assert created.state is TaskState.ACTIVE
    assert len(created.support_links) == 1


def test_support_only_appends_evidence_without_touching_semantic_fields():
    outcome = apply(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.DUPLICATE, target_task_ordinals=(1,)
            ),
            disposition=SignalDisposition.SUPPORT_ONLY,
            task_change=None,
        )
    )
    task_one = outcome.state.work_model.task_by_id("task-1")
    assert task_one.statement == "每週彙整營運週報"
    assert len(task_one.support_links) == 2


def test_exclude_and_open_issue_land_in_their_own_collections():
    outcome = apply(
        signal(
            disposition=SignalDisposition.EXCLUDE,
            task_change=None,
            exclude=ExcludePayload(
                reason=ExclusionReason.OTHER_PERSON_WORK, summary="那是主管做的"
            ),
        ),
        signal(
            disposition=SignalDisposition.OPEN_ISSUE,
            task_change=None,
            open_issue=OpenIssuePayload(
                kind=OpenIssueKind.INSUFFICIENT_EVIDENCE, summary="還不知道頻率"
            ),
        ),
    )
    work_model = outcome.state.work_model
    assert [item.summary for item in work_model.excluded_signals] == ["那是主管做的"]
    assert [item.summary for item in work_model.open_issues] == ["還不知道頻率"]
    assert work_model.open_issues[0].source_anchors[0].quote == "我每週要出一份營運週報"


def test_revise_updates_in_place_and_only_proposes_when_the_jd_text_must_change():
    outside = apply(change_signal(TaskChangeKind.REVISE, (2,)))
    assert outside.created_proposal_ids == ()
    assert outside.state.work_model.task_by_id("task-2").statement == "合併後的工作"

    inside = apply(change_signal(TaskChangeKind.REVISE, (1,)), current=state(jd=IN_JD))
    assert inside.created_proposal_ids == ("op-1-p0",)
    proposal = inside.state.proposals[0]
    assert proposal.action is ProposalAction.REVISE
    assert jd_map(proposal.jd_before)["task-1"].statement == "每週彙整營運週報"
    assert jd_map(proposal.jd_after)["task-1"].statement == "合併後的工作"
    # Work Model 立即更新;等 JD 的只有文字。
    assert inside.state.work_model.task_by_id("task-1").statement == "合併後的工作"


# ── §9.6 identity gate ──────────────────────────────────────────────────────


def test_withdraw_outside_the_jd_retires_immediately_with_the_reason_the_model_gave():
    """「那只是去年代班一次」是 `one_off`,不是 `employee_denied`;寫死一種就是把
    撤回理由寫成假的,而只有模型讀得出員工說的是哪一種。"""
    outcome = apply(
        change_signal(
            TaskChangeKind.WITHDRAW,
            (2,),
            payload={"withdraw_reason": RetirementReason.ONE_OFF},
        )
    )
    assert outcome.created_proposal_ids == ()
    retired = outcome.state.work_model.task_by_id("task-2")
    assert retired.state is TaskState.RETIRED
    assert retired.retirement.kind is RetirementKind.WITHDRAWN
    assert retired.retirement.reason is RetirementReason.ONE_OFF
    assert retired.retirement.source_ref.id == "turn-2"


def test_retirement_source_is_an_anchor_the_model_actually_used():
    transcript = (
        *TRANSCRIPT,
        ConversationTurn(
            turn_id="turn-3",
            speaker=TurnSpeaker.EMPLOYEE,
            text="另外我今天只是來補充別件事",
        ),
    )

    outcome = apply(
        change_signal(TaskChangeKind.WITHDRAW, (2,)),
        transcript=transcript,
        current_turn_id="turn-3",
    )

    assert (
        outcome.state.work_model.task_by_id("task-2").retirement.source_ref.id
        == "turn-2"
    )


def test_withdraw_inside_the_jd_goes_through_a_proposal():
    outcome = apply(change_signal(TaskChangeKind.WITHDRAW, (1,)), current=state(jd=IN_JD))
    task_one = outcome.state.work_model.task_by_id("task-1")
    assert task_one.state is TaskState.PENDING_RECONCILIATION
    assert task_one.retirement is None

    proposal = outcome.state.proposals[0]
    assert proposal.action is ProposalAction.WITHDRAW
    assert jd_map(proposal.jd_after) == {"task-1": None}
    lineage = proposal.staged_work_model_delta.lineage_changes[0]
    assert lineage.task_id == "task-1"
    assert lineage.retirement.kind is RetirementKind.WITHDRAWN


def test_merge_applies_immediately_when_no_member_is_in_the_jd():
    outcome = apply(change_signal(TaskChangeKind.MERGE, (1, 2)))
    assert outcome.created_proposal_ids == ()
    survivor = outcome.state.work_model.task_by_id("op-1-m0")
    assert survivor.statement == "合併後的工作"
    for member in ("task-1", "task-2"):
        merged = outcome.state.work_model.task_by_id(member)
        assert merged.state is TaskState.RETIRED
        assert merged.retirement.kind is RetirementKind.MERGED
        assert merged.merged_into == "op-1-m0"


def test_merge_preserves_member_support_and_adds_the_current_signal():
    """多個故事支持同一 Task；merge 不可只留下最後一輪原話。"""
    first = task("task-1", "每週彙整營運週報").model_copy(
        update={"support_links": (link("turn-old-1", "先前週報故事"),)}
    )
    second = task("task-2", "每週追蹤缺料").model_copy(
        update={"support_links": (link("turn-old-2", "先前缺料故事"),)}
    )
    current = JobAnalysisState(
        work_model=CurrentWorkModel(tasks=(first, second)),
    )

    outcome = apply(change_signal(TaskChangeKind.MERGE, (1, 2)), current=current)

    survivor = outcome.state.work_model.task_by_id("op-1-m0")
    assert {
        support.source_ref.id for support in survivor.effective_support_links
    } == {"turn-old-1", "turn-old-2", "turn-2"}


def test_merge_with_a_member_in_the_jd_creates_a_proposal_and_stages_the_topology():
    outcome = apply(
        change_signal(TaskChangeKind.MERGE, (1, 2)), current=state(jd=IN_JD)
    )
    # 兩層都還沒動:JD 等員工決定,Work Model 的 topology 也還沒套用。
    assert outcome.state.work_model.task_by_id("task-1").state is TaskState.ACTIVE
    assert outcome.state.work_model.task_by_id("op-1-m0") is None

    proposal = outcome.state.proposals[0]
    assert isinstance(proposal.target, MergeTarget)
    assert proposal.affected_task_ids == ("op-1-m0", "task-1", "task-2")
    after = jd_map(proposal.jd_after)
    assert after["task-1"] is None
    assert after["task-2"] is None
    assert after["op-1-m0"].statement == "合併後的工作"
    delta = proposal.staged_work_model_delta
    assert {change.task_id for change in delta.lineage_changes} == {"task-1", "task-2"}
    assert [staged.task_id for staged in delta.new_tasks] == ["op-1-m0"]
    assert delta.new_tasks[0].support_links


def test_split_follows_the_same_gate():
    children = (
        SplitChildPayload(
            task_fields=fields("每週彙整營運週報"),
            inherited_support_ordinals=(1,),
        ),
        SplitChildPayload(
            task_fields=fields("每週追蹤缺料"),
            inherited_support_ordinals=(1,),
        ),
    )
    outside = apply(
        change_signal(
            TaskChangeKind.SPLIT,
            (2,),
            payload={"task_fields": None, "split_children": children},
        )
    )
    parent = outside.state.work_model.task_by_id("task-2")
    assert parent.retirement.kind is RetirementKind.SPLIT
    assert outside.state.work_model.task_by_id("op-1-s0-0").split_from == "task-2"
    assert outside.created_proposal_ids == ()

    inside = apply(
        change_signal(
            TaskChangeKind.SPLIT,
            (1,),
            payload={"task_fields": None, "split_children": children},
        ),
        current=state(jd=IN_JD),
    )
    assert inside.state.work_model.task_by_id("task-1").state is TaskState.ACTIVE
    assert inside.state.proposals[0].action is ProposalAction.SPLIT


def test_split_assigns_only_the_selected_parent_support_to_each_child():
    parent = task("task-1", "處理營運例行工作").model_copy(
        update={
            "support_links": (
                link("turn-old-1", "先前週報故事"),
                link("turn-old-2", "先前缺料故事"),
            )
        }
    )
    current = JobAnalysisState(work_model=CurrentWorkModel(tasks=(parent,)))
    children = (
        SplitChildPayload(
            task_fields=fields("每週彙整營運週報"),
            inherited_support_ordinals=(1,),
        ),
        SplitChildPayload(
            task_fields=fields("每週追蹤缺料"),
            inherited_support_ordinals=(2,),
        ),
    )

    outcome = apply(
        change_signal(
            TaskChangeKind.SPLIT,
            (1,),
            payload={"task_fields": None, "split_children": children},
        ),
        current=current,
    )

    first = outcome.state.work_model.task_by_id("op-1-s0-0")
    second = outcome.state.work_model.task_by_id("op-1-s0-1")
    assert {link.source_ref.id for link in first.support_links} == {
        "turn-old-1",
        "turn-2",
    }
    assert {link.source_ref.id for link in second.support_links} == {
        "turn-old-2",
        "turn-2",
    }


def test_one_round_can_mix_an_immediate_change_with_a_proposal():
    outcome = apply(
        signal(),
        change_signal(TaskChangeKind.WITHDRAW, (1,)),
        current=state(jd=IN_JD),
    )
    assert outcome.is_applied
    assert outcome.immediate_task_ids == ("op-1-t0",)
    assert outcome.created_proposal_ids == ("op-1-p1",)
    assert outcome.state.work_model.task_by_id("op-1-t0") is not None
    assert (
        outcome.state.work_model.task_by_id("task-1").state
        is TaskState.PENDING_RECONCILIATION
    )


# ── §9.5 原子性三出口 ───────────────────────────────────────────────────────


def supersede_task_one(**overrides) -> WorkSignal:
    return change_signal(
        overrides.pop("change"),
        overrides.pop("targets", (1,)),
        supersedes_support_ordinals=(
            SupportOrdinalRef(task_ordinal=1, support_ordinal=1),
        ),
        **overrides,
    )


def test_exit_one_a_new_effective_support_link_keeps_the_task_alive():
    outcome = apply(supersede_task_one(change=TaskChangeKind.REVISE))
    assert outcome.is_applied
    task_one = outcome.state.work_model.task_by_id("task-1")
    assert task_one.state is TaskState.ACTIVE
    assert [link.is_effective for link in task_one.support_links] == [False, True]


def test_exit_two_pending_reconciliation_absorbs_the_supersession():
    outcome = apply(
        supersede_task_one(change=TaskChangeKind.WITHDRAW), current=state(jd=IN_JD)
    )
    assert outcome.is_applied
    task_one = outcome.state.work_model.task_by_id("task-1")
    assert task_one.state is TaskState.PENDING_RECONCILIATION
    assert task_one.effective_support_links == ()


def test_exit_three_retirement_absorbs_the_supersession():
    outcome = apply(supersede_task_one(change=TaskChangeKind.WITHDRAW))
    assert outcome.is_applied
    assert outcome.state.work_model.task_by_id("task-1").state is TaskState.RETIRED


def test_a_write_that_takes_no_exit_is_rejected_whole():
    """JD 內的 merge 只 staged topology:成員仍 active,最後一條依據卻被取代。

    §9.5 要求這種寫入整筆拒絕——放行就會留下「active 但零有效支持」的 Task。
    """
    before = state(jd=IN_JD)
    outcome = apply(
        supersede_task_one(change=TaskChangeKind.MERGE, targets=(1, 2)), current=before
    )
    assert outcome.outcome is TransitionOutcome.REJECTED
    assert "effective support link" in outcome.detail
    assert outcome.state == before


def test_a_result_that_fails_the_verifier_is_rejected_without_touching_state():
    before = state()
    outcome = apply(signal(anchors=(anchor("我從來沒說過這句"),)), current=before)
    assert outcome.outcome is TransitionOutcome.REJECTED
    assert outcome.state == before


# ── §10.8 stale disposition ────────────────────────────────────────────────


def existing_withdraw_proposal() -> Proposal:
    return Proposal(
        proposal_id="prop-old",
        target=SingleTaskTarget(action=ProposalAction.WITHDRAW, task_id="task-1"),
        jd_before=(
            JdEntry(
                task_id="task-1",
                value=jd_task("task-1", "每週彙整營運週報"),
            ),
        ),
        jd_after=(JdEntry(task_id="task-1"),),
        staged_work_model_delta=StagedWorkModelDelta(
            lineage_changes=(
                StagedTaskLineage(
                    task_id="task-1",
                    retirement=Retirement(
                        kind=RetirementKind.WITHDRAWN,
                        reason=RetirementReason.EMPLOYEE_DENIED,
                        source_ref=SourceRef(
                            kind=SourceKind.EMPLOYEE_TURN, id="turn-2"
                        ),
                    ),
                ),
            )
        ),
    )


def test_a_pending_proposal_for_the_same_task_goes_stale_with_a_visible_reason():
    outcome = apply(
        change_signal(TaskChangeKind.REVISE, (1,)),
        current=state(jd=IN_JD, proposals=(existing_withdraw_proposal(),)),
    )
    assert outcome.staled_proposal_ids == ("prop-old",)
    stale = next(p for p in outcome.state.proposals if p.proposal_id == "prop-old")
    assert stale.status is ProposalStatus.STALE
    assert stale.stale_reason  # 員工看得到的理由,不是靜默消失


def test_a_pending_proposal_goes_stale_when_its_task_is_retired_this_round():
    outcome = apply(
        change_signal(TaskChangeKind.WITHDRAW, (1,)),
        current=state(proposals=(existing_withdraw_proposal(),)),
    )
    assert outcome.staled_proposal_ids == ("prop-old",)
    assert outcome.created_proposal_ids == ()


def test_reanalysis_closes_an_old_proposal_even_without_a_replacement():
    outcome = apply(
        change_signal(
            TaskChangeKind.REVISE,
            (1,),
            payload={"task_fields": fields("每週彙整營運週報")},
        ),
        current=state(jd=IN_JD, proposals=(existing_withdraw_proposal(),)),
    )

    assert outcome.created_proposal_ids == ()
    assert outcome.staled_proposal_ids == ("prop-old",)
    stale = next(p for p in outcome.state.proposals if p.proposal_id == "prop-old")
    assert stale.status is ProposalStatus.STALE
    assert stale.stale_reason


# ── 寫入權威與冪等 ──────────────────────────────────────────────────────────


def test_the_transition_never_touches_the_current_jd():
    """§9.4／§10:Proposal 只 gate Current JD;JD 只在員工決定時才改。"""
    before = state(jd=IN_JD)
    outcome = apply(change_signal(TaskChangeKind.WITHDRAW, (1,)), current=before)
    assert outcome.state.current_jd == before.current_jd


def test_id_allocation_is_deterministic_for_the_same_operation_and_state():
    """同一份結果對同一份起始 state → 同樣的 ID 與同樣的結果。

    **這不是 replay 冪等**:把結果對已套用過的 state 再送一次,support link 會被追加
    第二次、open issue 會因 ID 重複被拒。§5 要求的 exactly-once 需要 operation ledger,
    第一版不做,留給 persistence plan。
    """
    first = apply(signal())
    second = apply(signal())
    assert first.state == second.state
    assert first.immediate_task_ids == second.immediate_task_ids == ("op-1-t0",)


def test_operation_id_collision_never_overwrites_a_different_task():
    existing = task("op-1-t0", "既有且不同的工作")
    before = JobAnalysisState(work_model=CurrentWorkModel(tasks=(existing,)))

    outcome = apply(signal(), current=before, operation_id="op-1")

    assert outcome.outcome is TransitionOutcome.REJECTED
    assert outcome.state == before
    assert "collision" in outcome.detail


def test_state_rejects_duplicate_jd_and_proposal_ids():
    duplicate_jd = (
        jd_task("task-1", "版本一", display_order=0),
        jd_task("task-1", "版本二", display_order=1),
    )
    with pytest.raises(ValidationError, match="duplicate current JD task ids"):
        JobAnalysisState(current_jd=duplicate_jd)

    duplicate = existing_withdraw_proposal()
    with pytest.raises(ValidationError, match="duplicate proposal ids"):
        JobAnalysisState(proposals=(duplicate, duplicate))

    with pytest.raises(ValidationError, match="current JD must be sorted"):
        JobAnalysisState(
            current_jd=(
                jd_task("task-2", "二", display_order=1),
                jd_task("task-1", "一", display_order=0),
            )
        )

    with pytest.raises(ValidationError, match="display orders must be unique"):
        JobAnalysisState(
            current_jd=(
                jd_task("task-1", "一", display_order=0),
                jd_task("task-2", "二", display_order=0),
            )
        )


@pytest.mark.parametrize("operation_id", ["op-1", "op-2"])
def test_ids_are_namespaced_by_operation(operation_id):
    outcome = apply(signal(), operation_id=operation_id)
    assert outcome.immediate_task_ids == (f"{operation_id}-t0",)
