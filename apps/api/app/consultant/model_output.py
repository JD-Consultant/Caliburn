"""Compact, provider-facing structured output for the consultant model.

The provider contract deliberately differs from :mod:`app.consultant.results`.
It contains no nullable unions, optional properties, free-form dictionaries, or
model-authored JSON Pointer paths.  Pydantic owns schema generation and local
shape validation; the pure mapper below restores the richer application result
without granting the model document authority.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.consultant.results import (
    AnalysisBasis,
    AttentionChange,
    AttentionOperation,
    ConsultantResult,
    DocumentChangeOperation,
    GapOperation,
    GapReason,
    NextQuestion,
    OpksKind,
    RequiredClarificationDraft,
    ReviewableDocumentChange,
    SkillId,
    SufficiencyRecommendation,
    UnderstandingChange,
    UnderstandingOperation,
    VisibleGap,
)
from app.consultant.state import (
    ApprovedEnablerKind,
    ApprovedResponsibilityRole,
    InterviewPriority,
    InterviewWorkStatus,
    QuoteAnchor,
    UnderstandingImpact,
)


NEUTRAL = "none"
NEUTRAL_INTEGER = -1


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class OutputOpksKind(StrEnum):
    NONE = NEUTRAL
    OUTPUT = OpksKind.OUTPUT.value
    PERFORMANCE_INDICATOR = OpksKind.PERFORMANCE_INDICATOR.value
    KNOWLEDGE = OpksKind.KNOWLEDGE.value
    SKILL = OpksKind.SKILL.value


class OutputResponsibilityRole(StrEnum):
    NONE = NEUTRAL
    PRIMARY = ApprovedResponsibilityRole.PRIMARY.value
    SHARED = ApprovedResponsibilityRole.SHARED.value
    ASSIST = ApprovedResponsibilityRole.ASSIST.value


class OutputDocumentTarget(StrEnum):
    JOB_TITLE = "job_title"
    WORK_DESCRIPTION = "work_description"
    DUTY = "duty"
    TASK = "task"
    OPKS = "opks"


class OutputDocumentField(StrEnum):
    VALUE = "top_level_value"
    ENTITY = "whole_entity"
    STATEMENT = "statement"
    DISPLAY_ORDER = "display_order"
    DUTY_ID = "duty_id"
    ACTION = "action"
    OBJECT = "object"
    PURPOSE_RESULT = "purpose_result"
    CONTEXT = "context"
    FREQUENCY_TEXT = "frequency_text"
    RESPONSIBILITY_ROLE = "responsibility_role"
    ENABLERS = "enablers"
    TEXT = "text"
    TASK_IDS = "task_ids"
    INDICATOR_IDS = "indicator_ids"


class OutputQuoteAnchor(OutputModel):
    source_id: UUID = Field(description="必須是 context 明列的員工來源 ID")
    start: int = Field(description="quote 在來源文字中的 0-based 起點；不得用占位值")
    end: int = Field(
        description="quote 的 exclusive 終點，必須等於 start + len(quote)"
    )
    quote: str = Field(description="必須逐字存在於指定員工來源")


class OutputAnalysisBasis(OutputModel):
    source_ids: tuple[UUID, ...]
    quote_anchors: tuple[OutputQuoteAnchor, ...] = Field(
        description="無法保證逐字位置時可留空，不得用假 offset 占位"
    )
    skill_ids: tuple[SkillId, ...]


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


class OutputEnabler(OutputModel):
    kind: ApprovedEnablerKind
    name: str


class OutputDuty(OutputModel):
    duty_id: str = Field(description='由應用程式配置新 ID 時填 ""')
    statement: str
    display_order: int = Field(description="新增時填 -1，由應用程式配置排序")


class OutputTask(OutputModel):
    task_id: str = Field(description='由應用程式配置新 ID 時填 ""')
    duty_id: str = Field(description='尚未分組時填 ""')
    statement: str
    action: str
    object: str
    purpose_result: str = Field(description='尚未確認時填 ""')
    context: str = Field(description='尚未確認時填 ""')
    frequency_text: str = Field(description='尚未確認時填 ""')
    responsibility_role: OutputResponsibilityRole = Field(
        description='尚未確認時填 "none"'
    )
    enablers: tuple[OutputEnabler, ...]
    display_order: int = Field(description="新增時填 -1，由應用程式配置排序")


class OutputOpksItem(OutputModel):
    item_id: str = Field(description='由應用程式配置新 ID 時填 ""')
    text: str
    display_order: int = Field(
        description='新增單一 OPKS 且由應用程式排序時填 -1'
    )
    task_ids: tuple[UUID, ...]
    indicator_ids: tuple[UUID, ...]


class OutputDocumentChange(OutputModel):
    operation: DocumentChangeOperation = Field(
        description="新增完整實體用 add；修改單一欄位用 revise／reassign／reorder"
    )
    target: OutputDocumentTarget = Field(description="要變更的文件層級或實體類型")
    target_id: str = Field(
        description='最上層欄位、集合操作或新增實體時填 ""'
    )
    field: OutputDocumentField = Field(
        description="job_title／work_description 使用 top_level_value；完整 Duty／Task／OPKS 使用 whole_entity；單欄修改才使用具名欄位"
    )
    text_value: str = Field(description='不是文字欄位時填 ""')
    integer_value: int = Field(description='不是排序欄位時填 -1')
    uuid_value: str = Field(description='不是單一 ID 欄位時填 ""')
    uuid_values: tuple[UUID, ...]
    enablers: tuple[OutputEnabler, ...]
    duties: tuple[OutputDuty, ...] = Field(
        description="只有 target=duty 且 field=whole_entity 時填；ADD 只能放一個"
    )
    tasks: tuple[OutputTask, ...] = Field(
        description="只有 target=task 且 field=whole_entity 時填；ADD 只能放一個"
    )
    opks_items: tuple[OutputOpksItem, ...] = Field(
        description="只有 target=opks 且 field=whole_entity 時填；ADD 只能放一個"
    )
    target_ids: tuple[UUID, ...]
    opks_kind: OutputOpksKind = Field(description='非 OPKS 變更時填 "none"')
    task_ids: tuple[UUID, ...]
    indicator_ids: tuple[UUID, ...]
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


class ConsultantModelOutput(OutputModel):
    visible_reply: str
    analysis_bases: tuple[OutputAnalysisBasis, ...]
    reply_basis_ordinal: int = Field(
        description="visible_reply 所用 analysis_bases 的 1-based ordinal"
    )
    used_skill_ids: tuple[SkillId, ...]
    understanding_changes: tuple[OutputUnderstandingChange, ...]
    attention_changes: tuple[OutputAttentionChange, ...]
    gaps: tuple[OutputGap, ...]
    reviewable_document_changes: tuple[OutputDocumentChange, ...]
    question: OutputQuestion
    sufficiency: OutputSufficiency


class ConsultantOutputMappingError(ValueError):
    pass


def map_consultant_model_output(output: ConsultantModelOutput) -> ConsultantResult:
    """Restore one provider wire value without inventing or discarding content."""

    try:
        bases = _BasisTable(output.analysis_bases)
        next_question, clarification = _map_question(output.question, bases)
        result = ConsultantResult(
            visible_reply=output.visible_reply,
            reply_basis=bases.resolve(
                output.reply_basis_ordinal, "reply_basis_ordinal"
            ),
            used_skill_ids=output.used_skill_ids,
            understanding_changes=tuple(
                _map_understanding(item, bases)
                for item in output.understanding_changes
            ),
            attention_changes=tuple(
                _map_attention(item, bases) for item in output.attention_changes
            ),
            gaps=tuple(_map_gap(item, bases) for item in output.gaps),
            reviewable_document_changes=tuple(
                _map_document_change(item, bases)
                for item in output.reviewable_document_changes
            ),
            next_question=next_question,
            required_clarification=clarification,
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
            "consultant model output could not be mapped to an application result"
        ) from error


def _map_basis(value: OutputAnalysisBasis) -> AnalysisBasis:
    return AnalysisBasis(
        source_ids=value.source_ids,
        quote_anchors=tuple(
            QuoteAnchor(
                source_id=item.source_id,
                start=item.start,
                end=item.end,
                quote=item.quote,
            )
            for item in value.quote_anchors
        ),
        skill_ids=value.skill_ids,
    )


class _BasisTable:
    def __init__(self, values: tuple[OutputAnalysisBasis, ...]) -> None:
        self._values = values
        self._mapped: dict[int, AnalysisBasis] = {}
        self._used: set[int] = set()

    def resolve(self, ordinal: int, label: str) -> AnalysisBasis:
        if ordinal <= 0 or ordinal > len(self._values):
            raise ConsultantOutputMappingError(
                f"{label} must reference a 1-based analysis basis ordinal"
            )
        self._used.add(ordinal)
        if ordinal not in self._mapped:
            self._mapped[ordinal] = _map_basis(self._values[ordinal - 1])
        return self._mapped[ordinal]

    def reject_unused(self) -> None:
        unused = set(range(1, len(self._values) + 1)) - self._used
        if unused:
            raise ConsultantOutputMappingError(
                f"unused analysis basis ordinals carry content: {sorted(unused)}"
            )


def _map_understanding(
    value: OutputUnderstandingChange, bases: _BasisTable
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
    value: OutputAttentionChange, bases: _BasisTable
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


def _map_gap(value: OutputGap, bases: _BasisTable) -> VisibleGap:
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


_COLLECTIONS = {
    OutputDocumentTarget.DUTY: "duties",
    OutputDocumentTarget.TASK: "tasks",
    OutputDocumentTarget.OPKS: "opks",
}
_FIELDS_BY_TARGET = {
    OutputDocumentTarget.DUTY: {
        OutputDocumentField.ENTITY,
        OutputDocumentField.STATEMENT,
        OutputDocumentField.DISPLAY_ORDER,
    },
    OutputDocumentTarget.TASK: {
        OutputDocumentField.ENTITY,
        OutputDocumentField.DUTY_ID,
        OutputDocumentField.STATEMENT,
        OutputDocumentField.ACTION,
        OutputDocumentField.OBJECT,
        OutputDocumentField.PURPOSE_RESULT,
        OutputDocumentField.CONTEXT,
        OutputDocumentField.FREQUENCY_TEXT,
        OutputDocumentField.RESPONSIBILITY_ROLE,
        OutputDocumentField.ENABLERS,
        OutputDocumentField.DISPLAY_ORDER,
    },
    OutputDocumentTarget.OPKS: {
        OutputDocumentField.ENTITY,
        OutputDocumentField.TEXT,
        OutputDocumentField.DISPLAY_ORDER,
        OutputDocumentField.TASK_IDS,
        OutputDocumentField.INDICATOR_IDS,
    },
}


def _map_document_change(
    value: OutputDocumentChange, bases: _BasisTable
) -> ReviewableDocumentChange:
    value = _normalize_document_wire_aliases(value)
    path = _document_path(value)
    after = _document_after(value)
    opks_kind = (
        None
        if value.opks_kind is OutputOpksKind.NONE
        else OpksKind(value.opks_kind.value)
    )
    if value.target is OutputDocumentTarget.OPKS:
        if opks_kind is None:
            raise ConsultantOutputMappingError("OPKS change requires opks_kind")
    elif opks_kind is not None or value.task_ids or value.indicator_ids:
        raise ConsultantOutputMappingError(
            "non-OPKS change cannot carry OPKS linkage fields"
        )
    return ReviewableDocumentChange(
        operation=value.operation,
        path=path,
        after=after,
        target_ids=value.target_ids,
        opks_kind=opks_kind,
        task_ids=value.task_ids,
        indicator_ids=value.indicator_ids,
        basis=bases.resolve(value.basis_ordinal, "document change basis_ordinal"),
    )


def _normalize_document_wire_aliases(
    value: OutputDocumentChange,
) -> OutputDocumentChange:
    """Canonicalize only combinations whose domain intent is unambiguous."""

    if value.target in {
        OutputDocumentTarget.JOB_TITLE,
        OutputDocumentTarget.WORK_DESCRIPTION,
    }:
        if (
            value.operation in {
                DocumentChangeOperation.ADD,
                DocumentChangeOperation.REVISE,
            }
            and not value.target_id
            and not value.target_ids
        ):
            return value.model_copy(
                update={
                    "operation": DocumentChangeOperation.REVISE,
                    "field": OutputDocumentField.VALUE,
                }
            )
        return value
    if value.operation in {
        DocumentChangeOperation.ADD,
        DocumentChangeOperation.WITHDRAW,
        DocumentChangeOperation.MERGE,
        DocumentChangeOperation.SPLIT,
    }:
        return value.model_copy(update={"field": OutputDocumentField.ENTITY})
    return value


def _document_path(value: OutputDocumentChange) -> str:
    if value.target in {
        OutputDocumentTarget.JOB_TITLE,
        OutputDocumentTarget.WORK_DESCRIPTION,
    }:
        if (
            value.operation is not DocumentChangeOperation.REVISE
            or value.field is not OutputDocumentField.VALUE
            or value.target_id
            or value.target_ids
        ):
            raise ConsultantOutputMappingError(
                "top-level document target requires revise/value without IDs"
            )
        return f"/{value.target.value}"

    allowed_fields = _FIELDS_BY_TARGET[value.target]
    if value.field not in allowed_fields:
        raise ConsultantOutputMappingError(
            f"field {value.field.value} is unsupported for {value.target.value}"
        )
    collection = _COLLECTIONS[value.target]
    if value.field is OutputDocumentField.ENTITY:
        if value.operation is DocumentChangeOperation.WITHDRAW:
            if value.target_ids:
                raise ConsultantOutputMappingError(
                    "withdraw cannot carry merge or split target IDs"
                )
            return f"/{collection}/{_required_uuid(value.target_id, 'target_id')}"
        if value.operation not in {
            DocumentChangeOperation.ADD,
            DocumentChangeOperation.MERGE,
            DocumentChangeOperation.SPLIT,
        }:
            raise ConsultantOutputMappingError(
                "entity field supports only add, withdraw, merge or split"
            )
        if value.target_id:
            raise ConsultantOutputMappingError(
                "collection operation cannot carry target_id"
            )
        if value.operation in {
            DocumentChangeOperation.MERGE,
            DocumentChangeOperation.SPLIT,
        } and not value.target_ids:
            raise ConsultantOutputMappingError("merge or split requires target_ids")
        if value.operation is DocumentChangeOperation.ADD and value.target_ids:
            raise ConsultantOutputMappingError("add cannot carry target_ids")
        return f"/{collection}"

    if value.target_ids:
        raise ConsultantOutputMappingError(
            "field-level change cannot carry merge or split target IDs"
        )
    target_id = _required_uuid(value.target_id, "target_id")
    expected_operation = (
        DocumentChangeOperation.REASSIGN
        if value.field is OutputDocumentField.DUTY_ID
        else DocumentChangeOperation.REORDER
        if value.field is OutputDocumentField.DISPLAY_ORDER
        else DocumentChangeOperation.REVISE
    )
    if value.operation is not expected_operation:
        raise ConsultantOutputMappingError(
            f"field {value.field.value} requires {expected_operation.value}"
        )
    return f"/{collection}/{target_id}/{value.field.value}"


def _document_after(value: OutputDocumentChange) -> Any:
    expected_slot = _expected_payload_slot(value)
    slots: dict[str, Any] = {
        "text": value.text_value,
        "integer": value.integer_value,
        "uuid": value.uuid_value,
        "uuid_list": value.uuid_values,
        "enabler_list": value.enablers,
        "duty_list": value.duties,
        "task_list": value.tasks,
        "opks_list": value.opks_items,
    }
    for name, slot_value in slots.items():
        if name != expected_slot and not _payload_slot_is_neutral(name, slot_value):
            raise ConsultantOutputMappingError(
                f"unused document payload slot {name} carries content"
            )

    if expected_slot == "none":
        return None
    if expected_slot == "text":
        if not value.text_value.strip():
            raise ConsultantOutputMappingError("text document payload is blank")
        return value.text_value
    if expected_slot == "integer":
        if value.integer_value < 0:
            raise ConsultantOutputMappingError(
                "display_order document payload must be non-negative"
            )
        return value.integer_value
    if expected_slot == "uuid":
        return _required_uuid(value.uuid_value, "document UUID payload")
    if expected_slot == "uuid_list":
        return [str(item) for item in value.uuid_values]
    if expected_slot == "enabler_list":
        return [
            {"kind": item.kind.value, "name": _required_text(item.name, "enabler name")}
            for item in value.enablers
        ]
    if expected_slot == "duty_list":
        return _entity_after(
            value.operation,
            tuple(_map_duty(item) for item in value.duties),
            "Duty",
        )
    if expected_slot == "task_list":
        return _entity_after(
            value.operation,
            tuple(_map_task(item) for item in value.tasks),
            "Task",
        )
    if expected_slot == "opks_list":
        return _map_opks_after(value)
    raise AssertionError(expected_slot)


def _expected_payload_slot(value: OutputDocumentChange) -> str:
    if value.field is OutputDocumentField.ENTITY:
        if value.operation is DocumentChangeOperation.WITHDRAW:
            return "none"
        return {
            OutputDocumentTarget.DUTY: "duty_list",
            OutputDocumentTarget.TASK: "task_list",
            OutputDocumentTarget.OPKS: "opks_list",
        }[value.target]
    if value.field is OutputDocumentField.DISPLAY_ORDER:
        return "integer"
    if value.field is OutputDocumentField.DUTY_ID:
        return "uuid"
    if value.field in {
        OutputDocumentField.TASK_IDS,
        OutputDocumentField.INDICATOR_IDS,
    }:
        return "uuid_list"
    if value.field is OutputDocumentField.ENABLERS:
        return "enabler_list"
    return "text"


def _payload_slot_is_neutral(name: str, value: Any) -> bool:
    if name == "text" or name == "uuid":
        return value == ""
    if name == "integer":
        return value == NEUTRAL_INTEGER
    return not value


def _entity_after(
    operation: DocumentChangeOperation,
    entities: tuple[dict[str, Any], ...],
    label: str,
) -> dict[str, Any] | list[dict[str, Any]]:
    expected_count = 2 if operation is DocumentChangeOperation.SPLIT else 1
    if operation is DocumentChangeOperation.SPLIT:
        if len(entities) < expected_count:
            raise ConsultantOutputMappingError(
                f"{label} split requires at least two replacements"
            )
        return list(entities)
    if len(entities) != expected_count:
        raise ConsultantOutputMappingError(
            f"{label} add or merge requires exactly one replacement"
        )
    return entities[0]


def _map_duty(value: OutputDuty) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "statement": _required_text(value.statement, "Duty statement"),
    }
    if value.display_order != NEUTRAL_INTEGER:
        payload["display_order"] = _non_negative(
            value.display_order, "Duty display_order"
        )
    duty_id = _optional_uuid(value.duty_id, "duty_id")
    if duty_id is not None:
        payload["duty_id"] = str(duty_id)
    return payload


def _map_task(value: OutputTask) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "statement": _required_text(value.statement, "Task statement"),
        "action": _required_text(value.action, "Task action"),
        "object": _required_text(value.object, "Task object"),
        "enablers": [
            {"kind": item.kind.value, "name": _required_text(item.name, "enabler name")}
            for item in value.enablers
        ],
    }
    if value.display_order != NEUTRAL_INTEGER:
        payload["display_order"] = _non_negative(
            value.display_order, "Task display_order"
        )
    task_id = _optional_uuid(value.task_id, "task_id")
    duty_id = _optional_uuid(value.duty_id, "duty_id")
    if task_id is not None:
        payload["task_id"] = str(task_id)
    if duty_id is not None:
        payload["duty_id"] = str(duty_id)
    for name in ("purpose_result", "context", "frequency_text"):
        text = getattr(value, name)
        if text:
            payload[name] = _required_text(text, f"Task {name}")
    if value.responsibility_role is not OutputResponsibilityRole.NONE:
        payload["responsibility_role"] = value.responsibility_role.value
    return payload


def _map_opks_after(value: OutputDocumentChange) -> Any:
    if not value.opks_items:
        raise ConsultantOutputMappingError("OPKS entity change requires a payload")
    single_item = value.opks_items[0] if len(value.opks_items) == 1 else None
    if (
        value.operation is DocumentChangeOperation.ADD
        and single_item is not None
        and single_item.item_id == ""
        and single_item.display_order == NEUTRAL_INTEGER
    ):
        # The review change owns ADD linkage.  The strict provider schema keeps
        # item-level linkage slots for merge/split replacements, but they are
        # redundant placeholders for a single application-owned ADD and must
        # never become a second authority.
        return _required_text(single_item.text, "OPKS text")
    if value.opks_kind is OutputOpksKind.NONE:
        raise ConsultantOutputMappingError("OPKS entity requires opks_kind")
    payload_task_ids = {
        item for payload in value.opks_items for item in payload.task_ids
    }
    payload_indicator_ids = {
        item for payload in value.opks_items for item in payload.indicator_ids
    }
    if payload_task_ids != set(value.task_ids):
        raise ConsultantOutputMappingError(
            "OPKS payload task IDs contradict change-level task IDs"
        )
    if payload_indicator_ids != set(value.indicator_ids):
        raise ConsultantOutputMappingError(
            "OPKS payload indicator IDs contradict change-level indicator IDs"
        )
    entities = tuple(
        _map_opks_item(item, value.opks_kind) for item in value.opks_items
    )
    return _entity_after(value.operation, entities, "OPKS")


def _map_opks_item(
    value: OutputOpksItem, kind: OutputOpksKind
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": kind.value,
        "text": _required_text(value.text, "OPKS text"),
        "display_order": _non_negative(value.display_order, "OPKS display_order"),
        "task_ids": [str(item) for item in value.task_ids],
        "indicator_ids": [str(item) for item in value.indicator_ids],
    }
    item_id = _optional_uuid(value.item_id, "OPKS item_id")
    if item_id is not None:
        payload["item_id"] = str(item_id)
    return payload


def _map_question(
    value: OutputQuestion,
    bases: _BasisTable,
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


def _required_text(value: str, label: str) -> str:
    if not value.strip():
        raise ConsultantOutputMappingError(f"{label} must not be blank")
    return value


def _optional_uuid(value: str, label: str) -> UUID | None:
    if value == "":
        return None
    return UUID(_required_uuid(value, label))


def _required_uuid(value: str, label: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ConsultantOutputMappingError(f"{label} must be a UUID") from error


def _non_negative(value: int, label: str) -> int:
    if value < 0:
        raise ConsultantOutputMappingError(f"{label} must be non-negative")
    return value
