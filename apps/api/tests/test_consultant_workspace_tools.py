from __future__ import annotations

import copy
import json
from typing import Any, Mapping
from uuid import UUID

import pytest
from deepagents.backends import StateBackend
from deepagents.backends.utils import create_file_data
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.prebuilt import ToolRuntime
from pydantic import PrivateAttr

from app.consultant.agent import (
    ProfessionalConsultantAgent,
    build_professional_consultant_agent,
)
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    RunPolicy,
    resolve_execution,
)
from app.consultant.state import ApprovedDuty, ApprovedJobDocument, ApprovedTask
from app.consultant.workspace_backend import (
    ConsultantWorkspaceBackendBinding,
    build_consultant_workspace_backend,
)
from app.consultant.workspace_resources import WorkspaceCatalog
from app.consultant.workspace_tools import (
    CandidateCheckToolBinding,
    WorkspaceToolWaveMiddleware,
    build_check_candidate_document_tool,
)


EXPECTED_WORKSPACE_TOOLS = frozenset(
    {
        "ls",
        "read_file",
        "grep",
        "write_file",
        "edit_file",
        "delete",
        "check_candidate_document",
    }
)
DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000101")
RUN_ID = UUID("00000000-0000-0000-0000-000000000102")
OTHER_RUN_ID = UUID("00000000-0000-0000-0000-000000000103")
DUTY_ID = UUID("00000000-0000-0000-0000-000000000201")
TASK_ID = UUID("00000000-0000-0000-0000-000000000202")


class RecordingCheckPort:
    def __init__(self, result: Any | None = None) -> None:
        self.result = result or {
            "status": "checked",
            "candidate_revision": 1,
            "revision_digest": "a" * 64,
            "action_ids": ["action-001"],
            "actions": [],
        }
        self.calls: list[dict[str, Any]] = []

    async def check_candidate_document(
        self,
        *,
        document_id: UUID,
        run_id: UUID,
        files: Mapping[str, str],
        tool_call_id: str,
        selected_skill_ids: tuple[str, ...],
        loaded_skill_ids: tuple[str, ...],
    ) -> Any:
        self.calls.append(
            {
                "document_id": document_id,
                "run_id": run_id,
                "files": dict(files),
                "tool_call_id": tool_call_id,
                "selected_skill_ids": selected_skill_ids,
                "loaded_skill_ids": loaded_skill_ids,
            }
        )
        return self.result


def _workspace_binding() -> ConsultantWorkspaceBackendBinding:
    document = ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        job_title="採購專員",
        work_description="管理採購流程。",
        competency_level=5,
        duties=(ApprovedDuty(duty_id=DUTY_ID, statement="管理採購作業", display_order=0),),
        tasks=(
            ApprovedTask(
                task_id=TASK_ID,
                duty_id=DUTY_ID,
                statement="整理需求",
                action="整理",
                object="採購需求",
                display_order=0,
                competency_level=4,
            ),
        ),
    )
    catalog = WorkspaceCatalog.from_snapshot(document)
    return build_consultant_workspace_backend(
        runtime=object(),  # type: ignore[arg-type] - source projection is not used here
        document_id=DOCUMENT_ID,
        run_id=RUN_ID,
        catalog=catalog,
        selected_skill_ids=("output",),
    )


def _execution() -> Any:
    profile = ConsultantModelProfile(
        profile_id="primary-consultant",
        revision=1,
        requested_model="anthropic/claude-opus-5",
        provider_allowlist=("Anthropic",),
        temperature=0.2,
        max_output_tokens=4096,
    )
    policy = RunPolicy(
        policy_id="interactive-consultation",
        revision=1,
        run_kind="interactive_consultation",
        allowed_skill_ids=("output",),
        allowed_tool_ids=tuple(EXPECTED_WORKSPACE_TOOLS),
        max_context_tokens=24_000,
        max_model_calls=8,
        max_lookup_waves=2,
        max_total_tool_calls=12,
        model_retry_count=0,
        tool_retry_count=0,
        max_elapsed_seconds=180,
        max_total_tokens=32_000,
        max_cost_usd=None,
    )
    return resolve_execution(profile, policy)


def _tool_call(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


class WaveModel(FakeMessagesListChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> WaveModel:
        del tools, kwargs
        return self


class ProviderBindingModel(FakeMessagesListChatModel):
    _bound_tool_schemas: list[dict[str, Any]] = PrivateAttr(default_factory=list)

    @property
    def bound_tool_schemas(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._bound_tool_schemas)

    def bind_tools(self, tools: Any, **kwargs: Any) -> ProviderBindingModel:
        del kwargs
        self._bound_tool_schemas = [convert_to_openai_tool(tool) for tool in tools]
        return self

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> Any:
        del messages, stop, run_manager, kwargs
        raise RuntimeError("stop after real provider binding")


def _walk_schema(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_schema(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_schema(value)


def _schema_tree_depth(node: Any) -> int:
    if isinstance(node, dict):
        return 1 + max((_schema_tree_depth(value) for value in node.values()), default=0)
    if isinstance(node, list):
        return max((_schema_tree_depth(value) for value in node), default=0)
    return 0


def _provider_schema_metrics(tool_schema: dict[str, Any]) -> dict[str, int]:
    parameters = tool_schema["function"]["parameters"]
    nodes = tuple(_walk_schema(parameters))
    objects = tuple(node for node in nodes if node.get("type") == "object")
    return {
        "properties": sum(len(node.get("properties", {})) for node in objects),
        "optional": sum(
            len(set(node.get("properties", {})) - set(node.get("required", ())))
            for node in objects
        ),
        "unions": sum("anyOf" in node or "oneOf" in node for node in nodes),
        "open_objects": sum(
            node.get("additionalProperties") is not False for node in objects
        ),
        "depth": _schema_tree_depth(parameters),
        "bytes": len(
            json.dumps(parameters, ensure_ascii=False, separators=(",", ":")).encode()
        ),
    }


async def _run_workspace_wave(
    workspace: ConsultantWorkspaceBackendBinding,
    calls: list[dict[str, Any]],
    *,
    check_tool: Any | None = None,
) -> dict[str, Any]:
    filesystem = FilesystemMiddleware(
        backend=workspace.composite_backend,
        tools=["ls", "read_file", "grep", "write_file", "edit_file", "delete"],
        system_prompt=None,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
        grep_max_count=None,
    )
    model = WaveModel(
        responses=[
            AIMessage(content="", tool_calls=calls),
            AIMessage(content="wave complete"),
        ]
    )
    graph = create_agent(
        model=model,
        tools=([check_tool] if check_tool is not None else []),
        middleware=(
            filesystem,
            WorkspaceToolWaveMiddleware(
                candidate_backend=workspace.candidate_backend
            ),
        ),
    )
    return await graph.ainvoke(
        {
            "messages": [HumanMessage(content="edit the candidate")],
            "files": copy.deepcopy(workspace.initial_files),
        }
    )


def _tool_messages(result: Mapping[str, Any]) -> list[ToolMessage]:
    return [
        message
        for message in result["messages"]
        if isinstance(message, ToolMessage)
    ]


def _candidate_text(result: Mapping[str, Any], path: str) -> str:
    return str(result["files"][path]["content"])


def test_check_tool_has_empty_model_schema_and_no_document_payload() -> None:
    workspace = _workspace_binding()
    check_tool = build_check_candidate_document_tool(
        binding=CandidateCheckToolBinding(
            runtime=RecordingCheckPort(),
            workspace=workspace,
        )
    )

    assert check_tool.name == "check_candidate_document"
    schema = check_tool.tool_call_schema.model_json_schema()
    assert schema["properties"] == {}
    assert schema.get("required", []) == []
    assert schema.get("additionalProperties") is False
    converted = convert_to_openai_tool(check_tool)
    assert converted["function"]["parameters"]["properties"] == {}
    schema_text = str(converted["function"]["parameters"])
    assert all(
        forbidden not in schema_text
        for forbidden in ("document_id", "run_id", "files", "runtime")
    )
    assert check_tool.func is None
    assert check_tool.coroutine is not None


@pytest.mark.asyncio
async def test_real_consultant_provider_binding_captures_exact_workspace_tools_and_metrics() -> None:
    workspace = _workspace_binding()
    model = ProviderBindingModel(responses=[])
    agent = build_professional_consultant_agent(
        model=model,
        execution=_execution(),
        selected_skill_ids=("output",),
        workspace_binding=workspace,
        candidate_check_binding=CandidateCheckToolBinding(
            runtime=RecordingCheckPort(),
            workspace=workspace,
        ),
    )

    with pytest.raises(RuntimeError, match="stop after real provider binding"):
        await agent.ainvoke(
            {
                "messages": [HumanMessage(content="inspect the candidate")],
                "files": copy.deepcopy(workspace.initial_files),
            }
        )

    captured = model.bound_tool_schemas
    assert len(captured) == 7
    captured_names = [schema["function"]["name"] for schema in captured]
    assert len(set(captured_names)) == len(captured_names)
    converted = {schema["function"]["name"]: schema for schema in captured}
    assert set(converted) == EXPECTED_WORKSPACE_TOOLS
    assert {
        name: _provider_schema_metrics(converted[name])
        for name in sorted(converted)
    } == {
        "ls": {"properties": 1, "optional": 0, "unions": 0, "open_objects": 1, "depth": 3, "bytes": 165},
        "read_file": {"properties": 3, "optional": 2, "unions": 0, "open_objects": 1, "depth": 3, "bytes": 433},
        "write_file": {"properties": 2, "optional": 0, "unions": 0, "open_objects": 1, "depth": 3, "bytes": 304},
        "edit_file": {"properties": 4, "optional": 1, "unions": 0, "open_objects": 1, "depth": 3, "bytes": 613},
        "delete": {"properties": 1, "optional": 0, "unions": 0, "open_objects": 1, "depth": 3, "bytes": 172},
        "grep": {"properties": 5, "optional": 4, "unions": 3, "open_objects": 1, "depth": 4, "bytes": 1598},
        "check_candidate_document": {"properties": 0, "optional": 0, "unions": 0, "open_objects": 0, "depth": 2, "bytes": 62},
    }
    assert converted["check_candidate_document"]["function"]["parameters"]["properties"] == {}


def test_workspace_agent_surface_has_only_framework_editor_verbs_and_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace_binding()
    check_binding = CandidateCheckToolBinding(
        runtime=RecordingCheckPort(),
        workspace=workspace,
    )
    captured: dict[str, Any] = {}

    def capture_agent(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.consultant.agent.build_consultant_agent", capture_agent)
    build_professional_consultant_agent(
        model=WaveModel(responses=[AIMessage(content="unused")]),
        execution=_execution(),
        selected_skill_ids=("output",),
        workspace_binding=workspace,
        candidate_check_binding=check_binding,
    )

    actual = {
        *(tool.name for tool in captured["tools"]),
        *(
            tool.name
            for middleware in captured["additional_middleware"]
            for tool in getattr(middleware, "tools", ())
        ),
    }
    assert actual == EXPECTED_WORKSPACE_TOOLS
    assert "glob" not in actual
    assert "execute" not in actual


def test_workspace_agent_sync_invoke_fails_fast() -> None:
    workspace = _workspace_binding()

    class SyncGraph:
        def invoke(self, *args: Any, **kwargs: Any) -> str:
            del args, kwargs
            return "sync result"

    workspace_agent = ProfessionalConsultantAgent(
        graph=SyncGraph(),
        skill_backend=workspace.skill_backend,
        workspace_binding=workspace,
    )
    with pytest.raises(RuntimeError, match="async-only"):
        workspace_agent.invoke({"messages": []})


@pytest.mark.asyncio
async def test_check_tool_uses_hidden_runtime_and_current_files_channel() -> None:
    workspace = _workspace_binding()
    port = RecordingCheckPort()
    check_tool = build_check_candidate_document_tool(
        binding=CandidateCheckToolBinding(runtime=port, workspace=workspace)
    )
    header_path = f"/candidate/{RUN_ID}/header.json"
    current_files = copy.deepcopy(workspace.initial_files)
    current_files[header_path]["content"] = "{\"job_title\":\"更新後\"}\n"

    result = await _run_workspace_wave(
        workspace,
        [_tool_call("check_candidate_document", {}, "check-001")],
        check_tool=check_tool,
    )

    assert [message.status for message in _tool_messages(result)] == ["success"]
    # The wave helper uses the initial state; the direct runtime invocation below
    # proves that the Tool reads the framework's current files channel, not the
    # binding's initial snapshot.
    runtime = ToolRuntime(
        state={"files": current_files},
        context={},
        config={},
        stream_writer=lambda _value: None,
        tool_call_id="check-002",
        store=None,
    )
    await check_tool.coroutine(runtime=runtime)  # type: ignore[misc]
    assert port.calls[-1]["tool_call_id"] == "check-002"
    assert port.calls[-1]["files"][header_path] == "{\"job_title\":\"更新後\"}\n"
    assert port.calls[-1]["selected_skill_ids"] == workspace.skill_backend.selected_skill_ids
    assert port.calls[-1]["loaded_skill_ids"] == workspace.skill_backend.loaded_skill_ids


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_path",
    [
        f"/candidate/{RUN_ID}/../{OTHER_RUN_ID}/header.json",
        f"/candidate/{RUN_ID}/./header.json",
        f"/candidate//{RUN_ID}/header.json",
        f"/candidate/{RUN_ID}\\header.json",
        f"/candidate/{RUN_ID}/not-a-resource.json",
        f"/candidate/{OTHER_RUN_ID}/header.json",
    ],
)
async def test_check_rejects_noncanonical_or_invalid_state_keys_before_port_call(
    invalid_path: str,
) -> None:
    workspace = _workspace_binding()
    port = RecordingCheckPort()
    check_tool = build_check_candidate_document_tool(
        binding=CandidateCheckToolBinding(runtime=port, workspace=workspace)
    )
    header_path = f"/candidate/{RUN_ID}/header.json"
    runtime = ToolRuntime(
        state={
            "files": {
                invalid_path: copy.deepcopy(workspace.initial_files[header_path]),
            }
        },
        context={},
        config={},
        stream_writer=lambda _value: None,
        tool_call_id="check-invalid-path",
        store=None,
    )

    with pytest.raises(RuntimeError, match="candidate"):
        await check_tool.coroutine(runtime=runtime)  # type: ignore[misc]
    assert port.calls == []


@pytest.mark.asyncio
async def test_parallel_reads_in_one_real_framework_wave_succeed() -> None:
    workspace = _workspace_binding()
    header_path = f"/candidate/{RUN_ID}/header.json"
    task_path = f"/candidate/{RUN_ID}/tasks/task-001.json"

    result = await _run_workspace_wave(
        workspace,
        [
            _tool_call("read_file", {"file_path": header_path}, "read-001"),
            _tool_call("read_file", {"file_path": task_path}, "read-002"),
        ],
    )

    messages = _tool_messages(result)
    assert [message.status for message in messages] == ["success", "success"]


@pytest.mark.asyncio
async def test_disjoint_edits_in_one_real_framework_wave_succeed() -> None:
    workspace = _workspace_binding()
    header_path = f"/candidate/{RUN_ID}/header.json"
    task_path = f"/candidate/{RUN_ID}/tasks/task-001.json"
    original_header = workspace.initial_files[header_path]["content"]
    original_task = workspace.initial_files[task_path]["content"]

    result = await _run_workspace_wave(
        workspace,
        [
            _tool_call(
                "edit_file",
                {
                    "file_path": header_path,
                    "old_string": "採購專員",
                    "new_string": "資深採購專員",
                },
                "edit-001",
            ),
            _tool_call(
                "edit_file",
                {
                    "file_path": task_path,
                    "old_string": "整理需求",
                    "new_string": "分析採購需求",
                },
                "edit-002",
            ),
        ],
    )

    messages = _tool_messages(result)
    assert [message.status for message in messages] == ["success", "success"]
    assert _candidate_text(result, header_path) != original_header
    assert _candidate_text(result, task_path) != original_task


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "alias_path",
    [
        f"/candidate/{RUN_ID}/./header.json",
        f"/candidate//{RUN_ID}/header.json",
        f"/candidate/{RUN_ID}\\header.json",
    ],
)
async def test_framework_canonical_aliases_to_same_file_reject_the_entire_wave(
    alias_path: str,
) -> None:
    workspace = _workspace_binding()
    canonical_path = f"/candidate/{RUN_ID}/header.json"
    original_header = workspace.initial_files[canonical_path]["content"]

    result = await _run_workspace_wave(
        workspace,
        [
            _tool_call(
                "edit_file",
                {
                    "file_path": alias_path,
                    "old_string": "採購專員",
                    "new_string": "別名修改",
                },
                "alias-001",
            ),
            _tool_call(
                "edit_file",
                {
                    "file_path": canonical_path,
                    "old_string": "採購專員",
                    "new_string": "正規修改",
                },
                "alias-002",
            ),
        ],
    )

    messages = _tool_messages(result)
    assert [message.status for message in messages] == ["error", "error"]
    assert _candidate_text(result, canonical_path) == original_header


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_path",
    [
        f"/candidate/{OTHER_RUN_ID}/header.json",
        f"/candidate/{RUN_ID}/not-a-resource.json",
    ],
)
async def test_cross_run_or_invalid_resource_mutation_rejects_sibling_before_zero_mutation(
    invalid_path: str,
) -> None:
    workspace = _workspace_binding()
    header_path = f"/candidate/{RUN_ID}/header.json"
    task_path = f"/candidate/{RUN_ID}/tasks/task-001.json"
    original_header = workspace.initial_files[header_path]["content"]
    original_task = workspace.initial_files[task_path]["content"]

    result = await _run_workspace_wave(
        workspace,
        [
            _tool_call(
                "edit_file",
                {
                    "file_path": invalid_path,
                    "old_string": "採購專員",
                    "new_string": "不應套用",
                },
                "invalid-001",
            ),
            _tool_call(
                "edit_file",
                {
                    "file_path": task_path,
                    "old_string": "整理需求",
                    "new_string": "不應套用",
                },
                "invalid-002",
            ),
        ],
    )

    messages = _tool_messages(result)
    assert [message.status for message in messages] == ["error", "error"]
    assert _candidate_text(result, header_path) == original_header
    assert _candidate_text(result, task_path) == original_task


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_args",
    [
        {
            "old_string": "採購專員",
            "new_string": "不應套用",
        },
        {
            "file_path": "",
            "old_string": "採購專員",
            "new_string": "不應套用",
        },
        {
            "file_path": "../candidate/outside/header.json",
            "old_string": "採購專員",
            "new_string": "不應套用",
        },
    ],
)
async def test_unvalidated_mutation_path_rejects_every_call_before_valid_sibling(
    bad_args: dict[str, Any],
) -> None:
    workspace = _workspace_binding()
    header_path = f"/candidate/{RUN_ID}/header.json"
    task_path = f"/candidate/{RUN_ID}/tasks/task-001.json"
    original_header = workspace.initial_files[header_path]["content"]
    original_task = workspace.initial_files[task_path]["content"]

    result = await _run_workspace_wave(
        workspace,
        [
            _tool_call("edit_file", bad_args, "missing-or-invalid-001"),
            _tool_call(
                "edit_file",
                {
                    "file_path": task_path,
                    "old_string": "整理需求",
                    "new_string": "不應套用",
                },
                "missing-or-invalid-002",
            ),
        ],
    )

    messages = _tool_messages(result)
    assert [message.status for message in messages] == ["error", "error"]
    assert _candidate_text(result, header_path) == original_header
    assert _candidate_text(result, task_path) == original_task


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "calls",
    [
        [
            _tool_call(
                "edit_file",
                {
                    "file_path": f"/candidate/{RUN_ID}/header.json",
                    "old_string": "採購專員",
                    "new_string": "甲",
                },
                "same-001",
            ),
            _tool_call(
                "edit_file",
                {
                    "file_path": f"/candidate/{RUN_ID}/header.json",
                    "old_string": "採購專員",
                    "new_string": "乙",
                },
                "same-002",
            ),
        ],
        [
            _tool_call(
                "write_file",
                {
                    "file_path": f"/candidate/{RUN_ID}/tasks",
                    "content": "invalid ancestor mutation",
                },
                "ancestor-001",
            ),
            _tool_call(
                "write_file",
                {
                    "file_path": f"/candidate/{RUN_ID}/tasks/task-002.json",
                    "content": "{}",
                },
                "ancestor-002",
            ),
        ],
    ],
)
async def test_overlapping_mutation_wave_rejects_every_call_before_mutation(
    calls: list[dict[str, Any]],
) -> None:
    workspace = _workspace_binding()
    header_path = f"/candidate/{RUN_ID}/header.json"
    original_header = workspace.initial_files[header_path]["content"]

    result = await _run_workspace_wave(workspace, calls)

    messages = _tool_messages(result)
    assert [message.status for message in messages] == ["error", "error"]
    assert len({str(message.content) for message in messages}) == 1
    assert _candidate_text(result, header_path) == original_header
    new_path = f"/candidate/{RUN_ID}/tasks/task-002.json"
    assert new_path not in result["files"]


@pytest.mark.asyncio
async def test_mutation_and_check_in_one_wave_reject_both_before_zero_mutation() -> None:
    workspace = _workspace_binding()
    port = RecordingCheckPort()
    check_tool = build_check_candidate_document_tool(
        binding=CandidateCheckToolBinding(runtime=port, workspace=workspace)
    )
    header_path = f"/candidate/{RUN_ID}/header.json"
    original_header = workspace.initial_files[header_path]["content"]

    result = await _run_workspace_wave(
        workspace,
        [
            _tool_call(
                "edit_file",
                {
                    "file_path": header_path,
                    "old_string": "採購專員",
                    "new_string": "不應套用",
                },
                "mutation-001",
            ),
            _tool_call("check_candidate_document", {}, "check-001"),
        ],
        check_tool=check_tool,
    )

    messages = _tool_messages(result)
    assert [message.status for message in messages] == ["error", "error"]
    assert len({str(message.content) for message in messages}) == 1
    assert "check_candidate_document" in str(messages[0].content)
    assert _candidate_text(result, header_path) == original_header
    assert port.calls == []
