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
from caliburn.workflows.work_memory.consolidation import MemoryConsolidationWorkflow


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
            (
                "某項工作的已知資訊已足以形成有用的工作情境時，要求 App 在背景整"
                "理工作情境與工作理解。不必等所有未知釐清，也不必每輪要求。傳入空"
                "物件；來源範圍由 App 決定。成功只回 message「已記錄整理要求；本"
                "輪成功完成後由系統處理。」表示要求已登記；本輪成功完成後才取得背"
                "景整理資格，不表示整理已開始、完成或發布。本輪取消或失敗不使要求"
                "生效。繼續依已發布正文與可見原話工作，無須等待；重複要求不會強制"
                "重試先前失敗的整理。"
            ),
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
