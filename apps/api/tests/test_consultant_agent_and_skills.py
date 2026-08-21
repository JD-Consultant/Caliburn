from __future__ import annotations

from decimal import Decimal
import inspect
import json
from pathlib import Path
import subprocess
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import PrivateAttr, ValidationError

from app.consultant.agent import build_professional_consultant_agent
from app.consultant.agent import (
    LookupWaveLimitExceeded,
    LookupWaveLimitMiddleware,
    RunScopedSkillsMiddleware,
)
from app.consultant.model_output import (
    ConsultantModelOutput,
    OutputAnalysisBasis,
    OutputCandidatePublication,
    OutputQuestion,
    OutputQuestionKind,
    OutputSufficiency,
)
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    RunPolicy,
    resolve_execution,
)
from app.consultant.candidate_tool import CandidateEditToolBinding
from app.consultant.results import (
    AnalysisBasis,
    AttentionChange,
    AttentionOperation,
    ConsultantResult,
    DocumentChangeOperation,
    GapReason,
    NextQuestion,
    OpksKind,
    ReviewableDocumentChange,
    SufficiencyRecommendation,
    UnderstandingChange,
    UnderstandingOperation,
    VisibleGap,
)
from app.consultant.skill_backend import (
    CONSULTANT_SKILL_IDS,
    DirectPackageSkillBackendAdapter,
    PackageSkillBackend,
    load_packaged_skill_text,
    skill_path,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedTask,
    EmployeeSource,
    EmployeeSourceKind,
    QuoteAnchor,
)
from app.consultant.verification import (
    ConsultantVerificationError,
    verify_candidate_document_changes,
    verify_consultant_result,
)
from app.consultant.workspace_backend import build_consultant_workspace_backend
from app.consultant.workspace_resources import WorkspaceCatalog


ALL_FIRST_RELEASE_SKILLS = (
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


class RecordingToolModel(FakeMessagesListChatModel):
    _seen_messages: list[list[BaseMessage]] = PrivateAttr(default_factory=list)
    _bound_tool_names: list[str] = PrivateAttr(default_factory=list)
    _bound_tool_descriptions: dict[str, str] = PrivateAttr(default_factory=dict)

    @property
    def seen_messages(self) -> list[list[BaseMessage]]:
        return self._seen_messages

    @property
    def bound_tool_names(self) -> list[str]:
        return self._bound_tool_names

    @property
    def bound_tool_descriptions(self) -> dict[str, str]:
        return self._bound_tool_descriptions

    def bind_tools(
        self,
        tools: Any,
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> RecordingToolModel:
        del tool_choice, kwargs
        self._bound_tool_names = []
        self._bound_tool_descriptions = {}
        for candidate in tools:
            if isinstance(candidate, dict):
                function = candidate.get("function", candidate)
                name = str(function.get("name", ""))
                description = str(function.get("description", ""))
            else:
                name = str(
                    getattr(candidate, "name", None)
                    or getattr(candidate, "__name__", None)
                    or ""
                )
                description = str(getattr(candidate, "description", ""))
            self._bound_tool_names.append(name)
            self._bound_tool_descriptions[name] = description
        return self

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any):
        self._seen_messages.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


def _execution(
    *,
    skills: tuple[str, ...] = ALL_FIRST_RELEASE_SKILLS,
    tools: tuple[str, ...] = ("read_file",),
    max_model_calls: int = 3,
):
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
        allowed_skill_ids=skills,
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
    )
    return resolve_execution(profile, policy)


def _employee_source(text: str) -> EmployeeSource:
    return EmployeeSource.pending(
        source_id=uuid4(),
        document_id=uuid4(),
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text=text,
    )


def _anchor(source: EmployeeSource, quote: str) -> QuoteAnchor:
    start = source.text.index(quote)
    return QuoteAnchor(
        source_id=source.source_id,
        start=start,
        end=start + len(quote),
        quote=quote,
    )


def _basis(
    source: EmployeeSource,
    *skills: str,
    quote: str | None = None,
) -> AnalysisBasis:
    return AnalysisBasis(
        source_ids=(source.source_id,),
        quote_anchors=((_anchor(source, quote),) if quote is not None else ()),
        skill_ids=skills,
    )


def _minimal_result(
    source: EmployeeSource,
    *,
    skills: tuple[str, ...] = ("task-boundary",),
) -> ConsultantResult:
    return ConsultantResult(
        visible_reply="我已整理目前線索，接下來只釐清一個關鍵邊界。",
        reply_basis=_basis(source, *skills),
        used_skill_ids=skills,
        next_question=NextQuestion(
            text="這件工作完成後，會留下什麼結果或讓什麼狀態改變？",
            answer_target="task_boundary",
            reason="目前只有行動，尚無足以界定 Task 的結果。",
            basis=_basis(source, *skills),
        ),
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="Task 邊界仍缺少有意義結果。",
            remaining_gap_reasons=(GapReason.TASK_BOUNDARY_UNCLEAR,),
            continuing_benefit="繼續訪談可釐清 Task 的實際結果。",
            basis=_basis(source, *skills),
        ),
    )


def _output_basis(source_id: UUID, *skills: str) -> OutputAnalysisBasis:
    return OutputAnalysisBasis(
        source_ids=(source_id,),
        quote_anchors=(),
        skill_ids=skills,
    )


def _no_output_question() -> OutputQuestion:
    return OutputQuestion(
        kind=OutputQuestionKind.NONE,
        text="",
        answer_target="",
        reason="",
        current_understanding="",
        choices=(),
        affected_work_ids=(),
        affected_branch="",
        basis_ordinal=0,
    )


def _minimal_model_output(
    source: EmployeeSource,
    *,
    skills: tuple[str, ...] = ("task-boundary",),
) -> ConsultantModelOutput:
    basis = _output_basis(source.source_id, *skills)
    return ConsultantModelOutput(
        visible_reply="我已整理目前線索，接下來只釐清一個關鍵邊界。",
        analysis_bases=(basis,),
        reply_basis_ordinal=1,
        used_skill_ids=skills,
        understanding_changes=(),
        attention_changes=(),
        gaps=(),
        candidate_publication=OutputCandidatePublication(
            candidate_revision=0,
            revision_digest="",
            action_ids=(),
        ),
        question=OutputQuestion(
            kind=OutputQuestionKind.NEXT,
            text="這件工作完成後，會留下什麼結果或讓什麼狀態改變？",
            answer_target="task_boundary",
            reason="目前只有行動，尚無足以界定 Task 的結果。",
            current_understanding="",
            choices=(),
            affected_work_ids=(),
            affected_branch="",
            basis_ordinal=1,
        ),
        sufficiency=OutputSufficiency(
            currently_enough=False,
            reason="Task 邊界仍缺少有意義結果。",
            remaining_gap_reasons=(GapReason.TASK_BOUNDARY_UNCLEAR,),
            continuing_benefit="繼續訪談可釐清 Task 的實際結果。",
            basis_ordinal=1,
        ),
    )


def _text_seen(messages: list[BaseMessage]) -> str:
    return "\n".join(
        str(message.content)
        for message in messages
        if isinstance(message.content, (str, list))
    )


def _workspace_skill_backend():
    document_id = UUID("00000000-0000-0000-0000-000000000301")
    run_id = UUID("00000000-0000-0000-0000-000000000302")
    duty_id = UUID("00000000-0000-0000-0000-000000000303")
    task_id = UUID("00000000-0000-0000-0000-000000000304")
    document = ApprovedJobDocument(
        document_id=document_id,
        job_title="採購專員",
        work_description="管理採購流程。",
        competency_level=5,
        duties=(ApprovedDuty(duty_id=duty_id, statement="管理採購作業", display_order=0),),
        tasks=(
            ApprovedTask(
                task_id=task_id,
                duty_id=duty_id,
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
        document_id=document_id,
        run_id=run_id,
        catalog=catalog,
        selected_skill_ids=("output",),
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


def test_first_release_skill_registry_is_exact_and_has_no_deferred_domains() -> None:
    assert CONSULTANT_SKILL_IDS == ALL_FIRST_RELEASE_SKILLS
    assert "reference" not in CONSULTANT_SKILL_IDS
    assert "competency-level" not in CONSULTANT_SKILL_IDS
    assert "attitude" not in CONSULTANT_SKILL_IDS


def test_declared_skill_resources_are_tracked_delivery_assets() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    for skill_id in CONSULTANT_SKILL_IDS:
        relative_path = (
            f"apps/api/app/consultant/skills/{skill_id}/SKILL.md"
        )
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"declared consultant Skill is not a Git delivery asset: {relative_path}"
        )


def test_package_skill_backend_is_selected_only_read_only_and_traversal_safe() -> None:
    backend = PackageSkillBackend(("task-boundary", "output"))

    mount_listing = backend.ls("/")
    assert mount_listing.error is None
    assert [entry["path"] for entry in mount_listing.entries or []] == [
        "/output/",
        "/task-boundary/",
    ]

    listing = backend.ls("/skills")
    assert listing.error is not None

    first = backend.read("/task-boundary/SKILL.md", offset=0, limit=1000)
    assert first.error is None
    assert first.file_data is not None
    assert "Task 邊界" in first.file_data["content"]
    assert backend.loaded_skill_ids == ("task-boundary",)

    duplicate = backend.read("/task-boundary/SKILL.md", offset=0, limit=1000)
    assert duplicate.error is not None
    assert "already loaded" in duplicate.error

    assert backend.read(skill_path("task-boundary")).error is not None
    assert backend.read("/skills/knowledge/SKILL.md").error is not None
    assert backend.read("/skills/../knowledge/SKILL.md").error is not None
    assert backend.read("\\skills\\task-boundary\\SKILL.md").error is not None
    assert backend.write("/skills/output/SKILL.md", "replace").error is not None


def test_direct_skill_adapter_is_the_only_public_mount_compatibility_seam() -> None:
    adapter = DirectPackageSkillBackendAdapter(PackageSkillBackend(("output",)))

    root = adapter.ls("/")
    assert root.error is None
    assert [entry["path"] for entry in root.entries or []] == ["/skills/"]

    listing = adapter.ls("/skills")
    assert listing.error is None
    assert [entry["path"] for entry in listing.entries or []] == [
        "/skills/output/",
    ]

    first = adapter.read(skill_path("output"), offset=0, limit=1000)
    assert first.error is None
    assert adapter.read("/output/SKILL.md").error is not None


@pytest.mark.asyncio
async def test_agent_composes_selected_skills_without_leaking_ineligible_content() -> None:
    source_id = uuid4()
    basis = _output_basis(source_id, "task-boundary", "output")
    task_basis = _output_basis(source_id, "task-boundary")
    output_basis = _output_basis(source_id, "output")
    result_payload = ConsultantModelOutput(
        visible_reply="我先把這項工作的邊界與產出一起整理。",
        analysis_bases=(basis, task_basis, output_basis),
        reply_basis_ordinal=1,
        used_skill_ids=("task-boundary", "output"),
        understanding_changes=(),
        attention_changes=(),
        gaps=(),
        candidate_publication=OutputCandidatePublication(
            candidate_revision=0,
            revision_digest="",
            action_ids=(),
        ),
        question=_no_output_question(),
        sufficiency=OutputSufficiency(
            currently_enough=False,
            reason="還需要確認完成標準。",
            remaining_gap_reasons=(GapReason.COMPLETION_STANDARD_MISSING,),
            continuing_benefit="繼續訪談可確認完成標準。",
            basis_ordinal=1,
        ),
    ).model_dump(mode="json")
    model = RecordingToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {
                            "file_path": skill_path("task-boundary"),
                            "limit": 1000,
                        },
                        "id": "read-task",
                        "type": "tool_call",
                    },
                    {
                        "name": "read_file",
                        "args": {
                            "file_path": skill_path("output"),
                            "limit": 1000,
                        },
                        "id": "read-output",
                        "type": "tool_call",
                    },
                ],
            ),
            AIMessage(
                content=json.dumps(result_payload, ensure_ascii=False),
            ),
        ]
    )
    assembly = build_professional_consultant_agent(
        model=model,
        execution=_execution(),
        selected_skill_ids=("task-boundary", "output"),
    )

    result = await assembly.ainvoke(
        {"messages": [HumanMessage(content=f"[employee source {source_id}]")]}
    )

    assert result["structured_response"].used_skill_ids == (
        "task-boundary",
        "output",
    )
    assert assembly.skill_backend.loaded_skill_ids == (
        "task-boundary",
        "output",
    )
    assert set(model.bound_tool_names) == {
        "read_file",
    }
    read_description = model.bound_tool_descriptions["read_file"]
    assert "eligible Caliburn analysis Skill" in read_description
    assert "/skills/<skill-id>/SKILL.md" in read_description
    assert "Omit offset and limit" in read_description
    lowered_description = read_description.casefold()
    assert all(
        term not in lowered_description
        for term in ("pdf", "image", "editing", "pagination")
    )
    first_call = _text_seen(model.seen_messages[0])
    assert "task-boundary" in first_call
    assert "output" in first_call
    assert "knowledge" not in first_call
    assert "Task 邊界" not in first_call  # metadata only; full method is progressive
    assert "context 是否已足夠" in first_call
    assert "同一波平行" in first_call
    assert "不固定先後" in first_call
    assert "不得自行編造 UUID" in first_call
    assert "quote anchor 可留空" in first_call
    assert "一般下一題（next）" in first_call
    assert "current_understanding、choices、affected_work_ids、affected_branch 全部留空" in first_call
    assert "同一 candidate batch" in first_call
    assert "`entity_ref`" in first_call
    assert "`task_refs`" in first_call
    assert "不要提交無 Task linkage 的 O／P／K／S 文件變更" not in first_call
    assert "不要使用專用 split／merge operation" in first_call
    assert "未使用的 `integer_value=-1`" in first_call
    assert "每個 ADD 只提交一個" in first_call
    assert "field=whole_entity" in first_call

    second_call = _text_seen(model.seen_messages[1])
    assert "Task 邊界" in second_call
    assert "操作型工作可合法沒有獨立 O" in second_call
    assert "K 是名詞性" not in second_call
    assert sum(isinstance(item, ToolMessage) for item in model.seen_messages[1]) == 2


def test_agent_rejects_skill_or_read_tool_outside_resolved_policy() -> None:
    model = RecordingToolModel(responses=[AIMessage(content="unused")])
    with pytest.raises(ValueError, match="ineligible Skills"):
        build_professional_consultant_agent(
            model=model,
            execution=_execution(skills=("task-boundary",)),
            selected_skill_ids=("knowledge",),
        )
    with pytest.raises(ValueError, match="read_file"):
        build_professional_consultant_agent(
            model=model,
            execution=_execution(tools=()),
            selected_skill_ids=("task-boundary",),
        )


@pytest.mark.asyncio
async def test_agent_receives_document_scoped_source_tools_from_the_runtime() -> None:
    @tool(description="Read one employee source.")
    async def employee_source_get(source_id: UUID) -> dict[str, str]:
        return {"source_id": str(source_id)}

    source = _employee_source("我每週整理採購需求。")
    model = RecordingToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {
                            "file_path": skill_path("task-boundary"),
                            "limit": 1000,
                        },
                        "id": "read-task-boundary",
                        "type": "tool_call",
                    },
                    {
                        "name": "employee_source_get",
                        "args": {"source_id": str(source.source_id)},
                        "id": "read-source",
                        "type": "tool_call",
                    },
                ],
            ),
            AIMessage(
                content=_minimal_model_output(source).model_dump_json(),
            ),
        ]
    )
    assembly = build_professional_consultant_agent(
        model=model,
        execution=_execution(tools=("read_file", "employee_source_get")),
        selected_skill_ids=("task-boundary",),
        source_tools=(employee_source_get,),
    )
    await assembly.ainvoke(
        {"messages": [HumanMessage(content=f"[employee source {source.source_id}]")]}
    )

    assert set(model.bound_tool_names) == {
        "read_file",
        "employee_source_get",
    }


def test_interactive_agent_rejects_policy_above_product_call_caps() -> None:
    model = RecordingToolModel(responses=[AIMessage(content="unused")])
    build_professional_consultant_agent(
        model=model,
        execution=_execution(max_model_calls=5),
        selected_skill_ids=("task-boundary",),
    )
    with pytest.raises(ValueError, match="five model calls"):
        build_professional_consultant_agent(
            model=model,
            execution=_execution(max_model_calls=6),
            selected_skill_ids=("task-boundary",),
        )
    with pytest.raises(ValueError, match="two lookup waves"):
        build_professional_consultant_agent(
            model=model,
            execution=_execution().model_copy(update={"max_lookup_waves": 3}),
            selected_skill_ids=("task-boundary",),
        )


def test_explicit_candidate_binding_adds_exactly_the_fifth_tool_without_lookup_wave_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @tool
    def employee_source_get(source_id: UUID) -> str:
        """Read one employee source."""
        return str(source_id)

    @tool
    def employee_source_lineage(source_id: UUID) -> str:
        """Read one employee source lineage."""
        return str(source_id)

    @tool
    def employee_source_search(query: str) -> str:
        """Search document-scoped employee sources."""
        return query

    binding = CandidateEditToolBinding(
        runtime=cast(Any, object()),
        document_id=uuid4(),
        run_id=uuid4(),
        baseline_revision=7,
        selected_skill_ids=("task-boundary",),
    )
    model = RecordingToolModel(responses=[AIMessage(content="unused")])
    captured: dict[str, Any] = {}

    def capture_agent(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.consultant.agent.build_consultant_agent", capture_agent)
    build_professional_consultant_agent(
        model=model,
        execution=_execution(
            tools=(
                "read_file",
                "employee_source_get",
                "employee_source_lineage",
                "employee_source_search",
                "job_document_candidate_edit",
            ),
            max_model_calls=5,
        ),
        selected_skill_ids=("task-boundary",),
        source_tools=(
            employee_source_get,
            employee_source_lineage,
            employee_source_search,
        ),
        candidate_edit_binding=binding,
    )

    files = captured["additional_middleware"][1]
    assert {
        *(item.name for item in captured["tools"]),
        *(item.name for item in files.tools),
    } == {
        "read_file",
        "employee_source_get",
        "employee_source_lineage",
        "employee_source_search",
        "job_document_candidate_edit",
    }


def test_parallel_skill_and_employee_source_reads_are_one_lookup_wave() -> None:
    middleware = LookupWaveLimitMiddleware(
        tool_names=frozenset(
            {
                "read_file",
                "employee_source_get",
                "employee_source_lineage",
                "employee_source_search",
            }
        ),
        run_limit=2,
    )
    first = middleware.after_model(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_file",
                            "args": {"file_path": skill_path(skill_id)},
                            "id": f"read-{skill_id}",
                            "type": "tool_call",
                        }
                        for skill_id in ("task-boundary", "output")
                    ],
                )
            ]
        },
        runtime=None,  # type: ignore[arg-type] - middleware does not use runtime
    )
    assert first == {"run_lookup_wave_count": 1}

    assert middleware.after_model(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "job_document_candidate_edit",
                            "args": {},
                            "id": "candidate-edit",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "run_lookup_wave_count": 1,
        },
        runtime=None,  # type: ignore[arg-type] - middleware does not use runtime
    ) is None

    same_wave = middleware.after_model(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_file",
                            "args": {"file_path": skill_path("task-boundary")},
                            "id": "read-task-boundary",
                            "type": "tool_call",
                        },
                        {
                            "name": "employee_source_get",
                            "args": {"source_id": str(uuid4())},
                            "id": "lookup-source",
                            "type": "tool_call",
                        },
                    ],
                )
            ]
        },
        runtime=None,  # type: ignore[arg-type] - middleware does not use runtime
    )
    assert same_wave == {"run_lookup_wave_count": 1}

    second = middleware.after_model(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "employee_source_search",
                            "args": {"query": "採購需求"},
                            "id": "search-source",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "run_lookup_wave_count": 1,
        },
        runtime=None,  # type: ignore[arg-type] - middleware does not use runtime
    )
    assert second == {"run_lookup_wave_count": 2}

    with pytest.raises(LookupWaveLimitExceeded):
        middleware.after_model(
            {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "employee_source_lineage",
                                "args": {"source_id": str(uuid4())},
                                "id": "third-wave",
                                "type": "tool_call",
                            }
                        ],
                    )
                ],
                "run_lookup_wave_count": 2,
            },
            runtime=None,  # type: ignore[arg-type] - middleware does not use runtime
        )


def test_run_scoped_skill_metadata_replaces_stale_framework_state() -> None:
    backend = DirectPackageSkillBackendAdapter(PackageSkillBackend(("output",)))
    middleware = RunScopedSkillsMiddleware(backend=backend)
    update = middleware.before_agent(
        {
            "messages": [],
            "skills_metadata": [
                {
                    "name": "knowledge",
                    "description": "stale ineligible Skill",
                    "path": "/skills/knowledge/SKILL.md",
                    "metadata": {},
                    "license": None,
                    "compatibility": None,
                    "allowed_tools": [],
                }
            ],
            "skills_load_errors": ["stale warning from another eligibility set"],
        },
        runtime=None,  # type: ignore[arg-type] - framework hook does not use runtime
        config={},
    )
    assert update is not None
    assert [item["name"] for item in update["skills_metadata"]] == ["output"]
    assert update["skills_load_errors"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/candidate/00000000-0000-0000-0000-000000000302/header.json",
        "/sources/current/source-001.txt",
        "/approved/header.json",
        "/pending/changesets.json",
    ],
)
def test_workspace_continuation_allows_non_skill_read_receipts(path: str) -> None:
    workspace = _workspace_skill_backend()
    middleware = RunScopedSkillsMiddleware(
        backend=workspace.composite_backend,
        receipt_backend=workspace.skill_backend,
        workspace_mode=True,
    )

    update = middleware.before_agent(
        _read_receipt_state(path),
        runtime=None,  # type: ignore[arg-type] - middleware does not use runtime
        config={},
    )

    assert update is not None
    assert update["skills_load_errors"] == []


def test_workspace_continuation_rejects_a_prior_skill_read_receipt() -> None:
    workspace = _workspace_skill_backend()
    middleware = RunScopedSkillsMiddleware(
        backend=workspace.composite_backend,
        receipt_backend=workspace.skill_backend,
        workspace_mode=True,
    )

    with pytest.raises(ValueError, match="stale Skill tool result"):
        middleware.before_agent(
            _read_receipt_state("/skills/output/SKILL.md"),
            runtime=None,  # type: ignore[arg-type]
            config={},
        )


def test_workspace_continuation_rejects_orphan_skill_read_receipt() -> None:
    workspace = _workspace_skill_backend()
    middleware = RunScopedSkillsMiddleware(
        backend=workspace.composite_backend,
        receipt_backend=workspace.skill_backend,
        workspace_mode=True,
    )

    with pytest.raises(ValueError, match="orphan"):
        middleware.before_agent(
            {
                "messages": [
                    ToolMessage(
                        content="orphan read result",
                        name="read_file",
                        tool_call_id="missing-ai-call",
                    )
                ]
            },
            runtime=None,  # type: ignore[arg-type]
            config={},
        )


def test_workspace_continuation_rejects_ambiguous_read_receipt_id() -> None:
    workspace = _workspace_skill_backend()
    middleware = RunScopedSkillsMiddleware(
        backend=workspace.composite_backend,
        receipt_backend=workspace.skill_backend,
        workspace_mode=True,
    )
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {
                            "file_path": "/candidate/00000000-0000-0000-0000-000000000302/header.json"
                        },
                        "id": "ambiguous-read",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": "/sources/current/source-001.txt"},
                        "id": "ambiguous-read",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="ambiguous read result",
                name="read_file",
                tool_call_id="ambiguous-read",
            ),
        ]
    }

    with pytest.raises(ValueError, match="ambiguous"):
        middleware.before_agent(
            state,
            runtime=None,  # type: ignore[arg-type]
            config={},
        )


def test_interactive_agent_cannot_reuse_prior_skill_tool_content_or_own_checkpoint() -> None:
    assert "checkpointer" not in inspect.signature(
        build_professional_consultant_agent
    ).parameters
    assert "store" not in inspect.signature(
        build_professional_consultant_agent
    ).parameters

    middleware = RunScopedSkillsMiddleware(
        backend=DirectPackageSkillBackendAdapter(PackageSkillBackend(("output",)))
    )
    with pytest.raises(ValueError, match="stale Skill tool result"):
        middleware.before_agent(
            {
                "messages": [
                    ToolMessage(
                        content=load_packaged_skill_text("knowledge"),
                        name="read_file",
                        tool_call_id="prior-run-read",
                    )
                ]
            },
            runtime=None,  # type: ignore[arg-type] - rejected before runtime use
            config={},
        )


def test_result_schema_cannot_directly_replace_the_approved_document() -> None:
    source = _employee_source("我整理採購需求。")
    payload = _minimal_result(source).model_dump(mode="json")
    payload["approved_document"] = {"job_title": "模型直接改寫"}

    with pytest.raises(ValidationError, match="approved_document"):
        ConsultantResult.model_validate(payload)


def test_result_schema_has_no_provider_native_unconstrained_json_node() -> None:
    empty_paths: list[str] = []

    def visit(value: object, path: str = "$") -> None:
        if value == {}:
            empty_paths.append(path)
        elif isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(ConsultantResult.model_json_schema())

    assert empty_paths == []


def test_verifier_accepts_anchored_source_and_selected_skill_dependencies() -> None:
    source = _employee_source("我整理採購需求，完成後交給主管審核。")
    quote = "整理採購需求"
    task_id = uuid4()
    result = ConsultantResult(
        visible_reply="我理解這項工作會形成採購需求並交付主管審核。",
        reply_basis=_basis(source, "task-boundary", quote=quote),
        used_skill_ids=("task-boundary",),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="current_responsibility",
                text="員工負責整理採購需求。",
                basis=_basis(source, "task-boundary", quote=quote),
            ),
        ),
        attention_changes=(
            AttentionChange(
                operation=AttentionOperation.ADD,
                kind="task_interview",
                subject_id=task_id,
                reason="需要釐清完成標準。",
                basis=_basis(source, "task-boundary", quote=quote),
            ),
        ),
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="仍缺完成標準。",
            remaining_gap_reasons=(GapReason.COMPLETION_STANDARD_MISSING,),
            continuing_benefit="繼續訪談可確認完成標準。",
            basis=_basis(source, "task-boundary", quote=quote),
        ),
    )

    verify_consultant_result(
        result,
        execution=_execution(),
        document_id=source.document_id,
        selected_skill_ids=("task-boundary",),
        loaded_skill_ids=("task-boundary",),
        employee_sources=(source,),
    )


@pytest.mark.parametrize("reference_kind", ["work", "subject"])
def test_verifier_rejects_model_invented_application_ids(
    reference_kind: str,
) -> None:
    source = _employee_source("我整理採購需求。")
    invented_id = uuid4()
    result = _minimal_result(source)
    if reference_kind == "work":
        result = result.model_copy(
            update={
                "understanding_changes": (
                    UnderstandingChange(
                        operation=UnderstandingOperation.ADD,
                        kind="current_responsibility",
                        text="員工負責整理採購需求。",
                        work_ids=(invented_id,),
                        basis=_basis(source, "task-boundary"),
                    ),
                )
            }
        )
    else:
        result = result.model_copy(
            update={
                "attention_changes": (
                    AttentionChange(
                        operation=AttentionOperation.ADD,
                        kind="task_interview",
                        subject_id=invented_id,
                        reason="仍需確認完成標準。",
                        basis=_basis(source, "task-boundary"),
                    ),
                )
            }
        )

    with pytest.raises(ConsultantVerificationError, match="unknown application ID"):
        verify_consultant_result(
            result,
            execution=_execution(),
            document_id=source.document_id,
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=("task-boundary",),
            employee_sources=(source,),
            known_work_ids=(),
            known_subject_ids=(),
        )


@pytest.mark.parametrize(
    "failure",
    ["unselected_skill", "unknown_source", "invalid_quote"],
)
def test_verifier_rejects_unauthorized_dependencies_and_bad_quote_anchors(
    failure: str,
) -> None:
    source = _employee_source("我整理採購需求。")
    result = _minimal_result(source)
    question = result.next_question
    assert question is not None
    if failure == "unselected_skill":
        bad_basis = AnalysisBasis(
            source_ids=(source.source_id,),
            skill_ids=("knowledge",),
        )
    elif failure == "unknown_source":
        bad_basis = AnalysisBasis(
            source_ids=(uuid4(),),
            skill_ids=("task-boundary",),
        )
    else:
        bad_basis = AnalysisBasis(
            source_ids=(source.source_id,),
            quote_anchors=(
                QuoteAnchor(
                    source_id=source.source_id,
                    start=0,
                    end=1,
                    quote="錯",
                ),
            ),
            skill_ids=("task-boundary",),
        )
    bad = result.model_copy(
        update={"next_question": question.model_copy(update={"basis": bad_basis})}
    )

    with pytest.raises(ConsultantVerificationError):
        verify_consultant_result(
            bad,
            execution=_execution(),
            document_id=source.document_id,
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=("task-boundary",),
            employee_sources=(source,),
        )


def test_risky_specific_claim_requires_an_exact_employee_quote_anchor() -> None:
    source = _employee_source("主管只說要整理採購需求。")
    unanchored = ConsultantResult(
        visible_reply="我先保留這項線索。",
        reply_basis=_basis(source, "task-boundary"),
        used_skill_ids=("task-boundary",),
        understanding_changes=(
            UnderstandingChange(
                operation=UnderstandingOperation.ADD,
                kind="completion_rule",
                text="依公司規定，必須在 24 小時內完成。",
                basis=_basis(source, "task-boundary"),
            ),
        ),
        sufficiency=_minimal_result(source).sufficiency,
    )

    with pytest.raises(ConsultantVerificationError, match="anchored employee quote"):
        verify_consultant_result(
            unanchored,
            execution=_execution(),
            document_id=source.document_id,
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=("task-boundary",),
            employee_sources=(source,),
        )

    supported_source = _employee_source("公司規定必須在 24 小時內完成。")
    supported = unanchored.model_copy(
        update={
            "reply_basis": _basis(supported_source, "task-boundary"),
            "understanding_changes": (
                unanchored.understanding_changes[0].model_copy(
                    update={
                        "basis": _basis(
                            supported_source,
                            "task-boundary",
                            quote="公司規定必須在 24 小時內完成",
                        )
                    }
                ),
            ),
            "sufficiency": unanchored.sufficiency.model_copy(
                update={"basis": _basis(supported_source, "task-boundary")}
            ),
        }
    )
    verify_consultant_result(
        supported,
        execution=_execution(),
        document_id=supported_source.document_id,
        selected_skill_ids=("task-boundary",),
        loaded_skill_ids=("task-boundary",),
        employee_sources=(supported_source,),
    )


def test_no_meaningful_output_is_a_visible_task_boundary_gap_not_a_fabricated_o() -> None:
    source = _employee_source("我就是每天打開系統看一下。")
    result = ConsultantResult(
        visible_reply="目前只有工具操作，還不能安全判定獨立 Task 或工作產出。",
        reply_basis=_basis(source, "task-boundary", "output"),
        used_skill_ids=("task-boundary", "output"),
        gaps=(
            VisibleGap(
                reason=GapReason.TASK_BOUNDARY_UNCLEAR,
                description="尚不清楚查看系統要促成什麼結果。",
                subject_kind="work_clue",
                basis=_basis(source, "task-boundary", "output"),
            ),
        ),
        next_question=NextQuestion(
            text="你查看系統後通常要做出哪個判斷或讓哪個狀態改變？",
            answer_target="meaningful_outcome",
            reason="操作本身不足以構成 Task 或 O。",
            basis=_basis(source, "task-boundary", "output"),
        ),
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="仍缺有意義結果。",
            remaining_gap_reasons=(GapReason.TASK_BOUNDARY_UNCLEAR,),
            continuing_benefit="繼續訪談可確認這項操作是否構成 Task。",
            basis=_basis(source, "task-boundary", "output"),
        ),
    )

    assert result.candidate_publication is None
    verify_consultant_result(
        result,
        execution=_execution(),
        document_id=source.document_id,
        selected_skill_ids=result.used_skill_ids,
        loaded_skill_ids=result.used_skill_ids,
        employee_sources=(source,),
    )


def test_each_skill_has_progressive_disclosure_contract_and_method_boundaries() -> None:
    for skill_id in CONSULTANT_SKILL_IDS:
        content = load_packaged_skill_text(skill_id)
        for heading in (
            "## 適用時機",
            "## 所需證據",
            "## 產出",
            "## 缺口",
            "## 防止臆測",
            "## 重新開啟",
        ):
            assert heading in content, (skill_id, heading)

    story = load_packaged_skill_text("story-interview")
    assert "Story／Event／Work Unit／Task 不是一對一" in story
    assert "精彩事件" in story and "例行工作" in story

    task = load_packaged_skill_text("task-boundary")
    for rule in ("action", "object", "meaningful outcome", "current responsibility"):
        assert rule in task
    for false_task in ("工具", "步驟", "一次性", "他人工作", "過去工作"):
        assert false_task in task

    duty = load_packaged_skill_text("duty-grouping")
    assert "可修訂" in duty
    assert "不得成為早期固定盒子" in duty

    knowledge = load_packaged_skill_text("knowledge")
    assert "K 是名詞性" in knowledge
    assert "文件層" in knowledge and "多對多" in knowledge
    assert "具備…之能力" in knowledge

    skill = load_packaged_skill_text("skill")
    assert "S 是應用或操作動作" in skill
    assert "文件層" in skill and "多對多" in skill
    assert "能力級別" in skill

    performance = load_packaged_skill_text("performance-indicator")
    assert "可觀察" in performance
    assert "人格" in performance


def test_completion_red_team_covers_known_biases_without_creating_many_questions() -> None:
    content = load_packaged_skill_text("completion-red-team")
    for issue in (
        "例行工作遺漏",
        "精彩事件偏誤",
        "他人工作",
        "過去工作",
        "一次性工作",
        "過度合併",
        "過度拆分",
        "重複 Task",
        "無來源 O／P／K／S",
        "高影響矛盾",
    ):
        assert issue in content
    assert "一個主要問題" in content


def test_result_has_only_one_structural_main_question_and_no_stop_lifecycle() -> None:
    fields = ConsultantResult.model_fields
    assert "next_question" in fields
    assert "questions" not in fields
    assert "pause" not in fields
    assert "finish" not in fields
    assert "end_interview" not in fields


def test_unanchored_named_law_in_visible_reply_is_rejected() -> None:
    source = _employee_source("主管只說要整理採購需求。")
    result = _minimal_result(source).model_copy(
        update={"visible_reply": "依勞動基準法，這項工作必須當天完成。"}
    )

    with pytest.raises(ConsultantVerificationError, match="anchored employee quote"):
        verify_consultant_result(
            result,
            execution=_execution(),
            document_id=source.document_id,
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=("task-boundary",),
            employee_sources=(source,),
        )


def test_verifier_rejects_unloaded_skill_and_cross_document_evidence() -> None:
    source = _employee_source("我整理採購需求。")
    result = _minimal_result(source)

    with pytest.raises(ConsultantVerificationError, match="not loaded"):
        verify_consultant_result(
            result,
            execution=_execution(),
            document_id=source.document_id,
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=(),
            employee_sources=(source,),
        )

    with pytest.raises(ConsultantVerificationError, match="document scope"):
        verify_consultant_result(
            result,
            execution=_execution(),
            document_id=uuid4(),
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=("task-boundary",),
            employee_sources=(source,),
        )


def test_candidate_document_verifier_checks_evidence_before_final_result() -> None:
    source = _employee_source("我使用採購流程知識來建立請購單。")
    task_id = uuid4()
    item_id = uuid4()
    change = ReviewableDocumentChange(
        operation=DocumentChangeOperation.ADD,
        path="/opks",
        after={
            "item_id": str(item_id),
            "kind": "knowledge",
            "text": "採購流程知識",
            "display_order": 0,
            "task_ids": [str(task_id)],
            "indicator_ids": [],
        },
        opks_kind=OpksKind.KNOWLEDGE,
        task_ids=(task_id,),
        basis=_basis(
            source,
            "knowledge",
            quote="採購流程知識",
        ),
    )

    used = verify_candidate_document_changes(
        (change,),
        document_id=source.document_id,
        selected_skill_ids=("knowledge",),
        loaded_skill_ids=("knowledge",),
        employee_sources=(source,),
    )

    assert used == ("knowledge",)


def test_candidate_document_verifier_ignores_application_owned_structural_metadata() -> None:
    source = _employee_source("我負責管理採購作業。")
    change = ReviewableDocumentChange(
        operation=DocumentChangeOperation.ADD,
        path="/duties",
        after={
            "duty_id": str(uuid4()),
            "statement": "管理採購作業",
            "display_order": 0,
        },
        basis=AnalysisBasis(
            source_ids=(source.source_id,),
            skill_ids=("task-boundary",),
        ),
    )

    used = verify_candidate_document_changes(
        (change,),
        document_id=source.document_id,
        selected_skill_ids=("task-boundary",),
        loaded_skill_ids=("task-boundary",),
        employee_sources=(source,),
    )

    assert used == ("task-boundary",)


@pytest.mark.parametrize("failure", ("unloaded", "invalid_quote", "cross_document"))
def test_candidate_document_verifier_fails_closed_for_receipt_or_evidence_mismatch(
    failure: str,
) -> None:
    source = _employee_source("我負責管理採購作業。")
    anchor = _anchor(source, "管理採購作業")
    if failure == "invalid_quote":
        anchor = anchor.model_copy(update={"quote": "錯誤引文"})
    change = ReviewableDocumentChange(
        operation=DocumentChangeOperation.ADD,
        path="/duties",
        after={
            "duty_id": str(uuid4()),
            "statement": "管理採購作業",
            "display_order": 0,
        },
        basis=AnalysisBasis(
            source_ids=(source.source_id,),
            quote_anchors=(anchor,),
            skill_ids=("task-boundary",),
        ),
    )

    with pytest.raises(ConsultantVerificationError):
        verify_candidate_document_changes(
            (change,),
            document_id=(uuid4() if failure == "cross_document" else source.document_id),
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=(() if failure == "unloaded" else ("task-boundary",)),
            employee_sources=(source,),
        )
