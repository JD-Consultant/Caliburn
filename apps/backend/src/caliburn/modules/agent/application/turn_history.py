"""由原生保存點組成輪次與模型步的唯讀投影。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from langgraph.types import Interrupt, StateSnapshot
from openai.types.responses import CompactedResponse, Response
from pydantic import JsonValue, TypeAdapter

from caliburn.modules.agent.agent import has_pending_work
from caliburn.modules.agent.application.views import (
    CompactionView,
    InterruptView,
    StepView,
    ToolCallView,
    TurnView,
    UsageView,
)
from caliburn.modules.agent.interrupts import ConfirmedInterrupts, can_resume_interrupt

_json = TypeAdapter(JsonValue)


@dataclass(frozen=True)
class TurnExecution:
    current: StateSnapshot
    history: list[StateSnapshot]
    confirmed_interrupts: ConfirmedInterrupts | None

    def can_resume_interrupt(self, target: Interrupt) -> bool:
        return can_resume_interrupt(self.current, target, self.confirmed_interrupts)


def applied_snapshot(snapshot: StateSnapshot, turn_id: UUID) -> bool:
    return bool(
        snapshot.metadata
        and snapshot.metadata.get("source") != "input"
        and snapshot.values.get("turn_id") == turn_id
    )


def response_usage(response: Response | CompactedResponse) -> UsageView | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return UsageView(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
    )


def compaction_views(
    history: list[StateSnapshot], turn_id: UUID
) -> list[CompactionView]:
    """只觀察父 State 已採用的結果；task 結果不能冒充採用或完整計費。"""
    compactions: dict[str, CompactionView] = {}
    for snapshot in reversed(history):
        if not applied_snapshot(snapshot, turn_id):
            continue
        response = snapshot.values.get("compaction_response")
        number = snapshot.values.get("model_step")
        if (
            not isinstance(response, CompactedResponse)
            or not isinstance(number, int)
            or number < 0
            or response.id in compactions
        ):
            continue
        compactions[response.id] = CompactionView(
            response_id=response.id, model_step=number, usage=response_usage(response)
        )
    return list(compactions.values())


def message_text(response: Response, *, final_only: bool = False) -> list[str]:
    messages = [
        item
        for item in response.output
        if item.type == "message" and (not final_only or item.phase != "commentary")
    ]
    if final_only:
        messages = messages[-1:]
    return [
        "".join(
            part.text if part.type == "output_text" else part.refusal
            for part in item.content
        )
        for item in messages
    ]


def step_views(history: list[StateSnapshot], turn_id: UUID) -> list[StepView]:
    steps: dict[int, StepView] = {}
    for snapshot in reversed(history):
        if not applied_snapshot(snapshot, turn_id):
            continue
        response = snapshot.values.get("model_response")
        number = snapshot.values.get("model_step")
        if (
            not isinstance(response, Response)
            or not isinstance(number, int)
            or number < 1
        ):
            continue
        if number not in steps:
            steps[number] = StepView(
                model_step=number,
                messages=message_text(response),
                reasoning_summary=[
                    part.text
                    for item in response.output
                    if item.type == "reasoning"
                    for part in item.summary
                ],
                usage=response_usage(response),
                tool_calls=[
                    ToolCallView(
                        call_id=item.call_id, name=item.name, arguments=item.arguments
                    )
                    for item in response.output
                    if item.type == "function_call"
                ],
            )
        # 只讀本回覆尾端的工具結果；其他步可重用同一 call_id。
        items = snapshot.values.get("model_request", {}).get("input", [])
        if isinstance(items, list):
            for item in reversed(items):
                if (
                    not isinstance(item, dict)
                    or item.get("type") != "function_call_output"
                ):
                    break
                for tool in steps[number].tool_calls:
                    if tool.call_id == item.get("call_id") and isinstance(
                        item.get("output"), str
                    ):
                        tool.output = item["output"]
                        tool.status = "recorded"
        for task in snapshot.tasks:
            for pending in task.interrupts:
                view = InterruptView(
                    interrupt_id=pending.id, value=_json.validate_python(pending.value)
                )
                if view not in steps[number].interrupts:
                    steps[number].interrupts.append(view)
    for compaction in compaction_views(history, turn_id):
        if compaction.model_step in steps:
            steps[compaction.model_step].compactions.append(compaction)
    return [steps[number] for number in sorted(steps)]


def turn_view(
    *,
    workspace_id: UUID,
    turn_id: UUID,
    history: list[StateSnapshot],
    current: StateSnapshot,
    running: bool,
    confirmed_waiting: bool = False,
) -> TurnView:
    latest = next((s for s in history if applied_snapshot(s, turn_id)), None)
    response = latest.values.get("model_response") if latest else None
    status: Literal["running", "waiting_for_input", "interrupted", "completed"]
    if running:
        status = "running"
    elif current.interrupts and (
        confirmed_waiting or not any(task.error is not None for task in current.tasks)
    ):
        status = "waiting_for_input"
    elif has_pending_work(current):
        # 已答後故障與下一題等待可能有完全相同的原生快照。
        status = "interrupted"
    else:
        status = "completed"
    output = None
    if isinstance(response, Response):
        final = message_text(response, final_only=True)
        if final:
            output = final[-1]
    steps = step_views(history, turn_id)
    known = [step.usage for step in steps if step.usage is not None]
    usage = None
    if steps and len(known) == len(steps):
        usage = UsageView(
            input_tokens=sum(u.input_tokens for u in known),
            output_tokens=sum(u.output_tokens for u in known),
            total_tokens=sum(u.total_tokens for u in known),
        )
    if history[-1].created_at is None or history[0].created_at is None:
        raise ValueError("保存點缺少時間資訊")
    raw_input = latest.values.get("turn_input") if latest else None
    return TurnView(
        workspace_id=workspace_id,
        turn_id=turn_id,
        status=status,
        input=raw_input if isinstance(raw_input, str) else None,
        output=output,
        interrupts=[
            InterruptView(interrupt_id=item.id, value=_json.validate_python(item.value))
            for item in current.interrupts
        ],
        usage=usage,
        compactions=compaction_views(history, turn_id),
        created_at=datetime.fromisoformat(history[-1].created_at),
        updated_at=datetime.fromisoformat(history[0].created_at),
    )
