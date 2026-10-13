"""Assemble the Memory role's native tools; execution owns calls and saved results."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from langchain_core.tools import BaseTool
from openai.types.responses import FunctionToolParam, ResponseFunctionToolCall

from caliburn.agent_execution.native_agent import NativeToolBinding, native_tool
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.excluded_work_reads import (
    ExcludedWorkReadTools,
    excluded_work_read_definitions,
)
from caliburn.transport.model_tools.memory_reads import (
    MemoryReadTools,
    memory_read_definitions,
    memory_read_names,
)
from caliburn.transport.model_tools.memory_write_checkpoint import require_prepared_memory_call
from caliburn.transport.model_tools.memory_writes import (
    MemoryWriteTools,
    memory_write_definitions,
)


def memory_analysis_tool_definitions(
    layer: MemoryLayer,
    *,
    excluded_work_enabled: bool = False,
) -> list[FunctionToolParam]:
    """Same contracts as bound tools, without persistence or a fabricated binding."""
    return [
        *memory_read_definitions(names=memory_read_names(layer)),
        *(excluded_work_read_definitions() if excluded_work_enabled else []),
        *memory_write_definitions(layer),
    ]


@dataclass(frozen=True, slots=True)
class MemoryAnalysisTools:
    reads: MemoryReadTools
    writes: MemoryWriteTools
    excluded_work: ExcludedWorkReadTools | None = None

    def standard_tools(self, ensure_active: Callable[[], Awaitable[None]]) -> list[BaseTool]:
        """同一 agent 工具接縫；原 typed 命令與 stage 准入仍由 owner 負責。"""

        async def no_command(prepared: object) -> str:
            raise ValueError("A read observation cannot execute a command")

        def reads(invoke: Callable[[str, str], Awaitable[str]]) -> NativeToolBinding:
            async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
                return await invoke(call.name, call.arguments)

            return NativeToolBinding(prepare, no_command)

        tools = [
            native_tool(definition, reads(self.reads.invoke), ensure_active)
            for definition in self.reads.definitions()
        ]
        if self.excluded_work is not None:
            tools.extend(
                native_tool(definition, reads(self.excluded_work.invoke), ensure_active)
                for definition in self.excluded_work.definitions()
            )

        async def prepare_write(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            return await self.writes.prepare(call.name, call.arguments, command_id=operation_id)

        binding = NativeToolBinding(prepare_write, self.execute)
        tools.extend(
            native_tool(definition, binding, ensure_active)
            for definition in self.writes.definitions()
        )
        return tools

    async def execute(self, prepared: object) -> str:
        return await self.writes.execute(require_prepared_memory_call(prepared))
