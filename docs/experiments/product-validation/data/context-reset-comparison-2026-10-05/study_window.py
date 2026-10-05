"""Initial raw-history selection; the retained common recent tail is never trimmed."""

import json
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.request_capacity import ReceivedInputCount


class StudyCapacityError(ValueError):
    """The study cannot admit this request without another unapproved reset."""


async def fit_raw_reset(
    request: ResponseRequest,
    count_input: Callable[[ResponseRequest, UUID], Awaitable[ReceivedInputCount]],
) -> ResponseRequest:
    payload = request.create_payload()
    if len(payload["input"]) != 2:
        raise ValueError("Raw selection is only allowed at the empty-history reset")
    reference = json.loads(payload["input"][0]["content"])
    messages = reference["historical_interview"]["messages"]
    if [m["interview_sequence"] for m in messages] != list(range(1, 106)):
        raise ValueError("Raw selection requires the frozen complete prefix")
    # Try the full prefix first; only remove complete oldest units. No tokenizer
    # monotonicity assumption or grading-dependent choice is needed (at most 51 counts).
    starts = [0] + [
        i
        for i in range(1, len(messages) - 1)
        if messages[i]["interview_sequence"] <= 101
        and messages[i]["speaker"] == "consultant"
        and messages[i + 1]["speaker"] == "employee"
    ]
    for start in starts:
        reference["historical_interview"]["messages"] = messages[start:]
        payload["input"][0]["content"] = json.dumps(reference, ensure_ascii=False)
        candidate = ResponseRequest.from_snapshot(payload)
        count = await count_input(candidate, uuid4())
        if count["input_tokens"] <= 128_000:
            return candidate
    raise StudyCapacityError("starting_request_exceeds_study_budget")
