"""已採用壓縮回覆的公開用量與模型回覆分開，跨快照及跨輪不重算。"""

from typing import Any, Literal, cast
from uuid import UUID

import pytest
from langgraph.types import StateSnapshot
from openai.types.responses import CompactedResponse, Response

from caliburn.modules.agent.application.turn_history import step_views, turn_view
from tests.unit.bundles.context.support import compacted_payload
from tests.unit.modules.agent.offline_openai import response_payload

TURN = UUID(int=101)
WORKSPACE = UUID(int=201)


def compacted(response_id: str) -> CompactedResponse:
    payload = {**compacted_payload(), "id": response_id}
    return CompactedResponse.model_construct(**cast(dict[str, Any], payload))


def model_response() -> Response:
    return Response.model_construct(**cast(dict[str, Any], response_payload()))


def snapshot(
    number: int,
    *,
    compaction: CompactedResponse | None = None,
    response: Response | None = None,
    turn_id: UUID = TURN,
    source: Literal["loop", "input"] = "loop",
) -> StateSnapshot:
    return StateSnapshot(
        values={
            "turn_id": turn_id,
            "turn_input": "合成輸入",
            "model_step": number,
            "compaction_response": compaction,
            "model_response": response,
        },
        next=(),
        config={"configurable": {"checkpoint_id": "synthetic"}},
        metadata={"source": source, "step": 1, "parents": {}},
        created_at="2026-11-06T00:00:00+00:00",
        parent_config=None,
        tasks=(),
        interrupts=(),
    )


def test_compactions_are_unique_and_belong_to_the_first_adopted_step() -> None:
    boundary, first, second = [compacted(name) for name in ("boundary", "one", "two")]
    first_response = model_response()
    second_response = first_response.model_copy(update={"id": "response_two"})
    history = list(
        reversed(
            [
                snapshot(0),
                snapshot(0, compaction=boundary),
                snapshot(1, compaction=boundary),
                snapshot(1, compaction=first),
                snapshot(1, compaction=first, response=first_response),
                snapshot(1, compaction=first, response=first_response),
                snapshot(2, compaction=first),
                snapshot(2, compaction=second),
                snapshot(2, compaction=second, response=second_response),
                snapshot(2, compaction=second, response=second_response),
            ]
        )
    )

    turn = turn_view(
        workspace_id=WORKSPACE,
        turn_id=TURN,
        history=history,
        current=history[0],
        running=False,
    ).model_dump()
    steps = [step.model_dump() for step in step_views(history, TURN)]

    assert [
        (item["response_id"], item["model_step"]) for item in turn["compactions"]
    ] == [
        ("boundary", 0),
        ("one", 1),
        ("two", 2),
    ]
    assert [
        [item["response_id"] for item in step["compactions"]] for step in steps
    ] == [
        ["one"],
        ["two"],
    ]
    assert turn["usage"] == {
        "input_tokens": 26,
        "output_tokens": 16,
        "total_tokens": 42,
    }
    assert [step["usage"]["total_tokens"] for step in steps] == [21, 21]
    assert [item["usage"]["total_tokens"] for item in turn["compactions"]] == [
        128020,
        128020,
        128020,
    ]
    assert all(
        set(item) == {"response_id", "model_step", "usage"}
        for item in turn["compactions"]
    )


@pytest.mark.parametrize("missing_usage", [False, True], ids=["null", "omitted"])
def test_unknown_compaction_usage_is_not_zero_or_part_of_model_usage(
    missing_usage: bool,
) -> None:
    payload = compacted_payload()
    if missing_usage:
        payload.pop("usage")
    else:
        payload["usage"] = None
    compaction = CompactedResponse.model_construct(**cast(dict[str, Any], payload))
    history = [snapshot(1, compaction=compaction, response=model_response())]

    turn = turn_view(
        workspace_id=WORKSPACE,
        turn_id=TURN,
        history=history,
        current=history[0],
        running=False,
    ).model_dump()

    assert turn["compactions"][0]["usage"] is None
    assert turn["usage"]["total_tokens"] == 21
    assert step_views(history, TURN)[0].model_dump()["compactions"][0]["usage"] is None


def test_adopted_compaction_is_visible_before_a_model_response_is_saved() -> None:
    history = [snapshot(1, compaction=compacted("before_model_failure")), snapshot(0)]

    turn = turn_view(
        workspace_id=WORKSPACE,
        turn_id=TURN,
        history=history,
        current=history[0],
        running=False,
    ).model_dump()

    assert len(turn["compactions"]) == 1
    assert turn["compactions"][0]["model_step"] == 1
    assert turn["usage"] is None
    assert step_views(history, TURN) == []


def test_previous_turn_and_input_only_snapshots_cannot_supply_compaction_usage() -> (
    None
):
    previous = compacted("previous")
    history = [
        snapshot(1, response=model_response()),
        snapshot(0),
        snapshot(3, compaction=previous, source="input"),
        snapshot(3, compaction=previous, turn_id=UUID(int=100)),
    ]

    turn = turn_view(
        workspace_id=WORKSPACE,
        turn_id=TURN,
        history=history,
        current=history[0],
        running=False,
    ).model_dump()

    assert turn["compactions"] == []
    assert step_views(history, TURN)[0].model_dump()["compactions"] == []
    assert turn["usage"]["total_tokens"] == 21


def test_known_compaction_usage_does_not_fill_unknown_model_usage() -> None:
    payload = {**response_payload(), "usage": None}
    history = [
        snapshot(
            1, compaction=compacted("known"), response=Response.model_validate(payload)
        )
    ]

    turn = turn_view(
        workspace_id=WORKSPACE,
        turn_id=TURN,
        history=history,
        current=history[0],
        running=False,
    ).model_dump()

    assert turn["usage"] is None
    assert turn["compactions"][0]["usage"]["total_tokens"] == 128020
