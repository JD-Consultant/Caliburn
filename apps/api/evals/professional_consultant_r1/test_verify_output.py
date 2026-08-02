"""模型輸出 deterministic checks 測試。全部離線。

需要網路的三條（provider route／binding、無隱藏 retry、無 cache replay）屬 Segment 2，
本檔不涵蓋，也刻意不假裝涵蓋。
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from .contracts import load_case, project_canonical_view
from .validate_r1_cases import CASES_DIR
from .verify_output import (
    ARM_CLASS_FULL,
    ARM_CLASS_MINIMAL,
    verify_grader_packet,
    verify_output,
)


@pytest.fixture()
def case_08() -> dict:
    return load_case(Path(CASES_DIR) / "TI-R1-08.json")


@pytest.fixture()
def case_01() -> dict:
    return load_case(Path(CASES_DIR) / "TI-R1-01.json")


@pytest.fixture()
def good_view() -> dict:
    return {
        "analysis_decision": "propose_current_tasks",
        "proposed_tasks": [
            {
                "task_statement": "執行版本上線前測試",
                "intended_outcome": "在交付維運部署前確認版本符合上線標準",
                "source_anchors": [{"source_id": "turn-002", "quote": "我只做上線前測試"}],
            }
        ],
        "next_question": {
            "text": "上線前測試要通過哪些條件你才會放行？",
            "purpose": "確認完成標準",
        },
        "limitations": [],
    }


@pytest.fixture()
def good_state_change() -> dict:
    return {"change_type": "withdraw", "affected_existing_task_ids": ["task-existing-001"]}


def _checks(result) -> list[str]:
    return [f.check for f in result.findings]


# --- 正例 -----------------------------------------------------------------------


def test_full_arm_valid_output(case_08, good_view, good_state_change) -> None:
    result = verify_output(case_08, good_view, ARM_CLASS_FULL, good_state_change)
    assert result.ok, [str(f) for f in result.findings]


def test_minimal_arm_valid_output_without_state_change(case_08, good_view) -> None:
    """A1 在 TI-R1-08 上不需要碰既有 ID 也能通過共同視圖檢查（設計 §6.1）。"""
    result = verify_output(case_08, good_view, ARM_CLASS_MINIMAL)
    assert result.ok, [str(f) for f in result.findings]


def test_clarify_with_zero_tasks_is_legal(case_01) -> None:
    view = {
        "analysis_decision": "clarify",
        "proposed_tasks": [],
        "next_question": {"text": "最近一次開發是為了解決什麼問題？", "purpose": "取得 outcome"},
        "limitations": ["目前只有工具名稱，沒有工作結果"],
    }
    assert verify_output(case_01, view, ARM_CLASS_MINIMAL).ok


def test_null_next_question_is_legal(case_01, good_view) -> None:
    view = copy.deepcopy(good_view)
    view["analysis_decision"] = "no_change"
    view["proposed_tasks"] = []
    view["next_question"] = None
    assert verify_output(case_01, view, ARM_CLASS_MINIMAL).ok


# --- 投影：rationale 不得進盲評視圖 ----------------------------------------------


def test_projection_strips_decision_basis(good_view) -> None:
    raw = dict(good_view, decision_basis="turn-002 更正了 turn-001 的責任歸屬")
    projected = project_canonical_view(raw)
    assert "decision_basis" not in projected
    assert projected == good_view


def test_projection_strips_arm_and_model_identity(good_view) -> None:
    raw = dict(good_view, arm="A4", model="openai/gpt-5.6-luna-pro", latency_ms=1234)
    projected = project_canonical_view(raw)
    assert set(projected) <= set(good_view)
    assert verify_grader_packet(projected).ok


def test_projection_of_non_dict_is_empty() -> None:
    for raw in (None, [], "text", 7):
        assert project_canonical_view(raw) == {}


def test_grader_packet_rejects_rationale(good_view) -> None:
    packet = dict(good_view, decision_basis="因為 turn-002")
    assert "grader_packet" in _checks(verify_grader_packet(packet))


def test_grader_packet_rejects_state_change_fields(good_view) -> None:
    packet = dict(good_view, affected_existing_task_ids=["task-existing-001"])
    assert "grader_packet" in _checks(verify_grader_packet(packet))


def test_verify_output_rejects_unprojected_raw_output(case_08, good_view) -> None:
    """未投影就送進來會被擋，避免有人跳過 projector。"""
    raw = dict(good_view, decision_basis="rationale")
    assert "canonical_view_shape" in _checks(verify_output(case_08, raw, ARM_CLASS_MINIMAL))


# --- 反例：形狀與洩漏 -------------------------------------------------------------


def test_rejects_bad_arm_class(case_08, good_view) -> None:
    assert "arm_contract" in _checks(verify_output(case_08, good_view, "wishful"))


def test_rejects_unknown_analysis_decision(case_08, good_view) -> None:
    good_view["analysis_decision"] = "ship_it"
    assert "canonical_view_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_unknown_top_level_key(case_08, good_view) -> None:
    good_view["arm_id"] = "A4"
    assert "canonical_view_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_FULL))


def test_rejects_full_only_field_leaking_into_common_view(case_08, good_view) -> None:
    """設計 §6.1 的核心不變量：state-change 欄位不得進共同盲評視圖。"""
    good_view["affected_existing_task_ids"] = ["task-existing-001"]
    assert "full_only_leak" in _checks(verify_output(case_08, good_view, ARM_CLASS_FULL))


def test_rejects_change_type_leaking_into_common_view(case_08, good_view) -> None:
    good_view["change_type"] = "withdraw"
    assert "full_only_leak" in _checks(verify_output(case_08, good_view, ARM_CLASS_FULL))


def test_rejects_propose_decision_with_no_tasks(case_08, good_view) -> None:
    good_view["proposed_tasks"] = []
    assert "decision_task_consistency" in _checks(
        verify_output(case_08, good_view, ARM_CLASS_MINIMAL)
    )


def test_rejects_next_question_unknown_key(case_08, good_view) -> None:
    good_view["next_question"]["confidence"] = 0.9
    assert "next_question_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_blank_next_question_text(case_08, good_view) -> None:
    good_view["next_question"]["text"] = "   "
    assert "next_question_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


# --- 反例：Task 與來源 ------------------------------------------------------------


def test_rejects_task_without_source_anchor(case_08, good_view) -> None:
    good_view["proposed_tasks"][0]["source_anchors"] = []
    assert "source_anchor" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_missing_source_anchors_field(case_08, good_view) -> None:
    del good_view["proposed_tasks"][0]["source_anchors"]
    assert "source_anchor" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_anchor_with_unknown_source_id(case_08, good_view) -> None:
    good_view["proposed_tasks"][0]["source_anchors"][0]["source_id"] = "turn-404"
    assert "source_reference" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_quote_belonging_to_a_different_source(case_08, good_view) -> None:
    """quote 逐字存在於 case，但不屬於它宣稱的那一筆 source —— 舊版驗證器抓不到這個。"""
    good_view["proposed_tasks"][0]["source_anchors"][0]["source_id"] = "turn-001"
    assert "quote_verbatim" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_non_verbatim_quote(case_08, good_view) -> None:
    good_view["proposed_tasks"][0]["source_anchors"][0]["quote"] = "我負責上線前的所有測試工作"
    assert "quote_verbatim" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_too_short_quote(case_08, good_view) -> None:
    good_view["proposed_tasks"][0]["source_anchors"][0]["quote"] = "測試"
    assert "quote_verbatim" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_anchor_unknown_key(case_08, good_view) -> None:
    good_view["proposed_tasks"][0]["source_anchors"][0]["confidence"] = 0.5
    assert "source_anchor" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_duplicate_task_statement(case_08, good_view) -> None:
    good_view["proposed_tasks"].append(copy.deepcopy(good_view["proposed_tasks"][0]))
    assert "mechanical_duplication" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_duplicate_anchor_within_task(case_08, good_view) -> None:
    anchors = good_view["proposed_tasks"][0]["source_anchors"]
    anchors.append(dict(anchors[0]))
    assert "mechanical_duplication" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


def test_rejects_unknown_task_key(case_08, good_view) -> None:
    good_view["proposed_tasks"][0]["confidence"] = 0.8
    assert "task_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


# --- fail-closed：任意 JSON 值都必須回 finding，不得拋例外 -------------------------

BAD_VALUES: tuple[Any, ...] = (123, 4.5, True, None, [], {}, "unexpected")


@pytest.mark.parametrize("bad", BAD_VALUES)
def test_canonical_view_of_any_type_never_raises(case_08, bad) -> None:
    result = verify_output(case_08, bad, ARM_CLASS_MINIMAL)
    assert not result.ok


@pytest.mark.parametrize("bad", BAD_VALUES)
def test_proposed_tasks_of_any_type_never_raises(case_08, good_view, bad) -> None:
    good_view["proposed_tasks"] = bad
    assert not verify_output(case_08, good_view, ARM_CLASS_MINIMAL).ok


@pytest.mark.parametrize("bad", BAD_VALUES)
def test_task_of_any_type_never_raises(case_08, good_view, bad) -> None:
    good_view["proposed_tasks"] = [bad]
    assert not verify_output(case_08, good_view, ARM_CLASS_MINIMAL).ok


@pytest.mark.parametrize("field", ["task_statement", "intended_outcome"])
@pytest.mark.parametrize("bad", (123, 4.5, True, None, [], {}))
def test_task_text_fields_of_any_type_never_raise(case_08, good_view, field, bad) -> None:
    good_view["proposed_tasks"][0][field] = bad
    assert "task_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


@pytest.mark.parametrize("bad", BAD_VALUES)
def test_source_anchors_of_any_type_never_raise(case_08, good_view, bad) -> None:
    good_view["proposed_tasks"][0]["source_anchors"] = bad
    assert not verify_output(case_08, good_view, ARM_CLASS_MINIMAL).ok


@pytest.mark.parametrize("bad", (123, 4.5, True, None, [], "text"))
def test_single_anchor_of_any_type_never_raises(case_08, good_view, bad) -> None:
    good_view["proposed_tasks"][0]["source_anchors"] = [bad]
    assert not verify_output(case_08, good_view, ARM_CLASS_MINIMAL).ok


@pytest.mark.parametrize("field", ["source_id", "quote"])
@pytest.mark.parametrize("bad", (123, 4.5, True, None, [], {}))
def test_anchor_fields_of_any_type_never_raise(case_08, good_view, field, bad) -> None:
    good_view["proposed_tasks"][0]["source_anchors"][0][field] = bad
    assert not verify_output(case_08, good_view, ARM_CLASS_MINIMAL).ok


@pytest.mark.parametrize("bad", BAD_VALUES)
def test_limitations_of_any_type_never_raise(case_08, good_view, bad) -> None:
    good_view["limitations"] = bad
    result = verify_output(case_08, good_view, ARM_CLASS_MINIMAL)
    if bad == []:
        assert result.ok
    else:
        assert not result.ok


def test_limitations_items_must_be_strings(case_08, good_view) -> None:
    good_view["limitations"] = ["fine", 42]
    assert "canonical_view_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


@pytest.mark.parametrize("bad", (123, 4.5, True, [], "text"))
def test_next_question_of_any_type_never_raises(case_08, good_view, bad) -> None:
    good_view["next_question"] = bad
    assert "next_question_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


@pytest.mark.parametrize("bad", (123, 4.5, [], {}))
def test_next_question_text_of_any_type_never_raises(case_08, good_view, bad) -> None:
    good_view["next_question"]["text"] = bad
    assert "next_question_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_MINIMAL))


@pytest.mark.parametrize("bad", (123, 4.5, True, [], "text"))
def test_state_change_of_any_type_never_raises(case_08, good_view, bad) -> None:
    assert not verify_output(case_08, good_view, ARM_CLASS_FULL, bad).ok


@pytest.mark.parametrize("bad", (123, 4.5, True, {}, "text"))
def test_affected_ids_of_any_type_never_raise(case_08, good_view, good_state_change, bad) -> None:
    good_state_change["affected_existing_task_ids"] = bad
    assert not verify_output(case_08, good_view, ARM_CLASS_FULL, good_state_change).ok


def test_affected_ids_items_must_be_strings(case_08, good_view, good_state_change) -> None:
    good_state_change["affected_existing_task_ids"] = [42]
    assert "state_change_shape" in _checks(
        verify_output(case_08, good_view, ARM_CLASS_FULL, good_state_change)
    )


# --- 反例：full-only 診斷視圖 -----------------------------------------------------


def test_rejects_minimal_arm_emitting_state_change_view(case_08, good_view, good_state_change) -> None:
    assert "arm_contract" in _checks(
        verify_output(case_08, good_view, ARM_CLASS_MINIMAL, good_state_change)
    )


def test_rejects_full_arm_missing_state_change_view_when_state_exists(case_08, good_view) -> None:
    assert "state_change_shape" in _checks(verify_output(case_08, good_view, ARM_CLASS_FULL))


def test_full_arm_needs_no_state_change_view_when_case_has_no_state(case_01) -> None:
    view = {
        "analysis_decision": "clarify",
        "proposed_tasks": [],
        "next_question": {"text": "最近一次開發交付給誰？", "purpose": "取得對象"},
        "limitations": [],
    }
    assert verify_output(case_01, view, ARM_CLASS_FULL).ok


def test_rejects_unknown_existing_task_id(case_08, good_view, good_state_change) -> None:
    good_state_change["affected_existing_task_ids"] = ["task-does-not-exist"]
    assert "existing_task_reference" in _checks(
        verify_output(case_08, good_view, ARM_CLASS_FULL, good_state_change)
    )


def test_rejects_withdraw_without_target(case_08, good_view, good_state_change) -> None:
    good_state_change["affected_existing_task_ids"] = []
    assert "existing_task_reference" in _checks(
        verify_output(case_08, good_view, ARM_CLASS_FULL, good_state_change)
    )


def test_rejects_unknown_change_type(case_08, good_view, good_state_change) -> None:
    good_state_change["change_type"] = "obliterate"
    assert "state_change_shape" in _checks(
        verify_output(case_08, good_view, ARM_CLASS_FULL, good_state_change)
    )


def test_rejects_unknown_state_change_key(case_08, good_view, good_state_change) -> None:
    good_state_change["arm"] = "A2"
    assert "state_change_shape" in _checks(
        verify_output(case_08, good_view, ARM_CLASS_FULL, good_state_change)
    )
