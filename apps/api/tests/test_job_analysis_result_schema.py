"""T2:`TaskAnalysisResult` 內部契約(研究稿 §12、ADR 0040 §6)。

**送出去的形狀不在這裡** —— 那是 `wire.py` 的 `task_analysis_result.v2`,
測試見 `test_job_analysis_wire_schema.py` 與 `test_job_analysis_wire_mapper.py`。
這一份只守 verifier 與下游吃的形狀。
"""

from __future__ import annotations

import json

import pytest

from app.job_analysis.domain import ExclusionReason, OpenIssueKind, TaskFields
from app.job_analysis.llm import (
    TASK_ANALYSIS_INSTRUCTIONS,
    ExcludePayload,
    IdentityAssessment,
    IdentityRelation,
    NextQuestion,
    NextQuestionTarget,
    NextQuestionTargetKind,
    OpenIssuePayload,
    ProviderSchemaPortabilityError,
    SignalAnchor,
    SignalDisposition,
    SplitChildPayload,
    TaskAnalysisResult,
    TaskChangeKind,
    TaskChangePayload,
    WorkSignal,
    assert_portable_strict_output_schema,
    compact_strict_output_schema,
)


# ── §12.1 形狀 ──────────────────────────────────────────────────────────────


def test_result_top_level_shape_is_frozen():
    assert list(TaskAnalysisResult.model_fields) == ["work_signals", "next_question"]
    assert list(WorkSignal.model_fields) == [
        "anchors",
        "identity",
        "supersedes_support_ordinals",
        "resolves_open_issue_ordinal",
        "disposition",
        "task_change",
        "exclude",
        "open_issue",
    ]
    assert list(TaskChangePayload.model_fields) == [
        "change",
        # §12.1 之後補上的唯一欄位:§9.5 要求 withdrawn 必有 reason,而只有模型知道
        # 是哪一種(「只代班過一次」是 one_off,不是 employee_denied)。
        "withdraw_reason",
        "target_task_ordinals",
        "task_fields",
        "split_children",
    ]
    assert list(SplitChildPayload.model_fields) == [
        "task_fields",
        "inherited_support_ordinals",
    ]
    assert list(SignalAnchor.model_fields) == ["turn_ordinal", "quote"]
    assert list(NextQuestion.model_fields) == ["text", "target"]


def test_result_has_no_overall_analysis_decision_field():
    """§12.1:本輪是提案、澄清還是不變更由 `work_signals` 推導,不另存一個可能矛盾的欄位。"""
    assert "analysis_decision" not in TaskAnalysisResult.model_fields


def test_task_fields_is_the_semantic_subset_only():
    """§12.1:`task_fields` 不含 task_id／support_links／retirement／merged_into／split_from
    ——那些全部由 application 依 anchors 與 gate 產生。"""
    assert list(TaskFields.model_fields) == [
        "statement",
        "action",
        "object",
        "purpose_result",
        "context",
        "enablers",
    ]


def test_split_children_can_assign_existing_parent_support_by_ordinal():
    """Split 不能把母 Task 的全部來源複製給每個 child，也不能全部丟掉。

    provider contract 必須讓每個 child 明確選擇要沿用的 task-local support ordinal。
    """
    split_children = TaskChangePayload.model_json_schema()["properties"][
        "split_children"
    ]
    assert split_children["items"]["$ref"].endswith("/SplitChildPayload")


def test_split_prompt_explains_child_specific_support_inheritance():
    assert "inherited_support_ordinals" in TASK_ANALYSIS_INSTRUCTIONS


def test_prompt_does_not_auto_merge_a_partial_jd_task_with_a_possible_duplicate():
    assert "resolves_open_issue_ordinal" in TASK_ANALYSIS_INSTRUCTIONS
    assert "duplicate／overlap／uncertain" in TASK_ANALYSIS_INSTRUCTIONS
    assert "不得自動換 ID 或 merge" in TASK_ANALYSIS_INSTRUCTIONS


def test_result_enum_domains_are_frozen():
    assert {member.value for member in IdentityRelation} == {
        "no_match",
        "duplicate",
        "overlap",
        "uncertain",
    }
    assert {member.value for member in SignalDisposition} == {
        "task_change",
        "support_only",
        "exclude",
        "open_issue",
    }
    assert {member.value for member in TaskChangeKind} == {
        "add",
        "revise",
        "withdraw",
        "merge",
        "split",
    }
    assert {member.value for member in NextQuestionTargetKind} == {
        "existing_open_issue",
        "new_signal",
    }


def make_result(**overrides) -> TaskAnalysisResult:
    base = {
        "work_signals": (
            WorkSignal(
                anchors=(SignalAnchor(turn_ordinal=3, quote="我每週要出一份週報"),),
                identity=IdentityAssessment(relation=IdentityRelation.NO_MATCH),
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.ADD,
                    task_fields=TaskFields(
                        statement="每週彙整營運週報", action="彙整", object="營運週報"
                    ),
                ),
            ),
        ),
        "next_question": NextQuestion(
            text="這份週報完成後交給誰?",
            target=NextQuestionTarget(
                kind=NextQuestionTargetKind.NEW_SIGNAL, index=0
            ),
        ),
    }
    base.update(overrides)
    return TaskAnalysisResult(**base)


def test_result_round_trips_through_json():
    result = make_result()
    reparsed = TaskAnalysisResult.model_validate_json(result.model_dump_json())
    assert reparsed == result


def test_signal_can_reference_the_open_issue_it_resolves():
    signal = WorkSignal(
        anchors=(SignalAnchor(turn_ordinal=3, quote="我每週彙整營運週報"),),
        identity=IdentityAssessment(relation=IdentityRelation.NO_MATCH),
        resolves_open_issue_ordinal=2,
        disposition=SignalDisposition.TASK_CHANGE,
        task_change=TaskChangePayload(
            change=TaskChangeKind.ADD,
            task_fields=TaskFields(
                statement="每週彙整營運週報",
                action="彙整",
                object="營運週報",
            ),
        ),
    )

    assert (
        WorkSignal.model_validate_json(signal.model_dump_json())
        .resolves_open_issue_ordinal
        == 2
    )


def test_contract_carries_no_cross_field_validation():
    """§12.3 的規則歸 verifier(T3):結構合法但語意違規的輸出必須 parse 得出來,
    才可能被 verifier 用明確理由拒絕,而不是變成看不出原因的 schema 失敗。"""
    contradictory = make_result(
        work_signals=(
            WorkSignal(
                anchors=(),
                identity=IdentityAssessment(
                    relation=IdentityRelation.NO_MATCH, target_task_ordinals=(1, 2)
                ),
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=None,
            ),
        )
    )
    assert contradictory.work_signals[0].task_change is None


def test_payload_slots_encode_the_disposition_union():
    """portable subset 沒有多支 union,四種 payload 落成三個 nullable 兄弟欄位;
    `support_only` 就是三者皆 null。"""
    signal = WorkSignal(
        anchors=(SignalAnchor(turn_ordinal=3, quote="就是這樣"),),
        identity=IdentityAssessment(
            relation=IdentityRelation.DUPLICATE, target_task_ordinals=(1,)
        ),
        disposition=SignalDisposition.SUPPORT_ONLY,
    )
    assert (signal.task_change, signal.exclude, signal.open_issue) == (None, None, None)


def test_payload_enums_reuse_the_domain_landing_spots():
    """§12.2:`exclude` 落在 `excluded_signals[]`、`open_issue` 落在 `open_issues[]`,
    值域必須是同一組,否則 mapping 時要翻譯就會漏。"""
    assert ExcludePayload.model_fields["reason"].annotation is ExclusionReason
    assert OpenIssuePayload.model_fields["kind"].annotation is OpenIssueKind


# ── portable subset lint(ADR 0040 決定 24)─────────────────────────────────


def test_projection_drops_local_constraints_and_requires_every_property():
    projected = compact_strict_output_schema(
        {
            "type": "object",
            "properties": {
                "quote": {"type": "string", "minLength": 1, "default": ""},
                "kind": {"const": "add"},
            },
        }
    )
    assert projected == {
        "type": "object",
        "properties": {
            "quote": {"type": "string"},
            "kind": {"enum": ["add"]},
        },
        "additionalProperties": False,
        "required": ["quote", "kind"],
    }


@pytest.mark.parametrize(
    ("case", "schema"),
    [
        (
            "unsupported keyword",
            {
                "type": "object",
                "properties": {"quote": {"type": "string", "minLength": 1}},
                "required": ["quote"],
                "additionalProperties": False,
            },
        ),
        (
            "open object",
            {"type": "object", "properties": {}, "required": []},
        ),
        (
            "optional property",
            {
                "type": "object",
                "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
                "required": ["a"],
                "additionalProperties": False,
            },
        ),
        (
            "three-branch union",
            {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"},
                    {"type": "null"},
                ]
            },
        ),
        (
            "non-nullable union",
            {"anyOf": [{"type": "string"}, {"type": "integer"}]},
        ),
        ("empty enum", {"type": "string", "enum": []}),
        ("unknown json type", {"type": "tuple"}),
    ],
)
def test_lint_rejects_schemas_outside_the_portable_subset(case, schema):
    with pytest.raises(ProviderSchemaPortabilityError):
        assert_portable_strict_output_schema(schema)


def test_lint_reaches_nested_definitions():
    schema = {
        "$defs": {
            "Inner": {
                "type": "object",
                "properties": {"a": {"type": "string", "pattern": "^x$"}},
                "required": ["a"],
                "additionalProperties": False,
            }
        },
        "type": "object",
        "properties": {"inner": {"$ref": "#/$defs/Inner"}},
        "required": ["inner"],
        "additionalProperties": False,
    }
    with pytest.raises(ProviderSchemaPortabilityError, match=r"\$defs\.Inner"):
        assert_portable_strict_output_schema(schema)
