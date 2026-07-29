"""T2:`TaskAnalysisResult.v1` 契約與 provider-facing schema(研究稿 §12、ADR 0040 §6)。"""

from __future__ import annotations

import json

import pytest

from app.job_analysis.domain import ExclusionReason, OpenIssueKind, TaskFields
from app.job_analysis.llm import (
    PROVIDER_SCHEMA_PATH,
    IdentityAssessment,
    IdentityRelation,
    NextQuestion,
    NextQuestionTarget,
    NextQuestionTargetKind,
    ProviderSchemaPortabilityError,
    SignalAnchor,
    SignalDisposition,
    TaskAnalysisResult,
    TaskChangeKind,
    TaskChangePayload,
    WorkSignal,
    assert_portable_strict_output_schema,
    committed_provider_schema,
    portable_strict_output_schema,
    render_provider_schema_file,
    task_analysis_result_provider_schema,
)


# ── §12.1 形狀 ──────────────────────────────────────────────────────────────


def test_result_top_level_shape_is_frozen():
    assert list(TaskAnalysisResult.model_fields) == [
        "work_signals",
        "next_question",
        "limitations",
    ]
    assert list(WorkSignal.model_fields) == [
        "anchors",
        "identity",
        "supersedes_support_ordinals",
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
    assert list(SignalAnchor.model_fields) == ["turn_ordinal", "quote"]
    assert list(NextQuestion.model_fields) == ["text", "purpose", "target"]


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
        "deliverable_hint",
        "success_criterion_hint",
        "enablers",
    ]


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
            purpose="釐清產出對象",
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
    schema = task_analysis_result_provider_schema()
    assert schema["$defs"]["ExclusionReason"]["enum"] == [
        member.value for member in ExclusionReason
    ]
    assert schema["$defs"]["OpenIssueKind"]["enum"] == [
        member.value for member in OpenIssueKind
    ]


# ── portable subset lint(ADR 0040 決定 24)─────────────────────────────────


def test_generated_provider_schema_is_portable():
    assert_portable_strict_output_schema(task_analysis_result_provider_schema())


def test_projection_drops_local_constraints_and_requires_every_property():
    projected = portable_strict_output_schema(
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


# ── golden(§12.4)──────────────────────────────────────────────────────────


def test_committed_provider_schema_matches_the_contract():
    """送給模型的形狀改變時,diff 必須在 review 裡看得見。

    重新產生:`uv run python -c "from pathlib import Path;
    from app.job_analysis.llm.provider_schema import PROVIDER_SCHEMA_PATH,
    render_provider_schema_file;
    PROVIDER_SCHEMA_PATH.write_text(render_provider_schema_file(), encoding='utf-8',
    newline='\\n')"`
    """
    assert (
        PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8") == render_provider_schema_file()
    )
    assert committed_provider_schema() == task_analysis_result_provider_schema()


def test_committed_schema_is_valid_json_and_portable():
    schema = json.loads(PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert_portable_strict_output_schema(schema)
    assert schema["title"] == "TaskAnalysisResult"
