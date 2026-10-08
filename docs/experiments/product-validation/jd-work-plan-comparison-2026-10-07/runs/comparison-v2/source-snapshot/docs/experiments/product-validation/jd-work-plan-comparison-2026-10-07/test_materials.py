"""Zero-key behavior cases for the new frozen disclosure materials."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
OLD = HERE.with_name("interview-plan-comparison-2026-10-07")
sys.path.insert(0, str(HERE))
from materials import Employee


def decision(*ids, mode="answer", **extra):
    return {
        "fact_ids": list(ids),
        "mode": mode,
        "reason": "相關的實際工作提問",
        **extra,
    }


@pytest.mark.parametrize(
    "profile,partial,topic,cue",
    [
        (
            "warehouse",
            "inventory-partial",
            "training",
            "剛才說盤點後面怎麼處理想不清楚，現在我想起一些了，可以再說明。",
        ),
        (
            "course_admin",
            "absence-partial",
            "refund",
            "剛才說代課後面怎麼接想不清楚，現在我想起一些了，可以再說明。",
        ),
    ],
)
def test_return_cue_follows_gap_and_is_not_replayed(profile, partial, topic, cue):
    employee = Employee(profile)
    employee.reviewed_answer("請說明剛才工作的後續？", decision(partial))
    answer = employee.reviewed_answer("請說明接著這項工作的步驟？", decision(topic))
    assert cue in answer
    assert cue not in employee.reviewed_answer("請確認剛才的流程？", decision(topic))


def test_refund_keyword_is_not_a_frozen_answer_for_true_unknown():
    employee = Employee("course_admin")
    answer = employee.reviewed_answer(
        "特殊退費是否普遍適用？", decision(mode="unknown")
    )
    assert "試算" not in answer
    assert not employee.disclosed


def test_hidden_topic_before_gap_does_not_unlock_return():
    employee = Employee("warehouse")
    employee.reviewed_answer("帶教怎麼做？", decision("training"))
    employee.reviewed_answer("盤點怎麼做？", decision("inventory-partial"))
    with pytest.raises(ValueError):
        employee.reviewed_answer("盤點誰批准調帳？", decision("inventory-authority"))


def test_correction_requires_prior_disclosure():
    employee = Employee("warehouse")
    with pytest.raises(ValueError):
        employee.reviewed_answer("新人誰批准上線？", decision("training-boundary"))


def test_refusal_does_not_block_general_privacy_procedure():
    employee = Employee("course_admin")
    employee.reviewed_answer("如何處理滿意度和投訴？", decision("sensitive-evaluation"))
    answer = employee.reviewed_answer("個資流程如何？", decision("privacy"))
    assert "密件副本" in answer
