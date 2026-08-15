from __future__ import annotations

from collections.abc import Iterator
import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

import app.consultant.model_runtime as model_runtime
from app.config import Settings
from app.consultant.candidate_tool import (
    CandidateEditToolBinding,
    build_job_document_candidate_edit_tool,
)
from app.consultant.context import DocumentSourceLookup, build_employee_source_tools
from app.consultant.model_runtime import build_consultant_agent
from app.consultant.model_output import (
    ConsultantModelOutput,
    ConsultantOutputMappingError,
    OutputAnalysisBasis,
    OutputAttentionChange,
    OutputAttentionDisposition,
    OutputCandidatePublication,
    OutputGap,
    OutputQuestion,
    OutputQuestionKind,
    OutputQuoteAnchor,
    OutputSufficiency,
    OutputUnderstandingChange,
    map_consultant_model_output,
)
from app.consultant.results import (
    AttentionOperation,
    CandidatePublication,
    GapOperation,
    GapReason,
    UnderstandingOperation,
)
from app.consultant.run_service import build_configured_execution
from app.consultant.skill_backend import PackageSkillBackend
from app.consultant.state import (
    InterviewPriority,
    InterviewWorkStatus,
    UnderstandingImpact,
)


def _basis(source_id: UUID, *skill_ids: str) -> OutputAnalysisBasis:
    return OutputAnalysisBasis(
        source_ids=(source_id,),
        quote_anchors=(),
        skill_ids=skill_ids,
    )


def _no_question() -> OutputQuestion:
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


def _sufficiency(source_id: UUID) -> OutputSufficiency:
    del source_id
    return OutputSufficiency(
        currently_enough=False,
        reason="仍缺完成標準。",
        remaining_gap_reasons=(GapReason.COMPLETION_STANDARD_MISSING,),
        continuing_benefit="繼續訪談可確認完成標準。",
        basis_ordinal=1,
    )


def _output(source_id: UUID, **overrides: Any) -> ConsultantModelOutput:
    values: dict[str, Any] = {
        "visible_reply": "我理解你會整理採購需求。",
        "analysis_bases": (_basis(source_id, "task-boundary"),),
        "reply_basis_ordinal": 1,
        "used_skill_ids": ("task-boundary",),
        "understanding_changes": (),
        "attention_changes": (),
        "gaps": (),
        "candidate_publication": OutputCandidatePublication(
            candidate_revision=0,
            revision_digest="",
            action_ids=(),
        ),
        "question": _no_question(),
        "sufficiency": _sufficiency(source_id),
    }
    values.update(overrides)
    return ConsultantModelOutput(**values)


def _walk_schema(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_schema(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_schema(value)


def _expanded_object_depth(schema: dict[str, Any]) -> int:
    definitions = schema.get("$defs", {})

    def visit(node: Any, active_refs: frozenset[str] = frozenset()) -> int:
        if not isinstance(node, dict):
            return 0
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            name = reference.rsplit("/", 1)[-1]
            if name in active_refs:
                return 0
            return visit(definitions[name], active_refs | {name})
        child_depth = 0
        for child in node.get("properties", {}).values():
            child_depth = max(child_depth, visit(child, active_refs))
        child_depth = max(child_depth, visit(node.get("items"), active_refs))
        return child_depth + (1 if node.get("type") == "object" else 0)

    return visit(schema)


def _schema_metrics(schema: dict[str, Any]) -> dict[str, int]:
    nodes = tuple(_walk_schema(schema))
    objects = tuple(node for node in nodes if node.get("type") == "object")
    return {
        "definitions": len(schema.get("$defs", {})),
        "properties": sum(len(node.get("properties", {})) for node in objects),
        "optional_parameters": sum(
            len(set(node.get("properties", {})) - set(node.get("required", ())))
            for node in objects
        ),
        "union_sites": sum(
            "anyOf" in node or "oneOf" in node for node in nodes
        ),
        "open_objects": sum(
            node.get("additionalProperties") is not False for node in objects
        ),
        "object_depth": _expanded_object_depth(schema),
    }


def _combined_schema_metrics(
    schemas: tuple[dict[str, Any], ...],
) -> dict[str, int]:
    metrics = tuple(_schema_metrics(schema) for schema in schemas)
    return {
        "schemas": len(schemas),
        "definitions": sum(item["definitions"] for item in metrics),
        "properties": sum(item["properties"] for item in metrics),
        "optional_parameters": sum(
            item["optional_parameters"] for item in metrics
        ),
        "union_sites": sum(item["union_sites"] for item in metrics),
        "open_objects": sum(item["open_objects"] for item in metrics),
        "max_object_depth": max(item["object_depth"] for item in metrics),
        "bytes": len(
            json.dumps(schemas, ensure_ascii=False, separators=(",", ":")).encode()
        ),
    }


def test_model_output_schema_is_closed_required_and_union_free() -> None:
    schema = ConsultantModelOutput.model_json_schema()
    nodes = tuple(_walk_schema(schema))
    objects = tuple(node for node in nodes if node.get("type") == "object")

    assert objects
    assert not any("anyOf" in node or "oneOf" in node for node in nodes)
    assert all(node.get("additionalProperties") is False for node in objects)
    assert all(
        set(node.get("required", ())) == set(node.get("properties", ()))
        for node in objects
    )
    assert _expanded_object_depth(schema) <= 5


def test_final_schema_has_only_candidate_publication_not_document_draft_payloads() -> None:
    schema = ConsultantModelOutput.model_json_schema()
    serialized = str(schema)

    assert "candidate_publication" in schema["properties"]
    assert "reviewable_document_changes" not in serialized
    assert "OutputDocumentChange" not in serialized
    assert "OutputDuty" not in serialized
    assert "OutputTask" not in serialized
    assert "OutputOpksItem" not in serialized


def test_model_output_schema_metrics_are_review_visible() -> None:
    assert _schema_metrics(ConsultantModelOutput.model_json_schema()) == {
        "definitions": 16,
        "properties": 61,
        "optional_parameters": 0,
        "union_sites": 0,
        "open_objects": 0,
        "object_depth": 3,
    }


def test_model_facing_id_anchor_and_question_fields_explain_safe_sentinels() -> None:
    assert "不得自行編造" in (
        OutputUnderstandingChange.model_fields["work_ids"].description or ""
    )
    assert "可留空" in (
        OutputAnalysisBasis.model_fields["quote_anchors"].description or ""
    )
    assert "exclusive" in (
        OutputQuoteAnchor.model_fields["end"].description or ""
    )
    assert "next 時必須留空" in (
        OutputQuestion.model_fields["affected_work_ids"].description or ""
    )


def test_langchain_converts_the_same_closed_union_free_pydantic_contract() -> None:
    converted = convert_to_openai_tool(ConsultantModelOutput)
    assert converted["function"]["name"] == "ConsultantModelOutput"
    provider_schema = converted["function"]["parameters"]
    nodes = tuple(_walk_schema(provider_schema))
    objects = tuple(node for node in nodes if node.get("type") == "object")

    assert not any("anyOf" in node or "oneOf" in node for node in nodes)
    assert all(node.get("additionalProperties") is False for node in objects)
    assert all(
        set(node.get("required", ())) == set(node.get("properties", ()))
        for node in objects
    )
    assert _schema_metrics(provider_schema) == {
        "definitions": 0,
        "properties": 61,
        "optional_parameters": 0,
        "union_sites": 0,
        "open_objects": 0,
        "object_depth": 3,
    }


def test_combined_model_grammar_measures_actual_tool_and_provider_strategy_schemas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = FilesystemMiddleware(
        backend=PackageSkillBackend(("task-boundary",)),
        tools=["read_file"],
        custom_tool_descriptions={
            "read_file": "Read one eligible Caliburn analysis Skill.",
        },
        system_prompt=None,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
    )
    source_tools = build_employee_source_tools(
        DocumentSourceLookup(runtime=object()),  # type: ignore[arg-type]
        document_id=uuid4(),
    )
    candidate_tool = build_job_document_candidate_edit_tool(
        binding=CandidateEditToolBinding(
            runtime=object(),  # type: ignore[arg-type]
            document_id=uuid4(),
            run_id=uuid4(),
            baseline_revision=1,
            selected_skill_ids=("task-boundary",),
        ),
        loaded_skill_ids=lambda: ("task-boundary",),
    )
    captured: dict[str, Any] = {}

    def capture_create_agent(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(model_runtime, "create_agent", capture_create_agent)
    build_consultant_agent(
        model=FakeMessagesListChatModel(responses=[]),
        execution=build_configured_execution(
            Settings(_env_file=None, openrouter_api_key="test-key")
        ),
        response_schema=ConsultantModelOutput,
    )
    tools = (*files.tools, *source_tools)
    schemas = tuple(
        convert_to_openai_tool(tool)["function"]["parameters"] for tool in tools
    ) + (
        convert_to_openai_tool(candidate_tool.tool_call_schema)["function"][
            "parameters"
        ],
        captured["response_format"].schema_spec.json_schema,
    )

    assert tuple(tool.name for tool in tools) == (
        "read_file",
        "employee_source_get",
        "employee_source_lineage",
        "employee_source_search",
    )
    assert candidate_tool.name == "job_document_candidate_edit"
    candidate_metrics = _schema_metrics(schemas[-2])
    final_metrics = _schema_metrics(schemas[-1])
    combined_metrics = _combined_schema_metrics(schemas)

    for metrics in (candidate_metrics, final_metrics):
        assert metrics["optional_parameters"] == 0
        assert metrics["union_sites"] == 0
        assert metrics["open_objects"] == 0
    assert combined_metrics["schemas"] == 6
    assert combined_metrics["definitions"] == 0
    assert combined_metrics["union_sites"] == 0
    assert combined_metrics["properties"] > 0
    assert combined_metrics["max_object_depth"] >= max(
        candidate_metrics["object_depth"], final_metrics["object_depth"]
    )
    assert combined_metrics["bytes"] > 0


def test_candidate_publication_maps_neutral_and_exact_valid_receipts() -> None:
    source_id = uuid4()
    action_id = uuid4()

    neutral = map_consultant_model_output(_output(source_id))
    published = map_consultant_model_output(
        _output(
            source_id,
            candidate_publication=OutputCandidatePublication(
                candidate_revision=2,
                revision_digest="a" * 64,
                action_ids=(action_id,),
            ),
        )
    )

    assert neutral.candidate_publication is None
    assert published.candidate_publication == CandidatePublication(
        candidate_revision=2,
        revision_digest="a" * 64,
        action_ids=(action_id,),
    )


@pytest.mark.parametrize(
    "candidate_revision, revision_digest, action_ids",
    [
        pytest.param(0, "a" * 64, (), id="neutral-with-digest"),
        pytest.param(0, "", (uuid4(),), id="neutral-with-action"),
        pytest.param(1, "", (uuid4(),), id="positive-without-digest"),
        pytest.param(1, "a" * 64, (), id="positive-without-action"),
        pytest.param(1, "a" * 64, (uuid4(),) * 2, id="duplicate-action"),
    ],
)
def test_candidate_publication_rejects_mixed_sentinels_and_duplicate_handles(
    candidate_revision: int,
    revision_digest: str,
    action_ids: tuple[UUID, ...],
) -> None:
    with pytest.raises(ConsultantOutputMappingError):
        map_consultant_model_output(
            _output(
                uuid4(),
                candidate_publication=OutputCandidatePublication(
                    candidate_revision=candidate_revision,
                    revision_digest=revision_digest,
                    action_ids=action_ids,
                ),
            )
        )


def test_candidate_publication_digest_requires_lowercase_sha256_or_neutral_empty() -> None:
    with pytest.raises(ValidationError):
        OutputCandidatePublication(
            candidate_revision=1,
            revision_digest="not-a-digest",
            action_ids=(uuid4(),),
        )


def test_model_output_normalizes_repeated_evidence_into_one_basis_table() -> None:
    assert "analysis_bases" in ConsultantModelOutput.model_fields
    assert "reply_basis_ordinal" in ConsultantModelOutput.model_fields
    assert "reply_basis" not in ConsultantModelOutput.model_fields
    for effect in (
        OutputUnderstandingChange,
        OutputAttentionChange,
        OutputGap,
        OutputQuestion,
        OutputSufficiency,
    ):
        assert "basis_ordinal" in effect.model_fields
        assert "basis" not in effect.model_fields

def test_minimal_model_output_maps_to_the_rich_application_result() -> None:
    source_id = uuid4()

    result = map_consultant_model_output(_output(source_id))

    assert result.visible_reply == "我理解你會整理採購需求。"
    assert result.used_skill_ids == ("task-boundary",)
    assert result.next_question is None
    assert result.required_clarification is None
    assert result.sufficiency.remaining_gap_reasons == (
        GapReason.COMPLETION_STANDARD_MISSING,
    )


def test_all_non_document_effects_survive_the_wire_mapping() -> None:
    source_id = uuid4()
    understanding_id = uuid4()
    attention_id = uuid4()
    subject_id = uuid4()
    gap_id = uuid4()
    anchor = OutputQuoteAnchor(
        source_id=source_id,
        start=0,
        end=4,
        quote="整理採購",
    )
    anchored_basis = OutputAnalysisBasis(
        source_ids=(source_id,),
        quote_anchors=(anchor,),
        skill_ids=("task-boundary",),
    )

    result = map_consultant_model_output(
        _output(
            source_id,
            analysis_bases=(anchored_basis,),
            understanding_changes=(
                OutputUnderstandingChange(
                    operation=UnderstandingOperation.REVISE,
                    understanding_id=str(understanding_id),
                    kind="current_responsibility",
                    text="員工負責整理採購需求。",
                    impact=UnderstandingImpact.MEANINGFUL_SHIFT,
                    work_ids=(attention_id,),
                    basis_ordinal=1,
                ),
            ),
            attention_changes=(
                OutputAttentionChange(
                    operation=AttentionOperation.REVISE,
                    attention_id=str(attention_id),
                    kind="task_interview",
                    title="整理採購需求",
                    subject_id=str(subject_id),
                    reason="仍需確認完成標準。",
                    missing_before_enough="可觀察的完成條件",
                    recommended_next_step="追問交付條件",
                    priority=InterviewPriority.TASK_BOUNDARY,
                    disposition=OutputAttentionDisposition.PARKED,
                    make_current=False,
                    basis_ordinal=1,
                ),
            ),
            gaps=(
                OutputGap(
                    operation=GapOperation.HOLD,
                    gap_id=str(gap_id),
                    reason=GapReason.COMPLETION_STANDARD_MISSING,
                    description="尚未確認完成條件。",
                    subject_kind="task",
                    subject_id=str(subject_id),
                    blocks_dependent_analysis=False,
                    basis_ordinal=1,
                ),
            ),
        )
    )

    assert result.understanding_changes[0].understanding_id == understanding_id
    assert result.understanding_changes[0].basis.quote_anchors[0].quote == "整理採購"
    assert result.attention_changes[0].attention_id == attention_id
    assert result.attention_changes[0].disposition is InterviewWorkStatus.PARKED
    assert result.gaps[0].gap_id == gap_id


def test_required_clarification_maps_to_the_employee_form_instead_of_next_question() -> None:
    source_id = uuid4()
    work_id = uuid4()
    result = map_consultant_model_output(
        _output(
            source_id,
            question=OutputQuestion(
                kind=OutputQuestionKind.REQUIRED_CLARIFICATION,
                text="這項核准是你負責，還是主管負責？",
                answer_target="",
                reason="責任歸屬互相衝突。",
                current_understanding="目前兩種說法都存在。",
                choices=("我負責", "主管負責"),
                affected_work_ids=(work_id,),
                affected_branch="task-responsibility",
                basis_ordinal=1,
            ),
        )
    )

    assert result.next_question is None
    assert result.required_clarification is not None
    assert result.required_clarification.question.startswith("這項核准")
    assert result.required_clarification.affected_work_ids == (work_id,)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        pytest.param(
            lambda source: {"question": _no_question().model_copy(update={"text": "偷渡問題"})},
            "question",
            id="content-in-none-question",
        ),
        pytest.param(
            lambda source: {
                "question": OutputQuestion(
                    kind=OutputQuestionKind.NEXT,
                    text="完成後交給誰？",
                    answer_target="task result",
                    reason="確認交付邊界。",
                    current_understanding="不應夾帶",
                    choices=(),
                    affected_work_ids=(),
                    affected_branch="",
                    basis_ordinal=1,
                )
            },
            "next question",
            id="clarification-content-in-next-question",
        ),
        pytest.param(
            lambda source: {
                "understanding_changes": (
                    OutputUnderstandingChange(
                        operation=UnderstandingOperation.ADD,
                        understanding_id=str(uuid4()),
                        kind="current_responsibility",
                        text="員工負責整理採購需求。",
                        impact=UnderstandingImpact.ROUTINE,
                        work_ids=(),
                        basis_ordinal=1,
                    ),
                )
            },
            "application-owned ID",
            id="new-understanding-smuggles-id",
        ),
        pytest.param(
            lambda source: {
                "attention_changes": (
                    OutputAttentionChange(
                        operation=AttentionOperation.ADD,
                        attention_id=str(uuid4()),
                        kind="task_interview",
                        title="整理採購需求",
                        subject_id="",
                        reason="需要繼續訪談。",
                        missing_before_enough="",
                        recommended_next_step="",
                        priority=InterviewPriority.TASK_BOUNDARY,
                        disposition=OutputAttentionDisposition.NONE,
                        make_current=False,
                        basis_ordinal=1,
                    ),
                )
            },
            "application-owned ID",
            id="new-attention-smuggles-id",
        ),
        pytest.param(
            lambda source: {"reply_basis_ordinal": 0},
            "1-based",
            id="zero-basis-ordinal",
        ),
        pytest.param(
            lambda source: {
                "analysis_bases": (
                    _basis(source, "task-boundary"),
                    _basis(source, "task-boundary"),
                )
            },
            "unused analysis basis",
            id="unused-basis-row",
        ),
    ],
)
def test_mapper_rejects_contradictory_or_unrepresentable_content(
    mutate: Any, message: str
) -> None:
    source_id = uuid4()

    with pytest.raises(ConsultantOutputMappingError, match=message):
        map_consultant_model_output(_output(source_id, **mutate(source_id)))
