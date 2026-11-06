"""輪次與模型步的公開觀察值，不包含原生請求或完整 Context。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class UsageView(BaseModel):
    input_tokens: int = Field(ge=0, le=9007199254740991)
    output_tokens: int = Field(ge=0, le=9007199254740991)
    total_tokens: int = Field(ge=0, le=9007199254740991)


class InterruptView(BaseModel):
    interrupt_id: str
    value: JsonValue


class CompactionView(BaseModel):
    """父 State 已採用的原生壓縮回覆，不公開窗口正文。"""

    response_id: str
    model_step: int = Field(
        ge=0,
        le=9007199254740991,
        description="首次採用的模型步；0 表示本輪開始、尚未開始模型步。",
    )
    usage: UsageView | None = Field(description="原生壓縮回覆的用量；缺值為未知。")


class TurnView(BaseModel):
    model_config = ConfigDict(frozen=True)
    workspace_id: UUID
    turn_id: UUID
    status: Literal["running", "waiting_for_input", "interrupted", "completed"]
    input: str | None
    output: str | None
    interrupts: list[InterruptView]
    usage: UsageView | None = Field(
        description="已保存模型回覆的步用量總和，不含壓縮；任一步缺值則未知。"
    )
    compactions: list[CompactionView] = Field(
        default_factory=list,
        description=(
            "本輪父 State 已採用的壓縮回覆，按 response_id 去重。"
            "不是帳單或所有外送紀錄；空列不能證明未呼叫壓縮。"
        ),
    )
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TurnSubmission:
    turn: TurnView
    created: bool


class ToolCallView(BaseModel):
    call_id: str
    name: str
    arguments: str
    output: str | None = None
    status: Literal["recorded", "not_recorded"] = "not_recorded"


class StepView(BaseModel):
    model_step: int = Field(ge=1, le=9007199254740991)
    messages: list[str]
    reasoning_summary: list[str]
    usage: UsageView | None
    compactions: list[CompactionView] = Field(
        default_factory=list,
        description=(
            "首次在本模型步由父 State 採用的壓縮回覆，不含輪前壓縮。"
            "不是帳單或所有外送紀錄；空列不能證明未呼叫壓縮。"
        ),
    )
    tool_calls: list[ToolCallView]
    interrupts: list[InterruptView] = Field(default_factory=list)
