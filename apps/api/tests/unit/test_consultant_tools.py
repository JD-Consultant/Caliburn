"""Role routing preserves observations and checkpoints only bound JD write commands."""

import json
from uuid import UUID, uuid4

import pytest
from openai.types.responses import ResponseFunctionToolCall
from pydantic import ValidationError

from caliburn.agents.job_consultant.tools import (
    CONSULTANT_MEMORY_READ_NAMES,
    ConsultantTools,
    consultant_tool_definitions,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.models import ProfileField, SetProfileField
from caliburn.features.job_description.tasks import CreateTask
from caliburn.transport.model_tools.context_compaction import ContextCompactionTools
from caliburn.transport.model_tools.contracts import reject_tool_call
from caliburn.transport.model_tools.jd_changes import JdChangesTools
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.transport.model_tools.jd_writes import JdWriteTools, PreparedJdWrite
from caliburn.transport.model_tools.memory_consolidation import MemoryConsolidationTools
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.workflows.jd_profile_writes import PreparedProfileWrite
from caliburn.workflows.jd_task_writes import PreparedTaskWrite


class FakeMemoryReadTools(MemoryReadTools):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    @property
    def names(self) -> tuple[str, ...]:
        return CONSULTANT_MEMORY_READ_NAMES

    async def invoke(self, name: str, arguments: str) -> str:
        self.calls.append((name, arguments))
        return f"Memory observation: {name} {arguments}"


class FakeJdReadTools(JdReadTools):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def invoke(self, name: str, arguments: str) -> str:
        self.calls.append((name, arguments))
        return "# JD\n原樣保留完整讀取結果。"


class FakeJdChangesTools(JdChangesTools):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def invoke(self, name: str, arguments: str) -> str:
        self.calls.append((name, arguments))
        return "# JD 差異\n尚未核對。"


class FakeJdWriteTools(JdWriteTools):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, UUID]] = []
        self.commands: list[PreparedJdWrite] = []
        self.executed: list[PreparedJdWrite] = []
        self.rejection: str | None = None

    async def prepare(self, name: str, arguments: str, command_id: UUID) -> PreparedJdWrite | str:
        self.calls.append((name, arguments, command_id))
        if self.rejection is not None:
            return self.rejection
        candidate = JdCandidateScope(uuid4(), uuid4())
        if name == "revise_jd_profile":
            prepared: PreparedJdWrite = PreparedProfileWrite(
                command_id,
                candidate,
                uuid4(),
                (SetProfileField(ProfileField.JOB_TITLE, "前端工程師"),),
                (),
            )
        else:
            prepared = PreparedTaskWrite(
                command_id,
                candidate,
                uuid4(),
                CreateTask(None, "盤點", None, (), ()),
                (),
                (),
                (),
            )
        self.commands.append(prepared)
        return prepared

    async def execute(self, prepared: PreparedJdWrite) -> str:
        self.executed.append(prepared)
        return (
            "updated"
            if isinstance(prepared, PreparedProfileWrite)
            else "created · read_ref: task_x"
        )


class FakeConsolidationTools(MemoryConsolidationTools):
    def __init__(self) -> None:
        self.prepared_ids = []

    def prepare(self, arguments, command_id):
        self.prepared_ids.append(command_id)
        return {"kind": "memory_consolidation", "command_id": str(command_id)}

    async def execute(self, prepared):
        return "request recorded"


class FakeCompactionTools(ContextCompactionTools):
    def __init__(self) -> None:
        pass


type Handlers = tuple[ConsultantTools, FakeMemoryReadTools, FakeJdReadTools, FakeJdWriteTools]


@pytest.fixture
def handlers() -> Handlers:
    memory, reads, writes = FakeMemoryReadTools(), FakeJdReadTools(), FakeJdWriteTools()
    return (
        ConsultantTools(
            memory,
            reads,
            writes,
            FakeJdChangesTools(),
            FakeConsolidationTools(),
            FakeCompactionTools(),
        ),
        memory,
        reads,
        writes,
    )


def native_call(name: str, arguments: str = "{}") -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        type="function_call",
        id="fc_provider_item",
        call_id="call_provider_identity",
        name=name,
        arguments=arguments,
    )


def test_definitions_can_be_built_before_binding_and_match_the_bound_handlers(
    handlers: Handlers,
) -> None:
    definitions = consultant_tool_definitions()
    assert tuple(item["name"] for item in definitions) == (
        "read_work_situation_map",
        "read_work_situation",
        "read_work_understanding_map",
        "read_work_understanding",
        "read_interview",
        "read_jd",
        "read_jd_changes",
        "revise_jd_profile",
        "create_jd_task",
        "create_jd_item",
        "revise_jd_item",
        "delete_jd_item",
        "move_jd_item",
        "request_memory_consolidation",
        "request_context_compaction",
    )
    tools, _, _, _ = handlers
    assert definitions == tools.definitions()


def test_advertises_existing_definitions_and_names_without_rewriting(handlers: Handlers) -> None:
    tools, memory, reads, writes = handlers
    expected = [
        *memory.definitions(),
        *reads.definitions(),
        *tools.jd_changes.definitions(),
        *writes.definitions(),
        *tools.consolidation.definitions(),
        *tools.compaction.definitions(),
    ]
    assert tools.definitions() == expected
    assert tools.names == (
        *memory.names,
        *reads.names,
        *tools.jd_changes.names,
        *writes.names,
        *tools.consolidation.names,
        *tools.compaction.names,
    )
    assert tuple(definition["name"] for definition in tools.definitions()) == tools.names


@pytest.mark.parametrize(
    "name",
    [
        "read_work_situation_map",
        "read_work_situation",
        "read_work_understanding_map",
        "read_work_understanding",
        "read_interview",
        "read_jd",
    ],
)
async def test_read_returns_the_selected_handlers_observation_without_preparing_a_write(
    handlers: Handlers, name: str
) -> None:
    tools, memory, reads, writes = handlers
    call = native_call(name, '{"selection":"原參數"}')
    output = await tools.prepare(call, uuid4())
    if name == "read_jd":
        assert output == "# JD\n原樣保留完整讀取結果。"
        assert reads.calls == [(name, call.arguments)]
        assert memory.calls == []
    else:
        assert output == f"Memory observation: {name} {call.arguments}"
        assert memory.calls == [(name, call.arguments)]
        assert reads.calls == []
    assert writes.calls == writes.executed == []


async def test_diff_is_a_read_observation_not_a_write_or_alignment(handlers: Handlers) -> None:
    tools, memory, reads, writes = handlers
    assert await tools.prepare(native_call("read_jd_changes", "{}"), uuid4()) == (
        "# JD 差異\n尚未核對。"
    )
    assert memory.calls == reads.calls == writes.calls == writes.executed == []


async def test_notification_is_saved_before_dispatch_without_entering_jd_writer(handlers):
    tools, memory, reads, writes = handlers
    prepared = await tools.prepare(native_call("request_memory_consolidation"), uuid4())
    assert isinstance(prepared, dict)
    assert prepared["kind"] == "memory_consolidation"
    assert await tools.execute(prepared) == "request recorded"
    assert memory.calls == reads.calls == writes.calls == writes.executed == []


@pytest.mark.parametrize(
    ("name", "kind", "result"),
    [
        ("revise_jd_profile", "profile", "updated"),
        ("create_jd_task", "task", "created · read_ref: task_x"),
    ],
)
async def test_write_uses_app_operation_identity_and_waits_for_saved_command_execution(
    handlers: Handlers, name: str, kind: str, result: str
) -> None:
    tools, memory, reads, writes = handlers
    call = native_call(name, '{"intent":"unchanged wire"}')
    operation_id = uuid4()
    saved = await tools.prepare(call, operation_id)
    assert isinstance(saved, dict)
    assert saved["kind"] == kind
    assert isinstance(saved["payload"], str)
    assert json.loads(saved["payload"])["command_id"] == str(operation_id)
    assert writes.calls == [(name, call.arguments, operation_id)]
    assert writes.executed == []
    assert memory.calls == reads.calls == []
    assert call.call_id == "call_provider_identity"
    assert await tools.execute(json.loads(json.dumps(saved))) == result
    assert writes.executed == writes.commands


async def test_write_rejection_is_a_direct_observation_not_an_executable_command(
    handlers: Handlers,
) -> None:
    tools, _, _, writes = handlers
    writes.rejection = reject_tool_call("invalid_arguments", "無效選取", "修正原參數")
    assert await tools.prepare(native_call("revise_jd_profile"), uuid4()) == writes.rejection
    assert writes.executed == []


async def test_unknown_tool_is_rejected_without_dispatching_any_handler(handlers: Handlers) -> None:
    tools, memory, reads, writes = handlers
    result = await tools.prepare(native_call("request_background_analysis"), uuid4())
    assert isinstance(result, str)
    rejected = json.loads(result)
    assert rejected["status"] == "rejected" and rejected["code"] == "scope_not_allowed"
    assert memory.calls == reads.calls == writes.calls == writes.executed == []


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        "updated",
        {"kind": "unknown", "payload": "{}"},
        {"kind": "profile", "payload": '{"command_id":"not-a-uuid"}'},
        {"kind": "task", "payload": "{}", "extra": True},
    ],
)
async def test_malformed_checkpoint_is_rejected_before_write_dispatch(
    handlers: Handlers, malformed: object
) -> None:
    tools, _, _, writes = handlers
    with pytest.raises(ValidationError):
        await tools.execute(malformed)
    assert writes.executed == []
