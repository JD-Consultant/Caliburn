"""T4:context assembler(研究稿 §11)。

重點在三件事:相同輸入產生逐字相同的 packet、ordinal↔ID mapping 正確且不進 domain、
待決 Proposal 明標「尚未成立」。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.job_analysis import domain as domain_package
from app.job_analysis.application import (
    ActiveQuestion,
    ConversationTurn,
    TurnSpeaker,
    build_context_packet,
    render_context_packet,
    verify_task_analysis_result,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    DomainModel,
    Enabler,
    EnablerKind,
    ExcludedSignal,
    ExclusionReason,
    JdEntry,
    JdTask,
    MergeTarget,
    OpenIssue,
    OpenIssueKind,
    Proposal,
    ProposalAction,
    ProposalStatus,
    Retirement,
    RetirementKind,
    RetirementReason,
    ResponsibilityRole,
    RevisionRequestResolution,
    SingleTaskTarget,
    SourceAnchor,
    SourceKind,
    SourceRef,
    StagedTask,
    StagedTaskLineage,
    StagedWorkModelDelta,
    SupportLink,
    Task,
    TaskFields,
)
from app.job_analysis.llm import (
    IdentityAssessment,
    IdentityRelation,
    NextQuestion,
    NextQuestionTarget,
    NextQuestionTargetKind,
    SignalAnchor,
    SignalDisposition,
    SupportOrdinalRef,
    TaskAnalysisResult,
    TaskChangeKind,
    TaskChangePayload,
    WorkSignal,
)


EMPLOYEE_TEXT = "我每週要出一份營運週報"


def employee_ref(turn_id: str = "turn-2") -> SourceRef:
    return SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=turn_id)


def support(**overrides) -> SupportLink:
    base = {
        "source_ref": employee_ref(),
        "quote": EMPLOYEE_TEXT,
        "question_turn_id": "turn-1",
    }
    base.update(overrides)
    return SupportLink(**base)


def make_task(task_id: str = "task-1", **overrides) -> Task:
    base = {
        "statement": "每週彙整營運週報並送交主管",
        "action": "彙整",
        "object": "營運週報",
        "purpose_result": "讓主管掌握營運狀況",
        "enablers": (Enabler(kind=EnablerKind.TOOL_SYSTEM, name="Excel"),),
        "support_links": (support(),),
    }
    base.update(overrides)
    return Task(task_id=task_id, **base)


def jd_task(
    task_id: str,
    statement: str,
    *,
    display_order: int = 0,
    purpose_result: str | None = None,
    context: str | None = None,
    frequency_text: str | None = None,
    responsibility_role: ResponsibilityRole | None = None,
    enablers: tuple[Enabler, ...] = (),
) -> JdTask:
    return JdTask(
        task_id=task_id,
        statement=statement,
        purpose_result=purpose_result,
        context=context,
        frequency_text=frequency_text,
        responsibility_role=responsibility_role,
        enablers=enablers,
        display_order=display_order,
    )


def retired_task(task_id: str = "task-9") -> Task:
    return make_task(
        task_id,
        statement="幫同事代班結帳",
        support_links=(support(superseded_by=employee_ref("turn-4")),),
        retirement=Retirement(
            kind=RetirementKind.WITHDRAWN,
            reason=RetirementReason.OTHER_PERSON,
            source_ref=employee_ref("turn-4"),
        ),
    )


TRANSCRIPT = (
    ConversationTurn(
        turn_id="turn-1", speaker=TurnSpeaker.CONSULTANT, text="可以說說你的一週嗎?"
    ),
    ConversationTurn(
        turn_id="turn-2", speaker=TurnSpeaker.EMPLOYEE, text=EMPLOYEE_TEXT
    ),
)


def build(**overrides):
    base = {
        "transcript": TRANSCRIPT,
        "current_turn_id": "turn-2",
        "work_model": CurrentWorkModel(tasks=(make_task(),)),
    }
    base.update(overrides)
    return build_context_packet(**base)


# ── 決定性(§11 完成條件)──────────────────────────────────────────────────


def test_same_input_produces_a_verbatim_identical_packet():
    work_model = CurrentWorkModel(
        tasks=(make_task(), retired_task()),
        open_issues=(
            OpenIssue(
                id="issue-1",
                kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
                summary="還不知道週報交給誰",
                source_anchors=(SourceAnchor(source_ref=employee_ref(), quote=EMPLOYEE_TEXT),),
            ),
        ),
        excluded_signals=(
            ExcludedSignal(
                id="ex-1",
                reason=ExclusionReason.OTHER_PERSON_WORK,
                summary="結帳是同事的工作",
                source_anchors=(SourceAnchor(source_ref=employee_ref(), quote=EMPLOYEE_TEXT),),
            ),
        ),
    )
    kwargs = {
        "work_model": work_model,
        "current_jd": (jd_task("task-1", "每週彙整營運週報"),),
        "active_question": ActiveQuestion(turn_id="turn-1", text="可以說說你的一週嗎?"),
    }
    first, second = build(**kwargs), build(**kwargs)
    assert first == second
    assert render_context_packet(first) == render_context_packet(second)
    assert render_context_packet(first).count("# Dynamic Context Packet") == 1


# ── ordinal↔ID mapping(§11.2、§9.3)──────────────────────────────────────


def test_ordinals_are_renumbered_each_round_and_spelled_out_in_the_packet():
    packet = build(
        work_model=CurrentWorkModel(tasks=(make_task("task-a"), make_task("task-b")))
    )
    assert [view.ordinal for view in packet.current_authorities.tasks] == [1, 2]
    assert [view.task.task_id for view in packet.current_authorities.tasks] == [
        "task-a",
        "task-b",
    ]
    assert [view.ordinal for view in packet.conversation_context.transcript] == [1, 2]
    assert packet.current_turn_ordinal == 2
    rendered = render_context_packet(packet)
    assert "[1] 每週彙整營運週報並送交主管" in rendered
    assert "[2] 員工: 我每週要出一份營運週報 ← 本次要分析的回合" in rendered
    assert (
        "      (1) [有效] [2] 「我每週要出一份營運週報」 回應提問 [1]" in rendered
    )


def test_retired_tasks_are_numbered_after_the_active_ones():
    """§11.4:另一組編號,唯讀;不相交才讓 verifier 判斷得出 target 指到已撤回的工作。"""
    packet = build(work_model=CurrentWorkModel(tasks=(make_task(), retired_task())))
    assert [view.ordinal for view in packet.current_authorities.tasks] == [1]
    assert [view.ordinal for view in packet.current_authorities.retired_tasks] == [2]
    rendered = render_context_packet(packet)
    assert "不得出現在任何 target" in rendered
    assert f"[2] 幫同事代班結帳 — withdrawn/other_person" in rendered


def test_ordinals_do_not_leak_into_the_domain():
    """§9.3:mapping 存在該輪呼叫紀錄側,不進產品 domain。"""
    offenders = [
        f"{name}.{field}"
        for name in dir(domain_package)
        for model in [getattr(domain_package, name)]
        if isinstance(model, type)
        and issubclass(model, DomainModel)
        for field in model.model_fields
        if "ordinal" in field
    ]
    assert offenders == []


def test_the_packet_feeds_the_verifier_with_the_same_ordinals():
    packet = build(work_model=CurrentWorkModel(tasks=(make_task(), retired_task())))
    context = packet.verification_context()
    assert context.task(1).task_id == "task-1"
    assert context.retired_task_ordinals == frozenset({2})
    assert context.current_turn_ordinal == 2

    result = TaskAnalysisResult(
        work_signals=(
            WorkSignal(
                anchors=(SignalAnchor(turn_ordinal=2, quote="營運週報"),),
                identity=IdentityAssessment(
                    relation=IdentityRelation.OVERLAP, target_task_ordinals=(1,)
                ),
                supersedes_support_ordinals=(
                    SupportOrdinalRef(task_ordinal=1, support_ordinal=1),
                ),
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.REVISE,
                    target_task_ordinals=(1,),
                    task_fields=TaskFields(
                        statement="改成雙週彙整", action="彙整", object="營運週報"
                    ),
                ),
            ),
        ),
        next_question=NextQuestion(
            text="雙週報交給誰?",
            purpose="釐清產出對象",
            target=NextQuestionTarget(
                kind=NextQuestionTargetKind.NEW_SIGNAL, index=0
            ),
        ),
    )
    assert verify_task_analysis_result(result, context).is_valid


def test_current_turn_must_be_an_employee_turn_in_the_transcript():
    with pytest.raises(ValueError, match="is not in the transcript"):
        build(current_turn_id="turn-99")
    with pytest.raises(ValidationError, match="current turn must be an employee turn"):
        build(current_turn_id="turn-1")


def test_transcript_turn_ids_must_be_unique():
    """ordinal↔turn_id 不是雙射時,anchor 會被解析到任意一個同名回合。"""
    duplicated = (
        *TRANSCRIPT,
        ConversationTurn(
            turn_id="turn-1", speaker=TurnSpeaker.CONSULTANT, text="再問一次"
        ),
    )
    with pytest.raises(ValidationError, match="duplicate transcript turn id"):
        build(transcript=duplicated)


@pytest.mark.parametrize(
    ("question", "message"),
    [
        (
            ActiveQuestion(turn_id="turn-9", text="可以說說你的一週嗎?"),
            "must reference a transcript turn",
        ),
        (
            ActiveQuestion(turn_id="turn-2", text=EMPLOYEE_TEXT),
            "must reference a consultant turn",
        ),
        (
            ActiveQuestion(turn_id="turn-3", text="那份週報交給誰?"),
            "must be earlier than the current turn",
        ),
        (
            ActiveQuestion(turn_id="turn-1", text="你平常都做些什麼?"),
            "text must match its transcript turn",
        ),
    ],
)
def test_active_question_must_be_the_earlier_consultant_turn_it_claims_to_be(
    question, message
):
    """指錯回合,員工的短答就會被接到另一個問題上,整條依據鏈從此指向錯的提問。"""
    transcript = (
        *TRANSCRIPT,
        ConversationTurn(
            turn_id="turn-3", speaker=TurnSpeaker.CONSULTANT, text="那份週報交給誰?"
        ),
    )
    with pytest.raises(ValidationError, match=message):
        build(transcript=transcript, active_question=question)


# ── jd_presence(§11.4)────────────────────────────────────────────────────


def test_jd_presence_carries_the_current_text_or_says_it_is_absent():
    packet = build(
        current_jd=(
            jd_task(
                "task-1",
                "每週彙整營運週報",
                purpose_result="讓主管掌握營運狀況",
                context="每週五結算後",
                frequency_text="每週一次",
                responsibility_role=ResponsibilityRole.PRIMARY,
                enablers=(
                    Enabler(kind=EnablerKind.TOOL_SYSTEM, name="Excel"),
                ),
            ),
        )
    )
    assert packet.current_authorities.tasks[0].in_jd
    rendered = render_context_packet(packet)
    assert "jd_presence: 在 Current JD——每週彙整營運週報" in rendered
    assert "jd_purpose_result: 讓主管掌握營運狀況" in rendered
    assert "jd_context: 每週五結算後" in rendered
    assert "jd_frequency: 每週一次" in rendered
    assert "jd_responsibility_role: primary" in rendered
    assert "jd_enablers: tool_system:Excel" in rendered
    assert "jd_presence: 不在 Current JD" in render_context_packet(build())


# ── open_issues／excluded_signals 的跨回合記憶(§11.4)──────────────────────


def test_open_issues_and_exclusions_show_their_anchors_and_last_asked():
    """少了 anchor 與 last-asked,模型看不出矛盾在哪兩句之間、也不知道剛剛才問過。"""
    work_model = CurrentWorkModel(
        tasks=(make_task(),),
        open_issues=(
            OpenIssue(
                id="issue-1",
                kind=OpenIssueKind.UNRESOLVED_CONTRADICTION,
                summary="是誰在做結帳",
                source_anchors=(
                    SourceAnchor(
                        source_ref=employee_ref(),
                        quote=EMPLOYEE_TEXT,
                        question_turn_id="turn-1",
                    ),
                    SourceAnchor(
                        source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-7")
                    ),
                ),
                last_asked_turn_id="turn-1",
            ),
        ),
        excluded_signals=(
            ExcludedSignal(
                id="ex-1",
                reason=ExclusionReason.OTHER_PERSON_WORK,
                summary="結帳是同事的工作",
                source_anchors=(
                    SourceAnchor(source_ref=employee_ref(), quote=EMPLOYEE_TEXT),
                ),
            ),
        ),
    )
    rendered = render_context_packet(build(work_model=work_model))
    assert f"    依據: [2] 「{EMPLOYEE_TEXT}」 回應提問 [1]" in rendered
    assert "    依據: (direct_edit) (無引用)" in rendered
    assert "    最近提問: [1]" in rendered
    assert f"- 他人工作: 結帳是同事的工作\n    依據: [2] 「{EMPLOYEE_TEXT}」" in rendered

    never_asked = render_context_packet(
        build(
            work_model=CurrentWorkModel(
                tasks=(make_task(),),
                open_issues=(
                    OpenIssue(
                        id="issue-2",
                        kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
                        summary="還不知道頻率",
                        source_anchors=(
                            SourceAnchor(source_ref=employee_ref(), quote=EMPLOYEE_TEXT),
                        ),
                    ),
                ),
            )
        )
    )
    assert "    最近提問: (尚未問過)" in never_asked


def test_jd_only_task_is_projected_through_its_open_issue_not_as_an_active_task():
    jd_only = jd_task("task-direct-1", "每週彙整營運週報")
    issue = OpenIssue(
        id="issue-direct-1",
        kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
        summary="員工剛新增，仍需分析工作內容",
        source_anchors=(
            SourceAnchor(
                source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-1")
            ),
        ),
        reconciliation_task_id=jd_only.task_id,
    )

    packet = build(
        work_model=CurrentWorkModel(open_issues=(issue,)),
        current_jd=(jd_only,),
    )

    assert packet.current_authorities.tasks == ()
    assert packet.current_authorities.open_issues[0].jd_task == jd_only
    assert (
        packet.verification_context().open_issues[0].reconciliation_task_id
        == jd_only.task_id
    )
    rendered = render_context_packet(packet)
    assert "Current JD Task: 每週彙整營運週報" in rendered
    assert "待分析欄位: purpose_result, context, frequency, responsibility_role" in rendered


def test_pending_jd_only_withdraw_is_derived_as_waiting_for_employee_decision():
    jd_only = jd_task("task-direct-1", "只幫同事做過一次盤點")
    issue = OpenIssue(
        id="issue-direct-1",
        kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
        summary="需要確認是否為正式責任",
        source_anchors=(
            SourceAnchor(
                source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-1")
            ),
        ),
        reconciliation_task_id=jd_only.task_id,
    )
    proposal = Proposal(
        proposal_id="proposal-withdraw-direct-1",
        target=SingleTaskTarget(
            action=ProposalAction.WITHDRAW,
            task_id=jd_only.task_id,
        ),
        jd_before=(JdEntry(task_id=jd_only.task_id, value=jd_only),),
        jd_after=(JdEntry(task_id=jd_only.task_id, value=None),),
    )

    rendered = render_context_packet(
        build(
            work_model=CurrentWorkModel(open_issues=(issue,)),
            current_jd=(jd_only,),
            proposals=(proposal,),
        )
    )

    assert "狀態: 等待員工決定 withdraw 提案" in rendered


def test_rendering_never_exposes_internal_ids():
    """§11.2:packet 只用 ordinal 說話;契約裡也沒有任何欄位可讓模型回填 ID。"""
    work_model = CurrentWorkModel(
        tasks=(make_task(), retired_task()),
        open_issues=(
            OpenIssue(
                id="issue-1",
                kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
                summary="還不知道週報交給誰",
                source_anchors=(
                    SourceAnchor(source_ref=employee_ref(), quote=EMPLOYEE_TEXT),
                ),
                last_asked_turn_id="turn-1",
            ),
        ),
    )
    rendered = render_context_packet(
        build(
            work_model=work_model,
            active_question=ActiveQuestion(turn_id="turn-1", text="可以說說你的一週嗎?"),
        )
    )
    for internal_id in ("task-1", "task-9", "issue-1", "turn-1", "turn-2"):
        assert internal_id not in rendered


# ── proposal_context(§11.1、§11.2、§9.6)─────────────────────────────────


def merge_proposal(status: ProposalStatus = ProposalStatus.PENDING, **overrides):
    base = {
        "proposal_id": "prop-1",
        "target": MergeTarget(
            new_task_id="task-new", member_task_ids=("task-1", "task-b")
        ),
        "jd_before": (
            JdEntry(
                task_id="task-1",
                value=jd_task("task-1", "每週彙整營運週報", display_order=0),
            ),
            JdEntry(
                task_id="task-b",
                value=jd_task("task-b", "每週追蹤缺料", display_order=1),
            ),
            JdEntry(task_id="task-new"),
        ),
        "jd_after": (
            JdEntry(task_id="task-1"),
            JdEntry(task_id="task-b"),
            JdEntry(
                task_id="task-new",
                value=jd_task(
                    "task-new",
                    "每週彙整營運週報並追蹤缺料",
                    display_order=0,
                ),
            ),
        ),
        "staged_work_model_delta": StagedWorkModelDelta(
            lineage_changes=tuple(
                StagedTaskLineage(
                    task_id=member,
                    retirement=Retirement(
                        kind=RetirementKind.MERGED, source_ref=employee_ref()
                    ),
                    merged_into="task-new",
                )
                for member in ("task-1", "task-b")
            ),
            new_tasks=(
                StagedTask(
                    task_id="task-new",
                    fields=TaskFields(
                        statement="合併後的工作", action="彙整", object="營運週報"
                    ),
                    support_links=(support(),),
                ),
            ),
        ),
        "status": status,
    }
    base.update(overrides)
    return Proposal(**base)


def test_pending_proposals_are_marked_as_not_yet_established():
    """§11.2:模型不得把待決提案當成現況事實。"""
    packet = build(
        work_model=CurrentWorkModel(tasks=(make_task(), make_task("task-b"))),
        proposals=(merge_proposal(),),
    )
    rendered = render_context_packet(packet)
    assert "尚未成立,不得當作現況事實" in rendered
    assert packet.proposal_context.pending[0].task_ordinals == (None, 1, 2)
    # §11.2:只引用 ordinal,不重複整份 Task 內容;staged 的新 ID 還不是 Task。
    assert "merge → (新項目), [1], [2](pending)" in rendered
    assert "task-new" not in rendered


def test_rejections_are_carried_only_for_tasks_in_this_packet():
    """§9.6:被拒絕的 topology 必須在再次分析相關 Task 時帶入,否則 direct edit
    會讓同一個判斷以「純 Work Model 整理」之姿無聲回來。"""
    relevant = merge_proposal(
        status=ProposalStatus.REJECTED, rejection_reason="這兩件事不一樣"
    )
    unrelated = Proposal(
        proposal_id="prop-2",
        target=SingleTaskTarget(action=ProposalAction.WITHDRAW, task_id="task-z"),
        jd_before=(
            JdEntry(
                task_id="task-z",
                value=jd_task("task-z", "舊的", display_order=0),
            ),
        ),
        jd_after=(JdEntry(task_id="task-z"),),
        staged_work_model_delta=StagedWorkModelDelta(
            lineage_changes=(
                StagedTaskLineage(
                    task_id="task-z",
                    retirement=Retirement(
                        kind=RetirementKind.WITHDRAWN,
                        reason=RetirementReason.EMPLOYEE_DENIED,
                        source_ref=employee_ref(),
                    ),
                ),
            )
        ),
        status=ProposalStatus.REJECTED,
    )
    packet = build(
        work_model=CurrentWorkModel(tasks=(make_task(), make_task("task-b"))),
        proposals=(relevant, unrelated),
    )
    assert len(packet.proposal_context.constraining_rejections) == 1
    rendered = render_context_packet(packet)
    assert "拒絕理由: 這兩件事不一樣" in rendered
    assert "task-z" not in rendered


def test_only_unresolved_revision_requests_are_carried():
    unresolved = merge_proposal(
        status=ProposalStatus.REVISION_REQUESTED, excluded_member_task_ids=("task-b",)
    )
    resolved = merge_proposal(
        proposal_id="prop-2",
        status=ProposalStatus.REVISION_REQUESTED,
        excluded_member_task_ids=("task-b",),
        revision_resolution=RevisionRequestResolution(
            closed_without_replacement_reason="重新分析後不需要改 JD"
        ),
    )
    packet = build(
        work_model=CurrentWorkModel(tasks=(make_task(), make_task("task-b"))),
        proposals=(unresolved, resolved),
    )
    assert len(packet.proposal_context.open_revision_requests) == 1
    assert "員工要求排除: [2]" in render_context_packet(packet)


# ── read-set(§11.3)───────────────────────────────────────────────────────


def test_read_set_is_the_projected_authority_data():
    """保守計入:當輪投影本身就是 read-set,不從模型輸出反推它讀了什麼。"""
    packet = build(proposals=(merge_proposal(),))
    assert packet.read_set == (packet.current_authorities, packet.proposal_context)
