"""An oversized recent-interview preload keeps whole newest messages and names what is left out."""

import json
from copy import deepcopy
from typing import Any

import pytest

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.request_capacity import RequestCapacityError, RequestOverflow
from caliburn.agents.job_consultant.recent_preload import fit_recent_interview_preload

HISTORY = [{"role": "user", "content": "先前輪次的原生歷史"}]
CURRENT_INPUT = {"role": "user", "content": "本輪員工原話：另一個也一樣。"}


def interview(
    first: int, last: int, *, size: int = 1_000, sizes: dict[int, int] | None = None
) -> list[dict[str, Any]]:
    """Sequence 1 is the App opening; then an employee answers on even sequences."""
    return [
        {
            "interview_sequence": sequence,
            "speaker": "app"
            if sequence == 1
            else "employee"
            if sequence % 2 == 0
            else "consultant",
            "text": f"第{sequence}則" + "訪" * (sizes or {}).get(sequence, size),
        }
        for sequence in range(first, last + 1)
    ]


def preload_request(
    messages: list[dict[str, Any]],
    *,
    covered: int = 0,
    context_sequences: tuple[int, ...] = (),
) -> ResponseRequest:
    app_data = {
        "data_kind": "consultant_turn_reference",
        "work_situation_map": {"items": []},
        "work_understanding_map": {"items": []},
        "historical_interview": {"data_kind": "historical_interview", "messages": messages},
        "interview_read_boundary": {
            "covered_through_sequence": covered,
            "through_sequence": messages[-1]["interview_sequence"],
            "context_sequences": list(context_sequences),
        },
    }
    return request_with(
        [
            *HISTORY,
            {"role": "user", "content": json.dumps(app_data, ensure_ascii=False)},
            CURRENT_INPUT,
        ]
    )


def request_with(input_items: list[dict[str, Any]]) -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic role",
        input_items=input_items,
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )


def request_chars(request: ResponseRequest) -> int:
    return len(json.dumps(request.count_payload(), ensure_ascii=False))


def overflow_for(
    request: ResponseRequest, *, allowed_share: float, attempt: int = 1
) -> RequestOverflow:
    """Two counted tokens per character; the limit is the given share of the counted size."""
    counted = request_chars(request) * 2
    return RequestOverflow(counted, int(counted * allowed_share), attempt)


def fitted_app_data(items: list[dict[str, Any]]) -> dict[str, Any]:
    return json.loads(items[-2]["content"])


def kept_sequences(items: list[dict[str, Any]]) -> list[int]:
    messages = fitted_app_data(items)["historical_interview"]["messages"]
    return [message["interview_sequence"] for message in messages]


def test_the_question_an_employee_answer_replies_to_is_kept_with_it() -> None:
    # Sequences 10-13 fit; the consultant question 9 does not, but 10 is an answer to it.
    messages = interview(1, 13, size=2_000, sizes={9: 20_000, 10: 300, 11: 300, 12: 300, 13: 300})
    request = preload_request(messages)
    items = fit_recent_interview_preload(request, overflow_for(request, allowed_share=0.18))
    assert kept_sequences(items) == [9, 10, 11, 12, 13]
    assert fitted_app_data(items)["historical_interview"]["messages"] == messages[8:]


def test_declares_the_range_that_is_not_preloaded() -> None:
    request = preload_request(interview(1, 13))
    items = fit_recent_interview_preload(request, overflow_for(request, allowed_share=0.4))
    first_kept = kept_sequences(items)[0]
    boundary = fitted_app_data(items)["interview_read_boundary"]
    assert first_kept > 1
    assert boundary["covered_through_sequence"] == 0
    assert boundary["through_sequence"] == 13
    assert boundary["not_preloaded"] == [{"from_sequence": 1, "through_sequence": first_kept - 1}]
    assert boundary["preloaded"] == {"from_sequence": first_kept, "through_sequence": 13}


def test_covered_messages_are_not_reported_as_unread_recent_interviews() -> None:
    # Memory covers through 7; message 7 only rides along as the question before 8.
    request = preload_request(interview(7, 13), covered=7, context_sequences=(7,))
    items = fit_recent_interview_preload(request, overflow_for(request, allowed_share=0.5))
    boundary = fitted_app_data(items)["interview_read_boundary"]
    first_kept = kept_sequences(items)[0]
    assert first_kept > 8
    assert boundary["covered_through_sequence"] == 7
    assert boundary["not_preloaded"] == [{"from_sequence": 8, "through_sequence": first_kept - 1}]
    assert boundary["context_sequences"] == []


@pytest.mark.parametrize("allowed_share", [0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 0.99])
def test_reduction_is_a_whole_message_suffix_that_is_estimated_to_fit(
    allowed_share: float,
) -> None:
    messages = interview(1, 13)
    request = preload_request(messages)
    overflow = overflow_for(request, allowed_share=allowed_share)
    items = fit_recent_interview_preload(request, overflow)
    sequences = kept_sequences(items)
    kept = fitted_app_data(items)["historical_interview"]["messages"]
    assert sequences == list(range(sequences[0], 14))
    assert len(sequences) < len(messages)
    assert kept == [message for message in messages if message["interview_sequence"] in sequences]
    assert kept[0]["speaker"] != "employee"
    estimated_tokens = (
        overflow.input_tokens * request_chars(request_with(items)) / request_chars(request)
    )
    assert estimated_tokens <= overflow.allowed_input_tokens


def test_a_reduction_that_would_keep_everything_drops_the_opening_instead() -> None:
    # Only the large opening exceeds the budget, but 2 is an answer that would pull it back.
    request = preload_request(interview(1, 13, sizes={1: 5_000}))
    items = fit_recent_interview_preload(request, overflow_for(request, allowed_share=0.95))
    assert kept_sequences(items) == list(range(3, 14))


def test_later_attempts_keep_strictly_less() -> None:
    request = preload_request(interview(1, 13))
    kept = [
        kept_sequences(
            fit_recent_interview_preload(
                request, overflow_for(request, allowed_share=0.9, attempt=attempt)
            )
        )
        for attempt in (1, 2, 3)
    ]
    assert len(kept[0]) > len(kept[1]) > len(kept[2])
    assert kept[2][-1] == 13


def test_never_drops_the_newest_message_even_when_nothing_else_can_fit() -> None:
    request = preload_request(interview(1, 13))
    items = fit_recent_interview_preload(request, overflow_for(request, allowed_share=0.01))
    assert kept_sequences(items) == [13]


def test_other_input_and_the_original_request_are_untouched() -> None:
    request = preload_request(interview(1, 13))
    before = deepcopy(request.create_payload())
    items = fit_recent_interview_preload(request, overflow_for(request, allowed_share=0.4))
    assert request.create_payload() == before
    assert items[:-2] == HISTORY
    assert items[-1] == CURRENT_INPUT
    data = fitted_app_data(items)
    original = json.loads(before["input"][-2]["content"])
    for key in ("data_kind", "work_situation_map", "work_understanding_map"):
        assert data[key] == original[key]
    assert data["historical_interview"]["data_kind"] == "historical_interview"


def test_the_same_reduction_is_produced_every_time() -> None:
    request = preload_request(interview(1, 13))
    overflow = overflow_for(request, allowed_share=0.4)
    assert fit_recent_interview_preload(request, overflow) == fit_recent_interview_preload(
        request, overflow
    )


def test_a_single_message_cannot_be_reduced_further() -> None:
    request = preload_request(interview(1, 1))
    with pytest.raises(RequestCapacityError, match="smaller"):
        fit_recent_interview_preload(request, overflow_for(request, allowed_share=0.4))


def test_an_already_minimal_preload_cannot_be_reduced_further() -> None:
    request = preload_request(interview(1, 13))
    minimal = request_with(
        fit_recent_interview_preload(request, overflow_for(request, allowed_share=0.01))
    )
    with pytest.raises(RequestCapacityError, match="smaller"):
        fit_recent_interview_preload(minimal, overflow_for(minimal, allowed_share=0.01))


def test_input_without_the_consultant_reference_data_is_not_guessed_at() -> None:
    request = request_with([{"role": "user", "content": "只是一般文字"}, CURRENT_INPUT])
    with pytest.raises(RequestCapacityError, match="preload"):
        fit_recent_interview_preload(request, RequestOverflow(2_000_000, 900_000, 1))
