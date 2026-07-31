"""T1:compact model-facing wire contract 的形狀與複雜度預算。**沒有網路呼叫。**

這一份測試守的是「送出去的 grammar 有餘裕」。官方明載個別限制全部滿足仍可能被拒
(structured outputs:「even if each individual limit in the preceding table is satisfied」),
所以預算不是抄官方數字,是留餘裕:union 直接歸零,而不是壓到 16。
"""

from __future__ import annotations

import json

import pytest

from app.job_analysis.domain import (
    EnablerKind,
    ExclusionReason,
    OpenIssueKind,
    RetirementReason,
)
from app.job_analysis.application.verifier import ViolationCode
from app.job_analysis.llm import IdentityRelation, SignalDisposition, TaskChangeKind
from app.job_analysis.llm.portable_schema import (
    assert_portable_strict_output_schema,
    compact_strict_output_schema,
    schema_complexity,
)
from app.job_analysis.llm.wire import (
    NEUTRAL,
    WIRE_SCHEMA_PATH,
    TaskAnalysisWire,
    WireNextQuestion,
    WireNextQuestionTargetKind,
    WireRejectionCode,
    WireSignal,
    WireSplitChild,
    WireTaskChange,
    WireTaskFields,
    WireWithdrawReason,
    committed_wire_schema,
    render_wire_schema_file,
    task_analysis_wire_provider_schema,
)


#: 送出去的形狀必須守住的預算。改動這裡等於改動「這份 grammar 能不能編譯」的假設。
UNION_BUDGET = 0
NESTING_BUDGET = 6
PROPERTY_BUDGET = 35
#: description 是**耦合規則的家**(欄位名表達不了「add 要 0 個 target」這種事),
#: 不是開發者註解的出口。上限從 600 放寬到 1,500:一條 description 只要擋掉一次
#: verifier rejection 就回本——被擋下的回合要付一整次呼叫,還賠掉員工那一輪。
DESCRIPTION_BYTES_BUDGET = 1500

#: 位元組是**粗略的迴歸護欄**,不是綁定條件——真正決定能不能編譯的是上面三個結構維度。
#: 貼著實測值訂會讓任何一次 description 微調都紅,而 description 正是我們刻意用來
#: 取代 prompt 散文的東西。
WIRE_BYTES_BUDGET = 5600


def wire_schema() -> dict:
    return task_analysis_wire_provider_schema()


def wire_bytes() -> int:
    return len(
        json.dumps(wire_schema(), separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    )


# ── 複雜度預算 ─────────────────────────────────────────────────────────────


def test_wire_schema_carries_no_unions_at_all():
    """union 是這次 400 最強的根因假說,也是唯一能直接歸零的維度。"""
    counts = schema_complexity(wire_schema())

    assert counts["union_parameters"] == UNION_BUDGET
    assert counts["optional_parameters"] == UNION_BUDGET


def test_wire_schema_stays_inside_the_structural_budget():
    counts = schema_complexity(wire_schema())

    assert counts["nesting_levels"] <= NESTING_BUDGET
    assert counts["properties"] <= PROPERTY_BUDGET


def test_wire_schema_stays_inside_the_byte_budget():
    assert wire_bytes() <= WIRE_BYTES_BUDGET


#: `task_analysis_result.v1` 送出去時的實測值(commit 9966255,撞上 400 的那一份)。
#: 留成常數而不是留著舊 schema 來比:那份已經不送了,留著只會變成沒人維護的化石。
V1_BASELINE = {
    "union_parameters": 17,
    "optional_parameters": 17,
    "properties": 54,
    "nesting_levels": 9,
}


@pytest.mark.parametrize("dimension", sorted(V1_BASELINE))
def test_every_dimension_improved_on_the_schema_that_hit_the_400(dimension: str):
    assert schema_complexity(wire_schema())[dimension] < V1_BASELINE[dimension]


# ── 沒有噪音漏給模型 ───────────────────────────────────────────────────────


def test_wire_schema_carries_no_generated_titles():
    """Pydantic 自動生成的 `title` 是欄位名的 Title Case 版,對模型零資訊量。"""
    text = json.dumps(wire_schema(), ensure_ascii=False)

    assert '"title"' not in text


def visible_to_the_model() -> str:
    """模型實際看得到的全部文字:schema 的 description ＋ Static Instructions。"""
    from app.job_analysis.llm import TASK_ANALYSIS_INSTRUCTIONS

    found: list[str] = [TASK_ANALYSIS_INSTRUCTIONS]

    def walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            description = node.get("description")
            if isinstance(description, str):
                found.append(description)
            for value in node.values():
                walk(value)

    walk(wire_schema())
    return "\n".join(found)


@pytest.mark.parametrize(
    ("code", "phrase"),
    [
        # verifier 擋下來不是免費的:要付一整次呼叫,還賠掉員工那一輪。所以每一條
        # **模型必須主動答對**的耦合規則,都得有一個模型看得到的出處。
        pytest.param(
            ViolationCode.RELATION_DOES_NOT_MATCH_MAPPING,
            "add→no_match",
            id="relation-mapping",
        ),
        pytest.param(
            ViolationCode.TASK_CHANGE_TARGET_COUNT,
            "merge 至少 2 個",
            id="target-count",
        ),
        pytest.param(
            ViolationCode.IDENTITY_TARGETS_NOT_EMPTY, "add 0 個", id="no-match-empty"
        ),
        pytest.param(
            ViolationCode.TASK_FIELDS_FORBIDDEN, "withdraw 不得填", id="withdraw-fields"
        ),
        pytest.param(
            ViolationCode.TASK_FIELDS_REQUIRED,
            "add／revise／merge 必填",
            id="fields-required",
        ),
        pytest.param(
            ViolationCode.WITHDRAW_REASON_REQUIRED,
            "僅 change=withdraw 時填",
            id="withdraw-reason",
        ),
        pytest.param(
            ViolationCode.SPLIT_CHILDREN_INSUFFICIENT, "至少兩個", id="split-children"
        ),
        pytest.param(
            ViolationCode.SPLIT_SUPPORT_UNKNOWN, "標示為有效", id="split-support"
        ),
        pytest.param(
            ViolationCode.SUPERSESSION_MISSING_CURRENT_TURN_ANCHOR,
            "anchors 必須包含目前這一輪的員工回合",
            id="supersession-anchor",
        ),
        pytest.param(
            ViolationCode.RESOLUTION_MAPPING_INVALID,
            "確認是新工作用 no_match ＋ add",
            id="resolution-mapping",
        ),
        pytest.param(
            ViolationCode.TARGET_ORDINAL_RETIRED,
            "只能指 current_authorities.tasks 的編號",
            id="retired-target",
        ),
        pytest.param(
            ViolationCode.QUOTE_NOT_VERBATIM, "逐字子字串", id="verbatim-quote"
        ),
        pytest.param(
            ViolationCode.OPEN_ISSUE_ANCHORS_INSUFFICIENT,
            "矛盾未解至少要引兩句",
            id="contradiction-anchors",
        ),
    ],
)
def test_every_rule_the_model_must_satisfy_is_discoverable(code, phrase: str):
    assert phrase in visible_to_the_model(), f"nothing tells the model about {code}"


def test_descriptions_are_deliberate_model_facing_and_budgeted():
    """`description` 只用來承載中性值約定,不是開發者註解的出口。"""
    found: list[str] = []

    def walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            description = node.get("description")
            if isinstance(description, str):
                found.append(description)
            for value in node.values():
                walk(value)

    walk(wire_schema())
    total = sum(len(text.encode("utf-8")) for text in found)

    assert total <= DESCRIPTION_BYTES_BUDGET
    for text in found:
        # 內部規格章節號與範例 ID 對模型不可解,而且是幻覺誘餌。
        assert "§" not in text
        assert "TI-" not in text


# ── strict 形狀 ────────────────────────────────────────────────────────────


def test_wire_schema_is_portable_and_strict_shaped():
    schema = wire_schema()
    assert_portable_strict_output_schema(schema)

    objects: list[dict] = []

    def walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("type") == "object":
                objects.append(node)
            for value in node.values():
                walk(value)

    walk(schema)

    assert objects
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert obj["required"] == list(obj["properties"])


# ── 形狀凍結 ───────────────────────────────────────────────────────────────


def test_wire_shape_is_frozen():
    assert list(TaskAnalysisWire.model_fields) == ["work_signals", "next_question"]
    assert list(WireSignal.model_fields) == [
        "anchors",
        "relation",
        "target_task_ordinals",
        "supersedes",
        "resolves_open_issue_ordinal",
        "disposition",
        "change",
        "withdraw_reason",
        "task",
        "split_children",
        "rejection_code",
        "rejection_summary",
    ]
    assert list(WireTaskFields.model_fields) == [
        "statement",
        "action",
        "object",
        "purpose_result",
        "enablers",
    ]
    assert list(WireSplitChild.model_fields) == [
        "statement",
        "action",
        "object",
        "inherited_support_ordinals",
    ]
    assert list(WireNextQuestion.model_fields) == [
        "text",
        "target_kind",
        "target_ordinal",
    ]


def test_split_children_do_not_carry_a_second_copy_of_the_task_fields():
    """`TaskFields` inline 兩次原本吃掉 17 個 union 中的 8 個,並多推 2 層巢狀。"""
    assert "purpose_result" not in WireSplitChild.model_fields
    assert "enablers" not in WireSplitChild.model_fields


def test_wire_drops_the_fields_nobody_reads():
    """`limitations` 與 `next_question.purpose` 全 repo 零消費者。"""
    assert "limitations" not in TaskAnalysisWire.model_fields
    assert "purpose" not in WireNextQuestion.model_fields


def test_identity_and_change_share_one_ordinal_list():
    """verifier 的 `TARGET_ORDINALS_DISAGREE` 本來就在驗兩份重複資料一致;送一份即可。"""
    assert "target_task_ordinals" in WireSignal.model_fields
    assert not any(
        name.endswith("target_task_ordinals")
        for name in WireTaskFields.model_fields | WireSplitChild.model_fields
    )


def test_hint_fields_are_not_asked_for_every_turn():
    """`context`／`deliverable_hint`／`success_criterion_hint` 的唯一消費者是下一回合的
    packet 自己;domain 欄位保留,但不再每回合要模型生成。"""
    for name in ("context", "deliverable_hint", "success_criterion_hint"):
        assert name not in WireTaskFields.model_fields


# ── 中性值:值域不得與 domain 漂開 ─────────────────────────────────────────


def test_neutral_value_is_reserved_and_not_a_domain_value():
    domain_values = (
        {member.value for member in TaskChangeKind}
        | {member.value for member in RetirementReason}
        | {member.value for member in ExclusionReason}
        | {member.value for member in OpenIssueKind}
    )

    assert NEUTRAL not in domain_values


@pytest.mark.parametrize(
    ("wire_enum", "domain_enums"),
    [
        pytest.param(WireTaskChange, (TaskChangeKind,), id="change"),
        pytest.param(WireWithdrawReason, (RetirementReason,), id="withdraw-reason"),
        pytest.param(
            WireRejectionCode, (ExclusionReason, OpenIssueKind), id="rejection-code"
        ),
    ],
)
def test_wire_enums_are_the_domain_values_plus_one_neutral(wire_enum, domain_enums):
    expected = {NEUTRAL}
    for domain_enum in domain_enums:
        expected |= {member.value for member in domain_enum}

    assert {member.value for member in wire_enum} == expected


def test_enums_reused_unchanged_keep_their_domain_values():
    schema = wire_schema()
    defs = schema["$defs"]

    assert defs["IdentityRelation"]["enum"] == [m.value for m in IdentityRelation]
    assert defs["SignalDisposition"]["enum"] == [m.value for m in SignalDisposition]
    assert defs["EnablerKind"]["enum"] == [m.value for m in EnablerKind]


def test_next_question_target_sentinel_is_carried_by_the_kind_not_the_number():
    """`new_signal` 的索引可以是 0,用「0 表示無」會吃掉合法值。"""
    assert NEUTRAL in {member.value for member in WireNextQuestionTargetKind}
    assert WireNextQuestion.model_fields["target_ordinal"].annotation is int


# ── golden ─────────────────────────────────────────────────────────────────


def test_committed_wire_schema_matches_the_contract():
    """送給模型的形狀改變時,diff 必須在 review 裡看得見。

    重新產生:`uv run python -c "from app.job_analysis.llm.wire import
    WIRE_SCHEMA_PATH, render_wire_schema_file;
    WIRE_SCHEMA_PATH.write_text(render_wire_schema_file(), encoding='utf-8',
    newline='\\n')"`
    """
    assert WIRE_SCHEMA_PATH.read_text(encoding="utf-8") == render_wire_schema_file()
    assert committed_wire_schema() == wire_schema()


# ── compact 投影本身 ───────────────────────────────────────────────────────


def test_compact_projection_drops_titles_but_keeps_deliberate_descriptions():
    projected = compact_strict_output_schema(
        {
            "type": "object",
            "title": "Generated",
            "properties": {
                "quote": {
                    "type": "string",
                    "title": "Quote",
                    "description": "逐字",
                    "minLength": 1,
                }
            },
        }
    )

    assert projected == {
        "type": "object",
        "properties": {"quote": {"type": "string", "description": "逐字"}},
        "additionalProperties": False,
        "required": ["quote"],
    }


def test_schema_complexity_counts_the_expanded_form():
    """官方限制以編譯後的 grammar 為準;`$ref` 共用不會讓計數變少。"""
    counts = schema_complexity(
        {
            "$defs": {
                "Leaf": {
                    "type": "object",
                    "properties": {"a": {"type": "string"}},
                    "required": ["a"],
                    "additionalProperties": False,
                }
            },
            "type": "object",
            "properties": {
                "one": {"$ref": "#/$defs/Leaf"},
                "two": {"$ref": "#/$defs/Leaf"},
            },
            "required": ["one", "two"],
            "additionalProperties": False,
        }
    )

    assert counts["properties"] == 4
