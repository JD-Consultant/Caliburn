"""Workflow assembly of candidate tools; native execution owns calls and saved results."""

from dataclasses import dataclass
from uuid import UUID

from openai.types.responses import FunctionToolParam, ResponseFunctionToolCall

from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    MemoryBatchPosition,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import (
    MemoryContent,
    MemoryContentChanges,
    ReferenceChanges,
)
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.contracts import reject_tool_call
from caliburn.transport.model_tools.memory_reads import (
    MemoryReadTools,
    memory_read_definitions,
    memory_read_names,
)
from caliburn.transport.model_tools.memory_writes import (
    MemoryWriteTools,
    PreparedMemoryToolCall,
    memory_write_definitions,
)

# Pass these to the existing official serializer at the composition root. No codec/registry.
MEMORY_CHECKPOINT_TYPES = (
    PreparedMemoryToolCall,
    CreateMemoryObject,
    ReviseMemoryObject,
    DeleteMemoryObject,
    MemoryBatchPosition,
    MemoryLayer,
    MemoryContent,
    MemoryContentChanges,
    ReferenceChanges,
)


def memory_analysis_tool_definitions(layer: MemoryLayer) -> list[FunctionToolParam]:
    """Same contracts as bound tools, without persistence or a fabricated binding."""
    return [
        *memory_read_definitions(names=memory_read_names(layer)),
        *memory_write_definitions(layer),
    ]


@dataclass(frozen=True, slots=True)
class MemoryAnalysisTools:
    reads: MemoryReadTools
    writes: MemoryWriteTools

    @property
    def names(self) -> tuple[str, ...]:
        return (*self.reads.names, *self.writes.names)

    def definitions(self) -> list[FunctionToolParam]:
        return [*self.reads.definitions(), *self.writes.definitions()]

    async def prepare(self, call: ResponseFunctionToolCall, operation_id: UUID) -> object:
        if call.name in self.reads.names:
            return await self.reads.invoke(call.name, call.arguments)
        if call.name in self.writes.names:
            return await self.writes.prepare(call.name, call.arguments, command_id=operation_id)
        return reject_tool_call(
            "scope_not_allowed", "本角色沒有這項工具權限。", "只使用本角色公開的工具。"
        )

    async def execute(self, prepared: object) -> str:
        _require_prepared(prepared)
        if not isinstance(prepared, PreparedMemoryToolCall):
            raise TypeError("Expected a restored Memory command")
        return await self.writes.execute(prepared)


def _require_prepared(value: object) -> None:
    """Fail closed when the official serializer has downgraded any nested constructor."""
    if type(value) is not PreparedMemoryToolCall or type(value.success_output) is not str:
        raise TypeError("Expected a restored Memory tool call")
    command = value.command
    if type(command) not in (CreateMemoryObject, ReviseMemoryObject, DeleteMemoryObject):
        raise TypeError("Expected a restored Memory edit")
    position = command.position
    if type(position) is not MemoryBatchPosition or type(command.layer) is not MemoryLayer:
        raise TypeError("Expected a typed Memory stage and layer")
    if type(position.phase) is not MemoryLayer or any(
        type(identity) is not UUID
        for identity in (
            command.command_id,
            position.job_file_id,
            position.execution_id,
            position.generation_id,
            position.stage_id,
            position.position_id,
        )
    ):
        raise TypeError("Expected original Memory identities")
    if isinstance(command, CreateMemoryObject):
        if type(command.content) is not MemoryContent:
            raise TypeError("Expected Memory content")
        _require_strings(command.content.title, command.content.description, command.content.body)
        _require_ids(command.reference_ids)
    else:
        if type(command.object_id) is not UUID:
            raise TypeError("Expected original Memory object identity")
    if isinstance(command, ReviseMemoryObject):
        if command.content_changes is not None:
            change = command.content_changes
            if type(change) is not MemoryContentChanges:
                raise TypeError("Expected Memory content changes")
            _require_strings(
                *(
                    text
                    for text in (change.title, change.description, change.body)
                    if text is not None
                )
            )
        if command.reference_changes is not None:
            references = command.reference_changes
            if type(references) is not ReferenceChanges:
                raise TypeError("Expected Memory reference changes")
            _require_ids(references.add)
            _require_ids(references.remove)


def _require_strings(*values: str) -> None:
    if any(type(value) is not str for value in values):
        raise TypeError("Expected restored text")


def _require_ids(values: frozenset[UUID]) -> None:
    if type(values) is not frozenset or any(type(value) is not UUID for value in values):
        raise TypeError("Expected restored reference identities")
