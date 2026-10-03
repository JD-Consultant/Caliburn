"""A's existing tools at the shared Graph's prepare/execute boundary."""

from uuid import UUID

from openai.types.responses import FunctionToolParam, ResponseFunctionToolCall

from caliburn.transport.model_tools.context_compaction import (
    ContextCompactionTools,
    context_compaction_definitions,
)
from caliburn.transport.model_tools.contracts import reject_tool_call
from caliburn.transport.model_tools.jd_changes import JdChangesTools, jd_changes_definitions
from caliburn.transport.model_tools.jd_reads import JdReadTools, jd_read_definitions
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.transport.model_tools.jd_writes import JdWriteTools, jd_write_definitions
from caliburn.transport.model_tools.memory_consolidation import (
    MemoryConsolidationTools,
    memory_consolidation_definitions,
)
from caliburn.transport.model_tools.memory_reads import MemoryReadTools, memory_read_definitions

CONSULTANT_MEMORY_READ_NAMES = (
    "read_work_situation_map",
    "read_work_situation",
    "read_work_understanding_map",
    "read_work_understanding",
    "read_interview",
)


def consultant_tool_definitions() -> list[FunctionToolParam]:
    """Build A's tool template before its published Memory scope has been selected."""
    return [
        *memory_read_definitions(names=CONSULTANT_MEMORY_READ_NAMES),
        *jd_read_definitions(),
        *jd_changes_definitions(),
        *jd_write_definitions(),
        *memory_consolidation_definitions(),
        *context_compaction_definitions(),
    ]


class ConsultantTools:
    def __init__(
        self,
        memory_reads: MemoryReadTools,
        jd_reads: JdReadTools,
        jd_writes: JdWriteTools,
        jd_changes: JdChangesTools,
        consolidation: MemoryConsolidationTools,
        compaction: ContextCompactionTools,
    ) -> None:
        self.memory_reads = memory_reads
        self.jd_reads = jd_reads
        self.jd_writes = jd_writes
        self.jd_changes = jd_changes
        self.consolidation = consolidation
        self.compaction = compaction

    @property
    def names(self) -> tuple[str, ...]:
        return (
            *self.memory_reads.names,
            *self.jd_reads.names,
            *self.jd_changes.names,
            *self.jd_writes.names,
            *self.consolidation.names,
            *self.compaction.names,
        )

    def definitions(self) -> list[FunctionToolParam]:
        return [
            *self.memory_reads.definitions(),
            *self.jd_reads.definitions(),
            *self.jd_changes.definitions(),
            *self.jd_writes.definitions(),
            *self.consolidation.definitions(),
            *self.compaction.definitions(),
        ]

    async def prepare(
        self, call: ResponseFunctionToolCall, operation_id: UUID
    ) -> str | dict[str, object]:
        """Return a read observation or a JSON-only command for the Graph to save."""
        if call.name in self.memory_reads.names:
            return await self.memory_reads.invoke(call.name, call.arguments)
        if call.name in self.jd_reads.names:
            return await self.jd_reads.invoke(call.name, call.arguments)
        if call.name in self.jd_changes.names:
            return await self.jd_changes.invoke(call.name, call.arguments)
        if call.name in self.jd_writes.names:
            prepared = await self.jd_writes.prepare(call.name, call.arguments, operation_id)
            return prepared if isinstance(prepared, str) else snapshot_jd_write(prepared)
        if call.name in self.consolidation.names:
            return self.consolidation.prepare(call.arguments, operation_id)
        if call.name in self.compaction.names:
            return self.compaction.prepare(call.arguments)
        return reject_tool_call(
            "scope_not_allowed", "本角色沒有這項工具。", "使用本角色已提供的具名工具。"
        )

    async def execute(self, prepared: object) -> str:
        """Validate the saved command before dispatch; native call/result pairing stays in Graph."""
        if isinstance(prepared, dict) and prepared.get("kind") == "memory_consolidation":
            return await self.consolidation.execute(prepared)
        if isinstance(prepared, dict) and prepared.get("kind") == "context_compaction":
            return await self.compaction.execute(prepared)
        return await self.jd_writes.execute(restore_jd_write(prepared))
