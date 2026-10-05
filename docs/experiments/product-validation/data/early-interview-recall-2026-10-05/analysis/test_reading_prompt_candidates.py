"""Protect paired comparisons from accidental context, schema or baseline changes."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from reading_prompt_candidates import navigation_candidate, precision_candidate

TRACE = Path(__file__).resolve().parents[1] / "live-01" / "trace.jsonl"


@pytest.fixture(scope="module", params=("c01", "c06"))
def captured_request(request: pytest.FixtureRequest) -> dict[str, Any]:
    with TRACE.open(encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if (
                row["event"] == "request"
                and row.get("path") == "/v1/responses"
                and row.get("arm") == "memory"
                and row.get("case_id") == request.param
            ):
                return row["payload"]
    raise AssertionError(f"Missing original request: {request.param}")


def test_navigation_changes_only_two_map_descriptions(captured_request):
    original = deepcopy(captured_request)
    candidate = navigation_candidate(captured_request)
    assert set(candidate) == set(original)
    assert {key for key in original if original[key] != candidate[key]} == {"tools"}
    assert len(candidate["tools"]) == len(original["tools"])
    changed = set()
    for before, after in zip(original["tools"], candidate["tools"], strict=True):
        assert set(before) == set(after)
        if before != after:
            assert {key for key in before if before[key] != after[key]} == {
                "description"
            }
            changed.add(before["name"])
    assert changed == {"read_work_understanding_map", "read_work_situation_map"}
    assert captured_request == original
    candidate["input"].clear()
    assert captured_request == original


def test_precision_replaces_one_clause_without_changing_other_instructions(
    captured_request,
):
    original = deepcopy(captured_request)
    candidate = precision_candidate(captured_request)
    assert set(candidate) == set(original)
    assert {key for key in original if original[key] != candidate[key]} == {
        "instructions"
    }
    prefix, suffix = original["instructions"].split(
        "回答一個細節時，保留解讀該細節所需的限定；"
    )
    assert candidate["instructions"].startswith(prefix)
    assert candidate["instructions"].endswith(suffix)
    assert captured_request == original
    candidate["input"].clear()
    assert captured_request == original


@pytest.mark.parametrize("mode", ("missing", "duplicate"))
def test_navigation_rejects_ambiguous_tool_selection(captured_request, mode):
    altered = deepcopy(captured_request)
    tools = altered["tools"]
    target = next(
        tool for tool in tools if tool["name"] == "read_work_understanding_map"
    )
    if mode == "missing":
        tools.remove(target)
    else:
        tools.append(deepcopy(target))
    with pytest.raises(ValueError, match="baseline"):
        navigation_candidate(altered)


@pytest.mark.parametrize("mode", ("missing", "duplicate"))
def test_precision_rejects_ambiguous_prompt_baseline(captured_request, mode):
    altered = deepcopy(captured_request)
    if mode == "missing":
        altered["instructions"] = "Different baseline"
    else:
        altered["instructions"] *= 2
    with pytest.raises(ValueError, match="baseline"):
        precision_candidate(altered)


@pytest.mark.parametrize("build", (navigation_candidate, precision_candidate))
def test_candidate_cannot_silently_become_its_own_control(captured_request, build):
    candidate = build(captured_request)
    with pytest.raises(ValueError, match="baseline"):
        build(candidate)
