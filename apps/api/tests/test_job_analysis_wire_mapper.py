"""T2:wire → domain 的純還原。**沒有網路呼叫。**

這份測試守兩件事:

1. **中性值還原正確** —— `""`／`"none"`／`0` 各自還原成 `None`。
2. **不做語意判斷,也不靜默丟棄** —— 「哪個欄位該非空」留給 verifier;
   模型在沒有 domain 落點的欄位夾帶內容時,mapper 必須讓整回合失敗,
   而不是把內容吃掉。吃掉就等於 verifier 少了一條攔截線。
"""

from __future__ import annotations

import pytest

from app.job_analysis.domain import (
    EnablerKind,
    ExclusionReason,
    OpenIssueKind,
    RetirementReason,
)
from app.job_analysis.llm import (
    IdentityRelation,
    NextQuestionTargetKind,
    SignalDisposition,
    TaskChangeKind,
)
from app.job_analysis.llm.wire import (
    TaskAnalysisWire,
    WireAnchor,
    WireEnabler,
    WireMappingError,
    WireNextQuestion,
    WireNextQuestionTargetKind,
    WireRejectionCode,
    WireSignal,
    WireSplitChild,
    WireSupersession,
    WireTaskChange,
    WireTaskFields,
    WireWithdrawReason,
    wire_to_task_analysis_result,
)


NEUTRAL_TASK = WireTaskFields(statement="", action="", object="", purpose_result="")


def signal(**overrides) -> WireSignal:
    base = {
        "anchors": (WireAnchor(turn_ordinal=3, quote="我每週彙整營運週報"),),
        "relation": IdentityRelation.NO_MATCH,
        "disposition": SignalDisposition.SUPPORT_ONLY,
        "change": WireTaskChange.NONE,
        "task": NEUTRAL_TASK,
    }
    base.update(overrides)
    return WireSignal(**base)


def wire(**overrides) -> TaskAnalysisWire:
    base = {
        "work_signals": (signal(),),
        "next_question": WireNextQuestion(text="這份週報完成後交給誰?"),
    }
    base.update(overrides)
    return TaskAnalysisWire(**base)


def only_signal(**overrides):
    return wire_to_task_analysis_result(wire(work_signals=(signal(**overrides),))).work_signals[0]


# ── 中性值還原 ─────────────────────────────────────────────────────────────


def test_empty_string_becomes_none():
    mapped = only_signal(
        disposition=SignalDisposition.TASK_CHANGE,
        change=WireTaskChange.ADD,
        task=WireTaskFields(
            statement="每週彙整營運週報", action="彙整", object="營運週報"
        ),
    )

    assert mapped.task_change.task_fields.purpose_result is None


def test_neutral_enum_becomes_none():
    mapped = only_signal(
        disposition=SignalDisposition.TASK_CHANGE,
        change=WireTaskChange.ADD,
        task=WireTaskFields(
            statement="每週彙整營運週報", action="彙整", object="營運週報"
        ),
    )

    assert mapped.task_change.withdraw_reason is None


def test_zero_ordinal_becomes_none_and_other_values_pass_through():
    assert only_signal(resolves_open_issue_ordinal=0).resolves_open_issue_ordinal is None
    assert only_signal(resolves_open_issue_ordinal=2).resolves_open_issue_ordinal == 2


def test_neutral_change_leaves_every_payload_empty():
    mapped = only_signal()

    assert (mapped.task_change, mapped.exclude, mapped.open_issue) == (None, None, None)


# ── 每一種 change ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("wire_change", "expected"),
    [
        pytest.param(WireTaskChange.ADD, TaskChangeKind.ADD, id="add"),
        pytest.param(WireTaskChange.REVISE, TaskChangeKind.REVISE, id="revise"),
        pytest.param(WireTaskChange.MERGE, TaskChangeKind.MERGE, id="merge"),
    ],
)
def test_changes_that_carry_task_fields(wire_change, expected):
    mapped = only_signal(
        disposition=SignalDisposition.TASK_CHANGE,
        change=wire_change,
        target_task_ordinals=(1, 2),
        task=WireTaskFields(
            statement="每週彙整營運週報",
            action="彙整",
            object="營運週報",
            purpose_result="讓主管掌握進度",
            enablers=(WireEnabler(kind=EnablerKind.TOOL_SYSTEM, name="Excel"),),
        ),
    )

    assert mapped.task_change.change is expected
    assert mapped.task_change.task_fields.statement == "每週彙整營運週報"
    assert mapped.task_change.task_fields.purpose_result == "讓主管掌握進度"
    assert mapped.task_change.task_fields.enablers[0].name == "Excel"


def test_withdraw_carries_a_reason_and_no_task_fields():
    mapped = only_signal(
        disposition=SignalDisposition.TASK_CHANGE,
        change=WireTaskChange.WITHDRAW,
        withdraw_reason=WireWithdrawReason.ONE_OFF,
        target_task_ordinals=(1,),
    )

    assert mapped.task_change.change is TaskChangeKind.WITHDRAW
    assert mapped.task_change.withdraw_reason is RetirementReason.ONE_OFF
    assert mapped.task_change.task_fields is None


def test_split_children_get_the_three_semantic_fields_and_leave_the_rest_open():
    """child 只帶足以成立一句話的欄位;其餘由後續回合以 revise 補。"""
    mapped = only_signal(
        disposition=SignalDisposition.TASK_CHANGE,
        change=WireTaskChange.SPLIT,
        target_task_ordinals=(1,),
        split_children=(
            WireSplitChild(
                statement="彙整營運數據",
                action="彙整",
                object="營運數據",
                inherited_support_ordinals=(1,),
            ),
            WireSplitChild(
                statement="撰寫週報結論", action="撰寫", object="週報結論"
            ),
        ),
    )

    children = mapped.task_change.split_children
    assert len(children) == 2
    assert children[0].task_fields.statement == "彙整營運數據"
    assert children[0].task_fields.purpose_result is None
    assert children[0].inherited_support_ordinals == (1,)
    assert children[1].inherited_support_ordinals == ()


# ── rejection:值決定落點,不看 disposition ────────────────────────────────


def test_exclusion_code_lands_in_the_exclude_payload():
    mapped = only_signal(
        disposition=SignalDisposition.EXCLUDE,
        rejection_code=WireRejectionCode.OTHER_PERSON_WORK,
        rejection_summary="那是同事在做的",
    )

    assert mapped.exclude.reason is ExclusionReason.OTHER_PERSON_WORK
    assert mapped.exclude.summary == "那是同事在做的"
    assert mapped.open_issue is None


def test_open_issue_code_lands_in_the_open_issue_payload():
    mapped = only_signal(
        disposition=SignalDisposition.OPEN_ISSUE,
        rejection_code=WireRejectionCode.INSUFFICIENT_EVIDENCE,
        rejection_summary="還看不出這件事的產出",
    )

    assert mapped.open_issue.kind is OpenIssueKind.INSUFFICIENT_EVIDENCE
    assert mapped.exclude is None


def test_payload_follows_the_code_so_the_verifier_still_sees_the_mismatch():
    """mapper 不「修正」disposition 與 payload 的矛盾——那是
    `PAYLOAD_DOES_NOT_MATCH_DISPOSITION` 的工作,吃掉就等於少一條攔截線。"""
    mapped = only_signal(
        disposition=SignalDisposition.EXCLUDE,
        rejection_code=WireRejectionCode.INSUFFICIENT_EVIDENCE,
        rejection_summary="證據不足",
    )

    assert mapped.disposition is SignalDisposition.EXCLUDE
    assert mapped.exclude is None
    assert mapped.open_issue is not None


# ── 夾帶:沒有 domain 落點的內容一律拒絕 ──────────────────────────────────


@pytest.mark.parametrize(
    ("case", "overrides"),
    [
        pytest.param(
            "task fields",
            {"task": WireTaskFields(statement="偷渡", action="", object="")},
            id="task-fields",
        ),
        pytest.param(
            "enablers",
            {
                "task": WireTaskFields(
                    statement="",
                    action="",
                    object="",
                    enablers=(WireEnabler(kind=EnablerKind.SKILL, name="偷渡"),),
                )
            },
            id="enablers",
        ),
        pytest.param(
            "split children",
            {
                "split_children": (
                    WireSplitChild(statement="偷渡", action="偷", object="渡"),
                )
            },
            id="split-children",
        ),
        pytest.param(
            "withdraw reason",
            {"withdraw_reason": WireWithdrawReason.ONE_OFF},
            id="withdraw-reason",
        ),
    ],
)
def test_content_with_no_domain_slot_is_rejected(case, overrides):
    """`change` 是 `"none"` 時沒有 `TaskChangePayload` 可以承載這些欄位。"""
    with pytest.raises(WireMappingError):
        only_signal(**overrides)


def test_rejection_summary_without_a_code_is_rejected():
    with pytest.raises(WireMappingError):
        only_signal(rejection_summary="沒有 code 的摘要無處可放")


def test_partially_filled_task_fields_are_rejected():
    """`statement`／`action`／`object` 在 domain 是必填;半填是壞掉的輸出,不是中性值。"""
    with pytest.raises(WireMappingError):
        only_signal(
            disposition=SignalDisposition.TASK_CHANGE,
            change=WireTaskChange.ADD,
            task=WireTaskFields(statement="", action="彙整", object="營運週報"),
        )


# ── 其餘欄位 ───────────────────────────────────────────────────────────────


def test_identity_and_change_both_receive_the_single_ordinal_list():
    mapped = only_signal(
        disposition=SignalDisposition.TASK_CHANGE,
        relation=IdentityRelation.OVERLAP,
        change=WireTaskChange.REVISE,
        target_task_ordinals=(2,),
        task=WireTaskFields(statement="每週彙整營運週報", action="彙整", object="營運週報"),
    )

    assert mapped.identity.relation is IdentityRelation.OVERLAP
    assert mapped.identity.target_task_ordinals == (2,)
    assert mapped.task_change.target_task_ordinals == (2,)


def test_anchors_and_supersessions_map_across():
    mapped = only_signal(
        anchors=(
            WireAnchor(turn_ordinal=3, quote="我每週彙整營運週報"),
            WireAnchor(turn_ordinal=5, quote="其實是雙週"),
        ),
        supersedes=(WireSupersession(task_ordinal=1, support_ordinal=2),),
    )

    assert [anchor.turn_ordinal for anchor in mapped.anchors] == [3, 5]
    assert mapped.supersedes_support_ordinals[0].support_ordinal == 2


@pytest.mark.parametrize(
    ("kind", "ordinal", "expected_ordinal", "expected_index"),
    [
        pytest.param(
            WireNextQuestionTargetKind.EXISTING_OPEN_ISSUE, 2, 2, None, id="open-issue"
        ),
        # wire 一律 1-based;domain 的 `index` 是 0-based,換算只發生在 mapper。
        pytest.param(
            WireNextQuestionTargetKind.NEW_SIGNAL, 1, None, 0, id="new-signal-first"
        ),
        pytest.param(
            WireNextQuestionTargetKind.NEW_SIGNAL, 3, None, 2, id="new-signal-third"
        ),
    ],
)
def test_next_question_target_splits_by_kind(
    kind, ordinal, expected_ordinal, expected_index
):
    result = wire_to_task_analysis_result(
        wire(
            next_question=WireNextQuestion(
                text="這份週報完成後交給誰?", target_kind=kind, target_ordinal=ordinal
            )
        )
    )
    target = result.next_question.target

    assert target.kind is NextQuestionTargetKind(kind.value)
    assert target.ordinal == expected_ordinal
    assert target.index == expected_index


def test_neutral_target_kind_leaves_no_target():
    result = wire_to_task_analysis_result(wire())

    assert result.next_question.target is None
    assert result.next_question.text == "這份週報完成後交給誰?"


def test_blank_question_text_is_rejected():
    with pytest.raises(WireMappingError):
        wire_to_task_analysis_result(wire(next_question=WireNextQuestion(text="")))


@pytest.mark.parametrize(
    "kind",
    [
        WireNextQuestionTargetKind.EXISTING_OPEN_ISSUE,
        WireNextQuestionTargetKind.NEW_SIGNAL,
    ],
)
def test_a_target_ordinal_below_one_is_rejected(kind):
    """0 不是「第 0 個」,是模型沒填。目標存在卻沒有編號就是壞掉的輸出。"""

    with pytest.raises(WireMappingError):
        wire_to_task_analysis_result(
            wire(
                next_question=WireNextQuestion(
                    text="那實際動手的是誰?", target_kind=kind, target_ordinal=0
                )
            )
        )


# ── 真模型回歸(兩次 live run 的實際輸出)────────────────────────────────


def test_the_last_signal_can_be_addressed_by_its_position():
    """真模型 2026-07-31 送 `target_ordinal: 3` 指三個訊號中的最後一個
    (run `20260731T121651Z`)。v2 當時對 `new_signal` 要求 0-based,3 因此超出
    範圍,被 `NEXT_QUESTION_TARGET_INVALID` 擋下——**這是契約的缺陷,不是模型的**:
    同場景的另一次(run `20260731T120931Z`)送 2,僥倖落在 0-based 範圍內而通過。

    一致的 1-based 之後,「最後一個訊號」＝ 訊號數,永遠在範圍內。
    """

    signals = (signal(), signal(), signal())
    result = wire_to_task_analysis_result(
        wire(
            work_signals=signals,
            next_question=WireNextQuestion(
                text="實際動手的是你還是別人?",
                target_kind=WireNextQuestionTargetKind.NEW_SIGNAL,
                target_ordinal=len(signals),
            ),
        )
    )

    index = result.next_question.target.index
    assert 0 <= index < len(result.work_signals)
    assert index == len(signals) - 1
