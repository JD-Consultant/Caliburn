"""將同一 Pydantic 參數契約用於 OpenAI 宣告與 ToolRuntime 入口。"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel

from caliburn.bundles.memory.tool_output import (
    MODEL_REJECTIONS,
    invalid_arguments,
    model_rejection,
)
from caliburn.modules.agent.plugins.contracts import AgentContext


def memory_tool[ArgumentsT: BaseModel](
    name: str,
    description: str,
    schema: type[ArgumentsT],
    handler: Callable[
        [ArgumentsT, ToolRuntime[AgentContext, Any]], Awaitable[str | Command[object]]
    ],
) -> StructuredTool:
    async def invoke(
        runtime: ToolRuntime[AgentContext, Any], **raw: object
    ) -> str | Command[object]:
        try:
            return await handler(schema.model_validate(raw), runtime)
        except MODEL_REJECTIONS as error:
            raise model_rejection(error) from error

    return StructuredTool.from_function(
        coroutine=invoke,
        name=name,
        description=description,
        # ToolRuntime is injected independently of the strict model argument schema.
        args_schema=schema.model_json_schema(),
        handle_tool_error=True,
        handle_validation_error=invalid_arguments,
    )
