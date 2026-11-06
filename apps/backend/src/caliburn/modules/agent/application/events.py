"""模型串流只公開具名白名單欄位，不轉送完整 SDK 物件。"""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from caliburn.modules.agent.application.views import TurnView
from caliburn.modules.agent.state import CancelStatus


class ModelDeltaData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_step: int = Field(ge=1, le=9007199254740991)
    delta: str


class ToolCallData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_step: int = Field(ge=1, le=9007199254740991)
    call_id: str
    name: str
    arguments: str


class ResyncRequiredData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["slow_subscriber"]


class CancellationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_id: UUID
    status: CancelStatus


class TurnStatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["status"]
    data: TurnView


class TextDeltaEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["text_delta"]
    data: ModelDeltaData


class ReasoningSummaryDeltaEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["reasoning_summary_delta"]
    data: ModelDeltaData


class ToolCallEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["tool_call"]
    data: ToolCallData


class ResyncRequiredEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["resync_required"]
    data: ResyncRequiredData


class CancellationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["cancellation"]
    data: CancellationData


type TurnEvent = Annotated[
    TurnStatusEvent
    | TextDeltaEvent
    | ReasoningSummaryDeltaEvent
    | ToolCallEvent
    | ResyncRequiredEvent
    | CancellationEvent,
    Field(discriminator="event"),
]


def model_event(part: dict[str, Any]) -> TurnEvent | None:
    if part.get("type") != "custom":
        return None
    data = part["data"]
    if not isinstance(data, dict):
        return None
    event = data.get("event")
    execution = data.get("execution")
    if not isinstance(event, dict) or not isinstance(execution, dict):
        return None
    step = execution.get("model_step")
    if type(step) is not int or not 1 <= step <= 9007199254740991:
        return None
    if event.get("type") in (
        "response.output_text.delta",
        "response.reasoning_summary_text.delta",
    ) and isinstance(event.get("delta"), str):
        delta = ModelDeltaData(model_step=step, delta=event["delta"])
        if event["type"] == "response.output_text.delta":
            return TextDeltaEvent(event="text_delta", data=delta)
        return ReasoningSummaryDeltaEvent(event="reasoning_summary_delta", data=delta)
    item = event.get("item")
    if (
        event.get("type") == "response.output_item.done"
        and isinstance(item, dict)
        and item.get("type") == "function_call"
    ):
        if all(
            isinstance(item.get(key), str) for key in ("call_id", "name", "arguments")
        ):
            return ToolCallEvent(
                event="tool_call",
                data=ToolCallData(
                    model_step=step,
                    call_id=item["call_id"],
                    name=item["name"],
                    arguments=item["arguments"],
                ),
            )
    return None
