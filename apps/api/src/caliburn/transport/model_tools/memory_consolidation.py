"""A's zero-argument request: checkpoint identity before recording a durable intent."""

import json
from typing import Literal, TypedDict
from uuid import UUID

from openai.types.responses import FunctionToolParam
from pydantic import ConfigDict, TypeAdapter, ValidationError, with_config

from caliburn.contracts.generated.tools.request_memory_consolidation_arguments import (
    RequestMemoryConsolidationArguments,
)
from caliburn.contracts.validation import parse_contract
from caliburn.features.executions.models import ExecutionWriter
from caliburn.transport.model_tools.contracts import function_definition, reject_tool_call
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow


@with_config(ConfigDict(strict=True, extra="forbid"))
class _Intent(TypedDict):
    kind: Literal["memory_consolidation"]
    execution_id: str
    job_file_id: str
    command_id: str


_INTENT = TypeAdapter(_Intent)


def memory_consolidation_definitions() -> list[FunctionToolParam]:
    return [
        function_definition(
            "request_memory_consolidation",
            "當訪談某項工作的資訊已值得整理時，要求背景整理受訪者工作記憶。"
            "只登記要求，本輪成功完成後才由系統整理；不是宣告已發布。"
            "不需填範圍、不等待整理完成，也不因後續仍有未知就禁止整理已知。",
            "request-memory-consolidation-arguments",
        )
    ]


class MemoryConsolidationTools:
    names = ("request_memory_consolidation",)

    def __init__(self, workflow: MemoryConsolidationWorkflow, writer: ExecutionWriter) -> None:
        self.workflow = workflow
        self.writer = writer

    def definitions(self) -> list[FunctionToolParam]:
        return memory_consolidation_definitions()

    def prepare(self, arguments: str, command_id: UUID) -> str | dict[str, object]:
        try:
            parse_contract(RequestMemoryConsolidationArguments, arguments)
        except ValidationError:
            return reject_tool_call(
                "invalid_arguments", "整理通知不接受參數。", "使用空物件 {}；來源範圍由 App 固定。"
            )
        return {
            "kind": "memory_consolidation",
            "execution_id": str(self.writer.scope.execution_id),
            "job_file_id": str(self.writer.scope.job_file_id),
            "command_id": str(command_id),
        }

    async def execute(self, prepared: object) -> str:
        command = _INTENT.validate_python(prepared)
        if (command["execution_id"], command["job_file_id"]) != (
            str(self.writer.scope.execution_id),
            str(self.writer.scope.job_file_id),
        ):
            raise ValueError("A saved notification belongs to another execution")
        await self.workflow.request(self.writer, UUID(command["command_id"]))
        return json.dumps(
            {"message": "已記錄整理要求；本輪成功完成後由系統處理。"}, ensure_ascii=False
        )
