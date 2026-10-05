"""Offline safeguards for the replacement probe, not semantic grading."""

import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent / "memory-added-value-2026-10-04"
sys.path.insert(0, str(BASE))
from contexts import replacement_context
from support import context_for, read_snapshot


@pytest.fixture
def material():
    return json.loads((BASE / "live-01/materials.json").read_text(encoding="utf-8"))


def test_recent_initial_context_excludes_covered_originals_without_changing_jd(
    material,
):
    raw = replacement_context(material, "raw", "核對")
    recent = replacement_context(material, "raw_memory", "核對")
    a, b = json.loads(raw[0]["content"]), json.loads(recent[0]["content"])
    assert [
        m["interview_sequence"] for m in a["historical_interview"]["messages"]
    ] == list(range(1, 106))
    assert [m["interview_sequence"] for m in b["historical_interview"]["messages"]] == [
        105
    ]
    assert a["jd_draft"] == b["jd_draft"]
    assert raw[1] == recent[1] == {"role": "user", "content": "核對"}
    assert len(raw) == len(recent) == 2
    assert all(item["role"] == "user" for item in raw + recent)
    assert b["work_situation_map"] == material["maps"]["work_situation"]
    assert (
        a["interview_read_boundary"]["through_sequence"]
        == b["interview_read_boundary"]["through_sequence"]
        == 105
    )
    assert b["interview_read_boundary"]["context_sequences"] == []
    # The previous additive-value builder must retain its original behavior.
    assert (
        len(
            json.loads(context_for(material, "raw_memory", "核對")[0]["content"])[
                "historical_interview"
            ]["messages"]
        )
        == 105
    )


def test_recent_employee_suffix_keeps_one_preceding_guidance(material):
    material["snapshot"]["covered_through_sequence"] = 103
    data = json.loads(replacement_context(material, "raw_memory", "核對")[0]["content"])
    assert [
        m["interview_sequence"] for m in data["historical_interview"]["messages"]
    ] == [103, 104, 105]
    assert data["interview_read_boundary"]["context_sequences"] == [103]


def test_both_arms_can_read_same_early_original_and_cannot_read_future(material):
    query = {"query": {"kind": "messages", "sequences": [8, 14, 94]}}
    for arm in ("raw", "raw_memory"):
        output = read_snapshot(material, arm, "read_interview", query)
        assert [m["interview_sequence"] for m in output["messages"]] == [8, 14, 94]
        assert "5%" in output["messages"][0]["text"]
        with pytest.raises(ValueError):
            read_snapshot(
                material,
                arm,
                "read_interview",
                {"query": {"kind": "messages", "sequences": [106]}},
            )


def test_invalid_coverage_is_not_silently_clipped(material):
    material["snapshot"]["covered_through_sequence"] = 106
    with pytest.raises(ValueError, match="coverage"):
        replacement_context(material, "raw_memory", "核對")
