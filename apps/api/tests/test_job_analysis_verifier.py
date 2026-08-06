"""T3:deterministic verifier(研究稿 §9.5、§12.3)。

每條規則都有正向與反向案例:反向證明它擋得住,正向證明它沒有順手擋掉合法輸出。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.job_analysis.application import (
    PacketOpenIssue,
    PacketRetiredTask,
    PacketSupportLink,
    PacketTask,
    PacketTurn,
    TurnSpeaker,
    VerificationContext,
    ViolationCode,
    verify_task_analysis_result,
)
from app.job_analysis.domain import (
    ExclusionReason,
    OpenIssueKind,
    RetirementReason,
    TaskFields,
)
from app.job_analysis.llm import (
    ExcludePayload,
    IdentityAssessment,
    IdentityRelation,
    NextQuestion,
    NextQuestionTarget,
    NextQuestionTargetKind,
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


EMPLOYEE_TEXT = "我每週要出一份營運週報,順便盯 request 3f0c-uuid 那張單"
CONSULTANT_TEXT = "可以說說你平常一週的工作嗎?"


def context(**overrides) -> VerificationContext:
    base = {
        "turns": (
            PacketTurn(
                ordinal=1,
                speaker=TurnSpeaker.CONSULTANT,
                turn_id="turn-1",
                text=CONSULTANT_TEXT,
            ),
            PacketTurn(
                ordinal=2,
                speaker=TurnSpeaker.EMPLOYEE,
                turn_id="turn-2",
                text=EMPLOYEE_TEXT,
            ),
        ),
        "current_turn_ordinal": 2,
        "tasks": (
            PacketTask(
                ordinal=1,
                task_id="task-1",
                support_links=(
                    PacketSupportLink(ordinal=1, is_effective=True),
                    PacketSupportLink(ordinal=2, is_effective=False),
                ),
            ),
            PacketTask(ordinal=2, task_id="task-2"),
        ),
        "retired_tasks": (PacketRetiredTask(ordinal=90, task_id="task-90"),),
        "open_issues": (PacketOpenIssue(ordinal=1, issue_id="issue-1"),),
    }
    base.update(overrides)
    return VerificationContext(**base)


def fields(statement: str = "每週彙整營運週報") -> TaskFields:
    return TaskFields(statement=statement, action="彙整", object="營運週報")


def anchor(turn_ordinal: int = 2, quote: str = "我每週要出一份營運週報") -> SignalAnchor:
    return SignalAnchor(turn_ordinal=turn_ordinal, quote=quote)


def signal(**overrides) -> WorkSignal:
    base = {
        "anchors": (anchor(),),
        "identity": IdentityAssessment(relation=IdentityRelation.NO_MATCH),
        "disposition": SignalDisposition.TASK_CHANGE,
        "task_change": TaskChangePayload(
            change=TaskChangeKind.ADD, task_fields=fields()
        ),
    }
    base.update(overrides)
    return WorkSignal(**base)


def result(*signals: WorkSignal, next_question: NextQuestion | None = None):
    signals = signals or (signal(),)
    return TaskAnalysisResult(
        work_signals=signals,
        next_question=next_question
        or NextQuestion(text="這份週報交給誰?"),
    )


def codes(*signals: WorkSignal, ctx: VerificationContext | None = None):
    return verify_task_analysis_result(result(*signals), ctx or context()).codes


# ── 正向基準 ────────────────────────────────────────────────────────────────


def test_a_well_formed_result_passes():
    report = verify_task_analysis_result(result(), context())
    assert report.is_valid
    assert report.violations == ()
    assert report.rejected_signal_indexes == frozenset()


def test_no_match_add_may_resolve_a_reconciliation_open_issue():
    ctx = context(
        open_issues=(
            PacketOpenIssue(
                ordinal=1,
                issue_id="issue-1",
                reconciliation_task_id="task-direct-1",
            ),
        )
    )

    assert verify_task_analysis_result(
        result(signal(resolves_open_issue_ordinal=1)), ctx
    ).is_valid


def test_exclude_may_resolve_a_reconciliation_open_issue():
    ctx = context(
        open_issues=(
            PacketOpenIssue(
                ordinal=1,
                issue_id="issue-1",
                reconciliation_task_id="task-direct-1",
            ),
        )
    )
    exclude = signal(
        resolves_open_issue_ordinal=1,
        disposition=SignalDisposition.EXCLUDE,
        task_change=None,
        exclude=ExcludePayload(
            reason=ExclusionReason.ONE_OFF_SUPPORT,
            summary="只代班過一次",
        ),
    )

    assert verify_task_analysis_result(result(exclude), ctx).is_valid


def test_open_issue_resolution_requires_an_issue_that_is_in_the_packet():
    assert ViolationCode.RESOLUTION_OPEN_ISSUE_UNKNOWN in codes(
        signal(resolves_open_issue_ordinal=99)
    )


def test_a_model_raised_open_issue_may_be_closed_by_any_disposition():
    """ADR 0047:只有處理這一輪答案的模型知道自己上一輪的問題有沒有被回答。"""
    ctx = context(open_issues=(PacketOpenIssue(ordinal=1, issue_id="issue-1"),))
    closing = signal(
        resolves_open_issue_ordinal=1,
        disposition=SignalDisposition.EXCLUDE,
        task_change=None,
        exclude=ExcludePayload(
            reason=ExclusionReason.OTHER_PERSON_WORK,
            summary="真正部署是平台組做的",
        ),
    )

    assert verify_task_analysis_result(result(closing), ctx).is_valid


def test_closing_an_open_issue_requires_the_current_turn_among_the_anchors():
    """與 supersession 同一條不變量:改寫既有結論要基於當下這次回答,不能批次清單。"""
    ctx = context(
        turns=(
            PacketTurn(ordinal=1, speaker=TurnSpeaker.CONSULTANT, turn_id="turn-1", text=CONSULTANT_TEXT),
            PacketTurn(ordinal=2, speaker=TurnSpeaker.EMPLOYEE, turn_id="turn-2", text=EMPLOYEE_TEXT),
            PacketTurn(ordinal=3, speaker=TurnSpeaker.CONSULTANT, turn_id="turn-3", text=CONSULTANT_TEXT),
            PacketTurn(ordinal=4, speaker=TurnSpeaker.EMPLOYEE, turn_id="turn-4", text=EMPLOYEE_TEXT),
        ),
        current_turn_ordinal=4,
        open_issues=(PacketOpenIssue(ordinal=1, issue_id="issue-1"),),
    )
    stale = signal(
        resolves_open_issue_ordinal=1,
        # 只引了舊回合,沒有引這一輪的答案。
        anchors=(anchor(turn_ordinal=2),),
        disposition=SignalDisposition.EXCLUDE,
        task_change=None,
        exclude=ExcludePayload(
            reason=ExclusionReason.OTHER_PERSON_WORK, summary="別人做的"
        ),
    )

    assert (
        ViolationCode.RESOLUTION_MISSING_CURRENT_TURN_ANCHOR
        in verify_task_analysis_result(result(stale), ctx).codes
    )


def test_duplicate_or_overlap_cannot_silently_resolve_the_issue():
    ctx = context(
        open_issues=(
            PacketOpenIssue(
                ordinal=1,
                issue_id="issue-1",
                reconciliation_task_id="task-direct-1",
            ),
        )
    )
    duplicate = signal(
        resolves_open_issue_ordinal=1,
        identity=IdentityAssessment(
            relation=IdentityRelation.DUPLICATE,
            target_task_ordinals=(1,),
        ),
        disposition=SignalDisposition.SUPPORT_ONLY,
        task_change=None,
    )

    assert ViolationCode.RESOLUTION_MAPPING_INVALID in verify_task_analysis_result(
        result(duplicate), ctx
    ).codes


def test_same_open_issue_cannot_be_resolved_twice_in_one_result():
    ctx = context(
        open_issues=(
            PacketOpenIssue(
                ordinal=1,
                issue_id="issue-1",
                reconciliation_task_id="task-direct-1",
            ),
        )
    )
    first = signal(resolves_open_issue_ordinal=1)
    second = signal(
        resolves_open_issue_ordinal=1,
        anchors=(anchor(quote="順便盯 request 3f0c-uuid 那張單"),),
    )

    assert ViolationCode.RESOLUTION_OPEN_ISSUE_REPEATED in verify_task_analysis_result(
        result(first, second), ctx
    ).codes


def test_verifier_is_pure_and_repeatable():
    payload, ctx = result(), context()
    assert verify_task_analysis_result(payload, ctx) == verify_task_analysis_result(
        payload, ctx
    )


# ── anchors／quote(§12.3)──────────────────────────────────────────────────


def test_signal_without_anchor_is_rejected():
    assert ViolationCode.ANCHOR_MISSING in codes(
        signal(anchors=(), identity=IdentityAssessment(relation=IdentityRelation.NO_MATCH))
    )


def test_anchor_must_point_at_a_packet_turn():
    assert ViolationCode.ANCHOR_TURN_UNKNOWN in codes(signal(anchors=(anchor(99),)))


def test_anchor_must_point_at_an_employee_turn():
    assert ViolationCode.ANCHOR_TURN_NOT_EMPLOYEE in codes(
        signal(anchors=(anchor(1, "可以說說你平常一週的工作嗎?"),))
    )


def test_quote_must_be_a_verbatim_substring_of_that_turn():
    assert ViolationCode.QUOTE_NOT_VERBATIM in codes(
        signal(anchors=(anchor(2, "我每週要出一份營運月報"),))
    )
    # 逐字子字串即可,不必整句
    assert verify_task_analysis_result(
        result(signal(anchors=(anchor(2, "營運週報"),))), context()
    ).is_valid


def test_quote_containing_a_uuid_is_not_scanned_or_rejected():
    """§12.3:不做全文 UUID 形狀掃描——員工原話可能合法含有 request／correlation UUID。"""
    assert verify_task_analysis_result(
        result(signal(anchors=(anchor(2, "盯 request 3f0c-uuid 那張單"),))), context()
    ).is_valid


# ── identity(§12.3)────────────────────────────────────────────────────────


def test_no_match_must_not_reference_any_task():
    assert ViolationCode.IDENTITY_TARGETS_NOT_EMPTY in codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.NO_MATCH, target_task_ordinals=(1,)
            )
        )
    )


@pytest.mark.parametrize(
    "relation", [IdentityRelation.DUPLICATE, IdentityRelation.OVERLAP]
)
def test_duplicate_and_overlap_require_a_target(relation):
    assert ViolationCode.IDENTITY_TARGETS_MISSING in codes(
        signal(
            identity=IdentityAssessment(relation=relation),
            disposition=SignalDisposition.SUPPORT_ONLY,
            task_change=None,
        )
    )


def test_target_ordinal_must_be_inside_the_packet():
    assert ViolationCode.TARGET_ORDINAL_UNKNOWN in codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.DUPLICATE, target_task_ordinals=(7,)
            ),
            disposition=SignalDisposition.SUPPORT_ONLY,
            task_change=None,
        )
    )


def test_retired_task_ordinals_may_not_be_targeted():
    """§11.4:`retired_tasks[]` 是 read-only 防重提資訊,不得出現在任何 target。"""
    assert ViolationCode.TARGET_ORDINAL_RETIRED in codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.OVERLAP, target_task_ordinals=(90,)
            ),
            task_change=TaskChangePayload(
                change=TaskChangeKind.REVISE,
                target_task_ordinals=(90,),
                task_fields=fields(),
            ),
        )
    )


# ── task_change(§12.2 mapping、§12.3)─────────────────────────────────────


def test_merge_requires_two_targets_and_cannot_be_faked_by_repetition():
    single = codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.OVERLAP, target_task_ordinals=(1,)
            ),
            task_change=TaskChangePayload(
                change=TaskChangeKind.MERGE,
                target_task_ordinals=(1,),
                task_fields=fields(),
            ),
        )
    )
    assert ViolationCode.TASK_CHANGE_TARGET_COUNT in single

    repeated = codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.OVERLAP, target_task_ordinals=(1, 2)
            ),
            task_change=TaskChangePayload(
                change=TaskChangeKind.MERGE,
                target_task_ordinals=(1, 1),
                task_fields=fields(),
            ),
        )
    )
    assert ViolationCode.TARGET_ORDINAL_REPEATED in repeated

    assert verify_task_analysis_result(
        result(
            signal(
                identity=IdentityAssessment(
                    relation=IdentityRelation.OVERLAP, target_task_ordinals=(1, 2)
                ),
                task_change=TaskChangePayload(
                    change=TaskChangeKind.MERGE,
                    target_task_ordinals=(1, 2),
                    task_fields=fields("合併後的工作"),
                ),
            )
        ),
        context(),
    ).is_valid


def test_withdraw_must_not_carry_task_fields():
    withdraw_target = {
        "identity": IdentityAssessment(
            relation=IdentityRelation.DUPLICATE, target_task_ordinals=(1,)
        ),
    }
    assert ViolationCode.TASK_FIELDS_FORBIDDEN in codes(
        signal(
            **withdraw_target,
            task_change=TaskChangePayload(
                change=TaskChangeKind.WITHDRAW,
                target_task_ordinals=(1,),
                task_fields=fields(),
                withdraw_reason=RetirementReason.EMPLOYEE_DENIED,
            ),
        )
    )
    assert verify_task_analysis_result(
        result(
            signal(
                **withdraw_target,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.WITHDRAW,
                    target_task_ordinals=(1,),
                    withdraw_reason=RetirementReason.ONE_OFF,
                ),
            )
        ),
        context(),
    ).is_valid


def test_withdraw_reason_is_required_by_withdraw_and_forbidden_elsewhere():
    """§9.5 要求 withdrawn 一定有 reason,而只有模型知道是哪一種。"""
    assert ViolationCode.WITHDRAW_REASON_REQUIRED in codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.DUPLICATE, target_task_ordinals=(1,)
            ),
            task_change=TaskChangePayload(
                change=TaskChangeKind.WITHDRAW, target_task_ordinals=(1,)
            ),
        )
    )
    assert ViolationCode.WITHDRAW_REASON_FORBIDDEN in codes(
        signal(
            task_change=TaskChangePayload(
                change=TaskChangeKind.ADD,
                task_fields=fields(),
                withdraw_reason=RetirementReason.ONE_OFF,
            )
        )
    )


@pytest.mark.parametrize(
    ("change", "targets"),
    [
        (TaskChangeKind.ADD, ()),
        (TaskChangeKind.REVISE, (1,)),
        (TaskChangeKind.MERGE, (1, 2)),
    ],
)
def test_changes_that_write_semantic_fields_require_task_fields(change, targets):
    relation = (
        IdentityRelation.NO_MATCH if not targets else IdentityRelation.OVERLAP
    )
    assert ViolationCode.TASK_FIELDS_REQUIRED in codes(
        signal(
            identity=IdentityAssessment(
                relation=relation, target_task_ordinals=targets
            ),
            task_change=TaskChangePayload(change=change, target_task_ordinals=targets),
        )
    )


@pytest.mark.parametrize(
    ("change", "targets"),
    [
        (TaskChangeKind.ADD, (1,)),
        (TaskChangeKind.REVISE, ()),
        (TaskChangeKind.WITHDRAW, (1, 2)),
        (TaskChangeKind.SPLIT, (1, 2)),
    ],
)
def test_target_count_must_make_the_mapping_total(change, targets):
    assert ViolationCode.TASK_CHANGE_TARGET_COUNT in codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.OVERLAP, target_task_ordinals=targets or (1,)
            ),
            task_change=TaskChangePayload(
                change=change,
                target_task_ordinals=targets,
                task_fields=None if change is TaskChangeKind.WITHDRAW else fields(),
                withdraw_reason=(
                    RetirementReason.EMPLOYEE_DENIED
                    if change is TaskChangeKind.WITHDRAW
                    else None
                    ),
                    split_children=(
                        SplitChildPayload(task_fields=fields("子一")),
                        SplitChildPayload(task_fields=fields("子二")),
                    )
                    if change is TaskChangeKind.SPLIT
                    else (),
            ),
        )
    )


def test_split_requires_one_parent_and_two_children():
    split_signal = lambda children: signal(  # noqa: E731 - 測試內的小工廠
        identity=IdentityAssessment(
            relation=IdentityRelation.OVERLAP, target_task_ordinals=(1,)
        ),
        task_change=TaskChangePayload(
            change=TaskChangeKind.SPLIT,
            target_task_ordinals=(1,),
            split_children=children,
        ),
    )
    assert ViolationCode.SPLIT_CHILDREN_INSUFFICIENT in codes(
        split_signal((SplitChildPayload(task_fields=fields("只有一個子")),))
    )
    assert verify_task_analysis_result(
        result(
            split_signal(
                (
                    SplitChildPayload(task_fields=fields("子一")),
                    SplitChildPayload(task_fields=fields("子二")),
                )
            )
        ),
        context(),
    ).is_valid


# ── disposition ↔ payload(§12.1 的可攜編碼)───────────────────────────────


def test_support_only_carries_no_payload():
    assert ViolationCode.PAYLOAD_DOES_NOT_MATCH_DISPOSITION in codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.DUPLICATE, target_task_ordinals=(1,)
            ),
            disposition=SignalDisposition.SUPPORT_ONLY,
        )
    )
    assert verify_task_analysis_result(
        result(
            signal(
                identity=IdentityAssessment(
                    relation=IdentityRelation.DUPLICATE, target_task_ordinals=(1,)
                ),
                disposition=SignalDisposition.SUPPORT_ONLY,
                task_change=None,
            )
        ),
        context(),
    ).is_valid


def test_disposition_requires_its_own_payload():
    assert ViolationCode.PAYLOAD_DOES_NOT_MATCH_DISPOSITION in codes(
        signal(disposition=SignalDisposition.EXCLUDE, task_change=None)
    )
    assert ViolationCode.PAYLOAD_DOES_NOT_MATCH_DISPOSITION in codes(
        signal(
            disposition=SignalDisposition.EXCLUDE,
            task_change=None,
            exclude=ExcludePayload(
                reason=ExclusionReason.OTHER_PERSON_WORK, summary="那是主管做的"
            ),
            open_issue=OpenIssuePayload(
                kind=OpenIssueKind.INSUFFICIENT_EVIDENCE, summary="說不清楚"
            ),
        )
    )
    assert verify_task_analysis_result(
        result(
            signal(
                disposition=SignalDisposition.EXCLUDE,
                task_change=None,
                exclude=ExcludePayload(
                    reason=ExclusionReason.OTHER_PERSON_WORK, summary="那是主管做的"
                ),
            )
        ),
        context(),
    ).is_valid


def test_unresolved_contradiction_requires_two_anchors():
    issue = OpenIssuePayload(
        kind=OpenIssueKind.UNRESOLVED_CONTRADICTION, summary="前後說法不一致"
    )
    assert ViolationCode.OPEN_ISSUE_ANCHORS_INSUFFICIENT in codes(
        signal(
            disposition=SignalDisposition.OPEN_ISSUE, task_change=None, open_issue=issue
        )
    )
    assert verify_task_analysis_result(
        result(
            signal(
                anchors=(anchor(2, "我每週要出一份營運週報"), anchor(2, "營運週報")),
                disposition=SignalDisposition.OPEN_ISSUE,
                task_change=None,
                open_issue=issue,
            )
        ),
        context(),
    ).is_valid


# ── §12.2 的組合一致性 ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("relation", "disposition", "change"),
    [
        (IdentityRelation.NO_MATCH, SignalDisposition.SUPPORT_ONLY, None),
        (IdentityRelation.DUPLICATE, SignalDisposition.TASK_CHANGE, TaskChangeKind.ADD),
        (
            IdentityRelation.DUPLICATE,
            SignalDisposition.TASK_CHANGE,
            TaskChangeKind.REVISE,
        ),
    ],
)
def test_relation_must_match_the_mapping_table(relation, disposition, change):
    """三者各自合法不代表組合合法:`duplicate` ＋ `add` 會憑既有 Task 的依據再造一個
    重複 Task,`no_match` ＋ `support_only` 則把沒有對象的依據掛到空氣上。"""
    targets = () if relation is IdentityRelation.NO_MATCH else (1,)
    assert ViolationCode.RELATION_DOES_NOT_MATCH_MAPPING in codes(
        signal(
            identity=IdentityAssessment(
                relation=relation, target_task_ordinals=targets
            ),
            disposition=disposition,
            task_change=None
            if change is None
            else TaskChangePayload(
                change=change, target_task_ordinals=targets, task_fields=fields()
            ),
        )
    )


def test_identity_and_task_change_must_agree_on_the_targets():
    """`revise` 沿用該 task_id、`merge` 併的就是那幾個;兩組 target 不同,application
    無從知道該信哪一組。"""
    assert ViolationCode.TARGET_ORDINALS_DISAGREE in codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.OVERLAP, target_task_ordinals=(1,)
            ),
            task_change=TaskChangePayload(
                change=TaskChangeKind.REVISE,
                target_task_ordinals=(2,),
                task_fields=fields(),
            ),
        )
    )
    assert ViolationCode.TARGET_ORDINALS_DISAGREE in codes(
        signal(
            identity=IdentityAssessment(
                relation=IdentityRelation.OVERLAP, target_task_ordinals=(1,)
            ),
            task_change=TaskChangePayload(
                change=TaskChangeKind.MERGE,
                target_task_ordinals=(1, 2),
                task_fields=fields(),
            ),
        )
    )


# ── supersession(§12.3 末段)──────────────────────────────────────────────


def revise_signal(**overrides) -> WorkSignal:
    base = {
        "identity": IdentityAssessment(
            relation=IdentityRelation.OVERLAP, target_task_ordinals=(1,)
        ),
        "task_change": TaskChangePayload(
            change=TaskChangeKind.REVISE,
            target_task_ordinals=(1,),
            task_fields=fields("改成雙週彙整營運週報"),
        ),
        "supersedes_support_ordinals": (
            SupportOrdinalRef(task_ordinal=1, support_ordinal=1),
        ),
    }
    base.update(overrides)
    return signal(**base)


def test_supersession_of_an_effective_link_on_a_targeted_task_passes():
    assert verify_task_analysis_result(result(revise_signal()), context()).is_valid


def test_supersession_must_point_at_an_existing_support_link():
    assert ViolationCode.SUPERSESSION_UNKNOWN in codes(
        revise_signal(
            supersedes_support_ordinals=(
                SupportOrdinalRef(task_ordinal=1, support_ordinal=9),
            )
        )
    )


def test_supersession_may_not_point_at_an_already_superseded_link():
    assert ViolationCode.SUPERSESSION_ALREADY_SUPERSEDED in codes(
        revise_signal(
            supersedes_support_ordinals=(
                SupportOrdinalRef(task_ordinal=1, support_ordinal=2),
            )
        )
    )


def test_supersession_task_must_be_targeted_by_the_same_signal():
    assert ViolationCode.SUPERSESSION_TASK_NOT_TARGETED in codes(
        revise_signal(
            supersedes_support_ordinals=(
                SupportOrdinalRef(task_ordinal=2, support_ordinal=1),
            )
        )
    )


def test_supersession_may_not_point_at_a_retired_task():
    assert ViolationCode.SUPERSESSION_UNKNOWN in codes(
        revise_signal(
            supersedes_support_ordinals=(
                SupportOrdinalRef(task_ordinal=90, support_ordinal=1),
            )
        )
    )


def test_supersession_requires_the_current_employee_turn_among_the_anchors():
    """第一版 `superseded_by` 一律指向本次處理的 employee turn(§12.3 末段)。"""
    ctx = context(
        turns=(
            PacketTurn(
                ordinal=1,
                speaker=TurnSpeaker.CONSULTANT,
                turn_id="turn-1",
                text=CONSULTANT_TEXT,
            ),
            PacketTurn(
                ordinal=2,
                speaker=TurnSpeaker.EMPLOYEE,
                turn_id="turn-2",
                text=EMPLOYEE_TEXT,
            ),
            PacketTurn(
                ordinal=3,
                speaker=TurnSpeaker.EMPLOYEE,
                turn_id="turn-3",
                text="其實那份週報是同事做的",
            ),
        ),
        current_turn_ordinal=3,
    )
    assert ViolationCode.SUPERSESSION_MISSING_CURRENT_TURN_ANCHOR in codes(
        revise_signal(), ctx=ctx
    )
    assert verify_task_analysis_result(
        result(revise_signal(anchors=(anchor(3, "其實那份週報是同事做的"),))), ctx
    ).is_valid


# ── 跨 signal(§12.3)──────────────────────────────────────────────────────


def test_two_task_changes_claiming_the_same_target_are_both_rejected():
    """不任選贏家:兩筆都拒。"""
    first = revise_signal(supersedes_support_ordinals=())
    second = signal(
        identity=IdentityAssessment(
            relation=IdentityRelation.DUPLICATE, target_task_ordinals=(1,)
        ),
        task_change=TaskChangePayload(
            change=TaskChangeKind.WITHDRAW,
            target_task_ordinals=(1,),
            withdraw_reason=RetirementReason.EMPLOYEE_DENIED,
        ),
    )
    report = verify_task_analysis_result(result(first, second), context())
    duplicates = [
        violation
        for violation in report.violations
        if violation.code is ViolationCode.DUPLICATE_TASK_CHANGE_TARGET
    ]
    assert len(duplicates) == 2
    assert report.rejected_signal_indexes == {0, 1}


def test_exact_duplicate_work_signals_are_both_rejected():
    duplicate = signal()

    report = verify_task_analysis_result(result(duplicate, duplicate), context())

    assert ViolationCode.DUPLICATE_WORK_SIGNAL in report.codes
    assert report.rejected_signal_indexes == {0, 1}


def test_split_child_may_only_inherit_an_effective_support_on_its_parent():
    split = signal(
        identity=IdentityAssessment(
            relation=IdentityRelation.UNCERTAIN, target_task_ordinals=(1,)
        ),
        task_change=TaskChangePayload(
            change=TaskChangeKind.SPLIT,
            target_task_ordinals=(1,),
            split_children=(
                SplitChildPayload(
                    task_fields=fields("彙整營運週報"),
                    inherited_support_ordinals=(1,),
                ),
                SplitChildPayload(
                    task_fields=fields("追蹤營運缺料"),
                    inherited_support_ordinals=(99,),
                ),
            ),
        ),
    )

    report = verify_task_analysis_result(result(split), context())

    assert ViolationCode.SPLIT_SUPPORT_UNKNOWN in report.codes
    assert report.rejected_signal_indexes == {0}


def test_distinct_targets_may_be_changed_in_the_same_round():
    first = revise_signal(supersedes_support_ordinals=())
    second = signal(
        identity=IdentityAssessment(
            relation=IdentityRelation.DUPLICATE, target_task_ordinals=(2,)
        ),
        task_change=TaskChangePayload(
            change=TaskChangeKind.WITHDRAW,
            target_task_ordinals=(2,),
            withdraw_reason=RetirementReason.EMPLOYEE_DENIED,
        ),
    )
    assert verify_task_analysis_result(result(first, second), context()).is_valid


# ── next_question(§12.3)──────────────────────────────────────────────────


def question(**overrides) -> NextQuestion:
    base = {"text": "這份週報交給誰?"}
    base.update(overrides)
    return NextQuestion(**base)


def test_next_question_target_may_be_omitted():
    assert verify_task_analysis_result(
        result(next_question=question(target=None)), context()
    ).is_valid


def test_next_question_may_target_an_existing_open_issue():
    assert verify_task_analysis_result(
        result(
            next_question=question(
                target=NextQuestionTarget(
                    kind=NextQuestionTargetKind.EXISTING_OPEN_ISSUE, ordinal=1
                )
            )
        ),
        context(),
    ).is_valid


@pytest.mark.parametrize(
    "target",
    [
        NextQuestionTarget(
            kind=NextQuestionTargetKind.EXISTING_OPEN_ISSUE, ordinal=42
        ),
        NextQuestionTarget(kind=NextQuestionTargetKind.EXISTING_OPEN_ISSUE),
        NextQuestionTarget(
            kind=NextQuestionTargetKind.EXISTING_OPEN_ISSUE, ordinal=1, index=0
        ),
        NextQuestionTarget(kind=NextQuestionTargetKind.NEW_SIGNAL, index=3),
        NextQuestionTarget(kind=NextQuestionTargetKind.NEW_SIGNAL),
        NextQuestionTarget(kind=NextQuestionTargetKind.NEW_SIGNAL, index=0, ordinal=1),
    ],
)
def test_next_question_target_must_resolve(target):
    report = verify_task_analysis_result(
        result(next_question=question(target=target)), context()
    )
    assert ViolationCode.NEXT_QUESTION_TARGET_INVALID in report.codes
    assert report.rejected_signal_indexes == frozenset()


def test_next_question_may_target_a_signal_produced_in_this_round():
    assert verify_task_analysis_result(
        result(
            next_question=question(
                target=NextQuestionTarget(
                    kind=NextQuestionTargetKind.NEW_SIGNAL, index=0
                )
            )
        ),
        context(),
    ).is_valid


# ── VerificationContext 自身的不變量 ────────────────────────────────────────


def test_packet_ordinals_are_unique_within_each_namespace():
    with pytest.raises(ValidationError, match="duplicate task ordinal"):
        context(
            tasks=(
                PacketTask(ordinal=1, task_id="task-1"),
                PacketTask(ordinal=1, task_id="task-2"),
            )
        )
    with pytest.raises(ValidationError, match="duplicate support link ordinal"):
        context(
            tasks=(
                PacketTask(
                    ordinal=1,
                    task_id="task-1",
                    support_links=(
                        PacketSupportLink(ordinal=1, is_effective=True),
                        PacketSupportLink(ordinal=1, is_effective=True),
                    ),
                ),
            )
        )


def test_retired_ordinals_must_not_collide_with_active_ones():
    """不相交才讓「retired 不得被指涉」可判定;否則 target 永遠先命中 active。"""
    with pytest.raises(ValidationError, match="must not collide"):
        context(retired_tasks=(PacketRetiredTask(ordinal=1, task_id="task-90"),))


def test_current_turn_must_be_an_employee_turn_in_the_packet():
    with pytest.raises(ValidationError, match="current turn must be an employee turn"):
        context(current_turn_ordinal=1)
    with pytest.raises(ValidationError, match="current turn must be an employee turn"):
        context(current_turn_ordinal=99)


# ── issue_resolutions[](ADR 0054 決定 22–23)────────────────────────────────


def resolution_context(*, subject_task_id="task-1"):
    from app.job_analysis.application import (
        PacketOpenIssue,
        PacketTask,
        PacketTurn,
        TurnSpeaker,
        VerificationContext,
    )

    return VerificationContext(
        turns=(
            PacketTurn(ordinal=1, turn_id="turn-1", speaker=TurnSpeaker.CONSULTANT, text="請說說你的一週"),
            PacketTurn(ordinal=2, turn_id="turn-2", speaker=TurnSpeaker.EMPLOYEE, text="我每週彙整營運週報"),
        ),
        current_turn_ordinal=2,
        tasks=(PacketTask(ordinal=1, task_id="task-1"),),
        open_issues=(
            PacketOpenIssue(
                ordinal=1,
                issue_id="op-1-gap0",
                subject_task_id=subject_task_id,
            ),
        ),
    )


def support_only_signal(*, target=1, anchors=True):
    from app.job_analysis.llm import (
        IdentityAssessment,
        IdentityRelation,
        SignalAnchor,
        SignalDisposition,
        WorkSignal,
    )

    return WorkSignal(
        anchors=(
            (SignalAnchor(turn_ordinal=2, quote="我每週彙整營運週報"),) if anchors else ()
        ),
        identity=IdentityAssessment(
            relation=IdentityRelation.DUPLICATE,
            target_task_ordinals=(target,),
        ),
        disposition=SignalDisposition.SUPPORT_ONLY,
    )


def result_with_resolutions(*resolutions, signals=()):
    from app.job_analysis.llm import (
        IssueResolution,
        IssueResolutionKind,
        NextQuestion,
        TaskAnalysisResult,
    )

    return TaskAnalysisResult(
        work_signals=signals,
        issue_resolutions=tuple(
            IssueResolution(ordinal=ordinal, resolution=IssueResolutionKind(kind))
            for ordinal, kind in resolutions
        ),
        next_question=NextQuestion(text="還有其他每週要做的事嗎？"),
    )


def codes_for(result, context):
    return {
        violation.code for violation in verify_task_analysis_result(result, context).violations
    }


def test_answered_needs_a_same_turn_signal_leaving_evidence_on_the_subject_task():
    """決定 23:否則 digest 不變、OPKS 不會再分析,缺口被**假關閉**。

    員工以為答過了,系統卻永遠不會用那個答案。
    """

    from app.job_analysis.application import ViolationCode

    assert ViolationCode.ISSUE_RESOLUTION_ANSWER_NOT_RECORDED in codes_for(
        result_with_resolutions((1, "answered")),
        resolution_context(),
    )


def test_answered_is_accepted_when_the_same_turn_records_the_answer():
    assert verify_task_analysis_result(
        result_with_resolutions((1, "answered"), signals=(support_only_signal(),)),
        resolution_context(),
    ).is_valid


def test_answered_rejects_a_signal_that_leaves_no_anchor():
    """沒有 anchor 就沒有 SupportLink,digest 一樣不會變。"""

    from app.job_analysis.application import ViolationCode

    assert ViolationCode.ISSUE_RESOLUTION_ANSWER_NOT_RECORDED in codes_for(
        result_with_resolutions(
            (1, "answered"),
            signals=(support_only_signal(anchors=False),),
        ),
        resolution_context(),
    )


@pytest.mark.parametrize("kind", ["employee_unknown", "not_applicable"])
def test_the_two_terminal_answers_need_no_work_signal(kind):
    """員工說不知道／不適用時本來就沒有新依據可留,要求 signal 等於逼模型編一個。"""

    assert verify_task_analysis_result(
        result_with_resolutions((1, kind)),
        resolution_context(),
    ).is_valid


def test_an_unknown_issue_ordinal_is_rejected():
    """決定 20:terminal issue 不配發 ordinal,指過去就是無效 ordinal。"""

    from app.job_analysis.application import ViolationCode

    assert ViolationCode.ISSUE_RESOLUTION_ORDINAL_UNKNOWN in codes_for(
        result_with_resolutions((99, "employee_unknown")),
        resolution_context(),
    )


def test_the_same_issue_cannot_be_resolved_twice_in_one_turn():
    from app.job_analysis.application import ViolationCode

    assert ViolationCode.ISSUE_RESOLUTION_REPEATED in codes_for(
        result_with_resolutions((1, "employee_unknown"), (1, "not_applicable")),
        resolution_context(),
    )


def test_one_answer_may_resolve_several_gaps_without_side_effects():
    """決定 22:一個答案同時解 P／K／S 三個缺口就是三筆,每一筆都沒有處置。"""

    from app.job_analysis.application import (
        PacketOpenIssue,
        PacketTask,
        PacketTurn,
        TurnSpeaker,
        VerificationContext,
    )

    context = VerificationContext(
        turns=(
            PacketTurn(ordinal=1, turn_id="turn-1", speaker=TurnSpeaker.CONSULTANT, text="請說說你的一週"),
            PacketTurn(ordinal=2, turn_id="turn-2", speaker=TurnSpeaker.EMPLOYEE, text="我每週彙整營運週報"),
        ),
        current_turn_ordinal=2,
        tasks=(PacketTask(ordinal=1, task_id="task-1"),),
        open_issues=tuple(
            PacketOpenIssue(
                ordinal=ordinal,
                issue_id=f"op-1-gap{ordinal}",
                subject_task_id="task-1",
            )
            for ordinal in (1, 2, 3)
        ),
    )

    assert verify_task_analysis_result(
        result_with_resolutions(
            (1, "answered"),
            (2, "answered"),
            (3, "answered"),
            signals=(support_only_signal(),),
        ),
        context,
    ).is_valid


def gap_closing_signal(**overrides) -> WorkSignal:
    base = {
        "resolves_open_issue_ordinal": 1,
        "disposition": SignalDisposition.EXCLUDE,
        "task_change": None,
        "exclude": ExcludePayload(
            reason=ExclusionReason.OTHER_PERSON_WORK,
            summary="那其實是別人在做的",
        ),
    }
    base.update(overrides)
    return signal(**base)


def test_an_opks_gap_may_not_be_closed_through_a_work_signal():
    """決定 22:gap resolution **不綁在 `WorkSignal.disposition` 上**。

    ADR 0047 把 `resolves_open_issue_ordinal` 開放給「模型自己提出的」open issue,理由
    是只有處理該回合答案的模型知道自己上一輪問過什麼。OPKS 缺口不在那個集合裡——它由
    specialist 提出,而決定 23 給了它一個機械可判的前提。

    缺口在資料上長得跟一般 issue 一樣(沒有 `reconciliation_task_id`),所以不擋的話
    模型只要送一筆帶當輪 anchor 的訊號就能把它整筆刪掉,不在該 Task 留下任何員工依據
    ——digest 不變、OPKS 不再分析,缺口被**假關閉**。決定 23 的檢查只掛在
    `issue_resolutions[]` 上,擋不到這條路。
    """

    assert ViolationCode.RESOLUTION_OPKS_GAP_NEEDS_ISSUE_RESOLUTION in (
        verify_task_analysis_result(
            result(gap_closing_signal()), resolution_context()
        ).codes
    )


def test_the_ban_holds_even_when_that_signal_would_leave_evidence():
    """一條規則、一個地方。

    帶依據的訊號看起來與 `answered` 等價,但放行等於把決定 23 的前提複製到第二處
    ——兩份遲早失步。缺口只有一條解決通道。
    """

    assert ViolationCode.RESOLUTION_OPKS_GAP_NEEDS_ISSUE_RESOLUTION in (
        verify_task_analysis_result(
            result(
                gap_closing_signal(
                    disposition=SignalDisposition.SUPPORT_ONLY,
                    exclude=None,
                    identity=IdentityAssessment(
                        relation=IdentityRelation.DUPLICATE,
                        target_task_ordinals=(1,),
                    ),
                )
            ),
            resolution_context(),
        ).codes
    )


def test_a_plain_model_raised_issue_is_still_closable_this_way():
    """ADR 0047 原樣保留:沒有 subject Task 的 issue 仍可由任何 disposition 關閉。

    收窄只針對 OPKS 缺口,不是把 0047 整條收回去。
    """

    assert verify_task_analysis_result(
        result(gap_closing_signal()),
        context(open_issues=(PacketOpenIssue(ordinal=1, issue_id="issue-1"),)),
    ).is_valid
