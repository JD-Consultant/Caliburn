"""原生 Responses 工作請求與 LangGraph 的輸入、輸出 channel。"""

from typing import Annotated, Literal, TypedDict, cast
from uuid import UUID

from openai.types.responses import (
    CompactedResponse,
    ParsedResponse,
    ParsedResponseOutputItem,
    ResponseInputItemParam,
    ResponseOutputItem,
)
from openai.types.responses.response_create_params import ResponseCreateParamsBase

type OpenAIItems = list[
    ResponseInputItemParam | ResponseOutputItem | ParsedResponseOutputItem[None]
]

type CancelStatus = Literal["pending", "completed"]


def preserve_workspace_id(current: UUID, incoming: UUID) -> UUID:
    """原生 channel 首次接受歸屬，之後只接受同一 Workspace。"""
    if incoming != current:
        raise ValueError("Workspace ownership cannot change")
    return current


class AgentInput(TypedDict, total=False):
    """可信入口建立的新輪輸入，不接受 caller 任意 State。"""

    workspace_id: UUID
    turn_id: UUID
    turn_input: str | list[ResponseInputItemParam]
    model_response: ParsedResponse[None] | None
    compaction_response: CompactedResponse | None
    model_step: int
    cancel_status: CancelStatus | None
    turn_completed: bool


class AgentOutput(TypedDict):
    turn_id: UUID
    model_response: ParsedResponse[None] | None


class AgentState(TypedDict, total=False):
    workspace_id: Annotated[UUID, preserve_workspace_id]
    turn_id: UUID
    turn_input: str | list[ResponseInputItemParam]
    model_request: ResponseCreateParamsBase
    model_response: ParsedResponse[None] | None
    compaction_response: CompactedResponse | None
    model_step: int
    cancel_status: CancelStatus | None
    turn_completed: bool


def request_items(request: ResponseCreateParamsBase) -> OpenAIItems:
    """SDK 接受完整 output items；靜態 input 型別只列輸入 TypedDict。"""
    return cast(OpenAIItems, request["input"])


class AgentLimitError(RuntimeError):
    """本輪已達配置上限，不能繼續執行。"""
