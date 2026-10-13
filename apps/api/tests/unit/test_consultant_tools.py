"""Role routing preserves observations and checkpoints only bound JD write commands."""

import json
from uuid import UUID, uuid4

import pytest
from openai.types.responses import ResponseFunctionToolCall

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agents.job_consultant.interview_plan_context import has_interview_plan_tools
from caliburn.agents.job_consultant.tools import (
    CONSULTANT_MEMORY_READ_NAMES,
    ConsultantTools,
    consultant_tool_definitions,
)
from caliburn.features.executions.models import ExecutionStateError
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.compound_edits import (
    CreateTaskWithSources,
    ReviseProfileWithSources,
)
from caliburn.features.job_description.models import ProfileField, SetProfileField
from caliburn.features.job_description.tasks import CreateTask
from caliburn.transport.model_tools.context_compaction import ContextCompactionTools
from caliburn.transport.model_tools.contracts import reject_tool_call
from caliburn.transport.model_tools.interview_plans import InterviewPlanTools
from caliburn.transport.model_tools.jd_changes import JdChangesTools
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.transport.model_tools.jd_writes import JdWriteTools, PreparedJdWrite
from caliburn.transport.model_tools.memory_consolidation import MemoryConsolidationTools
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.workflows.job_description.compound_writes import PreparedJdEdit
from tests.fixtures.native_tools import ensure_active, invoke_tool


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
        candidate = JdCandidateScope(uuid4())
        if name == "revise_jd_profile":
            prepared: PreparedJdWrite = PreparedJdEdit(
                candidate,
                ReviseProfileWithSources(
                    command_id,
                    uuid4(),
                    (SetProfileField(ProfileField.JOB_TITLE, "前端工程師"),),
                    (),
                ),
            )
        else:
            prepared = PreparedJdEdit(
                candidate,
                CreateTaskWithSources(
                    command_id, uuid4(), CreateTask(None, "盤點", None, (), ()), (), ()
                ),
            )
        self.commands.append(prepared)
        return prepared

    async def execute(self, prepared: PreparedJdWrite) -> str:
        self.executed.append(prepared)
        return (
            "updated"
            if isinstance(prepared.command, ReviseProfileWithSources)
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
    definitions = consultant_tool_definitions(interview_plans_enabled=False)
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
    registered = tools.standard_tools(ensure_active)
    assert [(tool.name, tool.args_schema) for tool in registered] == [
        (definition["name"], definition["parameters"]) for definition in definitions
    ]


def test_new_consultant_template_advertises_minimal_plan_read_and_edit_tools() -> None:
    definitions = {tool["name"]: tool for tool in consultant_tool_definitions()}
    assert "read_interview_plan" in definitions
    assert "edit_interview_plan" in definitions
    assert definitions["read_interview_plan"]["parameters"]["properties"] == {}
    edit = definitions["edit_interview_plan"]["parameters"]
    assert set(edit["properties"]) == {"diff"}
    assert edit["required"] == ["diff"]


@pytest.fixture
def captured_plan_request() -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="Captured plan capability contract",
        input_items=[],
        tools=consultant_tool_definitions(),
        reasoning_effort="high",
        max_output_tokens=64,
    )


def test_saved_plan_schema_accepts_original_bundle_and_annotation_changes(
    captured_plan_request: ResponseRequest,
) -> None:
    assert has_interview_plan_tools(captured_plan_request) is True
    snapshot = captured_plan_request.create_payload()
    for tool in snapshot["tools"]:
        if tool["name"] in {"read_interview_plan", "edit_interview_plan"}:
            tool["description"] = "An original captured description"
            tool["parameters"]["title"] = "An original captured title"
            tool["parameters"]["description"] = "An original schema annotation"
            if tool["name"] == "edit_interview_plan":
                tool["parameters"]["properties"]["diff"]["description"] = "Original diff wording"
    assert has_interview_plan_tools(ResponseRequest.from_snapshot(snapshot)) is True


@pytest.mark.parametrize(
    ("constraint", "saved_value"),
    [
        pytest.param("minLength", True, id="min-length-boolean"),
        pytest.param("minLength", 1.0, id="min-length-float"),
        pytest.param("maxLength", 16_000.0, id="max-length-float"),
    ],
)
def test_saved_plan_schema_preserves_numeric_constraint_types(
    captured_plan_request: ResponseRequest, constraint: str, saved_value: object
) -> None:
    snapshot = captured_plan_request.create_payload()
    edit = next(tool for tool in snapshot["tools"] if tool["name"] == "edit_interview_plan")
    edit["parameters"]["properties"]["diff"][constraint] = saved_value

    with pytest.raises(ExecutionStateError, match="interview plan schema"):
        has_interview_plan_tools(ResponseRequest.from_snapshot(snapshot))


@pytest.mark.parametrize("tool_name", ["read_interview_plan", "edit_interview_plan"])
@pytest.mark.parametrize("saved_value", [0, 0.0, "false", None])
def test_saved_plan_schema_requires_boolean_additional_properties(
    captured_plan_request: ResponseRequest, tool_name: str, saved_value: object
) -> None:
    snapshot = captured_plan_request.create_payload()
    tool = next(tool for tool in snapshot["tools"] if tool["name"] == tool_name)
    tool["parameters"]["additionalProperties"] = saved_value

    with pytest.raises(ExecutionStateError, match="interview plan schema"):
        has_interview_plan_tools(ResponseRequest.from_snapshot(snapshot))


@pytest.mark.parametrize("tool_name", ["read_interview_plan", "edit_interview_plan"])
@pytest.mark.parametrize("saved_value", [1, 1.0])
def test_saved_plan_schema_requires_boolean_strict_mode(
    captured_plan_request: ResponseRequest, tool_name: str, saved_value: object
) -> None:
    snapshot = captured_plan_request.create_payload()
    tool = next(tool for tool in snapshot["tools"] if tool["name"] == tool_name)
    tool["strict"] = saved_value

    with pytest.raises(ExecutionStateError, match="interview plan schema"):
        has_interview_plan_tools(ResponseRequest.from_snapshot(snapshot))


@pytest.mark.parametrize(
    ("tool_name", "on_diff", "constraint", "saved_value"),
    [
        pytest.param("read_interview_plan", False, "minProperties", 1, id="read-needs-property"),
        pytest.param("edit_interview_plan", False, "maxProperties", 0, id="edit-forbids-property"),
        pytest.param("edit_interview_plan", True, "pattern", "^allowed-only$", id="diff-pattern"),
    ],
)
def test_saved_plan_schema_rejects_additional_assertions_that_change_tool_arguments(
    captured_plan_request: ResponseRequest,
    tool_name: str,
    on_diff: bool,
    constraint: str,
    saved_value: object,
) -> None:
    snapshot = captured_plan_request.create_payload()
    tool = next(tool for tool in snapshot["tools"] if tool["name"] == tool_name)
    schema = tool["parameters"]["properties"]["diff"] if on_diff else tool["parameters"]
    schema[constraint] = saved_value

    with pytest.raises(ExecutionStateError, match="interview plan schema"):
        has_interview_plan_tools(ResponseRequest.from_snapshot(snapshot))


def test_advertises_existing_definitions_without_rewriting(handlers: Handlers) -> None:
    tools, memory, reads, writes = handlers
    expected = [
        *memory.definitions(),
        *reads.definitions(),
        *tools.jd_changes.definitions(),
        *writes.definitions(),
        *tools.consolidation.definitions(),
        *tools.compaction.definitions(),
    ]
    assert [(tool.name, tool.args_schema) for tool in tools.standard_tools(ensure_active)] == [
        (item["name"], item["parameters"]) for item in expected
    ]


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
async def test_standard_read_preserves_original_arguments_and_observation(handlers, name):
    tools, memory, reads, writes = handlers
    call = native_call(name, '{"selection":"原參數"}')
    output, _, _ = await invoke_tool(tools.standard_tools(ensure_active), call)
    if name == "read_jd":
        assert output == "# JD\n原樣保留完整讀取結果。"
        assert reads.calls == [(name, call.arguments)]
        assert memory.calls == []
    else:
        assert output == f"Memory observation: {name} {call.arguments}"
        assert memory.calls == [(name, call.arguments)]
        assert reads.calls == []
    assert writes.calls == writes.executed == []


async def test_diff_is_a_read_observation_not_a_write_or_alignment(handlers):
    tools, memory, reads, writes = handlers
    output, _, _ = await invoke_tool(
        tools.standard_tools(ensure_active), native_call("read_jd_changes")
    )
    assert output == "# JD 差異\n尚未核對。"
    assert memory.calls == reads.calls == writes.calls == writes.executed == []


async def test_notification_uses_standard_prepared_child_without_jd_writer(handlers):
    tools, memory, reads, writes = handlers
    output, prepared, operation_id = await invoke_tool(
        tools.standard_tools(ensure_active),
        native_call("request_memory_consolidation"),
    )
    assert prepared == {"kind": "memory_consolidation", "command_id": str(operation_id)}
    assert output == "request recorded"
    assert memory.calls == reads.calls == writes.calls == writes.executed == []


@pytest.mark.parametrize(
    ("name", "kind", "result"),
    [
        ("revise_jd_profile", "profile", "updated"),
        ("create_jd_task", "task", "created · read_ref: task_x"),
    ],
)
async def test_write_preserves_original_args_operation_identity_and_command_codec(
    handlers, name, kind, result
):
    tools, memory, reads, writes = handlers
    call = native_call(name, '{"intent":"unchanged wire"}')
    output, saved, operation_id = await invoke_tool(tools.standard_tools(ensure_active), call)
    assert saved["kind"] == kind
    assert isinstance(saved["payload"], str)
    assert json.loads(saved["payload"])["command"]["command_id"] == str(operation_id)
    assert writes.calls == [(name, call.arguments, operation_id)]
    assert memory.calls == reads.calls == []
    assert call.call_id == "call_provider_identity"
    assert output == result
    assert writes.executed == writes.commands


async def test_write_rejection_is_a_direct_observation_not_an_executable_command(handlers):
    tools, _, _, writes = handlers
    writes.rejection = reject_tool_call("invalid_arguments", "無效選取", "修正原參數")
    output, prepared, _ = await invoke_tool(
        tools.standard_tools(ensure_active),
        native_call("revise_jd_profile"),
    )
    assert output == prepared == writes.rejection
    assert writes.executed == []


class FakePlanTools(InterviewPlanTools):
    def __init__(self):
        self.calls = []
        self.executed = []

    async def invoke(self, name, arguments):
        self.calls.append((name, arguments))
        return '{"plan":null}'

    async def prepare(self, name, arguments, operation_id):
        self.calls.append((name, arguments, operation_id))
        return {"kind": "interview_plan_edit", "operation_id": str(operation_id)}

    async def execute(self, prepared):
        self.executed.append(prepared)
        return '{"status":"unchanged"}'


async def test_plan_capability_dispatches_read_and_prepared_edit_without_jd_write(handlers):
    tools, memory, reads, writes = handlers
    plans = FakePlanTools()
    tools.interview_plans = plans
    output, _, _ = await invoke_tool(
        tools.standard_tools(ensure_active), native_call("read_interview_plan")
    )
    assert output == '{"plan":null}'
    call = native_call("edit_interview_plan", '{"diff":"original"}')
    output, prepared, operation_id = await invoke_tool(tools.standard_tools(ensure_active), call)
    assert plans.calls == [
        ("read_interview_plan", "{}"),
        ("edit_interview_plan", call.arguments, operation_id),
    ]
    assert output == '{"status":"unchanged"}'
    assert plans.executed == [prepared]
    assert memory.calls == reads.calls == writes.calls == writes.executed == []
