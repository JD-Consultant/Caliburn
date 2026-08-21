from __future__ import annotations

from collections.abc import Iterator
import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

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
    OutputSufficiency,
    OutputUnderstandingChange,
    map_consultant_model_output,
)
from app.consultant.provider_wire import OutputEvidenceReference
from app.consultant.results import (
    AttentionOperation,
    CandidatePublication,
    GapOperation,
    GapReason,
    UnderstandingOperation,
)
from app.consultant.state import (
    ApprovedJobDocument,
    EmployeeSource,
    EmployeeSourceKind,
    InterviewPriority,
    InterviewWorkStatus,
    SourceProcessingStatus,
    UnderstandingImpact,
)
from app.consultant.workspace_resources import WorkspaceCatalog


def _source(source_id: UUID) -> EmployeeSource:
    return EmployeeSource.pending(
        source_id=source_id,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="我理解你會整理採購需求。",
    ).model_copy(update={"processing_status": SourceProcessingStatus.COMMITTED})


DOCUMENT_ID = uuid4()


def _catalog(source_id: UUID) -> WorkspaceCatalog:
    return WorkspaceCatalog.from_snapshot(
        ApprovedJobDocument(document_id=DOCUMENT_ID),
        sources=(_source(source_id),),
    )


def _basis(source_id: UUID, *skill_ids: str) -> OutputAnalysisBasis:
    return OutputAnalysisBasis(
        evidence=(
            OutputEvidenceReference(
                source_handle="source-001",
                quote="整理採購需求",
                occurrence=0,
                skill_ids=skill_ids,
            ),
        )
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


def _sufficiency() -> OutputSufficiency:
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
            action_handles=(),
        ),
        "question": _no_question(),
        "sufficiency": _sufficiency(),
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


def test_model_output_schema_is_closed_and_evidence_is_provider_neutral() -> None:
    schema = ConsultantModelOutput.model_json_schema()
    nodes = tuple(_walk_schema(schema))
    objects = tuple(node for node in nodes if node.get("type") == "object")

    assert objects
    assert all(node.get("additionalProperties") is False for node in objects)
    assert all(
        set(node.get("required", ())) == set(node.get("properties", ()))
        for node in objects
    )
    evidence_schema = schema["$defs"]["OutputEvidenceReference"]
    assert set(evidence_schema["required"]) == {
        "source_handle",
        "quote",
        "occurrence",
        "skill_ids",
    }
    assert evidence_schema["properties"]["occurrence"] == {
        "description": "逐字 quote 唯一時填 0；重複時填 1-based occurrence",
        "minimum": 0,
        "title": "Occurrence",
        "type": "integer",
    }
    assert "source_id" not in evidence_schema["properties"]
    assert "start" not in evidence_schema["properties"]
    assert "end" not in evidence_schema["properties"]
    publication_schema = schema["$defs"]["OutputCandidatePublication"]
    assert "action_handles" in publication_schema["properties"]
    assert "action_ids" not in publication_schema["properties"]
    assert publication_schema["properties"]["action_handles"]["items"]["type"] == "string"
    assert "format" not in publication_schema["properties"]["action_handles"]["items"]


def test_langchain_converts_the_same_final_contract() -> None:
    converted = convert_to_openai_tool(ConsultantModelOutput)
    provider_schema = converted["function"]["parameters"]
    assert converted["function"]["name"] == "ConsultantModelOutput"
    assert provider_schema["additionalProperties"] is False
    assert "candidate_publication" in provider_schema["properties"]


def test_model_evidence_is_resolved_by_handle_quote_and_occurrence() -> None:
    source_id = uuid4()
    output = _output(
        source_id,
        analysis_bases=(
            OutputAnalysisBasis(
                evidence=(
                    OutputEvidenceReference(
                        source_handle="source-001",
                        quote="採購",
                        occurrence=1,
                        skill_ids=("task-boundary",),
                    ),
                )
            ),
        ),
    )

    result = map_consultant_model_output(output, catalog=_catalog(source_id))

    anchor = result.reply_basis.quote_anchors[0]
    assert anchor.source_id == source_id
    assert (anchor.start, anchor.end, anchor.quote) == (7, 9, "採購")


def test_unknown_handle_or_quote_fails_before_rich_result_mapping() -> None:
    source_id = uuid4()
    output = _output(
        source_id,
        analysis_bases=(
            OutputAnalysisBasis(
                evidence=(
                    OutputEvidenceReference(
                        source_handle="source-999",
                        quote="不存在",
                        occurrence=0,
                        skill_ids=("task-boundary",),
                    ),
                )
            ),
        ),
    )

    with pytest.raises(ConsultantOutputMappingError, match="could not be resolved"):
        map_consultant_model_output(output, catalog=_catalog(source_id))


def test_candidate_publication_maps_neutral_and_exact_valid_receipts() -> None:
    source_id = uuid4()
    action_handle = "action-001"

    neutral = map_consultant_model_output(_output(source_id), catalog=_catalog(source_id))
    published = map_consultant_model_output(
        _output(
            source_id,
            candidate_publication=OutputCandidatePublication(
                candidate_revision=2,
                revision_digest="a" * 64,
                action_handles=(action_handle,),
            ),
        ),
        catalog=_catalog(source_id),
    )

    assert neutral.candidate_publication is None
    assert published.candidate_publication == CandidatePublication(
        candidate_revision=2,
        revision_digest="a" * 64,
        action_handles=(action_handle,),
    )
    assert published.candidate_publication.action_handles == (action_handle,)
    assert not hasattr(published.candidate_publication, "action_ids")


@pytest.mark.parametrize(
    "candidate_revision, revision_digest, action_handles",
    [
        pytest.param(0, "a" * 64, (), id="neutral-with-digest"),
        pytest.param(0, "", ("action-001",), id="neutral-with-action"),
        pytest.param(1, "", ("action-001",), id="positive-without-digest"),
        pytest.param(1, "a" * 64, (), id="positive-without-action"),
        pytest.param(1, "a" * 64, ("action-001",) * 2, id="duplicate-action"),
    ],
)
def test_candidate_publication_rejects_mixed_sentinels_and_duplicate_handles(
    candidate_revision: int,
    revision_digest: str,
    action_handles: tuple[str, ...],
) -> None:
    with pytest.raises(ConsultantOutputMappingError):
        map_consultant_model_output(
            _output(
                uuid4(),
                candidate_publication=OutputCandidatePublication(
                    candidate_revision=candidate_revision,
                    revision_digest=revision_digest,
                    action_handles=action_handles,
                ),
            ),
            catalog=_catalog(uuid4()),
        )


def test_candidate_publication_digest_requires_lowercase_sha256_or_neutral_empty() -> None:
    with pytest.raises(ValidationError):
        OutputCandidatePublication(
            candidate_revision=1,
            revision_digest="not-a-digest",
            action_handles=("action-001",),
        )


def test_all_non_document_effects_survive_the_wire_mapping() -> None:
    source_id = uuid4()
    understanding_id = uuid4()
    attention_id = uuid4()
    subject_id = uuid4()
    gap_id = uuid4()
    result = map_consultant_model_output(
        _output(
            source_id,
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
        ),
        catalog=_catalog(source_id),
    )

    assert result.understanding_changes[0].understanding_id == understanding_id
    assert result.understanding_changes[0].basis.quote_anchors[0].quote == "整理採購需求"
    assert result.attention_changes[0].attention_id == attention_id
    assert result.attention_changes[0].disposition is InterviewWorkStatus.PARKED
    assert result.gaps[0].gap_id == gap_id


def test_required_clarification_maps_to_employee_form() -> None:
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
        ),
        catalog=_catalog(source_id),
    )

    assert result.next_question is None
    assert result.required_clarification is not None
    assert result.required_clarification.affected_work_ids == (work_id,)


def test_model_output_rejects_contradictory_none_question() -> None:
    source_id = uuid4()
    with pytest.raises(ConsultantOutputMappingError, match="question"):
        map_consultant_model_output(
            _output(
                source_id,
                question=_no_question().model_copy(update={"text": "偷渡問題"}),
            ),
            catalog=_catalog(source_id),
        )


def test_model_output_schema_metrics_are_recorded_without_legacy_editor_schema() -> None:
    schema = ConsultantModelOutput.model_json_schema()
    serialized = json.dumps(schema, ensure_ascii=False)
    assert "analysis_bases" in schema["properties"]
    assert "candidate_publication" in schema["properties"]
    assert "document_draft" not in serialized
    assert "model_offsets" not in serialized
