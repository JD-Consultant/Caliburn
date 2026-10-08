"""Record a next-Turn intent; never compact within the tool or expose native context."""

from typing import Literal, TypedDict

from openai.types.responses import FunctionToolParam
from pydantic import ConfigDict, TypeAdapter, ValidationError, with_config

from caliburn.contracts.generated.tools.request_context_compaction_arguments import (
    RequestContextCompactionArguments,
)
from caliburn.transport.model_tools.contracts import function_definition, reject_tool_call
from caliburn.workflows.context_history import RoleContextHistory


@with_config(ConfigDict(strict=True, extra="forbid"))
class _Intent(TypedDict):
    kind: Literal["context_compaction"]
    job_file_id: str
    execution_id: str
    role: str


_INTENT = TypeAdapter(_Intent)


def context_compaction_definitions() -> list[FunctionToolParam]:
    return [
        function_definition(
            "request_context_compaction",
            "既有上下文冗長、需要整理接續歷史時，要求下一輪開始前壓縮。"
            "只登記要求；本輪成功完成後，系統在下一輪加入新資料與輸入前處理，"
            "本輪取消則不生效。不會立刻壓縮，也不整理或修改受訪者工作記憶。"
            "不需填摘要、範圍或門檻，不必每輪呼叫。",
            "request-context-compaction-arguments",
        )
    ]


class ContextCompactionTools:
    names = ("request_context_compaction",)

    def __init__(self, history: RoleContextHistory) -> None:
        self.history = history

    def definitions(self) -> list[FunctionToolParam]:
        return context_compaction_definitions()

    def prepare(self, arguments: str) -> str | dict[str, object]:
        try:
            RequestContextCompactionArguments.model_validate_json(arguments)
        except ValidationError:
            return reject_tool_call(
                "invalid_arguments",
                "壓縮要求不接受參數。",
                "使用空物件 {}；時點與範圍由 App 處理。",
            )
        return {
            "kind": "context_compaction",
            "job_file_id": str(self.history.writer.scope.job_file_id),
            "execution_id": str(self.history.writer.scope.execution_id),
            "role": self.history.role.value,
        }

    async def execute(self, prepared: object) -> str:
        intent = _INTENT.validate_python(prepared)
        if (intent["job_file_id"], intent["execution_id"], intent["role"]) != (
            str(self.history.writer.scope.job_file_id),
            str(self.history.writer.scope.execution_id),
            self.history.role.value,
        ):
            raise ValueError("The saved compaction intent belongs to another role or execution")
        await self.history.request_compaction()
        return '{"status":"requested"}'
