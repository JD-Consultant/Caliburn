"""The exact request must have a saved count and fit before generation is admitted."""

from dataclasses import replace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.agent_execution.request_capacity import RequestCapacityError, RequestOverflow
from caliburn.agent_execution.tool_steps import (
    run_response_loop,
)
from tests.fixtures.response_capacity import CapacityProbe, request_fixture


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
    assert probe.model_input_tokens == [488]
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
    probe = CapacityProbe([10, 160_000], final=False)
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
    probe = CapacityProbe([10, 159_999], final=False)
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
    assert probe.model_input_tokens == [10, 159_999]


def reduced(text: str = "reduced") -> list[dict]:
    return [{"role": "user", "content": text}]


class FitProbe:
    """Records what the data owner is asked to shrink; returns a fixed smaller input."""

    def __init__(self) -> None:
        self.overflows: list[RequestOverflow] = []

    def fit(self, request, overflow: RequestOverflow):
        self.overflows.append(overflow)
        return reduced(f"reduced {overflow.attempt}")


def loop_options(probe: CapacityProbe, fit, *, thread_id: str, max_steps: int = 2) -> dict:
    return dict(
        thread_id=thread_id,
        runtime=replace(probe.runtime(), fit_first_request=fit),
        max_tool_calls=2,
        max_model_steps=max_steps,
    )


async def test_first_request_over_capacity_is_recounted_after_the_owner_shrinks_it():
    probe = CapacityProbe([950_000, 500])
    fits = FitProbe()
    result = await run_response_loop(
        InMemorySaver(),
        request=request_fixture(),
        **loop_options(probe, fits.fit, thread_id="fit-first"),
    )
    assert fits.overflows == [RequestOverflow(950_000, 900_000, 1)]
    assert [payload["input"] for _, payload in probe.count_requests] == [
        request_fixture().count_payload()["input"],
        reduced("reduced 1"),
    ]
    assert probe.count_requests[0][0] != probe.count_requests[1][0]
    assert [payload["input"] for payload in probe.model_requests] == [reduced("reduced 1")]
    assert probe.model_input_tokens == [500]
    assert result["input_items"][0] == reduced("reduced 1")[0]
    assert result["next_action"] == "deliver_answer"


async def test_owner_is_asked_again_with_the_next_attempt_until_the_request_fits():
    probe = CapacityProbe([950_000, 940_000, 500])
    fits = FitProbe()
    await run_response_loop(
        InMemorySaver(),
        request=request_fixture(),
        **loop_options(probe, fits.fit, thread_id="fit-twice"),
    )
    assert [overflow.attempt for overflow in fits.overflows] == [1, 2]
    assert [overflow.input_tokens for overflow in fits.overflows] == [950_000, 940_000]
    assert [payload["input"] for payload in probe.model_requests] == [reduced("reduced 2")]
    assert len(probe.count_requests) == 3


async def test_first_request_fit_is_bounded_and_never_generates_while_still_over():
    probe = CapacityProbe([950_000] * 10)
    fits = FitProbe()
    saver = InMemorySaver()
    options = loop_options(probe, fits.fit, thread_id="fit-bounded")
    with pytest.raises(ValueError, match="capacity"):
        await run_response_loop(saver, request=request_fixture(), **options)
    assert [overflow.attempt for overflow in fits.overflows] == [1, 2, 3]
    assert len(probe.count_requests) == 4
    assert not probe.model_requests
    with pytest.raises(ValueError, match="capacity"):
        await run_response_loop(saver, request=None, **options)
    assert len(fits.overflows) == 3
    assert len(probe.count_requests) == 4
    assert not probe.model_requests


async def test_fitted_request_is_saved_before_recounting_and_resume_does_not_fit_again():
    probe = CapacityProbe([950_000, 500])
    fits = FitProbe()
    saver = InMemorySaver()
    options = loop_options(probe, fits.fit, thread_id="fit-resume")
    count_outage = [True]
    counted = options["runtime"].count_input

    async def flaky_count(request, request_id):
        if len(probe.count_requests) == 1 and count_outage[0]:
            count_outage[0] = False
            raise ConnectionError("synthetic count outage after the first count")
        return await counted(request, request_id)

    options["runtime"] = replace(options["runtime"], count_input=flaky_count)
    with pytest.raises(ConnectionError, match="count outage"):
        await run_response_loop(saver, request=request_fixture(), **options)
    assert len(fits.overflows) == 1
    assert not probe.model_requests
    await run_response_loop(saver, request=None, **options)
    assert len(fits.overflows) == 1
    assert [payload["input"] for _, payload in probe.count_requests] == [
        request_fixture().count_payload()["input"],
        reduced("reduced 1"),
    ]
    assert [payload["input"] for payload in probe.model_requests] == [reduced("reduced 1")]


async def test_overflow_after_a_completed_step_is_not_a_first_request_fit():
    probe = CapacityProbe([10, 950_000], final=False)
    fits = FitProbe()
    with pytest.raises(ValueError, match="capacity"):
        await run_response_loop(
            InMemorySaver(),
            request=request_fixture(),
            **loop_options(probe, fits.fit, thread_id="fit-middle", max_steps=3),
        )
    assert not fits.overflows
    assert len(probe.model_requests) == 1


async def test_owner_that_has_nothing_smaller_blocks_the_work_without_generation():
    probe = CapacityProbe([950_000])

    def nothing_smaller(request, overflow):
        raise RequestCapacityError("no smaller legal preload")

    with pytest.raises(RequestCapacityError, match="no smaller"):
        await run_response_loop(
            InMemorySaver(),
            request=request_fixture(),
            **loop_options(probe, nothing_smaller, thread_id="fit-refused"),
        )
    assert len(probe.count_requests) == 1
    assert not probe.model_requests


async def test_within_capacity_first_request_never_consults_the_owner():
    probe = CapacityProbe([899_999])
    fits = FitProbe()
    await run_response_loop(
        InMemorySaver(),
        request=request_fixture(),
        **loop_options(probe, fits.fit, thread_id="fit-unused"),
    )
    assert not fits.overflows
    assert len(probe.count_requests) == 1
