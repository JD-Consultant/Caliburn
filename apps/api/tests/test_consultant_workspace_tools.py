from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping
from uuid import UUID

import pytest
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.prebuilt import ToolRuntime
from langgraph.store.memory import InMemoryStore
from pydantic import PrivateAttr

from app.consultant.agent import (
    ProfessionalConsultantAgent,
    build_professional_consultant_agent,
)
from app.consultant.model_runtime import ConsultantModelProfile, RunPolicy, resolve_execution
from app.consultant.state import ApprovedDuty, ApprovedJobDocument, ApprovedTask
from app.consultant.workspace_backend import (
    ConsultantWorkspaceBackendBinding,
    build_consultant_workspace_backend,
)
from app.consultant.workspace_resources import WorkspaceCatalog
from app.consultant.workspace_state import StoreBackedWorkspace
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
    def __init__(self) -> None:
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
        return {
            "status": "checked",
            "candidate_revision": 1,
            "revision_digest": "a" * 64,
            "action_handles": ["action-001"],
            "actions": [],
        }


def _document() -> ApprovedJobDocument:
    return ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        job_title="採購專員",
        work_description="管理採購流程。",
        competency_level=5,
        duties=(
            ApprovedDuty(
                duty_id=DUTY_ID,
                statement="管理採購作業",
                display_order=0,
            ),
        ),
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


async def _workspace_binding() -> ConsultantWorkspaceBackendBinding:
    document = _document()
    catalog = WorkspaceCatalog.from_snapshot(document)
    workspace = StoreBackedWorkspace(store=InMemoryStore(), document_id=DOCUMENT_ID)
    await workspace.ensure_initialized(
        approved_document=document,
        approved_revision=0,
    )
    return build_consultant_workspace_backend(
        runtime=object(),  # type: ignore[arg-type] - source projection is unused
        document_id=DOCUMENT_ID,
        workspace=workspace,
        catalog=catalog,
        selected_skill_ids=("output",),
    )


def _workspace_binding_sync() -> ConsultantWorkspaceBackendBinding:
    return asyncio.run(_workspace_binding())


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

    def _generate(
        self,
        messages: Any,
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Any:
        del messages, stop, run_manager, kwargs
        raise RuntimeError("stop after real provider binding")


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
    graph = create_agent(
        model=WaveModel(
            responses=[
                AIMessage(content="", tool_calls=calls),
                AIMessage(content="wave complete"),
            ]
        ),
        tools=([check_tool] if check_tool is not None else []),
        middleware=(
            filesystem,
            WorkspaceToolWaveMiddleware(candidate_backend=workspace.workspace_backend),
        ),
    )
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="edit the workspace")]}
    )
    assert result.get("files", {}) == {}
    return result


def _tool_messages(result: Mapping[str, Any]) -> list[ToolMessage]:
    return [
        message for message in result["messages"] if isinstance(message, ToolMessage)
    ]


async def _workspace_text(
    workspace: ConsultantWorkspaceBackendBinding,
    path: str,
) -> str:
    return (await workspace.workspace.read_snapshot()).files[path]


def test_check_tool_has_empty_model_schema_and_no_document_payload() -> None:
    workspace = _workspace_binding_sync()
    check_tool = build_check_candidate_document_tool(
        binding=CandidateCheckToolBinding(
            runtime=RecordingCheckPort(),
            workspace=workspace,
            run_id=RUN_ID,
        )
    )

    schema = check_tool.tool_call_schema.model_json_schema()
    assert schema["properties"] == {}
    assert schema.get("required", []) == []
    assert schema.get("additionalProperties") is False
    converted = convert_to_openai_tool(check_tool)
    assert converted["function"]["parameters"]["properties"] == {}
    assert all(
        forbidden not in str(converted["function"]["parameters"])
        for forbidden in ("document_id", "run_id", "files", "runtime")
    )
    assert check_tool.func is None
    assert check_tool.coroutine is not None


@pytest.mark.asyncio
async def test_real_provider_binding_has_exact_workspace_tool_surface() -> None:
    workspace = await _workspace_binding()
    model = ProviderBindingModel(responses=[])
    agent = build_professional_consultant_agent(
        model=model,
        execution=_execution(),
        selected_skill_ids=("output",),
        workspace_binding=workspace,
        candidate_check_binding=CandidateCheckToolBinding(
            runtime=RecordingCheckPort(),
            workspace=workspace,
            run_id=RUN_ID,
        ),
    )

    with pytest.raises(RuntimeError, match="stop after real provider binding"):
        await agent.ainvoke({"messages": [HumanMessage(content="inspect workspace")]})

    captured = model.bound_tool_schemas
    assert len(captured) == 7
    assert {schema["function"]["name"] for schema in captured} == EXPECTED_WORKSPACE_TOOLS
    assert len({schema["function"]["name"] for schema in captured}) == len(captured)


def test_workspace_agent_surface_has_only_framework_editor_verbs_and_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace_binding_sync()
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
        candidate_check_binding=CandidateCheckToolBinding(
            runtime=RecordingCheckPort(),
            workspace=workspace,
            run_id=RUN_ID,
        ),
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
    workspace = _workspace_binding_sync()

    class SyncGraph:
        def invoke(self, *args: Any, **kwargs: Any) -> str:
            del args, kwargs
            return "sync result"

    agent = ProfessionalConsultantAgent(
        graph=SyncGraph(),
        skill_backend=workspace.skill_backend,
        workspace_binding=workspace,
    )
    with pytest.raises(RuntimeError, match="async-only"):
        agent.invoke({"messages": []})


@pytest.mark.asyncio
async def test_check_tool_reads_current_store_workspace_without_files_channel() -> None:
    workspace = await _workspace_binding()
    port = RecordingCheckPort()
    check_tool = build_check_candidate_document_tool(
        binding=CandidateCheckToolBinding(
            runtime=port,
            workspace=workspace,
            run_id=RUN_ID,
        )
    )
    assert (
        await workspace.workspace_backend.aedit(
            "/workspace/header.json",
            '"採購專員"',
            '"更新後"',
        )
    ).error is None
    runtime = ToolRuntime(
        state={"messages": []},
        context={},
        config={},
        stream_writer=lambda _value: None,
        tool_call_id="check-001",
        store=None,
    )

    await check_tool.coroutine(runtime=runtime)  # type: ignore[misc]

    assert port.calls[-1]["run_id"] == RUN_ID
    assert '"更新後"' in port.calls[-1]["files"]["/workspace/header.json"]


@pytest.mark.asyncio
async def test_check_tool_rejects_invalid_store_resource_before_port_call() -> None:
    workspace = await _workspace_binding()
    port = RecordingCheckPort()
    check_tool = build_check_candidate_document_tool(
        binding=CandidateCheckToolBinding(
            runtime=port,
            workspace=workspace,
            run_id=RUN_ID,
        )
    )
    assert (
        await workspace.workspace.backend.awrite(
            "/workspace/not-a-resource.json",
            "{}\n",
        )
    ).error is None
    runtime = ToolRuntime(
        state={"messages": []},
        context={},
        config={},
        stream_writer=lambda _value: None,
        tool_call_id="check-invalid",
        store=None,
    )

    with pytest.raises(RuntimeError, match="workspace path"):
        await check_tool.coroutine(runtime=runtime)  # type: ignore[misc]
    assert port.calls == []


@pytest.mark.asyncio
async def test_parallel_reads_and_disjoint_edits_succeed_in_real_waves() -> None:
    workspace = await _workspace_binding()
    header = "/workspace/header.json"
    task = "/workspace/tasks/task-001.json"

    reads = await _run_workspace_wave(
        workspace,
        [
            _tool_call("read_file", {"file_path": header}, "read-001"),
            _tool_call("read_file", {"file_path": task}, "read-002"),
        ],
    )
    assert [message.status for message in _tool_messages(reads)] == [
        "success",
        "success",
    ]

    edits = await _run_workspace_wave(
        workspace,
        [
            _tool_call(
                "edit_file",
                {
                    "file_path": header,
                    "old_string": "採購專員",
                    "new_string": "採購管理師",
                },
                "edit-001",
            ),
            _tool_call(
                "edit_file",
                {
                    "file_path": task,
                    "old_string": "整理需求",
                    "new_string": "彙整需求",
                },
                "edit-002",
            ),
        ],
    )
    assert [message.status for message in _tool_messages(edits)] == [
        "success",
        "success",
    ]
    assert "採購管理師" in await _workspace_text(workspace, header)
    assert "彙整需求" in await _workspace_text(workspace, task)


@pytest.mark.asyncio
async def test_overlapping_mutation_wave_rejects_every_call_before_mutation() -> None:
    workspace = await _workspace_binding()
    header = "/workspace/header.json"
    before = await _workspace_text(workspace, header)
    result = await _run_workspace_wave(
        workspace,
        [
            _tool_call(
                "edit_file",
                {
                    "file_path": header,
                    "old_string": "採購專員",
                    "new_string": "甲",
                },
                "same-001",
            ),
            _tool_call(
                "edit_file",
                {
                    "file_path": "/workspace/./header.json",
                    "old_string": "採購專員",
                    "new_string": "乙",
                },
                "same-002",
            ),
        ],
    )

    messages = _tool_messages(result)
    assert [message.status for message in messages] == ["error", "error"]
    assert all("overlap" in str(message.content) for message in messages)
    assert await _workspace_text(workspace, header) == before


@pytest.mark.asyncio
async def test_invalid_mutation_rejects_valid_sibling_before_zero_mutation() -> None:
    workspace = await _workspace_binding()
    header = "/workspace/header.json"
    before = await _workspace_text(workspace, header)
    result = await _run_workspace_wave(
        workspace,
        [
            _tool_call(
                "edit_file",
                {"old_string": "採購專員", "new_string": "錯誤"},
                "bad-001",
            ),
            _tool_call(
                "edit_file",
                {
                    "file_path": header,
                    "old_string": "採購專員",
                    "new_string": "正確",
                },
                "good-002",
            ),
        ],
    )

    assert [message.status for message in _tool_messages(result)] == ["error", "error"]
    assert await _workspace_text(workspace, header) == before


@pytest.mark.asyncio
async def test_mutation_and_check_wave_rejects_both_before_zero_mutation() -> None:
    workspace = await _workspace_binding()
    header = "/workspace/header.json"
    before = await _workspace_text(workspace, header)
    port = RecordingCheckPort()
    check_tool = build_check_candidate_document_tool(
        binding=CandidateCheckToolBinding(
            runtime=port,
            workspace=workspace,
            run_id=RUN_ID,
        )
    )
    result = await _run_workspace_wave(
        workspace,
        [
            _tool_call(
                "edit_file",
                {
                    "file_path": header,
                    "old_string": "採購專員",
                    "new_string": "採購管理師",
                },
                "edit-001",
            ),
            _tool_call("check_candidate_document", {}, "check-002"),
        ],
        check_tool=check_tool,
    )

    assert [message.status for message in _tool_messages(result)] == ["error", "error"]
    assert await _workspace_text(workspace, header) == before
    assert port.calls == []
