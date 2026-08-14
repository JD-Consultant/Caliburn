from __future__ import annotations

from decimal import Decimal
import inspect
from typing import Any
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
    OutputDocumentChange,
    OutputDocumentField,
    OutputDocumentTarget,
    OutputOpksItem,
    OutputOpksKind,
    OutputQuestion,
    OutputQuestionKind,
    OutputSufficiency,
)
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    RunPolicy,
    resolve_execution,
)
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
    PackageSkillBackend,
    load_packaged_skill_text,
    skill_path,
)
from app.consultant.state import EmployeeSource, EmployeeSourceKind, QuoteAnchor
from app.consultant.verification import (
    ConsultantVerificationError,
    verify_consultant_result,
)


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
        max_model_calls=3,
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
        reviewable_document_changes=(),
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


def _output_document_change(
    source_id: UUID,
    *,
    operation: DocumentChangeOperation,
    target: OutputDocumentTarget,
    target_id: str,
    field: OutputDocumentField,
    basis_ordinal: int,
    text_value: str = "",
    opks_items: tuple[OutputOpksItem, ...] = (),
    opks_kind: OutputOpksKind = OutputOpksKind.NONE,
    task_ids: tuple[UUID, ...] = (),
) -> OutputDocumentChange:
    return OutputDocumentChange(
        operation=operation,
        target=target,
        target_id=target_id,
        field=field,
        text_value=text_value,
        integer_value=-1,
        uuid_value="",
        uuid_values=(),
        enablers=(),
        duties=(),
        tasks=(),
        opks_items=opks_items,
        target_ids=(),
        opks_kind=opks_kind,
        task_ids=task_ids,
        indicator_ids=(),
        basis_ordinal=basis_ordinal,
    )


def _text_seen(messages: list[BaseMessage]) -> str:
    return "\n".join(
        str(message.content)
        for message in messages
        if isinstance(message.content, (str, list))
    )


def test_first_release_skill_registry_is_exact_and_has_no_deferred_domains() -> None:
    assert CONSULTANT_SKILL_IDS == ALL_FIRST_RELEASE_SKILLS
    assert "reference" not in CONSULTANT_SKILL_IDS
    assert "competency-level" not in CONSULTANT_SKILL_IDS
    assert "attitude" not in CONSULTANT_SKILL_IDS


def test_package_skill_backend_is_selected_only_read_only_and_traversal_safe() -> None:
    backend = PackageSkillBackend(("task-boundary", "output"))

    listing = backend.ls("/skills")
    assert listing.error is None
    assert [entry["path"] for entry in listing.entries or []] == [
        "/skills/output/",
        "/skills/task-boundary/",
    ]

    first = backend.read(skill_path("task-boundary"), offset=0, limit=1000)
    assert first.error is None
    assert first.file_data is not None
    assert "Task 邊界" in first.file_data["content"]
    assert backend.loaded_skill_ids == ("task-boundary",)

    duplicate = backend.read(skill_path("task-boundary"), offset=0, limit=1000)
    assert duplicate.error is not None
    assert "already loaded" in duplicate.error

    assert backend.read("/skills/knowledge/SKILL.md").error is not None
    assert backend.read("/skills/../knowledge/SKILL.md").error is not None
    assert backend.read("\\skills\\task-boundary\\SKILL.md").error is not None
    assert backend.write("/skills/output/SKILL.md", "replace").error is not None


@pytest.mark.asyncio
async def test_agent_composes_selected_skills_without_leaking_ineligible_content() -> None:
    task_id = uuid4()
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
        reviewable_document_changes=(
            _output_document_change(
                source_id,
                operation=DocumentChangeOperation.REVISE,
                target=OutputDocumentTarget.TASK,
                target_id=str(task_id),
                field=OutputDocumentField.PURPOSE_RESULT,
                text_value="形成可供主管審核的採購需求",
                basis_ordinal=2,
            ),
            _output_document_change(
                source_id,
                operation=DocumentChangeOperation.ADD,
                target=OutputDocumentTarget.OPKS,
                target_id="",
                field=OutputDocumentField.ENTITY,
                opks_items=(
                    OutputOpksItem(
                        item_id="",
                        text="採購需求文件",
                        display_order=-1,
                        task_ids=(),
                        indicator_ids=(),
                    ),
                ),
                opks_kind=OutputOpksKind.OUTPUT,
                task_ids=(task_id,),
                basis_ordinal=3,
            ),
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
                content="",
                tool_calls=[
                    {
                        "name": "ConsultantModelOutput",
                        "args": result_payload,
                        "id": "structured-result",
                        "type": "tool_call",
                    }
                ],
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
        "ConsultantModelOutput",
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
                content="",
                tool_calls=[
                    {
                        "name": "ConsultantModelOutput",
                        "args": _minimal_model_output(source).model_dump(mode="json"),
                        "id": "structured-result",
                        "type": "tool_call",
                    }
                ],
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
        "ConsultantModelOutput",
    }


def test_interactive_agent_rejects_policy_above_product_call_caps() -> None:
    model = RecordingToolModel(responses=[AIMessage(content="unused")])
    with pytest.raises(ValueError, match="three model calls"):
        build_professional_consultant_agent(
            model=model,
            execution=_execution().model_copy(update={"max_model_calls": 4}),
            selected_skill_ids=("task-boundary",),
        )
    with pytest.raises(ValueError, match="two lookup waves"):
        build_professional_consultant_agent(
            model=model,
            execution=_execution().model_copy(update={"max_lookup_waves": 3}),
            selected_skill_ids=("task-boundary",),
        )


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
    backend = PackageSkillBackend(("output",))
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


def test_interactive_agent_cannot_reuse_prior_skill_tool_content_or_own_checkpoint() -> None:
    assert "checkpointer" not in inspect.signature(
        build_professional_consultant_agent
    ).parameters
    assert "store" not in inspect.signature(
        build_professional_consultant_agent
    ).parameters

    middleware = RunScopedSkillsMiddleware(
        backend=PackageSkillBackend(("output",))
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
        reviewable_document_changes=(
            ReviewableDocumentChange(
                operation=DocumentChangeOperation.REVISE,
                path=f"/tasks/{task_id}/purpose_result",
                after="形成採購需求並交付主管審核",
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


@pytest.mark.parametrize(
    "path",
    [
        "/competency_level",
        "/tasks/00000000-0000-0000-0000-000000000001/competency_level",
        "/occupation_code",
        "/occupation_name",
        "/occupation_category_name",
        "/industry_code",
        "/industry_name",
        "/icap_code",
        "/notes",
    ],
)
def test_verifier_rejects_model_authored_unsupported_document_paths(path: str) -> None:
    source = _employee_source("我整理採購需求。")
    result = _minimal_result(source).model_copy(
        update={
            "reviewable_document_changes": (
                ReviewableDocumentChange(
                    operation=DocumentChangeOperation.REVISE,
                    path=path,
                    after="模型不得寫入",
                    basis=_basis(source, "task-boundary", quote="整理採購需求"),
                ),
            )
        }
    )

    with pytest.raises(ConsultantVerificationError, match="unsupported document"):
        verify_consultant_result(
            result,
            execution=_execution(),
            document_id=source.document_id,
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=("task-boundary",),
            employee_sources=(source,),
        )


def test_result_schema_makes_attitude_generation_unrepresentable() -> None:
    source = _employee_source("我整理採購需求。")
    with pytest.raises(ValidationError, match="opks_kind"):
        ReviewableDocumentChange.model_validate(
            {
                "operation": "add",
                "path": "/opks",
                "after": "主動積極",
                "opks_kind": "attitude",
                "basis": _basis(
                    source, "task-boundary", quote="整理採購需求"
                ).model_dump(mode="json"),
            }
        )


def test_verifier_rejects_attitude_smuggled_through_full_opks_replacement() -> None:
    source = _employee_source("我整理採購需求。")
    task_id = uuid4()
    item_id = uuid4()
    result = _minimal_result(source).model_copy(
        update={
            "reviewable_document_changes": (
                ReviewableDocumentChange(
                    operation=DocumentChangeOperation.MERGE,
                    path="/opks",
                    target_ids=(item_id,),
                    after={
                        "item_id": str(item_id),
                        "kind": "attitude",
                        "text": "主動積極",
                        "display_order": 0,
                        "task_ids": [],
                        "indicator_ids": [],
                    },
                    opks_kind=OpksKind.KNOWLEDGE,
                    task_ids=(task_id,),
                    basis=_basis(
                        source,
                        "knowledge",
                        quote="整理採購需求",
                    ),
                ),
            )
        }
    )

    with pytest.raises(ConsultantVerificationError, match="OPKS payload kind"):
        verify_consultant_result(
            result,
            execution=_execution(),
            document_id=source.document_id,
            selected_skill_ids=("task-boundary", "knowledge"),
            loaded_skill_ids=("task-boundary", "knowledge"),
            employee_sources=(source,),
        )


@pytest.mark.parametrize(
    "operation",
    [DocumentChangeOperation.MERGE, DocumentChangeOperation.SPLIT],
)
def test_verifier_requires_merge_and_split_collection_paths(
    operation: DocumentChangeOperation,
) -> None:
    source = _employee_source("我整理採購需求。")
    item_id = uuid4()
    replacement_id = uuid4()
    result = _minimal_result(source).model_copy(
        update={
            "reviewable_document_changes": (
                ReviewableDocumentChange(
                    operation=operation,
                    path=f"/tasks/{item_id}",
                    target_ids=(item_id,),
                    after={
                        "task_id": str(replacement_id),
                        "statement": "整理採購需求",
                        "action": "整理",
                        "object": "採購需求",
                        "display_order": 0,
                    },
                    basis=_basis(
                        source,
                        "task-boundary",
                        quote="整理採購需求",
                    ),
                ),
            )
        }
    )

    with pytest.raises(ConsultantVerificationError, match="collection path"):
        verify_consultant_result(
            result,
            execution=_execution(),
            document_id=source.document_id,
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=("task-boundary",),
            employee_sources=(source,),
        )


def test_non_merge_change_cannot_carry_merge_target_ids() -> None:
    source = _employee_source("我整理採購需求。")
    with pytest.raises(ValidationError, match="target_ids"):
        ReviewableDocumentChange(
            operation=DocumentChangeOperation.REVISE,
            path="/job_title",
            after="採購專員",
            target_ids=(uuid4(),),
            basis=_basis(
                source,
                "task-boundary",
                quote="整理採購需求",
            ),
        )


@pytest.mark.parametrize(
    ("path", "after"),
    [
        ("/tasks", []),
        (
            "/tasks/00000000-0000-0000-0000-000000000001",
            {
                "task_id": "00000000-0000-0000-0000-000000000001",
                "statement": "整理採購需求",
                "action": "整理",
                "object": "採購需求",
                "display_order": 0,
            },
        ),
        (
            "/tasks/00000000-0000-0000-0000-000000000001/duty_id",
            "00000000-0000-0000-0000-000000000002",
        ),
        (
            "/tasks/00000000-0000-0000-0000-000000000001/display_order",
            1,
        ),
    ],
)
def test_revise_cannot_bypass_granular_structural_operations(
    path: str,
    after: object,
) -> None:
    source = _employee_source("我整理採購需求。")
    result = _minimal_result(source).model_copy(
        update={
            "reviewable_document_changes": (
                ReviewableDocumentChange(
                    operation=DocumentChangeOperation.REVISE,
                    path=path,
                    after=after,
                    basis=_basis(
                        source,
                        "task-boundary",
                        quote="整理採購需求",
                    ),
                ),
            )
        }
    )

    with pytest.raises(ConsultantVerificationError, match="revise operation"):
        verify_consultant_result(
            result,
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


def test_opks_axes_allow_early_output_and_document_level_many_to_many_ks() -> None:
    source = _employee_source(
        "我會整理採購需求文件，並比對需求與預算後送主管審核。"
    )
    task_ids = (uuid4(), uuid4())
    changes = (
        ReviewableDocumentChange(
            operation=DocumentChangeOperation.REVISE,
            path=f"/tasks/{task_ids[0]}/statement",
            after="整理並確認採購需求",
            basis=_basis(source, "task-boundary", quote="整理採購需求文件"),
        ),
        ReviewableDocumentChange(
            operation=DocumentChangeOperation.ADD,
            path="/opks",
            after="採購需求文件",
            opks_kind=OpksKind.OUTPUT,
            task_ids=(task_ids[0],),
            basis=_basis(source, "output", quote="採購需求文件"),
        ),
        ReviewableDocumentChange(
            operation=DocumentChangeOperation.ADD,
            path="/opks",
            after="採購需求與預算原則",
            opks_kind=OpksKind.KNOWLEDGE,
            task_ids=task_ids,
            basis=_basis(source, "knowledge", quote="比對需求與預算"),
        ),
        ReviewableDocumentChange(
            operation=DocumentChangeOperation.ADD,
            path="/opks",
            after="比對需求與預算",
            opks_kind=OpksKind.SKILL,
            task_ids=task_ids,
            basis=_basis(source, "skill", quote="比對需求與預算"),
        ),
    )
    result = ConsultantResult(
        visible_reply="Task 邊界仍可修訂，但已有足夠證據先整理 O／K／S。",
        reply_basis=_basis(
            source, "task-boundary", "output", "knowledge", "skill"
        ),
        used_skill_ids=("task-boundary", "output", "knowledge", "skill"),
        reviewable_document_changes=changes,
        sufficiency=SufficiencyRecommendation(
            currently_enough=False,
            reason="仍需確認行為指標。",
            remaining_gap_reasons=(GapReason.PERFORMANCE_EVIDENCE_MISSING,),
            continuing_benefit="繼續訪談可補齊可觀察的行為指標。",
            basis=_basis(
                source, "task-boundary", "output", "knowledge", "skill"
            ),
        ),
    )

    verify_consultant_result(
        result,
        execution=_execution(),
        document_id=source.document_id,
        selected_skill_ids=result.used_skill_ids,
        loaded_skill_ids=result.used_skill_ids,
        employee_sources=(source,),
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

    assert not result.reviewable_document_changes
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


def test_collection_change_cannot_smuggle_deferred_or_unknown_fields() -> None:
    source = _employee_source("我整理採購需求。")
    result = _minimal_result(source).model_copy(
        update={
            "reviewable_document_changes": (
                ReviewableDocumentChange(
                    operation=DocumentChangeOperation.ADD,
                    path="/tasks",
                    after={
                        "statement": "整理採購需求",
                        "action": "整理",
                        "object": "採購需求",
                        "competency_level": 4,
                    },
                    basis=_basis(
                        source,
                        "task-boundary",
                        quote="整理採購需求",
                    ),
                ),
            )
        }
    )

    with pytest.raises(ConsultantVerificationError, match="unsupported payload"):
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


def test_document_operation_must_match_its_target_shape() -> None:
    source = _employee_source("我整理採購需求。")
    bad = _minimal_result(source).model_copy(
        update={
            "reviewable_document_changes": (
                ReviewableDocumentChange(
                    operation=DocumentChangeOperation.REASSIGN,
                    path="/job_title",
                    after="採購管理人員",
                    basis=_basis(
                        source, "task-boundary", quote="整理採購需求"
                    ),
                ),
            )
        }
    )

    with pytest.raises(ConsultantVerificationError, match="Task duty_id"):
        verify_consultant_result(
            bad,
            execution=_execution(),
            document_id=source.document_id,
            selected_skill_ids=("task-boundary",),
            loaded_skill_ids=("task-boundary",),
            employee_sources=(source,),
        )
