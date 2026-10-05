"""Protect source isolation and capacity claims, not the wording of human prose."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from preparation import (
    describe_capacity,
    employee_input,
    load_scenario,
    measure_requests,
    preflight_requests,
    validate_grading_sources,
)

HERE = Path(__file__).resolve().parent


@pytest.fixture
def scenario():
    return {
        "opening": "請介紹工作。",
        "events": [
            {"event_id": "e001", "topic": "private_topic", "employee_text": "  原句\n保留。"},
            {"event_id": "e002", "topic": "correction", "employee_text": "週一改08:50。"},
        ],
        "research_answer": "DO_NOT_SEND_THIS_GOLD_ANSWER",
    }


def test_current_input_keeps_original_text_without_research_metadata(scenario):
    requests = preflight_requests(scenario)
    for request in requests.values():
        # The counterfactual is a count-only reference bundle, not a current-input request.
        if request is requests["raw_preload_counterfactual"]:
            continue
        payload = request.create_payload()
        assert payload["input"][-1] == {"role": "user", "content": "  原句\n保留。"}
        assert "DO_NOT_SEND_THIS_GOLD_ANSWER" not in str(payload)
        assert "private_topic" not in str(payload)
        assert "interview_sequence" not in str(payload["input"][-1])


def test_raw_and_recent_groups_do_not_gain_memory_tools(scenario):
    requests = preflight_requests(scenario)
    hierarchical = requests["compaction_hierarchical_memory"].count_payload()
    raw = requests["compaction_raw_history"].count_payload()
    recent = requests["compaction_recent_history"].count_payload()
    assert "read_work_situation" in {tool["name"] for tool in hierarchical["tools"]}
    assert "read_interview" in {tool["name"] for tool in raw["tools"]}
    assert "read_work_situation" not in {tool["name"] for tool in raw["tools"]}
    assert "read_interview" not in {tool["name"] for tool in recent["tools"]}
    for payload in (hierarchical, raw, recent):
        assert {"read_jd", "revise_jd_profile", "request_context_compaction"} <= {
            tool["name"] for tool in payload["tools"]
        }
        assert "jd_map" not in str(payload["input"])
        assert payload["reasoning"] == {"context": "all_turns", "effort": "high"}


def test_raw_counterfactual_does_not_fabricate_formal_transcript(scenario):
    payload = preflight_requests(scenario)["raw_preload_counterfactual"].count_payload()
    bundle = json.loads(payload["input"][0]["content"])
    assert bundle["employee_messages"] == ["  原句\n保留。", "週一改08:50。"]
    assert "research_answer" not in str(payload)
    assert "interview_sequence" not in str(payload["input"])
    assert "role': 'assistant'" not in str(payload["input"])


def test_unknown_event_is_rejected_instead_of_using_another_input(scenario):
    with pytest.raises(ValueError, match="Unknown employee event"):
        employee_input(scenario, "e999")


def test_future_source_is_rejected_for_an_earlier_observation(scenario):
    grading = {
        "cases": [
            {"case_id": "one", "observe_after_event_id": "e001", "source_event_ids": ["e002"]}
        ]
    }
    with pytest.raises(ValueError, match="future"):
        validate_grading_sources(scenario, grading)


def test_capacity_distinguishes_policy_threshold_from_hard_limit():
    result = describe_capacity(160_000, 16_384)
    assert result["fits_model"] is True
    assert result["pre_turn_threshold_reached"] is True
    assert result["complete_step_threshold_reached"] is True
    assert result["allowed_input_tokens"] == 922_000
    assert describe_capacity(922_001, 16_384)["fits_model"] is False
    assert describe_capacity(None, 16_384)["fits_model"] is None


@pytest.mark.parametrize("invalid_count", [-1, True])
def test_invalid_counts_cannot_be_claimed_as_valid_capacity(invalid_count):
    with pytest.raises(ValueError):
        describe_capacity(invalid_count, 16_384)


def test_real_corpus_sources_exist_and_do_not_point_to_future_answers():
    scenario = load_scenario(HERE / "employee-scenario.json")
    grading = json.loads((HERE / "grading-cases.json").read_text(encoding="utf-8"))
    validate_grading_sources(scenario, grading)
    assert len({event["event_id"] for event in scenario["events"]}) == 61
    damaged = deepcopy(grading)
    damaged["cases"][0]["source_event_ids"].append("e999")
    with pytest.raises(ValueError, match="Unknown"):
        validate_grading_sources(scenario, damaged)


@pytest.mark.asyncio
async def test_count_failure_stops_without_guessing_or_counting_remaining_inputs(scenario):
    requests = preflight_requests(scenario)
    calls = []

    async def count(request):
        calls.append(request)
        if len(calls) == 2:
            raise TimeoutError("external count unavailable")
        return 7000

    results = await measure_requests(requests, count)
    assert len(calls) == 2
    assert results[0]["input_tokens"] == 7000
    assert results[1]["input_tokens"] is None
    assert results[1]["capacity"]["fits_model"] is None
    assert results[1]["status"] == "count_failed"
    assert results[1]["error_type"] == "TimeoutError"


@pytest.mark.asyncio
async def test_count_limit_is_checked_before_any_network_side_effect(scenario):
    requests = preflight_requests(scenario)
    requests["unplanned_sixth_request"] = requests["raw_preload_counterfactual"]
    calls = []

    async def count(request):
        calls.append(request)
        return 10

    with pytest.raises(ValueError, match="five"):
        await measure_requests(requests, count)
    assert calls == []


@pytest.mark.asyncio
async def test_successful_counts_keep_per_request_capacity_and_output_reserve(scenario):
    async def count(request):
        return 128_000

    results = await measure_requests(preflight_requests(scenario), count)
    assert len(results) == 5
    assert all(result["status"] == "counted" for result in results)
    assert all(result["capacity"]["fits_model"] is True for result in results)
    assert all(result["capacity"]["output_reserve_tokens"] == 16_384 for result in results)


@pytest.mark.asyncio
async def test_malformed_external_count_does_not_become_success(scenario):
    async def count(request):
        return True

    results = await measure_requests(preflight_requests(scenario), count)
    assert len(results) == 1
    assert results[0]["status"] == "count_failed"
    assert results[0]["input_tokens"] is None
