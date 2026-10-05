"""Select research capabilities, delegating all behavior to production tool owners."""

from uuid import UUID

from caliburn.transport.model_tools.contracts import reject_tool_call
from caliburn.transport.model_tools.jd_changes import JdChangesTools, jd_changes_definitions
from caliburn.transport.model_tools.jd_reads import jd_read_definitions
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.transport.model_tools.jd_writes import jd_write_definitions
from caliburn.transport.model_tools.memory_reads import (
    MemoryReadTools,
    memory_read_definitions,
    memory_read_names,
)
from jd_workspace import ResearchJdTurn
from openai.types.responses import FunctionToolParam, ResponseFunctionToolCall
from study_context import StudyArm


def study_tool_definitions(arm: StudyArm) -> list[FunctionToolParam]:
    names = memory_read_names() if arm == "memory" else ("read_interview",)
    return [
        *memory_read_definitions(names=names),
        *jd_read_definitions(),
        *jd_changes_definitions(),
        *jd_write_definitions(),
    ]


class StudyTools:
    def __init__(
        self, turn: ResearchJdTurn, memory: MemoryReadTools, changes: JdChangesTools, arm: StudyArm
    ) -> None:
        self.turn = turn
        self.memory = memory
        self.changes = changes
        self.arm = arm
        self.memory_names = memory.names if arm == "memory" else ("read_interview",)

    def definitions(self) -> list[FunctionToolParam]:
        return study_tool_definitions(self.arm)

    async def prepare(self, call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        if call.name in self.memory_names:
            return await self.memory.invoke(call.name, call.arguments)
        if call.name in self.turn.reads.names:
            return await self.turn.reads.invoke(call.name, call.arguments)
        if call.name in self.changes.names:
            return await self.changes.invoke(call.name, call.arguments)
        if call.name in self.turn.writes.names:
            prepared = await self.turn.writes.prepare(call.name, call.arguments, operation_id)
            return prepared if isinstance(prepared, str) else snapshot_jd_write(prepared)
        return reject_tool_call(
            "scope_not_allowed", "本組沒有這項工具。", "使用本次已提供的具名工具。"
        )

    async def execute(self, prepared: object) -> str:
        return await self.turn.writes.execute(restore_jd_write(prepared))
