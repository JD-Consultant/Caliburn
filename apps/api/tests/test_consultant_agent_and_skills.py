from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.store.memory import InMemoryStore

from app.consultant.agent import (
    LookupWaveLimitExceeded,
    LookupWaveLimitMiddleware,
    ProfessionalConsultantAgent,
    RunScopedSkillsMiddleware,
    WorkspaceAgentAsyncOnlyError,
    build_professional_consultant_agent,
)
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    RunPolicy,
    resolve_execution,
)
from app.consultant.skill_backend import (
    CONSULTANT_SKILL_IDS,
    PackageSkillBackend,
    load_packaged_skill_text,
    skill_path,
)
from app.consultant.state import ApprovedDuty, ApprovedJobDocument, ApprovedTask
from app.consultant.workspace_backend import (
    ConsultantWorkspaceBackendBinding,
    build_consultant_workspace_backend,
)
from app.consultant.workspace_resources import WorkspaceCatalog
from app.consultant.workspace_state import StoreBackedWorkspace
from app.consultant.workspace_tools import CandidateCheckToolBinding
from app.consultant.workspace_validation import WorkspaceValidationMiddleware


EXPECTED_TOOLS = (
    "ls",
    "read_file",
    "grep",
    "write_file",
    "edit_file",
    "delete",
    "check_candidate_document",
)


class RecordingCheckPort:
    async def check_candidate_document(self, **kwargs: Any) -> dict[str, Any]:
        return {"status": "checked", **kwargs}


def _workspace() -> ConsultantWorkspaceBackendBinding:
    document_id = UUID("00000000-0000-0000-0000-000000000801")
    duty_id = UUID("00000000-0000-0000-0000-000000000803")
    task_id = UUID("00000000-0000-0000-0000-000000000804")
    document = ApprovedJobDocument(
        document_id=document_id,
        job_title="採購專員",
        work_description="管理採購流程。",
        duties=(ApprovedDuty(duty_id=duty_id, statement="管理採購作業", display_order=0),),
        tasks=(
            ApprovedTask(
                task_id=task_id,
                duty_id=duty_id,
                statement="整理需求",
                action="整理",
                object="採購需求",
                display_order=0,
            ),
        ),
    )
    return build_consultant_workspace_backend(
        runtime=object(),  # type: ignore[arg-type]
        document_id=document_id,
        workspace=StoreBackedWorkspace(
            store=InMemoryStore(),
            document_id=document_id,
        ),
        catalog=WorkspaceCatalog.from_snapshot(document),
        selected_skill_ids=("output",),
    )


def _execution(*, tools: tuple[str, ...] = EXPECTED_TOOLS, max_model_calls: int = 8):
    return resolve_execution(
        ConsultantModelProfile(
            profile_id="primary-consultant",
            revision=1,
            requested_model="anthropic/claude-opus-5",
            provider_allowlist=("Anthropic",),
            max_output_tokens=4096,
        ),
        RunPolicy(
            policy_id="interactive-consultation",
            revision=1,
            run_kind="interactive_consultation",
            allowed_skill_ids=("output",),
            allowed_tool_ids=tools,
            max_context_tokens=24_000,
            max_model_calls=max_model_calls,
            max_lookup_waves=2,
            max_total_tool_calls=12,
            model_retry_count=0,
            tool_retry_count=0,
            max_elapsed_seconds=180,
            max_total_tokens=32_000,
            max_cost_usd=Decimal("2.00"),
        ),
    )


def _read_receipt_state(path: str, call_id: str = "prior-read") -> dict[str, Any]:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": path},
                        "id": call_id,
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="prior read result",
                name="read_file",
                tool_call_id=call_id,
            ),
        ]
    }


def test_first_release_skills_are_packaged_and_read_only() -> None:
    assert CONSULTANT_SKILL_IDS == (
        "work-discovery",
        "story-interview",
        "task-boundary",
        "duty-grouping",
        "output",
        "performance-indicator",
        "knowledge",
        "skill",
        "completion-red-team",
    )
    backend = PackageSkillBackend(("task-boundary", "output"))
    assert [entry["path"] for entry in backend.ls("/").entries or []] == [
        "/output/",
        "/task-boundary/",
    ]
    loaded = backend.read("/task-boundary/SKILL.md", limit=1000)
    assert loaded.error is None
    assert loaded.file_data is not None
    assert "Task 邊界" in loaded.file_data["content"]
    assert backend.loaded_skill_ids == ("task-boundary",)
    assert backend.read(skill_path("task-boundary"), limit=1000).error is not None
    assert backend.read("/skills/knowledge/SKILL.md").error is not None
    assert backend.write("/output/SKILL.md", "replace").error is not None


def test_professional_agent_composes_exactly_one_workspace_and_check_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace()
    binding = CandidateCheckToolBinding(
        runtime=RecordingCheckPort(),
        workspace=workspace,
    )
    captured: dict[str, Any] = {}

    def capture_agent(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.consultant.agent.build_consultant_agent", capture_agent)
    assembled = build_professional_consultant_agent(
        model=FakeMessagesListChatModel(responses=[AIMessage(content="unused")]),
        execution=_execution(),
        selected_skill_ids=("output",),
        workspace_binding=workspace,
        candidate_check_binding=binding,
    )

    assert assembled.skill_backend is workspace.skill_backend
    assert tuple(tool.name for tool in captured["tools"]) == (
        "check_candidate_document",
    )
    filesystem = captured["additional_middleware"][1]
    assert {tool.name for tool in filesystem.tools} == set(EXPECTED_TOOLS[:6])
    assert captured["additional_middleware"][2].run_limit == 2
    assert isinstance(
        captured["additional_middleware"][-1],
        WorkspaceValidationMiddleware,
    )


def test_professional_agent_allows_eleven_calls_but_rejects_a_twelfth() -> None:
    workspace = _workspace()
    binding = CandidateCheckToolBinding(runtime=RecordingCheckPort(), workspace=workspace)
    model = FakeMessagesListChatModel(responses=[AIMessage(content="unused")])
    eleven_call_execution = _execution().model_copy(update={"max_model_calls": 11})

    build_professional_consultant_agent(
        model=model,
        execution=eleven_call_execution,
        selected_skill_ids=("output",),
        workspace_binding=workspace,
        candidate_check_binding=binding,
    )
    with pytest.raises(ValueError, match="at most eleven"):
        build_professional_consultant_agent(
            model=model,
            execution=eleven_call_execution.model_copy(update={"max_model_calls": 12}),
            selected_skill_ids=("output",),
            workspace_binding=workspace,
            candidate_check_binding=binding,
        )


def test_professional_agent_rejects_non_workspace_surface() -> None:
    workspace = _workspace()
    binding = CandidateCheckToolBinding(runtime=RecordingCheckPort(), workspace=workspace)
    model = FakeMessagesListChatModel(responses=[AIMessage(content="unused")])

    with pytest.raises(ValueError, match="exactly the workspace Tool surface"):
        build_professional_consultant_agent(
            model=model,
            execution=_execution(tools=EXPECTED_TOOLS[:-1]),
            selected_skill_ids=("output",),
            workspace_binding=workspace,
            candidate_check_binding=binding,
        )


def test_lookup_waves_count_only_path_aware_external_workspace_reads() -> None:
    middleware = LookupWaveLimitMiddleware(
        tool_names=frozenset({"ls", "read_file", "grep"}),
        run_limit=2,
    )

    def state(name: str, path: str | None = None, count: int = 0) -> dict[str, Any]:
        args = {} if path is None else {"file_path": path}
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": name, "args": args, "id": name, "type": "tool_call"}
                    ],
                )
            ],
            "run_lookup_wave_count": count,
        }

    assert middleware.after_model(state("read_file", "/workspace/header.json"), None) is None  # type: ignore[arg-type]
    assert middleware.after_model(state("read_file", "/sources/current/source-001.txt"), None) == {"run_lookup_wave_count": 1}  # type: ignore[arg-type]
    assert middleware.after_model(state("grep", "/approved" , count=1), None) == {"run_lookup_wave_count": 2}  # type: ignore[arg-type]
    with pytest.raises(LookupWaveLimitExceeded):
        middleware.after_model(state("ls", "/pending", count=2), None)  # type: ignore[arg-type]
    assert middleware.after_model(state("grep", count=0), None) == {"run_lookup_wave_count": 1}  # type: ignore[arg-type]
    assert middleware.after_model(state("grep", "/", count=1), None) == {"run_lookup_wave_count": 2}  # type: ignore[arg-type]
    assert middleware.after_model(state("grep", "/workspace", count=2), None) is None  # type: ignore[arg-type]
    with pytest.raises(LookupWaveLimitExceeded):
        middleware.after_model(state("grep", count=2), None)  # type: ignore[arg-type]


def test_skill_activation_does_not_consume_external_data_lookup_waves() -> None:
    middleware = LookupWaveLimitMiddleware(
        tool_names=frozenset({"ls", "read_file", "grep"}),
        run_limit=2,
    )

    def state(path: str, count: int) -> dict[str, Any]:
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_file",
                            "args": {"file_path": path},
                            "id": path,
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "run_lookup_wave_count": count,
        }

    assert middleware.after_model(  # type: ignore[arg-type]
        state("/skills/task-boundary/SKILL.md", count=2),
        None,
    ) is None
    with pytest.raises(LookupWaveLimitExceeded):
        middleware.after_model(  # type: ignore[arg-type]
            state("/pending/index.json", count=2),
            None,
        )


def test_run_scoped_skills_reject_stale_skill_receipts_but_allow_vfs_receipts() -> None:
    workspace = _workspace()
    middleware = RunScopedSkillsMiddleware(
        backend=workspace.composite_backend,
        receipt_backend=workspace.skill_backend,
        workspace_mode=True,
    )
    update = middleware.before_agent(
        {
            "messages": [],
            "skills_metadata": [{"name": "stale"}],
            "skills_load_errors": ["stale"],
        },
        runtime=None,  # type: ignore[arg-type]
        config={},
    )
    assert update is not None
    assert [item["name"] for item in update["skills_metadata"]] == ["output"]
    assert update["skills_load_errors"] == []

    middleware.before_agent(
        _read_receipt_state("/approved/header.json"),
        runtime=None,  # type: ignore[arg-type]
        config={},
    )
    with pytest.raises(ValueError, match="stale Skill tool result"):
        middleware.before_agent(
            _read_receipt_state("/skills/output/SKILL.md"),
            runtime=None,  # type: ignore[arg-type]
            config={},
        )


def test_workspace_agent_has_no_synchronous_execution_path() -> None:
    agent = ProfessionalConsultantAgent(
        graph=object(),
        skill_backend=PackageSkillBackend(("output",)),
        workspace_binding=_workspace(),
    )
    with pytest.raises(WorkspaceAgentAsyncOnlyError):
        agent.invoke()


def test_skill_content_is_not_loaded_by_metadata_discovery() -> None:
    backend = PackageSkillBackend(("output",))
    listing = backend.ls("/")
    assert listing.error is None
    assert backend.loaded_skill_ids == ()
    assert load_packaged_skill_text("output")
