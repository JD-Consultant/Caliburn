"""Study boundaries: no treatment leakage and no unadmitted paid sends."""

import json
from decimal import Decimal

import pytest
from caliburn.adapters.openai_responses import ResponseRequest, compaction_payload
from main_support import StudyAllowance, StudyStop, project_request, selected_tools
from preparation import preflight_requests


def request_payload():
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="work analysis",
        tools=[],
        reasoning_effort="high",
        max_output_tokens=16_384,
        input_items=[
            {"type": "reasoning", "encrypted_content": "opaque"},
            {"role": "assistant", "phase": "commentary", "content": "先查看"},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "data_kind": "consultant_turn_reference",
                        "work_situation_map": {"items": [{"target_title": "情境"}]},
                        "work_understanding_map": {"items": [{"target_title": "理解"}]},
                        "historical_interview": {
                            "data_kind": "historical_interview",
                            "messages": [
                                {"interview_sequence": 1, "speaker": "app", "text": "請說明"},
                                {"interview_sequence": 2, "speaker": "employee", "text": "之前"},
                                {
                                    "interview_sequence": 3,
                                    "speaker": "consultant",
                                    "text": "請補充",
                                },
                                {"interview_sequence": 4, "speaker": "employee", "text": "剛才"},
                                {"interview_sequence": 5, "speaker": "consultant", "text": "現在?"},
                            ],
                        },
                        "interview_read_boundary": {
                            "covered_through_sequence": 0,
                            "through_sequence": 5,
                            "context_sequences": [],
                        },
                    },
                    ensure_ascii=False,
                ),
            },
            {"role": "user", "content": "原話，不改寫。"},
        ],
    ).create_payload()


@pytest.mark.parametrize("arm", ["compaction_raw_history", "compaction_recent_history"])
def test_non_memory_arm_keeps_native_items_but_removes_maps(arm):
    original = request_payload()
    projected = project_request(original, arm=arm, covered=2, summary="not for this arm")
    assert projected["input"][:2] == original["input"][:2]
    assert projected["input"][-1] == {"role": "user", "content": "原話，不改寫。"}
    app = json.loads(projected["input"][-2]["content"])
    assert "work_situation_map" not in app
    assert "work_understanding_map" not in app
    assert "work_summary" not in app
    assert [m["interview_sequence"] for m in app["historical_interview"]["messages"]] == [3, 4, 5]
    assert (
        json.loads(original["input"][-2]["content"])["interview_read_boundary"][
            "covered_through_sequence"
        ]
        == 0
    )


def test_flat_summary_is_user_data_not_an_extra_employee_or_instruction():
    projected = project_request(
        request_payload(), arm="compaction_flat_summary", covered=4, summary="摘要: 08:35，來源2"
    )
    assert len(projected["input"]) == 4
    assert projected["instructions"] == "work analysis"
    assert projected["input"][-2]["role"] == "user"
    app = json.loads(projected["input"][-2]["content"])
    assert app["work_summary"] == "摘要: 08:35，來源2"
    assert [m["interview_sequence"] for m in app["historical_interview"]["messages"]] == [5]


def test_projection_does_not_hide_an_employee_answer_without_its_question():
    projected = project_request(
        request_payload(), arm="compaction_raw_history", covered=3, summary=""
    )
    app = json.loads(projected["input"][-2]["content"])
    assert [m["interview_sequence"] for m in app["historical_interview"]["messages"]] == [3, 4, 5]
    assert app["interview_read_boundary"]["context_sequences"] == [3]


def test_recent_arm_cannot_advertise_old_history_or_memory_tools():
    tools = preflight_requests(
        {"opening": "說明工作", "events": [{"event_id": "e1", "employee_text": "資料"}]}
    )["compaction_hierarchical_memory"].count_payload()["tools"]
    names = {item["name"] for item in selected_tools(tools, "compaction_recent_history")}
    assert "read_interview" not in names
    assert "read_work_situation" not in names
    assert "read_work_understanding" not in names
    assert "read_jd" in names
    assert "create_jd_task" in names


def test_generation_without_matching_exact_count_is_not_admitted():
    allowance = StudyAllowance()
    with pytest.raises(StudyStop, match="missing_count"):
        allowance.admit("/v1/responses", request_payload())
    assert allowance.outbound_calls == 0


def test_compaction_is_bounded_and_requires_count_of_its_own_window():
    allowance = StudyAllowance(max_compactions=1)
    request = ResponseRequest.from_snapshot(request_payload())
    allowance.record_count(request.count_payload(), 180_000)
    compact = compaction_payload(model="gpt-6-luna", input_items=request.create_payload()["input"])
    allowance.admit("/v1/responses/compact", compact)
    with pytest.raises(StudyStop, match="compaction_limit"):
        allowance.admit("/v1/responses/compact", compact)
    different = {**compact, "input": [{"role": "user", "content": "different"}]}
    with pytest.raises(StudyStop, match="missing_count"):
        StudyAllowance().admit("/v1/responses/compact", different)


def test_settlement_does_not_release_unknown_spend_and_known_spend_is_counted():
    allowance = StudyAllowance(max_estimated_usd=Decimal("0.02"))
    request = ResponseRequest.from_snapshot(request_payload())
    allowance.record_count(request.count_payload(), 1000)
    payload = request.create_payload()
    allowance.admit("/v1/responses", payload)
    before = allowance.occupied_usd
    with pytest.raises(StudyStop, match="unknown_usage"):
        allowance.settle("/v1/responses", payload, None)
    assert allowance.occupied_usd == before
    allowance.settle("/v1/responses", payload, Decimal("0.001"))
    assert allowance.occupied_usd == Decimal("0.001")
    allowance.admit("/v1/responses", payload)
    assert allowance.occupied_usd > Decimal("0.001")


def test_mid_step_130k_is_not_rejected_as_a_before_work_threshold():
    allowance = StudyAllowance()
    request = ResponseRequest.from_snapshot(request_payload())
    allowance.record_count(request.count_payload(), 130_000)
    allowance.admit("/v1/responses", request.create_payload())
    assert allowance.generation_calls == 1
