from __future__ import annotations

import copy
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

from app.consultant.agent import build_professional_consultant_agent
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
    ) -> Any:
        self.calls.append(
            {
                "document_id": document_id,
                "run_id": run_id,
                "files": dict(files),
                "tool_call_id": tool_call_id,
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
        max_model_calls=5,
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
        middleware=(filesystem, WorkspaceToolWaveMiddleware()),
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
    assert not actual.intersection(
        {
            "glob",
            "execute",
            "employee_source_get",
            "employee_source_lineage",
            "employee_source_search",
            "job_document_candidate_edit",
        }
    )


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
    assert "sequential" in str(messages[0].content).casefold()
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
