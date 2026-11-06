"""正常完成資格沿 Core terminal 規則，不能只憑 Graph END 或 Response 存在。"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

import pytest
from langgraph.checkpoint.base import CheckpointMetadata
from langgraph.types import Interrupt, PregelTask, StateSnapshot
from openai.types.responses import ParsedResponse, Response

from caliburn.modules.agent.agent import Agent, completed_turn_id
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from tests.unit.modules.agent.offline_openai import (
    call,
    message,
    reasoning,
    response_payload,
)

TURN = UUID(int=101)
NEXT_TURN = UUID(int=102)


def response(payload: dict[str, object]) -> Response:
    return Response.model_construct(**cast(dict[str, Any], payload))


def snapshot(values: dict[str, object]) -> StateSnapshot:
    return StateSnapshot(
        values={"turn_id": TURN, "model_step": 1, **values},
        next=(),
        config={},
        metadata=cast(
            CheckpointMetadata,
            {"source": "loop", "step": 2, "parents": {}, "turn_id": str(TURN)},
        ),
        created_at=None,
        parent_config=None,
        tasks=(),
        interrupts=(),
    )


@pytest.mark.parametrize(
    "values",
    [
        {"model_response": response(response_payload())},
        {
            "turn_completed": True,
            "model_response": response(response_payload([call()])),
        },
        {
            "turn_completed": True,
            "model_response": response(response_payload([message("commentary")])),
        },
        {
            "turn_completed": True,
            "model_response": response(response_payload(status="incomplete")),
        },
    ],
    ids=["missing-completion-marker", "tool-call", "commentary", "incomplete"],
)
def test_previous_completed_turn_skips_nonfinal_snapshots(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, object]
) -> None:
    candidate = snapshot(values)
    anchor = candidate._replace(
        metadata=cast(
            CheckpointMetadata,
            {"source": "input", "step": 3, "parents": {}, "turn_id": str(NEXT_TURN)},
        )
    )

    async def history(self: Agent, **kwargs: object) -> AsyncIterator[StateSnapshot]:
        yield anchor
        yield candidate

    monkeypatch.setattr(Agent, "aget_state_history", history)
    agent = Agent(
        agent_id="read-completion",
        resume_version="v1",
        graph=cast(Any, None),
        context=AgentContext(PluginServices({})),
    )

    async def run() -> None:
        assert (
            await agent.aget_previous_completed_turn(
                workspace_id=UUID(int=1), before_turn_id=NEXT_TURN
            )
            is None
        )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("response_type", [Response, ParsedResponse])
@pytest.mark.parametrize(
    "output",
    [
        [message()],
        [message(None)],
        [{**message(), "content": [{"type": "refusal", "refusal": "Cannot comply"}]}],
        [reasoning(), message(text="First final"), message(text="Last final")],
    ],
    ids=["text", "legacy-phase", "refusal", "multiple-final"],
)
def test_completed_turn_accepts_core_final_response_shapes(
    response_type: type[Response], output: list[dict[str, object]]
) -> None:
    final_response = response_type.model_construct(
        **cast(dict[str, Any], response_payload(output))
    )

    assert (
        completed_turn_id(
            snapshot({"turn_completed": True, "model_response": final_response})
        )
        == TURN
    )


@pytest.mark.parametrize(
    "payload",
    [
        response_payload([call()]),
        response_payload([message("commentary")]),
        response_payload(status="failed"),
        response_payload(status="incomplete"),
        response_payload([]),
        response_payload([message(text="")]),
        response_payload([message("future-phase")]),
        response_payload([{**message(), "status": "in_progress"}]),
        response_payload([{**message(), "role": "user"}]),
        response_payload(
            [{"id": "cmp", "type": "compaction", "encrypted_content": "opaque"}]
        ),
    ],
    ids=[
        "tools",
        "commentary",
        "failed",
        "incomplete",
        "no-message",
        "empty-content",
        "unsupported-phase",
        "unfinished-message",
        "user-message",
        "unsupported-output",
    ],
)
def test_completed_turn_rejects_responses_that_core_cannot_finish(
    payload: dict[str, object],
) -> None:
    candidate = snapshot({"turn_completed": True, "model_response": response(payload)})

    assert completed_turn_id(candidate) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"turn_completed": False},
        {"turn_completed": None},
        {"turn_completed": 1},
        {"turn_id": str(TURN)},
        {"cancel_status": "pending"},
        {"cancel_status": "completed"},
        {"model_response": None},
        {"model_response": response_payload()},
    ],
    ids=[
        "unfinished",
        "missing-marker",
        "invalid-marker",
        "non-uuid",
        "cancel-pending",
        "cancelled",
        "no-response",
        "dict-response",
    ],
)
def test_completed_turn_requires_completed_uuid_state(
    changes: dict[str, object],
) -> None:
    candidate = snapshot(
        {
            "turn_completed": True,
            "model_response": response(response_payload()),
            **changes,
        }
    )

    assert completed_turn_id(candidate) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"metadata": None},
        {"metadata": {"source": "loop", "turn_id": str(NEXT_TURN)}},
        {"metadata": {"source": "input", "turn_id": str(TURN)}},
        {"next": ("finish_turn",)},
        {"tasks": (PregelTask(id="task", name="after_model", path=()),)},
        {"interrupts": (Interrupt(value="answer", id="waiting"),)},
    ],
    ids=[
        "no-metadata",
        "different-turn",
        "input-checkpoint",
        "next-node",
        "pending-task",
        "interrupt",
    ],
)
def test_completed_turn_requires_matching_metadata_and_no_pending_work(
    changes: dict[str, Any],
) -> None:
    candidate = snapshot(
        {
            "turn_completed": True,
            "model_response": response(response_payload()),
        }
    )._replace(**changes)

    assert completed_turn_id(candidate) is None
