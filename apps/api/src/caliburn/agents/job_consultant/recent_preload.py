"""Bound A's recent-interview preload when its counted first request exceeds capacity.

The full preload stays the normal path. Only when the exact count of the whole first
request is above the hard model limit does the loop ask for a smaller assembly: the newest
whole messages that are estimated to fit, plus the consultant question an employee answer
replies to. No message is cut, no other input is touched, and the omitted range is named
so A reads it with read_interview instead of assuming it was read or organized.
The result is a pure function of the saved request and count, so recovery repeats it.
"""

import json
from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import NativeItems
from caliburn.agent_execution.request_capacity import RequestCapacityError, RequestOverflow
from caliburn.agents.job_consultant.context_binding import REFERENCE_DATA_KIND
from caliburn.contracts.generated.tools.historical_interview import (
    HistoricalInterview,
    HistoricalInterviewMessage,
    Speaker,
)

# The count is exact but characters only estimate what a reduction saves, so aim well under
# the limit and let the next exact count decide. Later attempts halve the target again.
_TARGET_SHARE = 0.8


def fit_recent_interview_preload(
    request: ResponseRequest, overflow: RequestOverflow
) -> NativeItems:
    """Replace the App data message's messages with a whole-message newest suffix.

    Raises RequestCapacityError when the input is not A's reference data or no smaller legal
    preload exists; the caller then reports the work as capacity-blocked.
    """
    items = request.create_payload()["input"]
    data, historical = _read_reference_data(items)
    messages = historical.messages
    lengths = [_json_length(message) for message in messages]
    total_chars = len(json.dumps(request.count_payload(), ensure_ascii=False))
    tokens_per_char = overflow.input_tokens / total_chars
    target_tokens = overflow.allowed_input_tokens * _TARGET_SHARE * 0.5 ** (overflow.attempt - 1)
    budget_chars = int(target_tokens / tokens_per_char) - (total_chars - sum(lengths))
    index = _newest_suffix_start(lengths, budget_chars)
    start = _with_question(messages, index)
    while start == 0 and index < len(messages) - 1:
        # Keeping everything is no reduction; drop the oldest message instead.
        index += 1
        start = _with_question(messages, index)
    if start == 0:
        raise RequestCapacityError("No smaller legal recent-interview preload exists")
    kept = messages[start:]
    boundary = dict(data["interview_read_boundary"])
    kept_sequences = {message.interview_sequence for message in kept}
    unread = [
        message.interview_sequence
        for message in messages[:start]
        if message.interview_sequence > boundary["covered_through_sequence"]
    ]
    boundary["context_sequences"] = [
        sequence for sequence in boundary["context_sequences"] if sequence in kept_sequences
    ]
    boundary["preloaded"] = {
        "from_sequence": kept[0].interview_sequence,
        "through_sequence": kept[-1].interview_sequence,
    }
    boundary["not_preloaded"] = (
        [{"from_sequence": unread[0], "through_sequence": unread[-1]}] if unread else []
    )
    fitted = {
        **data,
        "historical_interview": HistoricalInterview(
            data_kind="historical_interview", messages=kept
        ).model_dump(mode="json"),
        "interview_read_boundary": boundary,
    }
    return [
        *deepcopy(items[:-2]),
        {**items[-2], "content": json.dumps(fitted, ensure_ascii=False)},
        deepcopy(items[-1]),
    ]


def _read_reference_data(items: NativeItems) -> tuple[dict[str, Any], HistoricalInterview]:
    """The App data message is second to last, before the current employee input."""
    try:
        data = json.loads(items[-2]["content"])
        if data["data_kind"] != REFERENCE_DATA_KIND:
            raise ValueError("not A's reference data")
        boundary = data["interview_read_boundary"]
        if type(boundary["covered_through_sequence"]) is not int or not isinstance(
            boundary["context_sequences"], list
        ):
            raise ValueError("malformed read boundary")
        return data, HistoricalInterview.model_validate(data["historical_interview"])
    except (IndexError, KeyError, TypeError, ValueError, ValidationError) as error:
        raise RequestCapacityError("The input has no recent-interview preload to reduce") from error


def _json_length(message: HistoricalInterviewMessage) -> int:
    return len(json.dumps(message.model_dump(mode="json"), ensure_ascii=False))


def _newest_suffix_start(lengths: list[int], budget_chars: int) -> int:
    """Index of the oldest message in the longest suffix within budget; the newest always stays."""
    index = len(lengths) - 1
    used = lengths[index]
    while index > 0 and used + lengths[index - 1] <= budget_chars:
        index -= 1
        used += lengths[index]
    return index


def _with_question(messages: list[HistoricalInterviewMessage], index: int) -> int:
    """An employee answer is unreadable without the guidance it replies to, however large."""
    if (
        index > 0
        and messages[index].speaker == Speaker.EMPLOYEE
        and messages[index - 1].speaker != Speaker.EMPLOYEE
    ):
        return index - 1
    return index
