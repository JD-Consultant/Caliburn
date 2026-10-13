"""Exact Memory command types and restoration validation for the native checkpoint."""

from dataclasses import dataclass
from uuid import UUID

from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    MemoryBatchPosition,
    MemoryEdit,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import (
    MemoryContent,
    MemoryContentChanges,
    ReferenceChanges,
)
from caliburn.features.work_memory.revisions import MemoryLayer


@dataclass(frozen=True, slots=True)
class PreparedMemoryToolCall:
    """App-only checkpoint payload, not another editable candidate or a committed receipt."""

    command: MemoryEdit
    success_output: str


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


def require_prepared_memory_call(value: object) -> PreparedMemoryToolCall:
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
    return value


def _require_strings(*values: str) -> None:
    if any(type(value) is not str for value in values):
        raise TypeError("Expected restored text")


def _require_ids(values: frozenset[UUID]) -> None:
    if type(values) is not frozenset or any(type(value) is not UUID for value in values):
        raise TypeError("Expected restored reference identities")
