"""Compact, provider-facing structured output for the consultant model.

The provider contract deliberately differs from :mod:`app.consultant.results`.
It contains no nullable unions, optional properties, free-form dictionaries, or
model-authored JSON Pointer paths.  Pydantic owns schema generation and local
shape validation; the pure mapper below restores the richer application result
without granting the model document authority.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, ValidationError

from app.consultant.provider_wire import (
    AnalysisBasisTable,
    OutputAnalysisBasis,
    ProviderWireModel as OutputModel,
)
from app.consultant.results import (
    AttentionChange,
    AttentionOperation,
    ConsultantResult,
    GapOperation,
    GapReason,
    NextQuestion,
    RequiredClarificationDraft,
    SkillId,
    SourceSupersession,
    SufficiencyRecommendation,
    UnderstandingChange,
    UnderstandingOperation,
    VisibleGap,
)
from app.consultant.state import (
    InterviewPriority,
    InterviewWorkStatus,
    SourceProcessingStatus,
    SourceValidity,
    UnderstandingImpact,
)
from app.consultant.workspace_resources import Handle, WorkspaceCatalog


NEUTRAL = "none"
class OutputQuestionKind(StrEnum):
    NONE = NEUTRAL
    NEXT = "next"
    REQUIRED_CLARIFICATION = "required_clarification"


class OutputAttentionDisposition(StrEnum):
    NONE = NEUTRAL
    AVAILABLE = InterviewWorkStatus.AVAILABLE.value
    ACTIVE = InterviewWorkStatus.ACTIVE.value
    PARKED = InterviewWorkStatus.PARKED.value
    BLOCKED = InterviewWorkStatus.BLOCKED.value
    SUFFICIENT_FOR_NOW = InterviewWorkStatus.SUFFICIENT_FOR_NOW.value
    UNKNOWN = InterviewWorkStatus.UNKNOWN.value
    NOT_APPLICABLE = InterviewWorkStatus.NOT_APPLICABLE.value
    RETIRED = InterviewWorkStatus.RETIRED.value


class OutputUnderstandingChange(OutputModel):
    operation: UnderstandingOperation
    understanding_id: str = Field(description='新增時填 ""，其餘填既有穩定 ID')
    kind: str
    text: str
    impact: UnderstandingImpact
    work_ids: tuple[UUID, ...] = Field(
        description="只引用 context 既有 work ID；新 work 不得自行編造 ID，請留空"
    )
    basis_ordinal: int = Field(description="analysis_bases 的 1-based ordinal")


class OutputAttentionChange(OutputModel):
    operation: AttentionOperation
    attention_id: str = Field(description='新增時填 ""，其餘填既有穩定 ID')
    kind: str
    title: str = Field(description='不適用時填 ""')
    subject_id: str = Field(
        description='只引用 context 既有主體 ID；沒有既有主體時填 ""'
    )
    reason: str
    missing_before_enough: str = Field(description='不適用時填 ""')
    recommended_next_step: str = Field(description='不適用時填 ""')
    priority: InterviewPriority
    disposition: OutputAttentionDisposition = Field(
        description='不變更狀態時填 "none"'
    )
    make_current: bool
    basis_ordinal: int = Field(description="analysis_bases 的 1-based ordinal")


class OutputGap(OutputModel):
    operation: GapOperation
    gap_id: str = Field(description='新增時填 ""，其餘填既有穩定 ID')
    reason: GapReason
    description: str
    subject_kind: str
    subject_id: str = Field(
        description='只引用 context 既有主體 ID；沒有既有主體時填 ""'
    )
    blocks_dependent_analysis: bool
    basis_ordinal: int = Field(description="analysis_bases 的 1-based ordinal")


class OutputQuestion(OutputModel):
    kind: OutputQuestionKind
    text: str = Field(description='沒有問題時填 ""')
    answer_target: str = Field(description='非一般下一題時填 ""')
    reason: str = Field(description='沒有問題時填 ""')
    current_understanding: str = Field(description='非必要澄清時填 ""')
    choices: tuple[str, ...]
    affected_work_ids: tuple[UUID, ...] = Field(
        description="只引用 context 既有 work ID；none／next 時必須留空"
    )
    affected_branch: str = Field(description='非必要澄清時填 ""')
    basis_ordinal: int = Field(
        description='沒有問題時填 0，其餘填 analysis_bases 的 1-based ordinal'
    )


class OutputSufficiency(OutputModel):
    currently_enough: bool
    reason: str
    remaining_gap_reasons: tuple[GapReason, ...]
    continuing_benefit: str
    basis_ordinal: int = Field(description="analysis_bases 的 1-based ordinal")


class OutputSourceSupersession(OutputModel):
    superseded_source_handle: Handle


class ConsultantModelOutput(OutputModel):
    visible_reply: str
    analysis_bases: tuple[OutputAnalysisBasis, ...]
    reply_basis_ordinal: int = Field(
        description="visible_reply 所用 analysis_bases 的 1-based ordinal"
    )
    understanding_changes: tuple[OutputUnderstandingChange, ...]
    attention_changes: tuple[OutputAttentionChange, ...]
    gaps: tuple[OutputGap, ...]
    question: OutputQuestion
    sufficiency: OutputSufficiency
    source_supersessions: tuple[OutputSourceSupersession, ...] = Field(max_length=1)


class ConsultantOutputMappingError(ValueError):
    pass


def map_consultant_model_output(
    output: ConsultantModelOutput,
    *,
    catalog: WorkspaceCatalog,
    current_source_id: UUID,
) -> ConsultantResult:
    """Restore one provider wire value without inventing or discarding content."""

    try:
        bases = AnalysisBasisTable(output.analysis_bases, catalog=catalog)
        next_question, clarification = _map_question(output.question, bases)
        source_supersession = _map_source_supersession(
            output.source_supersessions,
            question_kind=output.question.kind,
            catalog=catalog,
            current_source_id=current_source_id,
        )
        result = ConsultantResult(
            visible_reply=output.visible_reply,
            reply_basis=bases.resolve(
                output.reply_basis_ordinal, "reply_basis_ordinal"
            ),
            understanding_changes=tuple(
                _map_understanding(item, bases)
                for item in output.understanding_changes
            ),
            attention_changes=tuple(
                _map_attention(item, bases) for item in output.attention_changes
            ),
            gaps=tuple(_map_gap(item, bases) for item in output.gaps),
            next_question=next_question,
            required_clarification=clarification,
            source_supersession=source_supersession,
            sufficiency=SufficiencyRecommendation(
                currently_enough=output.sufficiency.currently_enough,
                reason=output.sufficiency.reason,
                remaining_gap_reasons=output.sufficiency.remaining_gap_reasons,
                continuing_benefit=output.sufficiency.continuing_benefit,
                basis=bases.resolve(
                    output.sufficiency.basis_ordinal,
                    "sufficiency basis_ordinal",
                ),
            ),
        )
        bases.reject_unused()
        return result
    except ConsultantOutputMappingError:
        raise
    except (ValidationError, ValueError) as error:
        raise ConsultantOutputMappingError(
            str(error)
        ) from error


def _map_source_supersession(
    values: tuple[OutputSourceSupersession, ...],
    *,
    question_kind: OutputQuestionKind,
    catalog: WorkspaceCatalog,
    current_source_id: UUID,
) -> SourceSupersession | None:
    if not values:
        return None
    if question_kind is OutputQuestionKind.REQUIRED_CLARIFICATION:
        raise ConsultantOutputMappingError(
            "required clarification cannot carry a source supersession"
        )
    if len(values) > 1:
        raise ConsultantOutputMappingError(
            "source supersessions support at most one target"
        )
    handles = tuple(item.superseded_source_handle for item in values)
    if len(handles) != len(set(handles)):
        raise ConsultantOutputMappingError(
            "source supersession targets must be unique"
        )

    try:
        current_handle = catalog.source_handle_for_id(current_source_id)
        current_source = catalog.source_for_handle(current_handle)
    except (KeyError, ValueError) as error:
        raise ConsultantOutputMappingError(
            "current answer source is not a materialized source in this document"
        ) from error
    if current_source.document_id != catalog.document_id:
        raise ConsultantOutputMappingError(
            "current answer source crosses document scope"
        )
    if current_source.validity is not SourceValidity.CURRENT:
        raise ConsultantOutputMappingError(
            "current answer source is already superseded"
        )
    if current_source.processing_status is not SourceProcessingStatus.COMMITTED:
        raise ConsultantOutputMappingError(
            "current answer source is not committed"
        )

    try:
        target = catalog.source_for_handle(handles[0])
    except (KeyError, ValueError) as error:
        raise ConsultantOutputMappingError(
            "source supersession target is not a known employee source"
        ) from error
    if target.document_id != catalog.document_id:
        raise ConsultantOutputMappingError(
            "source supersession target crosses document scope"
        )
    if target.source_id == current_source_id:
        raise ConsultantOutputMappingError(
            "source supersession cannot target itself"
        )
    exact_pair_replay = (
        target.validity is SourceValidity.SUPERSEDED
        and target.superseded_by_source_id == current_source_id
        and current_source.supersedes_source_id == target.source_id
    )
    if target.validity is not SourceValidity.CURRENT and not exact_pair_replay:
        raise ConsultantOutputMappingError(
            "source supersession target is already superseded"
        )
    if target.processing_status is not SourceProcessingStatus.COMMITTED:
        raise ConsultantOutputMappingError(
            "source supersession target is not committed"
        )
    return SourceSupersession(superseded_source_id=target.source_id)


def _map_understanding(
    value: OutputUnderstandingChange, bases: AnalysisBasisTable
) -> UnderstandingChange:
    if value.operation is UnderstandingOperation.ADD and value.understanding_id:
        raise ConsultantOutputMappingError(
            "new understanding cannot carry an application-owned ID"
        )
    return UnderstandingChange(
        operation=value.operation,
        understanding_id=_optional_uuid(
            value.understanding_id, "understanding_id"
        ),
        kind=value.kind,
        text=value.text,
        impact=value.impact,
        work_ids=value.work_ids,
        basis=bases.resolve(value.basis_ordinal, "understanding basis_ordinal"),
    )


def _map_attention(
    value: OutputAttentionChange, bases: AnalysisBasisTable
) -> AttentionChange:
    if value.operation is AttentionOperation.ADD and value.attention_id:
        raise ConsultantOutputMappingError(
            "new attention item cannot carry an application-owned ID"
        )
    disposition = (
        None
        if value.disposition is OutputAttentionDisposition.NONE
        else InterviewWorkStatus(value.disposition.value)
    )
    return AttentionChange(
        operation=value.operation,
        attention_id=_optional_uuid(value.attention_id, "attention_id"),
        kind=value.kind,
        title=_optional_text(value.title),
        subject_id=_optional_uuid(value.subject_id, "attention subject_id"),
        reason=value.reason,
        missing_before_enough=_optional_text(value.missing_before_enough),
        recommended_next_step=_optional_text(value.recommended_next_step),
        priority=value.priority,
        disposition=disposition,
        make_current=value.make_current,
        basis=bases.resolve(value.basis_ordinal, "attention basis_ordinal"),
    )


def _map_gap(value: OutputGap, bases: AnalysisBasisTable) -> VisibleGap:
    return VisibleGap(
        operation=value.operation,
        gap_id=_optional_uuid(value.gap_id, "gap_id"),
        reason=value.reason,
        description=value.description,
        subject_kind=value.subject_kind,
        subject_id=_optional_uuid(value.subject_id, "gap subject_id"),
        blocks_dependent_analysis=value.blocks_dependent_analysis,
        basis=bases.resolve(value.basis_ordinal, "gap basis_ordinal"),
    )


def _map_question(
    value: OutputQuestion,
    bases: AnalysisBasisTable,
) -> tuple[NextQuestion | None, RequiredClarificationDraft | None]:
    if value.kind is OutputQuestionKind.NONE:
        if (
            value.text
            or value.answer_target
            or value.reason
            or value.current_understanding
            or value.choices
            or value.affected_work_ids
            or value.affected_branch
            or value.basis_ordinal != 0
        ):
            raise ConsultantOutputMappingError(
                "question kind none cannot carry question content"
            )
        return None, None
    if value.kind is OutputQuestionKind.NEXT:
        if (
            value.current_understanding
            or value.choices
            or value.affected_work_ids
            or value.affected_branch
        ):
            raise ConsultantOutputMappingError(
                "next question cannot carry required-clarification content"
            )
        return (
            NextQuestion(
                text=value.text,
                answer_target=value.answer_target,
                reason=value.reason,
                basis=bases.resolve(
                    value.basis_ordinal, "next question basis_ordinal"
                ),
            ),
            None,
        )
    if value.answer_target:
        raise ConsultantOutputMappingError(
            "required clarification cannot carry next-question answer_target"
        )
    return (
        None,
        RequiredClarificationDraft(
            reason=value.reason,
            question=value.text,
            current_understanding=value.current_understanding,
            choices=value.choices,
            affected_work_ids=value.affected_work_ids,
            affected_branch=value.affected_branch,
            basis=bases.resolve(
                value.basis_ordinal, "required clarification basis_ordinal"
            ),
        ),
    )


def _optional_text(value: str) -> str | None:
    return None if value == "" else value


def _optional_uuid(value: str, label: str) -> UUID | None:
    if value == "":
        return None
    return UUID(_required_uuid(value, label))


def _required_uuid(value: str, label: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ConsultantOutputMappingError(f"{label} must be a UUID") from error
