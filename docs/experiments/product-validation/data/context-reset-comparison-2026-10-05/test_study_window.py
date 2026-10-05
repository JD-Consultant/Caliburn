"""Raw retention depends on whole-message boundaries, never on the grading cases."""

import asyncio
import json

import pytest
from caliburn.adapters.openai_responses import ResponseRequest
from study_window import fit_raw_reset


def request():
    messages = [
        {"interview_sequence": i, "speaker": "consultant" if i % 2 else "employee", "text": str(i)}
        for i in range(1, 106)
    ]
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="共同指引",
        tools=[],
        reasoning_effort="high",
        max_output_tokens=16384,
        input_items=[
            {
                "role": "user",
                "content": json.dumps({"historical_interview": {"messages": messages}}),
            },
            {"role": "user", "content": "當次輸入"},
        ],
    )


@pytest.mark.parametrize("minimum_start", [1, 5, 101])
def test_keeps_maximum_complete_units_that_fit(minimum_start):
    original = request()
    counted = []

    async def count(candidate, request_id):
        messages = json.loads(candidate.create_payload()["input"][0]["content"])[
            "historical_interview"
        ]["messages"]
        first = messages[0]["interview_sequence"]
        counted.append(first)
        return {"input_tokens": 128000 if first >= minimum_start else 128001}

    fitted = asyncio.run(fit_raw_reset(original, count))
    payload = fitted.create_payload()
    messages = json.loads(payload["input"][0]["content"])["historical_interview"]["messages"]
    assert [m["interview_sequence"] for m in messages] == list(range(minimum_start, 106))
    assert counted == list(range(1, minimum_start + 1, 2))
    assert payload["input"][-1] == original.create_payload()["input"][-1]
    assert (
        json.loads(original.create_payload()["input"][0]["content"])["historical_interview"][
            "messages"
        ][0]["interview_sequence"]
        == 1
    )


def test_does_not_trim_common_recent_tail_or_fall_back_to_compaction():
    async def count(candidate, request_id):
        return {"input_tokens": 128001}

    with pytest.raises(ValueError, match="starting_request_exceeds_study_budget"):
        asyncio.run(fit_raw_reset(request(), count))
