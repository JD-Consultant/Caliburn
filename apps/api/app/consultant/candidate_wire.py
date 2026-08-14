"""Strict candidate-document wire and deterministic local-reference mapping."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID, uuid5

from pydantic import Field

from app.consultant.provider_wire import (
    AnalysisBasisTable,
    OutputAnalysisBasis,
    ProviderWireModel,
)
from app.consultant.results import (
    DocumentChangeOperation,
    OpksKind,
    ReviewableDocumentChange,
)
from app.consultant.state import ApprovedEnablerKind, ApprovedResponsibilityRole


NEUTRAL = "none"
NEUTRAL_INTEGER = -1
_LOCAL_REF_PATTERN = r"^(?:|[a-z][a-z0-9_-]{0,31})$"
_CHANGE_REF_PATTERN = r"^[a-z][a-z0-9_-]{0,31}$"
LocalRef = Annotated[str, Field(pattern=_LOCAL_REF_PATTERN)]
ChangeRef = Annotated[str, Field(pattern=_CHANGE_REF_PATTERN)]


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


class OutputEnabler(ProviderWireModel):
    kind: ApprovedEnablerKind
    name: str


class OutputDuty(ProviderWireModel):
    duty_id: str
    entity_ref: LocalRef
    statement: str
    display_order: int


class OutputTask(ProviderWireModel):
    task_id: str
    duty_id: str
    entity_ref: LocalRef
    duty_ref: LocalRef
    statement: str
    action: str
    object: str
    purpose_result: str
    context: str
    frequency_text: str
    responsibility_role: OutputResponsibilityRole
    enablers: tuple[OutputEnabler, ...]
    display_order: int


class OutputOpksItem(ProviderWireModel):
    item_id: str
    entity_ref: LocalRef
    text: str
    display_order: int
    task_ids: tuple[UUID, ...]
    indicator_ids: tuple[UUID, ...]
    task_refs: tuple[ChangeRef, ...]
    indicator_refs: tuple[ChangeRef, ...]


class OutputDocumentChange(ProviderWireModel):
    change_ref: ChangeRef
    depends_on_change_refs: tuple[ChangeRef, ...]
    depends_on_action_ids: tuple[UUID, ...]
    supersedes_action_ids: tuple[UUID, ...]
    atomic_group_ref: LocalRef
    operation: DocumentChangeOperation
    target: OutputDocumentTarget
    target_id: str
    field: OutputDocumentField = Field(
        description="job_title／work_description 使用 top_level_value；完整 Duty／Task／OPKS 使用 whole_entity；單欄修改才使用具名欄位"
    )
    text_value: str
    integer_value: int
    uuid_value: str
    uuid_values: tuple[UUID, ...]
    enablers: tuple[OutputEnabler, ...]
    duties: tuple[OutputDuty, ...]
    tasks: tuple[OutputTask, ...]
    opks_items: tuple[OutputOpksItem, ...]
    target_ids: tuple[UUID, ...]
    opks_kind: OutputOpksKind
    task_ids: tuple[UUID, ...]
    indicator_ids: tuple[UUID, ...]
    basis_ordinal: int


class CandidateEditBatch(ProviderWireModel):
    base_candidate_revision: int = Field(ge=0)
    summary: str = Field(min_length=1, max_length=240)
    analysis_bases: tuple[OutputAnalysisBasis, ...] = Field(
        min_length=1, max_length=32
    )
    replacement_changes: tuple[OutputDocumentChange, ...] = Field(
        min_length=1, max_length=32
    )


class CandidateWireMappingError(ValueError):
    pass


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


def map_candidate_edit_batch(
    batch: CandidateEditBatch,
    *,
    document_id: UUID,
    materialization_run_id: UUID,
) -> tuple[ReviewableDocumentChange, ...]:
    """Map one replacement batch without giving provider text document authority."""

    _validate_change_graph(batch.replacement_changes)
    resolver = _LocalRefResolver(document_id, materialization_run_id)
    resolver.register(batch.replacement_changes)
    bases = AnalysisBasisTable(batch.analysis_bases)
    mapped = tuple(
        _map_provider_document_change(
            resolver.resolve_change(value),
            bases,
            include_candidate_identities=True,
            include_candidate_metadata=True,
        )
        for value in batch.replacement_changes
    )
    bases.reject_unused()
    return mapped


def map_provider_document_change(
    value: OutputDocumentChange, bases: AnalysisBasisTable
) -> ReviewableDocumentChange:
    """Map the legacy final-output document wire without candidate local refs."""

    return _map_provider_document_change(
        value,
        bases,
        include_candidate_identities=False,
        include_candidate_metadata=False,
    )


def _validate_change_graph(values: tuple[OutputDocumentChange, ...]) -> None:
    refs = tuple(value.change_ref for value in values)
    if len(refs) != len(set(refs)):
        raise CandidateWireMappingError("duplicate change_ref")
    known = set(refs)
    for value in values:
        dependencies = value.depends_on_change_refs
        if len(dependencies) != len(set(dependencies)):
            raise CandidateWireMappingError("duplicate change dependency")
        if value.change_ref in dependencies:
            raise CandidateWireMappingError("self dependency")
        unknown = set(dependencies) - known
        if unknown:
            raise CandidateWireMappingError("unknown change_ref dependency")

    visiting: set[str] = set()
    visited: set[str] = set()
    graph = {value.change_ref: value.depends_on_change_refs for value in values}

    def visit(change_ref: str) -> None:
        if change_ref in visiting:
            raise CandidateWireMappingError("dependency cycle")
        if change_ref in visited:
            return
        visiting.add(change_ref)
        for dependency in graph[change_ref]:
            visit(dependency)
        visiting.remove(change_ref)
        visited.add(change_ref)

    for change_ref in refs:
        visit(change_ref)


class _LocalRefResolver:
    def __init__(self, document_id: UUID, materialization_run_id: UUID) -> None:
        self._document_id = document_id
        self._materialization_run_id = materialization_run_id
        self._ids: dict[tuple[str, str], UUID] = {}

    def register(self, changes: tuple[OutputDocumentChange, ...]) -> None:
        for change in changes:
            for kind, item in (
                *(("duty", duty) for duty in change.duties),
                *(("task", task) for task in change.tasks),
                *(("opks", item) for item in change.opks_items),
            ):
                entity_ref = item.entity_ref
                if not entity_ref:
                    continue
                key = (kind, entity_ref)
                if key in self._ids:
                    raise CandidateWireMappingError("duplicate local ref")
                self._ids[key] = uuid5(
                    self._document_id,
                    f"consultant:{self._materialization_run_id}:local:{kind}:{entity_ref}",
                )

    def resolve(self, kind: str, ref: str) -> UUID | None:
        if not ref:
            return None
        try:
            return self._ids[(kind, ref)]
        except KeyError as error:
            raise CandidateWireMappingError("unknown local ref") from error

    def resolve_change(self, value: OutputDocumentChange) -> OutputDocumentChange:
        duties = tuple(
            item.model_copy(
                update={"duty_id": _resolved_add_id(value, item.duty_id, self.resolve("duty", item.entity_ref))}
            )
            for item in value.duties
        )
        tasks = tuple(
            item.model_copy(
                update={
                    "task_id": _resolved_add_id(value, item.task_id, self.resolve("task", item.entity_ref)),
                    "duty_id": _resolved_reference_id(item.duty_id, self.resolve("duty", item.duty_ref)),
                }
            )
            for item in value.tasks
        )
        opks_items = tuple(
            item.model_copy(
                update={
                    "item_id": _resolved_add_id(value, item.item_id, self.resolve("opks", item.entity_ref)),
                    "task_ids": _resolved_reference_ids(item.task_ids, tuple(self.resolve("task", ref) for ref in item.task_refs)),
                    "indicator_ids": _resolved_reference_ids(item.indicator_ids, tuple(self.resolve("opks", ref) for ref in item.indicator_refs)),
                }
            )
            for item in value.opks_items
        )
        if opks_items:
            task_ids = tuple(
                item for payload in opks_items for item in payload.task_ids
            )
            indicator_ids = tuple(
                item for payload in opks_items for item in payload.indicator_ids
            )
            if (
                value.task_ids
                and set(value.task_ids) != set(task_ids)
                or value.indicator_ids
                and set(value.indicator_ids) != set(indicator_ids)
            ):
                raise CandidateWireMappingError(
                    "OPKS linkage contradicts change-level IDs"
                )
            return value.model_copy(
                update={
                    "duties": duties,
                    "tasks": tasks,
                    "opks_items": opks_items,
                    "task_ids": task_ids,
                    "indicator_ids": indicator_ids,
                }
            )
        return value.model_copy(update={"duties": duties, "tasks": tasks})


def _resolved_add_id(
    value: OutputDocumentChange, supplied_id: str, local_id: UUID | None
) -> str:
    if value.operation is DocumentChangeOperation.ADD and supplied_id:
        raise CandidateWireMappingError("ADD cannot carry an application-owned ID")
    return str(local_id) if local_id is not None else supplied_id


def _resolved_reference_id(supplied_id: str, local_id: UUID | None) -> str:
    if local_id is not None and supplied_id:
        raise CandidateWireMappingError("local ref contradicts application-owned ID")
    return str(local_id) if local_id is not None else supplied_id


def _resolved_reference_ids(
    supplied_ids: tuple[UUID, ...], local_ids: tuple[UUID | None, ...]
) -> tuple[UUID, ...]:
    if supplied_ids and local_ids:
        raise CandidateWireMappingError("local refs contradict application-owned IDs")
    return tuple(item for item in local_ids if item is not None) or supplied_ids


def _map_provider_document_change(
    value: OutputDocumentChange,
    bases: AnalysisBasisTable,
    *,
    include_candidate_identities: bool,
    include_candidate_metadata: bool,
) -> ReviewableDocumentChange:
    value = _normalize_document_wire_aliases(value)
    path = _document_path(value)
    after = _document_after(value, include_candidate_identities=include_candidate_identities)
    opks_kind = (
        None if value.opks_kind is OutputOpksKind.NONE else OpksKind(value.opks_kind.value)
    )
    if value.target is OutputDocumentTarget.OPKS:
        if opks_kind is None:
            raise CandidateWireMappingError("OPKS change requires opks_kind")
    elif opks_kind is not None or value.task_ids or value.indicator_ids:
        raise CandidateWireMappingError(
            "non-OPKS change cannot carry OPKS linkage fields"
        )
    metadata = (
        {
            "change_ref": value.change_ref,
            "depends_on_change_refs": value.depends_on_change_refs,
            "depends_on_action_ids": value.depends_on_action_ids,
            "supersedes_action_ids": value.supersedes_action_ids,
            "atomic_group_ref": value.atomic_group_ref,
        }
        if include_candidate_metadata
        else {}
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
        **metadata,
    )


def _normalize_document_wire_aliases(value: OutputDocumentChange) -> OutputDocumentChange:
    if value.target in {OutputDocumentTarget.JOB_TITLE, OutputDocumentTarget.WORK_DESCRIPTION}:
        if value.operation in {DocumentChangeOperation.ADD, DocumentChangeOperation.REVISE} and not value.target_id and not value.target_ids:
            return value.model_copy(update={"operation": DocumentChangeOperation.REVISE, "field": OutputDocumentField.VALUE})
        return value
    if value.operation in {DocumentChangeOperation.ADD, DocumentChangeOperation.WITHDRAW, DocumentChangeOperation.MERGE, DocumentChangeOperation.SPLIT}:
        return value.model_copy(update={"field": OutputDocumentField.ENTITY})
    return value


def _document_path(value: OutputDocumentChange) -> str:
    if value.target in {OutputDocumentTarget.JOB_TITLE, OutputDocumentTarget.WORK_DESCRIPTION}:
        if value.operation is not DocumentChangeOperation.REVISE or value.field is not OutputDocumentField.VALUE or value.target_id or value.target_ids:
            raise CandidateWireMappingError("top-level document target requires revise/value without IDs")
        return f"/{value.target.value}"
    allowed_fields = _FIELDS_BY_TARGET[value.target]
    if value.field not in allowed_fields:
        raise CandidateWireMappingError(f"field {value.field.value} is unsupported for {value.target.value}")
    collection = _COLLECTIONS[value.target]
    if value.field is OutputDocumentField.ENTITY:
        if value.operation is DocumentChangeOperation.WITHDRAW:
            if value.target_ids:
                raise CandidateWireMappingError("withdraw cannot carry merge or split target IDs")
            return f"/{collection}/{_required_uuid(value.target_id, 'target_id')}"
        if value.operation not in {DocumentChangeOperation.ADD, DocumentChangeOperation.MERGE, DocumentChangeOperation.SPLIT}:
            raise CandidateWireMappingError("entity field supports only add, withdraw, merge or split")
        if value.target_id:
            raise CandidateWireMappingError("collection operation cannot carry target_id")
        if value.operation in {DocumentChangeOperation.MERGE, DocumentChangeOperation.SPLIT} and not value.target_ids:
            raise CandidateWireMappingError("merge or split requires target_ids")
        if value.operation is DocumentChangeOperation.ADD and value.target_ids:
            raise CandidateWireMappingError("add cannot carry target_ids")
        return f"/{collection}"
    if value.target_ids:
        raise CandidateWireMappingError("field-level change cannot carry merge or split target IDs")
    target_id = _required_uuid(value.target_id, "target_id")
    expected_operation = DocumentChangeOperation.REASSIGN if value.field is OutputDocumentField.DUTY_ID else DocumentChangeOperation.REORDER if value.field is OutputDocumentField.DISPLAY_ORDER else DocumentChangeOperation.REVISE
    if value.operation is not expected_operation:
        raise CandidateWireMappingError(f"field {value.field.value} requires {expected_operation.value}")
    return f"/{collection}/{target_id}/{value.field.value}"


def _document_after(value: OutputDocumentChange, *, include_candidate_identities: bool) -> Any:
    expected_slot = _expected_payload_slot(value)
    slots: dict[str, Any] = {"text": value.text_value, "integer": value.integer_value, "uuid": value.uuid_value, "uuid_list": value.uuid_values, "enabler_list": value.enablers, "duty_list": value.duties, "task_list": value.tasks, "opks_list": value.opks_items}
    for name, slot_value in slots.items():
        if name != expected_slot and not _payload_slot_is_neutral(name, slot_value):
            raise CandidateWireMappingError(f"unused document payload slot {name} carries content")
    if expected_slot == "none":
        return None
    if expected_slot == "text":
        return _required_text(value.text_value, "text document payload")
    if expected_slot == "integer":
        if value.integer_value < 0:
            raise CandidateWireMappingError("display_order document payload must be non-negative")
        return value.integer_value
    if expected_slot == "uuid":
        return _required_uuid(value.uuid_value, "document UUID payload")
    if expected_slot == "uuid_list":
        return [str(item) for item in value.uuid_values]
    if expected_slot == "enabler_list":
        return [{"kind": item.kind.value, "name": _required_text(item.name, "enabler name")} for item in value.enablers]
    if expected_slot == "duty_list":
        return _entity_after(value.operation, tuple(_map_duty(item) for item in value.duties), "Duty")
    if expected_slot == "task_list":
        return _entity_after(value.operation, tuple(_map_task(item) for item in value.tasks), "Task")
    if expected_slot == "opks_list":
        return _map_opks_after(value, include_candidate_identities=include_candidate_identities)
    raise AssertionError(expected_slot)


def _expected_payload_slot(value: OutputDocumentChange) -> str:
    if value.field is OutputDocumentField.ENTITY:
        if value.operation is DocumentChangeOperation.WITHDRAW:
            return "none"
        return {OutputDocumentTarget.DUTY: "duty_list", OutputDocumentTarget.TASK: "task_list", OutputDocumentTarget.OPKS: "opks_list"}[value.target]
    if value.field is OutputDocumentField.DISPLAY_ORDER:
        return "integer"
    if value.field is OutputDocumentField.DUTY_ID:
        return "uuid"
    if value.field in {OutputDocumentField.TASK_IDS, OutputDocumentField.INDICATOR_IDS}:
        return "uuid_list"
    if value.field is OutputDocumentField.ENABLERS:
        return "enabler_list"
    return "text"


def _payload_slot_is_neutral(name: str, value: Any) -> bool:
    if name in {"text", "uuid"}:
        return value == ""
    if name == "integer":
        return value == NEUTRAL_INTEGER
    return not value


def _entity_after(operation: DocumentChangeOperation, entities: tuple[dict[str, Any], ...], label: str) -> dict[str, Any] | list[dict[str, Any]]:
    if operation is DocumentChangeOperation.SPLIT:
        if len(entities) < 2:
            raise CandidateWireMappingError(f"{label} split requires at least two replacements")
        return list(entities)
    if len(entities) != 1:
        raise CandidateWireMappingError(f"{label} add or merge requires exactly one replacement")
    return entities[0]


def _map_duty(value: OutputDuty) -> dict[str, Any]:
    payload: dict[str, Any] = {"statement": _required_text(value.statement, "Duty statement")}
    if value.display_order != NEUTRAL_INTEGER:
        payload["display_order"] = _non_negative(value.display_order, "Duty display_order")
    duty_id = _optional_uuid(value.duty_id, "duty_id")
    if duty_id is not None:
        payload["duty_id"] = str(duty_id)
    return payload


def _map_task(value: OutputTask) -> dict[str, Any]:
    payload: dict[str, Any] = {"statement": _required_text(value.statement, "Task statement"), "action": _required_text(value.action, "Task action"), "object": _required_text(value.object, "Task object"), "enablers": [{"kind": item.kind.value, "name": _required_text(item.name, "enabler name")} for item in value.enablers]}
    if value.display_order != NEUTRAL_INTEGER:
        payload["display_order"] = _non_negative(value.display_order, "Task display_order")
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


def _map_opks_after(value: OutputDocumentChange, *, include_candidate_identities: bool) -> Any:
    if not value.opks_items:
        raise CandidateWireMappingError("OPKS entity change requires a payload")
    single_item = value.opks_items[0] if len(value.opks_items) == 1 else None
    if not include_candidate_identities and value.operation is DocumentChangeOperation.ADD and single_item is not None and single_item.item_id == "" and single_item.display_order == NEUTRAL_INTEGER:
        return _required_text(single_item.text, "OPKS text")
    if value.opks_kind is OutputOpksKind.NONE:
        raise CandidateWireMappingError("OPKS entity requires opks_kind")
    payload_task_ids = {item for payload in value.opks_items for item in payload.task_ids}
    payload_indicator_ids = {item for payload in value.opks_items for item in payload.indicator_ids}
    if payload_task_ids != set(value.task_ids):
        raise CandidateWireMappingError("OPKS payload task IDs contradict change-level task IDs")
    if payload_indicator_ids != set(value.indicator_ids):
        raise CandidateWireMappingError("OPKS payload indicator IDs contradict change-level indicator IDs")
    entities = tuple(_map_opks_item(item, value.opks_kind, allow_neutral_order=include_candidate_identities) for item in value.opks_items)
    return _entity_after(value.operation, entities, "OPKS")


def _map_opks_item(value: OutputOpksItem, kind: OutputOpksKind, *, allow_neutral_order: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": kind.value, "text": _required_text(value.text, "OPKS text"), "task_ids": [str(item) for item in value.task_ids], "indicator_ids": [str(item) for item in value.indicator_ids]}
    if value.display_order != NEUTRAL_INTEGER:
        payload["display_order"] = _non_negative(value.display_order, "OPKS display_order")
    elif not allow_neutral_order:
        payload["display_order"] = _non_negative(value.display_order, "OPKS display_order")
    item_id = _optional_uuid(value.item_id, "OPKS item_id")
    if item_id is not None:
        payload["item_id"] = str(item_id)
    return payload


def _required_text(value: str, label: str) -> str:
    if not value.strip():
        raise CandidateWireMappingError(f"{label} must not be blank")
    return value


def _optional_uuid(value: str, label: str) -> UUID | None:
    return None if value == "" else UUID(_required_uuid(value, label))


def _required_uuid(value: str, label: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise CandidateWireMappingError(f"{label} must be a UUID") from error


def _non_negative(value: int, label: str) -> int:
    if value < 0:
        raise CandidateWireMappingError(f"{label} must be non-negative")
    return value
