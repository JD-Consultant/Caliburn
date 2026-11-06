"""正常執行證據只解鎖原生快照中精確相符的目標。"""

from copy import deepcopy
from uuid import UUID

from langgraph.types import Interrupt, PregelTask, StateSnapshot

from caliburn.modules.agent.interrupts import can_resume_interrupt, confirmed_interrupts


def test_confirming_one_interrupt_cannot_unlock_another_failed_target() -> None:
    left = Interrupt(id="left", value={"operation": "deploy", "revision": "a1"})
    right = Interrupt(id="right", value={"operation": "rotate", "revision": "b1"})
    snapshot = StateSnapshot(
        values={"turn_id": UUID(int=11)},
        next=("approval",),
        config={"configurable": {"checkpoint_id": "checkpoint"}},
        metadata=None,
        created_at=None,
        parent_config=None,
        tasks=(PregelTask("task", "approval", (), RuntimeError("earlier failure")),),
        interrupts=(left, right),
    )
    confirmed = confirmed_interrupts(snapshot, (deepcopy(left),))
    assert confirmed is not None
    assert can_resume_interrupt(snapshot, left, confirmed)
    assert not can_resume_interrupt(snapshot, right, confirmed)
    assert not can_resume_interrupt(snapshot, left, None)
    assert can_resume_interrupt(snapshot._replace(tasks=()), right, None)
    assert not can_resume_interrupt(
        snapshot, Interrupt(id="unknown", value=right.value), confirmed
    )
    left.value["revision"] = "a2"
    assert not can_resume_interrupt(snapshot, left, confirmed)
    replaced = snapshot._replace(config={"configurable": {"checkpoint_id": "new"}})
    assert not confirmed.matches(replaced)


def test_step_history_preserves_distinct_raw_interrupt_payloads() -> None:
    from openai.types.responses import Response

    from caliburn.modules.agent.application.turn_history import step_views
    from tests.unit.modules.agent.offline_openai import call, response_payload

    first = Interrupt(id="same", value={"operation": "deploy", "revision": "a1"})
    second = Interrupt(id="same", value={"operation": "deploy", "revision": "a2"})
    payload = response_payload([call("deploy")])
    payload["usage"] = None
    snapshot = StateSnapshot(
        values={
            "turn_id": UUID(int=11),
            "model_step": 1,
            "model_response": Response.model_validate(payload),
        },
        next=("approval",),
        config={"configurable": {"checkpoint_id": "checkpoint"}},
        metadata={"source": "loop", "step": 1, "parents": {}},
        created_at=None,
        parent_config=None,
        tasks=(PregelTask("task", "approval", (), interrupts=(first,)),),
        interrupts=(first,),
    )
    newer = snapshot._replace(
        tasks=(PregelTask("task", "approval", (), interrupts=(second,)),),
        interrupts=(second,),
    )
    steps = step_views([newer, snapshot, snapshot], UUID(int=11))
    assert [(item.interrupt_id, item.value) for item in steps[0].interrupts] == [
        ("same", {"operation": "deploy", "revision": "a1"}),
        ("same", {"operation": "deploy", "revision": "a2"}),
    ]
    assert steps[0].tool_calls[0].name == "deploy"
