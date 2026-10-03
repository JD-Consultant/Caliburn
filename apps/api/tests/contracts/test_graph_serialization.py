"""Checkpoint allowlists must block unknown constructors before tool execution."""

from dataclasses import dataclass, fields, is_dataclass
from typing import ClassVar
from uuid import UUID

import pytest

from caliburn.adapters.graph_checkpointer import create_graph_serializer
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
from caliburn.transport.model_tools.memory_writes import PreparedMemoryToolCall

# The caller owns these exact payload types; the adapter has no domain registry.
MEMORY_TYPES = (
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


@dataclass(frozen=True, slots=True)
class UnregisteredPayload:
    value: str
    constructions: ClassVar[int] = 0

    def __post_init__(self) -> None:
        type(self).constructions += 1


class PickleOnlyPayload:
    """An ordinary class has no native msgpack representation."""


@pytest.fixture(params=list(MemoryLayer))
def position(request: pytest.FixtureRequest) -> MemoryBatchPosition:
    return MemoryBatchPosition(
        job_file_id=UUID(int=1),
        execution_id=UUID(int=2),
        generation_id=UUID(int=3),
        stage_id=UUID(int=4),
        phase=MemoryLayer(request.param),
        position_id=UUID(int=5),
    )


@pytest.fixture(params=["create", "revise", "delete"])
def prepared_call(
    request: pytest.FixtureRequest, position: MemoryBatchPosition
) -> PreparedMemoryToolCall:
    command: MemoryEdit
    match request.param:
        case "create":
            command = CreateMemoryObject(
                command_id=UUID(int=6),
                position=position,
                layer=position.phase,
                content=MemoryContent("合成盤點", "核對差異", "# 盤點\n每週核對。"),
                reference_ids=frozenset({UUID(int=7), UUID(int=8)}),
            )
            output = '{"status":"created"}'
        case "revise":
            command = ReviseMemoryObject(
                command_id=UUID(int=6),
                position=position,
                layer=position.phase,
                object_id=UUID(int=9),
                content_changes=MemoryContentChanges(
                    title="合成盤點修訂", description=None, body="# 盤點\n每日核對。"
                ),
                reference_changes=ReferenceChanges(
                    add=frozenset({UUID(int=7)}), remove=frozenset({UUID(int=8)})
                ),
            )
            output = '{"status":"updated","body_diff":"-每週核對。\\n+每日核對。"}'
        case "delete":
            command = DeleteMemoryObject(
                command_id=UUID(int=6),
                position=position,
                layer=position.phase,
                object_id=UUID(int=9),
            )
            output = '{"status":"deleted"}'
        case _:
            raise AssertionError("Unknown test operation")
    return PreparedMemoryToolCall(command=command, success_output=output)


def assert_same_value_and_type(restored: object, original: object) -> None:
    # Equality alone misses StrEnum -> str and nested constructor degradation.
    assert type(restored) is type(original)
    assert restored == original
    if is_dataclass(original) and not isinstance(original, type):
        for field in fields(original):
            assert_same_value_and_type(getattr(restored, field.name), getattr(original, field.name))
    elif isinstance(original, frozenset):
        assert isinstance(restored, frozenset)
        for member in original:
            restored_member = next(item for item in restored if item == member)
            assert_same_value_and_type(restored_member, member)


def test_default_serializer_does_not_execute_unregistered_constructor() -> None:
    original = UnregisteredPayload("synthetic")
    before_load = UnregisteredPayload.constructions
    serializer = create_graph_serializer()

    restored = serializer.loads_typed(serializer.dumps_typed(original))

    assert UnregisteredPayload.constructions == before_load
    assert type(restored) is dict
    assert restored == {"value": "synthetic"}


def test_prepared_memory_commands_restore_every_nested_value_and_type(
    prepared_call: PreparedMemoryToolCall,
) -> None:
    writer = create_graph_serializer(allowed_types=MEMORY_TYPES)
    serialized = writer.dumps_typed(prepared_call)
    # A fresh instance must not rely on types learned while encoding.
    reader = create_graph_serializer(allowed_types=MEMORY_TYPES)

    restored = reader.loads_typed(serialized)

    assert serialized[0] == "msgpack"
    assert restored is not prepared_call
    assert_same_value_and_type(restored, prepared_call)


def test_allowing_outer_payload_does_not_implicitly_allow_nested_commands(
    prepared_call: PreparedMemoryToolCall,
) -> None:
    serializer = create_graph_serializer(allowed_types=(PreparedMemoryToolCall,))

    restored = serializer.loads_typed(serializer.dumps_typed(prepared_call))

    # Inspect the untrusted field without assuming its declared MemoryEdit type.
    restored_command: object = restored.command
    assert type(restored) is PreparedMemoryToolCall
    assert type(restored_command) is dict
    assert type(restored_command["position"]) is dict
    assert type(restored_command["layer"]) is str


def test_missing_enum_allowlist_entry_degrades_even_inside_restored_dataclasses(
    prepared_call: PreparedMemoryToolCall,
) -> None:
    serializer = create_graph_serializer(
        allowed_types=tuple(cls for cls in MEMORY_TYPES if cls is not MemoryLayer)
    )

    restored = serializer.loads_typed(serializer.dumps_typed(prepared_call))

    assert type(restored) is PreparedMemoryToolCall
    assert type(restored.command) is type(prepared_call.command)
    assert type(restored.command.position) is MemoryBatchPosition
    assert type(restored.command.layer) is str
    assert type(restored.command.position.phase) is str
    # Dataclass equality cannot be used as a validation gate before execute.
    assert restored == prepared_call


def test_explicit_allowlist_does_not_allow_other_classes_in_the_same_module() -> None:
    original = UnregisteredPayload("synthetic")
    before_load = UnregisteredPayload.constructions
    serializer = create_graph_serializer(allowed_types=(PickleOnlyPayload,))

    restored = serializer.loads_typed(serializer.dumps_typed(original))

    assert UnregisteredPayload.constructions == before_load
    assert restored == {"value": "synthetic"}


def test_native_tuple_degrades_to_list_even_when_tuple_is_allowlisted(
    prepared_call: PreparedMemoryToolCall,
) -> None:
    """Pinned 4.2.0 limitation: State must not assume immutable tuple roundtrips."""
    serializer = create_graph_serializer(allowed_types=(*MEMORY_TYPES, tuple))
    original = (prepared_call, (UUID(int=10), prepared_call.command.layer))

    restored = serializer.loads_typed(serializer.dumps_typed(original))

    assert type(restored) is list
    assert type(restored[1]) is list
    assert_same_value_and_type(restored[0], prepared_call)
    assert_same_value_and_type(restored[1][0], UUID(int=10))
    assert_same_value_and_type(restored[1][1], prepared_call.command.layer)


def test_unsupported_objects_fail_without_pickle_fallback() -> None:
    serializer = create_graph_serializer()

    with pytest.raises(TypeError):
        serializer.dumps_typed(PickleOnlyPayload())


def test_pickle_checkpoints_are_not_loaded() -> None:
    serializer = create_graph_serializer()

    with pytest.raises(NotImplementedError, match="Unknown serialization type: pickle"):
        serializer.loads_typed(("pickle", b"N."))
