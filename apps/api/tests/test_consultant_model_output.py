from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.consultant.model_output import (
    ConsultantModelOutput,
    ConsultantOutputMappingError,
    OutputAnalysisBasis,
    OutputAttentionChange,
    OutputAttentionDisposition,
    OutputDocumentChange,
    OutputDocumentField,
    OutputDocumentTarget,
    OutputDuty,
    OutputEnabler,
    OutputGap,
    OutputOpksItem,
    OutputOpksKind,
    OutputQuestion,
    OutputQuestionKind,
    OutputQuoteAnchor,
    OutputResponsibilityRole,
    OutputSufficiency,
    OutputTask,
    OutputUnderstandingChange,
    map_consultant_model_output,
)
from app.consultant.results import (
    AttentionOperation,
    DocumentChangeOperation,
    GapOperation,
    GapReason,
    UnderstandingOperation,
)
from app.consultant.state import (
    ApprovedResponsibilityRole,
    ApprovedEnablerKind,
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
        "reviewable_document_changes": (),
        "question": _no_question(),
        "sufficiency": _sufficiency(source_id),
    }
    values.update(overrides)
    return ConsultantModelOutput(**values)


def _document_change(source_id: UUID, **overrides: Any) -> OutputDocumentChange:
    values: dict[str, Any] = {
        "operation": DocumentChangeOperation.REVISE,
        "target": OutputDocumentTarget.JOB_TITLE,
        "target_id": "",
        "field": OutputDocumentField.VALUE,
        "text_value": "採購專員",
        "integer_value": -1,
        "uuid_value": "",
        "uuid_values": (),
        "enablers": (),
        "duties": (),
        "tasks": (),
        "opks_items": (),
        "target_ids": (),
        "opks_kind": OutputOpksKind.NONE,
        "task_ids": (),
        "indicator_ids": (),
        "basis_ordinal": 1,
    }
    values.update(overrides)
    return OutputDocumentChange(**values)


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


def test_model_output_schema_metrics_are_review_visible() -> None:
    assert _schema_metrics(ConsultantModelOutput.model_json_schema()) == {
        "definitions": 26,
        "properties": 96,
        "optional_parameters": 0,
        "union_sites": 0,
        "open_objects": 0,
        "object_depth": 4,
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


def test_model_facing_document_field_discriminators_are_unambiguous() -> None:
    assert OutputDocumentField.VALUE.value == "top_level_value"
    assert OutputDocumentField.ENTITY.value == "whole_entity"
    description = OutputDocumentChange.model_fields["field"].description or ""
    assert "job_title" in description
    assert "whole_entity" in description


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
        "properties": 98,
        "optional_parameters": 0,
        "union_sites": 0,
        "open_objects": 0,
        "object_depth": 4,
    }


def test_model_output_schema_does_not_expose_free_form_document_json() -> None:
    fields = OutputDocumentChange.model_fields

    assert "path" not in fields
    assert "after" not in fields
    assert set(fields) >= {
        "target",
        "target_id",
        "field",
        "text_value",
        "integer_value",
        "uuid_value",
        "uuid_values",
        "enablers",
        "duties",
        "tasks",
        "opks_items",
    }


def test_model_output_normalizes_repeated_evidence_into_one_basis_table() -> None:
    assert "analysis_bases" in ConsultantModelOutput.model_fields
    assert "reply_basis_ordinal" in ConsultantModelOutput.model_fields
    assert "reply_basis" not in ConsultantModelOutput.model_fields
    for effect in (
        OutputUnderstandingChange,
        OutputAttentionChange,
        OutputGap,
        OutputDocumentChange,
        OutputQuestion,
        OutputSufficiency,
    ):
        assert "basis_ordinal" in effect.model_fields
        assert "basis" not in effect.model_fields


def test_neutral_wire_enums_track_the_application_enums() -> None:
    assert {item.value for item in OutputAttentionDisposition} == {
        "none",
        *(item.value for item in InterviewWorkStatus),
    }
    assert {item.value for item in OutputOpksKind} == {
        "none",
        "output",
        "indicator",
        "knowledge",
        "skill",
    }
    assert {item.value for item in OutputResponsibilityRole} == {
        "none",
        *(item.value for item in ApprovedResponsibilityRole),
    }


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


@pytest.mark.parametrize(
    ("change", "expected_path", "expected_after"),
    [
        pytest.param(
            {"target": OutputDocumentTarget.WORK_DESCRIPTION, "text_value": "負責採購作業。"},
            "/work_description",
            "負責採購作業。",
            id="top-level-text",
        ),
        pytest.param(
            {
                "operation": DocumentChangeOperation.REORDER,
                "target": OutputDocumentTarget.DUTY,
                "target_id": "00000000-0000-0000-0000-000000000001",
                "field": OutputDocumentField.DISPLAY_ORDER,
                "text_value": "",
                "integer_value": 0,
            },
            "/duties/00000000-0000-0000-0000-000000000001/display_order",
            0,
            id="integer",
        ),
        pytest.param(
            {
                "operation": DocumentChangeOperation.REASSIGN,
                "target": OutputDocumentTarget.TASK,
                "target_id": "00000000-0000-0000-0000-000000000002",
                "field": OutputDocumentField.DUTY_ID,
                "text_value": "",
                "uuid_value": "00000000-0000-0000-0000-000000000003",
            },
            "/tasks/00000000-0000-0000-0000-000000000002/duty_id",
            "00000000-0000-0000-0000-000000000003",
            id="uuid",
        ),
        pytest.param(
            {
                "target": OutputDocumentTarget.OPKS,
                "target_id": "00000000-0000-0000-0000-000000000004",
                "field": OutputDocumentField.TASK_IDS,
                "text_value": "",
                "uuid_values": (UUID("00000000-0000-0000-0000-000000000002"),),
                "opks_kind": OutputOpksKind.KNOWLEDGE,
                "task_ids": (UUID("00000000-0000-0000-0000-000000000002"),),
            },
            "/opks/00000000-0000-0000-0000-000000000004/task_ids",
            ["00000000-0000-0000-0000-000000000002"],
            id="uuid-list",
        ),
        pytest.param(
            {
                "target": OutputDocumentTarget.TASK,
                "target_id": "00000000-0000-0000-0000-000000000002",
                "field": OutputDocumentField.ENABLERS,
                "text_value": "",
                "enablers": (
                    OutputEnabler(kind=ApprovedEnablerKind.TOOL_SYSTEM, name="ERP"),
                ),
            },
            "/tasks/00000000-0000-0000-0000-000000000002/enablers",
            [{"kind": "tool_system", "name": "ERP"}],
            id="typed-object-list",
        ),
    ],
)
def test_typed_scalar_document_payloads_map_to_existing_review_changes(
    change: dict[str, Any], expected_path: str, expected_after: object
) -> None:
    source_id = uuid4()
    mapped = map_consultant_model_output(
        _output(
            source_id,
            reviewable_document_changes=(
                _document_change(source_id, **change),
            ),
        )
    ).reviewable_document_changes[0]

    assert mapped.path == expected_path
    assert mapped.after == expected_after


def test_typed_entity_payloads_preserve_duty_task_and_opks_proposals() -> None:
    source_id = uuid4()
    task_id = uuid4()
    changes = (
        _document_change(
            source_id,
            operation=DocumentChangeOperation.ADD,
            target=OutputDocumentTarget.DUTY,
            field=OutputDocumentField.ENTITY,
            text_value="",
            duties=(OutputDuty(duty_id="", statement="管理採購作業", display_order=-1),),
        ),
        _document_change(
            source_id,
            operation=DocumentChangeOperation.ADD,
            target=OutputDocumentTarget.TASK,
            field=OutputDocumentField.ENTITY,
            text_value="",
            tasks=(
                OutputTask(
                    task_id=str(task_id),
                    duty_id="",
                    statement="建立請購單",
                    action="建立",
                    object="請購單",
                    purpose_result="",
                    context="",
                    frequency_text="",
                    responsibility_role=OutputResponsibilityRole.NONE,
                    enablers=(),
                    display_order=-1,
                ),
            ),
        ),
        _document_change(
            source_id,
            operation=DocumentChangeOperation.ADD,
            target=OutputDocumentTarget.OPKS,
            field=OutputDocumentField.ENTITY,
            text_value="",
            opks_items=(
                OutputOpksItem(
                    item_id="",
                    text="完成的請購單",
                    display_order=-1,
                    task_ids=(),
                    indicator_ids=(),
                ),
            ),
            opks_kind=OutputOpksKind.OUTPUT,
            task_ids=(task_id,),
        ),
    )

    mapped = map_consultant_model_output(
        _output(source_id, reviewable_document_changes=changes)
    ).reviewable_document_changes

    assert mapped[0].path == "/duties"
    assert mapped[0].after == {"statement": "管理採購作業"}
    assert mapped[1].path == "/tasks"
    assert mapped[1].after["task_id"] == str(task_id)
    assert mapped[1].after["statement"] == "建立請購單"
    assert "display_order" not in mapped[1].after
    assert mapped[2].path == "/opks"
    assert mapped[2].after == "完成的請購單"


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
                "reviewable_document_changes": (
                    _document_change(source, integer_value=0),
                )
            },
            "unused document payload",
            id="unused-payload-slot",
        ),
        pytest.param(
            lambda source: {
                "reviewable_document_changes": (
                    _document_change(
                        source,
                        target=OutputDocumentTarget.TASK,
                        target_id=str(uuid4()),
                        field=OutputDocumentField.TEXT,
                    ),
                )
            },
            "field",
            id="unsupported-target-field",
        ),
        pytest.param(
            lambda source: {
                "reviewable_document_changes": (
                    _document_change(source, opks_kind=OutputOpksKind.KNOWLEDGE),
                )
            },
            "non-OPKS",
            id="opks-metadata-on-other-target",
        ),
        pytest.param(
            lambda source: {
                "reviewable_document_changes": (
                    _document_change(
                        source,
                        operation=DocumentChangeOperation.REASSIGN,
                        target=OutputDocumentTarget.TASK,
                        target_id=str(uuid4()),
                        field=OutputDocumentField.DUTY_ID,
                        text_value="",
                        uuid_value="not-a-uuid",
                    ),
                )
            },
            "UUID",
            id="invalid-uuid-sentinel-field",
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
            lambda source: {
                "reviewable_document_changes": (
                    _document_change(
                        source,
                        operation=DocumentChangeOperation.MERGE,
                        target=OutputDocumentTarget.OPKS,
                        target_id="",
                        field=OutputDocumentField.ENTITY,
                        text_value="",
                        target_ids=(uuid4(),),
                        opks_kind=OutputOpksKind.KNOWLEDGE,
                        task_ids=(uuid4(),),
                        opks_items=(
                            OutputOpksItem(
                                item_id=str(uuid4()),
                                text="採購流程知識",
                                display_order=0,
                                task_ids=(uuid4(),),
                                indicator_ids=(),
                            ),
                        ),
                    ),
                )
            },
            "contradict",
            id="opks-linkage-copies-disagree",
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
