"""讀取原生 SDK 串流，將完整 output 接續一次並判讀下一步。"""

import logging
from asyncio import CancelledError
from dataclasses import asdict
from typing import Any, Literal, cast

from langgraph.runtime import ExecutionInfo, Runtime
from openai import APIConnectionError, APIError, AsyncOpenAI
from openai.types.responses import ParsedResponse, Response
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.infrastructure.diagnostics import log_failure
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import (
    AgentState,
    request_items,
)


class ModelResponseError(RuntimeError):
    """非成功的完整模型回應；原生原件留給可信呼叫端檢查。"""

    def __init__(self, response: Response):
        super().__init__("Model response did not complete")
        self.response = response


def validate_response(response: ParsedResponse[None]) -> None:
    """提交前驗證 terminal；conditional edge 不可在已提交更新後才失敗。"""
    if response.status != "completed" or response.error or response.incomplete_details:
        raise ModelResponseError(response)
    for item in response.output:
        if item.type not in ("function_call", "message", "reasoning"):
            raise ValueError("Unsupported response output type")
        if item.type == "message" and item.phase not in (
            None,
            "commentary",
            "final_answer",
        ):
            raise ValueError("Unsupported assistant phase")
    if any(item.type == "function_call" for item in response.output):
        return
    messages = [item for item in response.output if item.type == "message"]
    if (
        not messages
        or messages[-1].status != "completed"
        or messages[-1].role != "assistant"
    ):
        raise ValueError("Response requires a complete assistant message")
    message = messages[-1]
    if not any(
        part.text.strip() if part.type == "output_text" else part.refusal.strip()
        for part in message.content
    ):
        raise ValueError("Response requires nonempty assistant content")


def classify_model_response(
    state: AgentState,
) -> Literal["tools", "continue", "finish"]:
    response = state["model_response"]
    assert response is not None
    if any(item.type == "function_call" for item in response.output):
        return "tools"
    messages = [item for item in response.output if item.type == "message"]
    return "continue" if messages[-1].phase == "commentary" else "finish"


logger = logging.getLogger(__name__)


class OpenAIModelNode:
    def __init__(self, client: AsyncOpenAI):
        self._client = client.with_options(max_retries=0)

    async def __call__(
        self, state: AgentState, runtime: Runtime[AgentContext]
    ) -> AgentState:
        try:
            return await self._call(state, runtime)
        except Exception as error:
            log_failure(
                logger,
                event="agent.model.failed",
                error=error,
                execution=runtime.execution_info,
                response=error.response
                if isinstance(error, ModelResponseError)
                else None,
            )
            if isinstance(error, APIError):
                raise RuntimeError("Model provider request failed") from None
            raise

    async def _call(
        self, state: AgentState, runtime: Runtime[AgentContext]
    ) -> AgentState:
        execution = cast(ExecutionInfo, runtime.execution_info)
        # SDK 接受原生 output BaseModel 並排除 parsed 輔助欄位，靜態 input 仍為
        # TypedDict。只在此已驗證的 SDK 邊界適配，不先 model_dump 工作歷史。
        sdk_request = cast(dict[str, Any], state["model_request"])
        response: ParsedResponse[None] | None = None
        try:
            async with self._client.responses.stream(**sdk_request) as stream:
                async for event in stream:
                    redacted_fields: list[str] = []
                    projection = redact_encrypted_content(
                        event.model_dump(
                            mode="json",
                            exclude_unset=True,
                            serialize_as_any=True,
                            warnings=False,
                        ),
                        "$",
                        redacted_fields,
                    )
                    runtime.stream_writer(
                        {
                            "execution": {
                                **asdict(execution),
                                "turn_id": str(state["turn_id"]),
                                "model_step": state["model_step"],
                            },
                            "event": projection,
                            "redacted_fields": redacted_fields,
                        }
                    )
                    if event.type == "response.completed":
                        validate_response(event.response)
                        response = event.response
                        # SDK 已解析完整原件；get_final_response 仍會讀取後方串流。
                        break
                    if event.type in ("response.failed", "response.incomplete"):
                        raise ModelResponseError(event.response)
                    if event.type == "error":
                        raise ValueError("Model provider stream reported an error")
        except Exception as error:
            # HTTP 清理可能遮蔽讀取取消；SDK 只在連線邊界再包一層。
            masked = error
            if isinstance(error, APIConnectionError) and isinstance(
                error.__cause__, Exception
            ):
                masked = error.__cause__
            if isinstance(masked.__context__, CancelledError):
                raise masked.__context__ from None
            if response is None:
                raise
            # 只有已驗證原件後的普通清理錯誤可留存結果；取消仍直接傳出。
            log_failure(
                logger,
                event="agent.model.stream_cleanup_failed",
                error=error,
                execution=execution,
                response=response,
            )
        if response is None:
            raise RuntimeError("Model stream ended without a completed response")
        request = state["model_request"]
        items = [*request_items(request), *response.output]
        return {
            "model_response": response,
            "model_request": {**request, "input": cast(ResponseInputParam, items)},
        }


def redact_encrypted_content(value: object, path: str, fields: list[str]) -> object:
    """只改觀察投影；保留完整工作歷史所需的 opaque SDK 原件。"""
    if isinstance(value, dict):
        projected: dict[str, object] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "encrypted_content":
                fields.append(child_path)
                projected[key] = "[REDACTED]"
            else:
                projected[key] = redact_encrypted_content(child, child_path, fields)
        return projected
    if isinstance(value, list):
        return [
            redact_encrypted_content(child, f"{path}[{index}]", fields)
            for index, child in enumerate(value)
        ]
    return value
