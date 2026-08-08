"""OPKS pre-gate 純函式(ADR 0054 決定 2–6)。

這是 application 的判斷,不是模型 routing:主顧問繼續擁有唯一聊天室與唯一 active
question,OPKS 是有邊界的 specialist。純函式的紀律沿用 0052 決定 1。

**pre-gate 只擋明顯過早,不宣稱資料完整。** 兩條禁令各有一筆測試釘住:
`purpose_result` 不得是硬條件(0052 決定 15),不得用引文數／字數／涵蓋度加強
(0052 決定 6 禁止的完成百分比換皮)。
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.job_analysis.application import (
    JobAnalysisState,
    eligible_opks_candidates,
)
from app.job_analysis.domain import (
    CurrentJdOpks,
    CurrentWorkModel,
    JdTask,
    OpenIssue,
    OpenIssueKind,
    OpenIssueTerminalResolution,
    OpenIssueTerminalResolutionKind,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksGapAxis,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    OpksProposalStatus,
    Retirement,
    RetirementKind,
    RetirementReason,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)


NOW = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


def employee_link(source_id: str = "turn-1", quote: str = "我每週彙整營運週報"):
    return SupportLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=source_id),
        quote=quote,
    )


def decision_link():
    return SupportLink(
        source_ref=SourceRef(kind=SourceKind.PROPOSAL_DECISION, id="decision-1"),
    )


def work_task(task_id: str = "task-1", *links: SupportLink, **overrides) -> Task:
    return Task(
        **{
            "task_id": task_id,
            "statement": "彙整營運週報，提供主管追蹤營運狀況",
            "action": "彙整",
            "object": "營運週報",
            "purpose_result": "提供主管追蹤營運狀況",
            "support_links": links or (employee_link(),),
            **overrides,
        }
    )


def jd_task(task_id: str = "task-1", display_order: int = 0) -> JdTask:
    return JdTask(
        task_id=task_id,
        statement="每週彙整營運週報",
        display_order=display_order,
    )


def state(
    *,
    tasks: tuple[Task, ...] = (),
    jd: tuple[JdTask, ...] = (),
    open_issues: tuple[OpenIssue, ...] = (),
    opks_proposals: tuple[OpksProposal, ...] = (),
    current_opks: CurrentJdOpks | None = None,
) -> JobAnalysisState:
    return JobAnalysisState(
        work_model=CurrentWorkModel(tasks=tasks, open_issues=open_issues),
        current_jd=jd,
        current_opks=current_opks or CurrentJdOpks(),
        opks_proposals=opks_proposals,
    )


def ready() -> JobAnalysisState:
    return state(tasks=(work_task(),), jd=(jd_task(),))


def issue(**overrides) -> OpenIssue:
    return OpenIssue(
        **{
            "id": "issue-1",
            "kind": OpenIssueKind.INSUFFICIENT_EVIDENCE,
            "summary": "還不確定這項工作的邊界",
            "source_anchors": (employee_link(),),
            **overrides,
        }
    )


def opks_item(entity_id: str = "output-1") -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=("task-1",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-1"),
                quote="我每週彙整營運週報",
            ),
        ),
    )


def opks_proposal(status: OpksProposalStatus) -> OpksProposal:
    terminal = status in {
        OpksProposalStatus.ACCEPTED,
        OpksProposalStatus.EDITED,
        OpksProposalStatus.REJECTED,
        OpksProposalStatus.STALE,
    }
    return OpksProposal(
        proposal_id="opks-proposal-1",
        operation_id="opks-operation-1",
        entity_id="output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        action=OpksProposalAction.ADD,
        after=opks_item(),
        base_authority_generation=0,
        created_at=NOW,
        status=status,
        resolved_at=NOW if terminal else None,
        rejection_reason="這其實是別人的產出" if status is OpksProposalStatus.REJECTED else None,
    )


def task_ids(candidates) -> tuple[str, ...]:
    return tuple(candidate.task_id for candidate in candidates)


# ── 通過的基準 ───────────────────────────────────────────────────────────────


def test_a_stable_task_with_employee_evidence_is_eligible():
    candidates = eligible_opks_candidates(ready())

    assert task_ids(candidates) == ("task-1",)
    assert candidates[0].analysis_input_digest


# ── 兩條明令禁止的加嚴 ───────────────────────────────────────────────────────


def test_a_missing_purpose_result_does_not_block_analysis():
    """0052 決定 15:工作產出可合法缺省,meaningful outcome 可隱含於 action + object。"""

    subject = state(
        tasks=(work_task(purpose_result=None),),
        jd=(jd_task(),),
    )

    assert task_ids(eligible_opks_candidates(subject)) == ("task-1",)


def test_a_single_short_quote_does_not_block_analysis():
    """決定 5:機械條件的誠實極限是「≥1 筆有效 SupportLink」。

    再往上就是 0052 決定 6 禁止的完成百分比換皮。證據太薄時由 specialist 回全
    `uncertain`,該 digest 的終端 receipt 使浪費上限為「每個輸入狀態一次呼叫」。
    """

    subject = state(
        tasks=(work_task("task-1", employee_link(quote="對帳")),),
        jd=(jd_task(),),
    )

    assert task_ids(eligible_opks_candidates(subject)) == ("task-1",)


# ── 七個 pre-gate 條件各自單獨阻擋 ───────────────────────────────────────────


def test_a_task_outside_current_jd_is_not_analysed():
    assert eligible_opks_candidates(state(tasks=(work_task(),))) == ()


def test_a_task_pending_reconciliation_is_not_analysed():
    subject = state(
        tasks=(
            work_task(
                pending_reconciliation=SourceRef(
                    kind=SourceKind.DIRECT_EDIT,
                    id="edit-1",
                )
            ),
        ),
        jd=(jd_task(),),
    )

    assert eligible_opks_candidates(subject) == ()


def test_a_retired_task_is_not_analysed():
    subject = state(
        tasks=(
            work_task(
                retirement=Retirement(
                    kind=RetirementKind.WITHDRAWN,
                    reason=RetirementReason.PAST_WORK,
                    source_ref=SourceRef(
                        kind=SourceKind.EMPLOYEE_TURN,
                        id="turn-5",
                    ),
                )
            ),
        ),
        jd=(jd_task(),),
    )

    assert eligible_opks_candidates(subject) == ()


def test_a_task_without_effective_employee_evidence_is_not_analysed():
    """0049 決定 13:proposal_decision 不是 Evidence,不能拿來當分析依據。"""

    subject = state(
        tasks=(work_task("task-1", decision_link()),),
        jd=(jd_task(),),
    )

    assert eligible_opks_candidates(subject) == ()


def test_an_active_issue_about_the_task_blocks_analysis():
    subject = state(
        tasks=(work_task(),),
        jd=(jd_task(),),
        open_issues=(issue(subject_task_id="task-1"),),
    )

    assert eligible_opks_candidates(subject) == ()


def test_an_active_opks_gap_blocks_analysis():
    subject = state(
        tasks=(work_task(),),
        jd=(jd_task(),),
        open_issues=(
            issue(subject_task_id="task-1", opks_axis=OpksGapAxis.OUTPUT),
        ),
    )

    assert eligible_opks_candidates(subject) == ()


def test_a_terminal_gap_does_not_block_analysis():
    """決定 20:只有 active issue 阻擋 pre-gate。

    terminal issue 留著只作「已問過、勿重問」的 context memory;讓它繼續擋住分析,
    等於員工誠實回答「不知道」之後這個 Task 就永遠不再被分析。
    """

    subject = state(
        tasks=(work_task(),),
        jd=(jd_task(),),
        open_issues=(
            issue(
                subject_task_id="task-1",
                opks_axis=OpksGapAxis.OUTPUT,
                terminal_resolution=OpenIssueTerminalResolution(
                    kind=OpenIssueTerminalResolutionKind.EMPLOYEE_UNKNOWN,
                    source_ref=SourceRef(
                        kind=SourceKind.EMPLOYEE_TURN,
                        id="turn-9",
                    ),
                ),
            ),
        ),
    )

    assert task_ids(eligible_opks_candidates(subject)) == ("task-1",)


def test_a_reconciliation_issue_about_the_task_blocks_analysis():
    subject = state(
        tasks=(work_task(),),
        jd=(jd_task(),),
        open_issues=(issue(reconciliation_task_id="task-1"),),
    )

    assert eligible_opks_candidates(subject) == ()


def test_an_issue_pointing_at_another_task_does_not_block_analysis():
    subject = state(
        tasks=(work_task(),),
        jd=(jd_task(),),
        open_issues=(issue(subject_task_id="task-2"),),
    )

    assert task_ids(eligible_opks_candidates(subject)) == ("task-1",)


def test_a_pending_or_deferred_opks_proposal_blocks_analysis():
    for status in (OpksProposalStatus.PENDING, OpksProposalStatus.DEFERRED):
        subject = state(
            tasks=(work_task(),),
            jd=(jd_task(),),
            opks_proposals=(opks_proposal(status),),
        )

        assert eligible_opks_candidates(subject) == (), status


def test_a_rejected_opks_proposal_does_not_block_analysis():
    """決定 14:拒絕回饋是 rejection memory,不是分析觸發器,也不該是永久封鎖。"""

    subject = state(
        tasks=(work_task(),),
        jd=(jd_task(),),
        opks_proposals=(opks_proposal(OpksProposalStatus.REJECTED),),
    )

    assert task_ids(eligible_opks_candidates(subject)) == ("task-1",)


def test_the_task_the_consultant_just_asked_about_is_not_analysed():
    """兩個 active question 的問題:員工不該同時被主顧問與 OPKS 問同一件事。"""

    assert eligible_opks_candidates(
        ready(),
        question_task_ids=frozenset({"task-1"}),
    ) == ()


# ── 排序(決定 6)───────────────────────────────────────────────────────────


def test_candidates_are_ordered_by_current_jd_display_order():
    """員工可隨時結束訪談,順序**會**影響最終覆蓋,所以必須決定性且 reload 一致。

    `immediate_task_ids` 只活在 `TransitionResult`,replay 不保留,因此排序必須從
    current state 重算。
    """

    subject = state(
        tasks=(work_task("task-a"), work_task("task-b")),
        jd=(jd_task("task-b", display_order=0), jd_task("task-a", display_order=1)),
    )

    assert task_ids(eligible_opks_candidates(subject)) == ("task-b", "task-a")


# ── 本輪已被問到的 Task(決定 3 的最後一條)──────────────────────────────────


def packet_for(*tasks: Task, open_issues: tuple[OpenIssue, ...] = ()):
    from app.job_analysis.application import ConversationTurn, TurnSpeaker, build_context_packet

    return build_context_packet(
        transcript=(
            ConversationTurn(
                turn_id="turn-1",
                speaker=TurnSpeaker.CONSULTANT,
                text="可以說說你的一週嗎？",
            ),
            ConversationTurn(
                turn_id="turn-2",
                speaker=TurnSpeaker.EMPLOYEE,
                text="我每週彙整營運週報",
            ),
        ),
        current_turn_id="turn-2",
        work_model=CurrentWorkModel(tasks=tasks, open_issues=open_issues),
    )


def result_with_target(target):
    from app.job_analysis.llm import NextQuestion, TaskAnalysisResult

    return TaskAnalysisResult(
        work_signals=(),
        next_question=NextQuestion(text="這份週報交給誰？", target=target),
    )


def test_no_question_target_blocks_nothing():
    from app.job_analysis.application import question_target_task_ids

    assert question_target_task_ids(
        result=result_with_target(None),
        packet=packet_for(work_task()),
        operation_id="operation-1",
    ) == frozenset()


def test_a_question_about_an_open_issue_blocks_its_subject_task():
    from app.job_analysis.application import question_target_task_ids
    from app.job_analysis.llm import NextQuestionTarget, NextQuestionTargetKind

    gap = issue(subject_task_id="task-1", opks_axis=OpksGapAxis.OUTPUT)

    assert question_target_task_ids(
        result=result_with_target(
            NextQuestionTarget(
                kind=NextQuestionTargetKind.EXISTING_OPEN_ISSUE,
                ordinal=1,
            )
        ),
        packet=packet_for(work_task(), open_issues=(gap,)),
        operation_id="operation-1",
    ) == frozenset({"task-1"})


def test_a_question_about_a_new_task_blocks_the_id_that_turn_will_mint():
    """剛加進 Current JD 的 Task 當輪就可能 eligible;漏掉它就會問兩題。"""

    from app.job_analysis.application import question_target_task_ids
    from app.job_analysis.llm import (
        IdentityAssessment,
        IdentityRelation,
        NextQuestion,
        NextQuestionTarget,
        NextQuestionTargetKind,
        SignalAnchor,
        SignalDisposition,
        TaskAnalysisResult,
        TaskChangeKind,
        TaskChangePayload,
        WorkSignal,
    )

    result = TaskAnalysisResult(
        work_signals=(
            WorkSignal(
                anchors=(SignalAnchor(turn_ordinal=2, quote="我每週彙整營運週報"),),
                identity=IdentityAssessment(relation=IdentityRelation.NO_MATCH),
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.ADD,
                    task_fields={
                        "statement": "每週彙整營運週報",
                        "action": "彙整",
                        "object": "營運週報",
                    },
                ),
            ),
        ),
        next_question=NextQuestion(
            text="這份週報交給誰？",
            target=NextQuestionTarget(
                kind=NextQuestionTargetKind.NEW_SIGNAL,
                index=0,
            ),
        ),
    )

    assert question_target_task_ids(
        result=result,
        packet=packet_for(work_task()),
        operation_id="operation-1",
    ) == frozenset({"operation-1-t0"})


# ── 三態呈現(ADR 0054 決定 36 ＋ 0052 決定 1–3、6–7)──────────────────────────


def status_of(subject, task_id: str = "task-1"):
    from app.job_analysis.application import opks_task_status

    return opks_task_status(subject, task_id)


def test_an_unanalysable_task_says_it_is_not_ready():
    from app.job_analysis.application import OpksTaskStatus

    assert status_of(
        state(tasks=(work_task("task-1", decision_link()),), jd=(jd_task(),))
    ) is OpksTaskStatus.NOT_READY


def test_a_task_with_an_unanswered_gap_says_information_is_still_needed():
    from app.job_analysis.application import OpksTaskStatus

    subject = state(
        tasks=(work_task(),),
        jd=(jd_task(),),
        open_issues=(
            issue(subject_task_id="task-1", opks_axis=OpksGapAxis.OUTPUT),
        ),
    )

    assert status_of(subject) is OpksTaskStatus.AWAITING_ANSWER


def test_a_task_with_pending_proposals_says_suggestions_are_ready():
    from app.job_analysis.application import OpksTaskStatus

    subject = state(
        tasks=(work_task(),),
        jd=(jd_task(),),
        opks_proposals=(opks_proposal(OpksProposalStatus.PENDING),),
    )

    assert status_of(subject) is OpksTaskStatus.PROPOSALS_READY


def test_an_unanswered_gap_outranks_pending_proposals():
    """決定 18 的 item-level 部分發布讓兩者同時存在是常態。

    這時只說「已可提出建議」會讓員工以為這個工作已經談完——那正是誠實邊界
    「不宣稱完整」要擋的事。
    """

    from app.job_analysis.application import OpksTaskStatus

    subject = state(
        tasks=(work_task(),),
        jd=(jd_task(),),
        open_issues=(
            issue(subject_task_id="task-1", opks_axis=OpksGapAxis.OUTPUT),
        ),
        opks_proposals=(opks_proposal(OpksProposalStatus.PENDING),),
    )

    assert status_of(subject) is OpksTaskStatus.AWAITING_ANSWER


def test_a_settled_task_gets_no_label_at_all():
    """ADR 0052 決定 6:「無法確定的一律不提示。」

    資料夠、沒缺口、沒待審提案的工作,可能還沒分析,也可能已經分析完且都處理掉了
    ——兩者無法從現況區分,所以不給第四個標籤,也不編一個出來。
    """

    assert status_of(ready()) is None


def test_only_three_labels_exist():
    """決定 36:狀態**僅**呈現這三種。多一個就是往完成度 dashboard 滑。"""

    from app.job_analysis.application import OpksTaskStatus

    assert {member.value for member in OpksTaskStatus} == {
        "awaiting_employee_answer",
        "proposals_ready",
        "not_ready_for_analysis",
    }
