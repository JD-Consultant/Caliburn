"""A's existing tools at the shared Graph's prepare/execute boundary."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from langchain_core.tools import BaseTool
from openai.types.responses import FunctionToolParam, ResponseFunctionToolCall

from caliburn.agent_execution.native_agent import NativeToolBinding, native_tool
from caliburn.transport.model_tools.context_compaction import (
    ContextCompactionTools,
    context_compaction_definitions,
)
from caliburn.transport.model_tools.interview_plans import (
    InterviewPlanTools,
    interview_plan_definitions,
)
from caliburn.transport.model_tools.jd_changes import JdChangesTools, jd_changes_definitions
from caliburn.transport.model_tools.jd_reads import JdReadTools, jd_read_definitions
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.transport.model_tools.jd_writes import JdWriteTools, jd_write_definitions
from caliburn.transport.model_tools.memory_consolidation import (
    MemoryConsolidationTools,
    memory_consolidation_definitions,
)
from caliburn.transport.model_tools.memory_reads import MemoryReadTools, memory_read_definitions
from caliburn.transport.model_tools.occupation_references import (
    OccupationReferenceTools,
    occupation_reference_definitions,
)
from caliburn.transport.model_tools.task_hints import TaskHintTools, search_task_hints_definition

CONSULTANT_MEMORY_READ_NAMES = (
    "read_work_situation_map",
    "read_work_situation",
    "read_work_understanding_map",
    "read_work_understanding",
    "read_interview",
)


def consultant_tool_definitions(
    *,
    occupation_references_enabled: bool = False,
    interview_plans_enabled: bool = True,
) -> list[FunctionToolParam]:
    """Build A's tool template before its published Memory scope has been selected."""
    return [
        *memory_read_definitions(names=CONSULTANT_MEMORY_READ_NAMES),
        *jd_read_definitions(),
        *jd_changes_definitions(),
        *jd_write_definitions(),
        *memory_consolidation_definitions(),
        *context_compaction_definitions(),
        *(interview_plan_definitions() if interview_plans_enabled else []),
        *(occupation_reference_definitions() if occupation_references_enabled else []),
        *([search_task_hints_definition()] if occupation_references_enabled else []),
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
        *,
        occupation_references: OccupationReferenceTools | None = None,
        task_hints: TaskHintTools | None = None,
        interview_plans: InterviewPlanTools | None = None,
    ) -> None:
        self.memory_reads = memory_reads
        self.jd_reads = jd_reads
        self.jd_writes = jd_writes
        self.jd_changes = jd_changes
        self.consolidation = consolidation
        self.compaction = compaction
        self.occupation_references = occupation_references
        self.task_hints = task_hints
        self.interview_plans = interview_plans

    def standard_tools(self, ensure_active: Callable[[], Awaitable[None]]) -> list[BaseTool]:
        """交標準 registry 管理名稱；原工具仍擁有正式准入與命令 codec。"""
        tools: list[BaseTool] = []

        def add(definitions: list[FunctionToolParam], binding: NativeToolBinding) -> None:
            for definition in definitions:
                tools.append(native_tool(definition, binding, ensure_active))

        async def no_command(prepared: object) -> str:
            raise ValueError("A read observation cannot be executed as a command")

        def read_binding(invoke: Callable[[str, str], Awaitable[str]]) -> NativeToolBinding:
            async def read(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
                return await invoke(call.name, call.arguments)

            return NativeToolBinding(read, no_command)

        for reads in (self.memory_reads, self.jd_reads, self.jd_changes):
            add(reads.definitions(), read_binding(reads.invoke))

        async def prepare_jd(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            prepared = await self.jd_writes.prepare(call.name, call.arguments, operation_id)
            return prepared if isinstance(prepared, str) else snapshot_jd_write(prepared)

        async def execute_jd(prepared: object) -> str:
            return await self.jd_writes.execute(restore_jd_write(prepared))

        add(self.jd_writes.definitions(), NativeToolBinding(prepare_jd, execute_jd))

        async def consolidate(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            return self.consolidation.prepare(call.arguments, operation_id)

        async def compact(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            return self.compaction.prepare(call.arguments)

        add(
            self.consolidation.definitions(),
            NativeToolBinding(consolidate, self.consolidation.execute),
        )
        add(self.compaction.definitions(), NativeToolBinding(compact, self.compaction.execute))

        def write_binding(
            prepare: Callable[[str, str, UUID], Awaitable[str | dict[str, object]]],
            execute: Callable[[object], Awaitable[str]],
        ) -> NativeToolBinding:
            async def prepare_call(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
                return await prepare(call.name, call.arguments, operation_id)

            return NativeToolBinding(prepare_call, execute)

        if self.task_hints is not None:
            add(self.task_hints.definitions(), read_binding(self.task_hints.invoke))

        for owner in (self.interview_plans, self.occupation_references):
            if owner is None:
                continue
            for definition in owner.definitions():
                if definition["name"] in owner.read_names:
                    add([definition], read_binding(owner.invoke))
                else:
                    add([definition], write_binding(owner.prepare, owner.execute))
        return tools
