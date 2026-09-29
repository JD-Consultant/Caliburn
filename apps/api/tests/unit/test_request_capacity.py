"""The exact request must have a saved count and fit before generation is admitted."""

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses import Response

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponse,
    ResponseStepRuntime,
    run_response_loop,
)


def request_fixture() -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic fixed instructions",
        input_items=[{"role": "user", "content": "synthetic pinned map"}],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )


class CapacityProbe:
    def __init__(self, counts: list[int], *, final: bool = True) -> None:
        self.counts = counts
        self.count_requests = []
        self.model_requests = []
        self.fail_model = False
        self.final = final

    async def count(self, request, request_id):
        self.count_requests.append((request_id, request.count_payload()))
        return {
            "input_tokens": self.counts[len(self.count_requests) - 1],
            "attempt_id": uuid4(),
        }

    async def model(self, request, request_id):
        if self.fail_model:
            raise ConnectionError("synthetic before generation admission")
        self.model_requests.append(request.create_payload())
        payload = json.loads(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text("utf-8")
        )
        payload["output"] = payload["output"][:2]
        payload["output"][1]["phase"] = (
            "final_answer" if self.final or len(self.model_requests) > 1 else "commentary"
        )
        return ReceivedModelResponse(Response.model_validate(payload), uuid4())

    async def guard(self):
        pass

    async def account(self, response):
        pass

    async def tool(self, *args):
        pytest.fail("This capacity fixture has no tools")

    def runtime(self, **limits):
        return ResponseStepRuntime(
            request_model=self.model,
            prepare_tool=self.tool,
            execute_tool=self.tool,
            ensure_active=self.guard,
            account_response=self.account,
            count_input=self.count,
            capacity_limits={
                "model": "gpt-6-luna",
                "max_input_tokens": 900_000,
                "context_window_tokens": 1_000_000,
                "max_output_tokens": 100_000,
                **limits,
            },
        )


@pytest.mark.parametrize(
    "input_tokens,limits",
    [(901, {"max_input_tokens": 900}), (489, {"context_window_tokens": 1000})],
)
async def test_capacity_excess_never_generates_or_recounts_on_resume(input_tokens, limits):
    probe = CapacityProbe([input_tokens])
    saver = InMemorySaver()
    options = dict(
        thread_id="over-capacity",
        runtime=probe.runtime(**limits),
        max_tool_calls=2,
        max_model_steps=2,
    )
    for request in (request_fixture(), None):
        with pytest.raises(ValueError, match="capacity"):
            await run_response_loop(saver, request=request, **options)
    assert not probe.model_requests
    assert len(probe.count_requests) == 1


async def test_saved_count_survives_next_node_failure_and_matches_exact_request():
    probe = CapacityProbe([488])
    probe.fail_model = True
    saver = InMemorySaver()
    options = dict(
        thread_id="saved-count",
        runtime=probe.runtime(context_window_tokens=1000),
        max_tool_calls=2,
        max_model_steps=2,
    )
    with pytest.raises(ConnectionError):
        await run_response_loop(saver, request=request_fixture(), **options)
    probe.fail_model = False
    result = await run_response_loop(saver, request=None, **options)
    assert len(probe.count_requests) == len(probe.model_requests) == 1
    assert result["input_count"]["input_tokens"] == 488
    assert probe.count_requests[0][1] == request_fixture().count_payload()
    assert probe.model_requests == [request_fixture().create_payload()]


async def test_capacity_policy_cannot_be_relaxed_during_resume():
    probe = CapacityProbe([489])
    saver = InMemorySaver()
    runtime = probe.runtime(context_window_tokens=1000)
    options = dict(thread_id="fixed-policy", max_tool_calls=2, max_model_steps=2)
    with pytest.raises(ValueError, match="capacity"):
        await run_response_loop(saver, request=request_fixture(), runtime=runtime, **options)
    changed = replace(
        runtime, capacity_limits={**runtime.capacity_limits, "context_window_tokens": 2000}
    )
    with pytest.raises(ValueError, match="original capacity limits"):
        await run_response_loop(saver, request=None, runtime=changed, **options)
    assert len(probe.count_requests) == 1
    assert not probe.model_requests


@pytest.mark.parametrize("count", [-1, True, "10"])
async def test_invalid_remote_count_never_turns_into_zero_or_generation(count):
    probe = CapacityProbe([count])
    with pytest.raises(ValueError, match="capacity"):
        await run_response_loop(
            InMemorySaver(),
            thread_id="bad-count",
            request=request_fixture(),
            runtime=probe.runtime(),
            max_tool_calls=2,
            max_model_steps=2,
        )
    assert not probe.model_requests


@pytest.mark.parametrize("limits", [{"model": "different-model"}, {"max_output_tokens": 511}])
async def test_known_invalid_request_is_rejected_before_paid_counting(limits):
    probe = CapacityProbe([10])
    with pytest.raises(ValueError, match="capacity"):
        await run_response_loop(
            InMemorySaver(),
            thread_id="bad-config",
            request=request_fixture(),
            runtime=probe.runtime(**limits),
            max_tool_calls=2,
            max_model_steps=2,
        )
    assert not probe.count_requests
    assert not probe.model_requests


async def test_count_failure_has_no_estimate_fallback():
    probe = CapacityProbe([])

    async def fail_count(*args):
        raise ConnectionError("synthetic counting unavailable")

    runtime = replace(probe.runtime(), count_input=fail_count)
    with pytest.raises(ConnectionError, match="counting unavailable"):
        await run_response_loop(
            InMemorySaver(),
            thread_id="count-error",
            request=request_fixture(),
            runtime=runtime,
            max_tool_calls=2,
            max_model_steps=2,
        )
    assert not probe.model_requests


async def test_middle_threshold_stops_before_second_generation_without_rewriting_history():
    probe = CapacityProbe([10, 272_000], final=False)
    saver = InMemorySaver()
    options = dict(thread_id="middle", runtime=probe.runtime(), max_tool_calls=2, max_model_steps=3)
    with pytest.raises(ValueError, match="compaction"):
        await run_response_loop(saver, request=request_fixture(), **options)
    assert len(probe.model_requests) == 1
    assert len(probe.count_requests) == 2
    assert probe.count_requests[1][1]["input"][0] == request_fixture().count_payload()["input"][0]
    assert [item["type"] for item in probe.count_requests[1][1]["input"][1:]] == [
        "reasoning",
        "message",
    ]


async def test_first_request_above_middle_threshold_is_not_an_automatic_compaction():
    probe = CapacityProbe([300_000])
    result = await run_response_loop(
        InMemorySaver(),
        thread_id="first",
        request=request_fixture(),
        runtime=probe.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
    )
    assert result["next_action"] == "deliver_answer"
    assert len(probe.count_requests) == len(probe.model_requests) == 1


async def test_below_middle_threshold_continues_and_final_needs_no_more_count():
    probe = CapacityProbe([10, 271_999], final=False)
    result = await run_response_loop(
        InMemorySaver(),
        thread_id="below-middle",
        request=request_fixture(),
        runtime=probe.runtime(),
        max_tool_calls=2,
        max_model_steps=2,
    )
    assert result["completed_steps"] == 2
    assert result["next_action"] == "deliver_answer"
    assert len(probe.count_requests) == len(probe.model_requests) == 2
    assert probe.count_requests[0][0] != probe.count_requests[1][0]
