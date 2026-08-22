"""Canonical typed resources for the consultant virtual JD workspace.

The resources deliberately contain local handles instead of authority IDs.
``WorkspaceCatalog`` is the application-owned bridge back to the approved
snapshot; the JSON files are a disposable model-editable projection.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing_extensions import Annotated

from app.consultant.results import SkillId
from app.consultant.state import (
    ApprovedDuty,
    ApprovedEnabler,
    ApprovedEnablerKind,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedResponsibilityRole,
    ApprovedTask,
    EmployeeSource,
)
from app.consultant.workspace_state import Sha256Digest, workspace_resource_digest


NonEmptyText = Annotated[str, StringConstraints(min_length=1)]
Handle = Annotated[
    str,
    StringConstraints(
        min_length=5,
        pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-[0-9]{3,}$",
    ),
]


class WorkspaceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WorkspaceHeaderResource(WorkspaceModel):
    job_title: NonEmptyText | None = None
    occupation_category_name: NonEmptyText | None = None
    occupation_name: NonEmptyText | None = None
    occupation_code: NonEmptyText | None = None
    industry_name: NonEmptyText | None = None
    industry_code: NonEmptyText | None = None
    work_description: NonEmptyText | None = None
    notes: NonEmptyText | None = None


class WorkspaceDutyResource(WorkspaceModel):
    handle: Handle
    statement: NonEmptyText
    display_order: int | None = Field(default=None, ge=0)


class WorkspaceEnablerResource(WorkspaceModel):
    kind: ApprovedEnablerKind
    name: NonEmptyText


class WorkspaceTaskResource(WorkspaceModel):
    handle: Handle
    duty_handle: Handle | None = None
    statement: NonEmptyText
    action: NonEmptyText
    object: NonEmptyText
    purpose_result: NonEmptyText | None = None
    context: NonEmptyText | None = None
    frequency_text: NonEmptyText | None = None
    responsibility_role: ApprovedResponsibilityRole | None = None
    enablers: tuple[WorkspaceEnablerResource, ...] = ()
    display_order: int | None = Field(default=None, ge=0)


class WorkspaceOpksKind(StrEnum):
    OUTPUT = "output"
    PERFORMANCE_INDICATOR = "indicator"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"


class WorkspaceEvidenceReference(WorkspaceModel):
    source_handle: Handle
    quote: NonEmptyText
    occurrence: int | None = Field(default=None, ge=1)
    skill_ids: tuple[SkillId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def skill_references_are_unique(self) -> WorkspaceEvidenceReference:
        if len(self.skill_ids) != len(set(self.skill_ids)):
            raise ValueError("duplicate Skill dependency")
        return self


class WorkspaceOpksResource(WorkspaceModel):
    handle: Handle
    kind: WorkspaceOpksKind
    text: NonEmptyText
    task_handles: tuple[Handle, ...] = ()
    indicator_handles: tuple[Handle, ...] = ()
    evidence: tuple[WorkspaceEvidenceReference, ...] = ()
    display_order: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def references_are_unique(self) -> WorkspaceOpksResource:
        for label, values in (
            ("task_handles", self.task_handles),
            ("indicator_handles", self.indicator_handles),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")
        return self


class WorkspaceOpksEvidenceBinding(WorkspaceModel):
    """Keep model-authored evidence attached to its owning OPKS handle."""

    opks_handle: Handle
    references: tuple[WorkspaceEvidenceReference, ...] = Field(min_length=1)


class WorkspaceReviewGroupResource(WorkspaceModel):
    handle: Handle
    action_handles: tuple[Handle, ...] = ()
    depends_on_handles: tuple[Handle, ...] = ()

    @model_validator(mode="after")
    def handles_are_unique(self) -> WorkspaceReviewGroupResource:
        for label, values in (
            ("action_handles", self.action_handles),
            ("depends_on_handles", self.depends_on_handles),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")
        return self


class WorkspaceReviewGroupsResource(WorkspaceModel):
    groups: tuple[WorkspaceReviewGroupResource, ...] = ()

    @model_validator(mode="after")
    def group_handles_are_unique(self) -> WorkspaceReviewGroupsResource:
        handles = [group.handle for group in self.groups]
        if len(handles) != len(set(handles)):
            raise ValueError("duplicate review group handle")
        return self


class WorkspaceResourceError(ValueError):
    """A workspace resource cannot be parsed into a valid document draft."""


@dataclass(frozen=True, slots=True)
class WorkspaceCatalog:
    """Immutable application-side mapping for one approved snapshot."""

    document: ApprovedJobDocument
    sources: tuple[EmployeeSource, ...] = ()
    _stable_to_handle: Mapping[UUID, str] = field(default_factory=dict, repr=False)
    _handle_to_stable: Mapping[str, UUID] = field(default_factory=dict, repr=False)
    _source_by_handle: Mapping[str, EmployeeSource] = field(
        default_factory=dict, repr=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(
            self,
            "_stable_to_handle",
            MappingProxyType(dict(self._stable_to_handle)),
        )
        object.__setattr__(
            self,
            "_handle_to_stable",
            MappingProxyType(dict(self._handle_to_stable)),
        )
        object.__setattr__(
            self,
            "_source_by_handle",
            MappingProxyType(dict(self._source_by_handle)),
        )

    @classmethod
    def from_snapshot(
        cls,
        document: ApprovedJobDocument,
        sources: Sequence[EmployeeSource] = (),
        *,
        employee_sources: Sequence[EmployeeSource] | None = None,
    ) -> WorkspaceCatalog:
        source_values = tuple(
            sorted(
                (
                    employee_sources
                    if employee_sources is not None
                    else sources
                ),
                key=lambda source: (source.created_at, str(source.source_id)),
            )
        )

        source_by_id: dict[UUID, EmployeeSource] = {}
        for source in source_values:
            previous = source_by_id.get(source.source_id)
            if previous is None:
                source_by_id[source.source_id] = source
            elif previous != source:
                raise WorkspaceResourceError(
                    f"stable ID collision for employee source: {source.source_id}"
                )
        source_values = tuple(
            sorted(
                source_by_id.values(),
                key=lambda source: (source.created_at, str(source.source_id)),
            )
        )

        stable_to_handle: dict[UUID, str] = {}
        handle_to_stable: dict[str, UUID] = {}

        def add_mapping(stable_id: UUID, handle: str) -> None:
            if stable_id in stable_to_handle:
                raise WorkspaceResourceError(f"stable ID collision: {stable_id}")
            if handle in handle_to_stable:
                raise WorkspaceResourceError(f"workspace handle collision: {handle}")
            stable_to_handle[stable_id] = handle
            handle_to_stable[handle] = stable_id

        for prefix, values in _sorted_entity_groups(document):
            for index, stable_id in enumerate(values, start=1):
                add_mapping(stable_id, f"{prefix}-{index:03d}")

        source_ids = {source.source_id for source in source_values}
        source_ids.update(
            source_id
            for item in document.opks
            for source_id in item.evidence_source_ids
        )
        source_order = sorted(
            source_ids,
            key=lambda source_id: (
                0,
                source_by_id[source_id].created_at,
                str(source_id),
            )
            if source_id in source_by_id
            else (1, str(source_id)),
        )
        for index, source_id in enumerate(source_order, start=1):
            add_mapping(source_id, f"source-{index:03d}")

        source_by_handle = {
            stable_to_handle[stable_id]: source
            for stable_id, source in source_by_id.items()
            if stable_to_handle.get(stable_id, "").startswith("source-")
        }
        return cls(
            document=document,
            sources=source_values,
            _stable_to_handle=stable_to_handle,
            _handle_to_stable=handle_to_stable,
            _source_by_handle=source_by_handle,
        )

    @property
    def document_id(self) -> UUID:
        return self.document.document_id

    @property
    def handle_by_id(self) -> Mapping[UUID, str]:
        return self._stable_to_handle

    @property
    def id_by_handle(self) -> Mapping[str, UUID]:
        return self._handle_to_stable

    @property
    def stable_id_to_handle(self) -> Mapping[UUID, str]:
        return self._stable_to_handle

    @property
    def handle_to_stable_id(self) -> Mapping[str, UUID]:
        return self._handle_to_stable

    @property
    def stable_to_handle(self) -> Mapping[UUID, str]:
        return self._stable_to_handle

    @property
    def handle_to_stable(self) -> Mapping[str, UUID]:
        return self._handle_to_stable

    @property
    def source_handle_by_id(self) -> Mapping[UUID, str]:
        return MappingProxyType(
            {
                stable_id: handle
                for stable_id, handle in self._stable_to_handle.items()
                if handle.startswith("source-")
            }
        )

    @property
    def source_by_handle(self) -> Mapping[str, EmployeeSource]:
        return self._source_by_handle

    @property
    def source_ids(self) -> tuple[UUID, ...]:
        return tuple(
            stable_id
            for stable_id, handle in self._stable_to_handle.items()
            if handle.startswith("source-")
        )

    def handle_for_id(self, stable_id: UUID) -> str:
        try:
            return self._stable_to_handle[stable_id]
        except KeyError as error:
            raise KeyError(f"unknown stable ID: {stable_id}") from error

    def id_for_handle(self, handle: str) -> UUID:
        try:
            return self._handle_to_stable[handle]
        except KeyError as error:
            raise KeyError(f"unknown workspace handle: {handle}") from error

    def source_for_handle(self, handle: str) -> EmployeeSource:
        try:
            return self._source_by_handle[handle]
        except KeyError as error:
            if handle in self._handle_to_stable:
                raise KeyError(f"source is not materialized for handle: {handle}") from error
            raise KeyError(f"unknown source handle: {handle}") from error

    def source_handle_for_id(self, source_id: UUID) -> str:
        handle = self.handle_for_id(source_id)
        if not handle.startswith("source-"):
            raise KeyError(f"stable ID is not an employee source: {source_id}")
        return handle


def canonical_resource_json(value: BaseModel) -> str:
    """Serialize one resource without provider- or platform-specific drift."""

    payload = value.model_dump(mode="json")
    if payload.get("display_order") is None:
        payload.pop("display_order", None)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


class WorkspaceDraftDuty(WorkspaceModel):
    duty_id: UUID
    statement: NonEmptyText
    display_order: int = Field(default=0, ge=0)


class WorkspaceDraftTask(WorkspaceModel):
    task_id: UUID
    duty_id: UUID | None = None
    statement: NonEmptyText
    action: NonEmptyText
    object: NonEmptyText
    purpose_result: NonEmptyText | None = None
    context: NonEmptyText | None = None
    frequency_text: NonEmptyText | None = None
    responsibility_role: ApprovedResponsibilityRole | None = None
    enablers: tuple[WorkspaceEnablerResource, ...] = ()
    display_order: int = Field(default=0, ge=0)


class WorkspaceDraftOpks(WorkspaceModel):
    item_id: UUID
    kind: WorkspaceOpksKind
    text: NonEmptyText
    task_ids: tuple[UUID, ...] = ()
    indicator_ids: tuple[UUID, ...] = ()
    evidence_source_ids: tuple[UUID, ...] = ()
    display_order: int = Field(default=0, ge=0)


class WorkspaceEditableDocument(WorkspaceModel):
    document_id: UUID
    job_title: NonEmptyText | None = None
    occupation_category_name: NonEmptyText | None = None
    occupation_name: NonEmptyText | None = None
    occupation_code: NonEmptyText | None = None
    industry_name: NonEmptyText | None = None
    industry_code: NonEmptyText | None = None
    work_description: NonEmptyText | None = None
    notes: NonEmptyText | None = None
    duties: tuple[WorkspaceDraftDuty, ...] = ()
    tasks: tuple[WorkspaceDraftTask, ...] = ()
    opks: tuple[WorkspaceDraftOpks, ...] = ()


class WorkspaceDocumentDraft(WorkspaceModel):
    """Validated editable workspace content plus evidence and identity metadata."""

    document: WorkspaceEditableDocument
    handle_registry: dict[str, UUID]
    baseline_document: ApprovedJobDocument | None = Field(
        default=None,
        exclude=True,
        repr=False,
    )
    review_groups: WorkspaceReviewGroupsResource = Field(
        default_factory=WorkspaceReviewGroupsResource
    )
    evidence_references: tuple[WorkspaceEvidenceReference, ...] = ()
    opks_evidence: tuple[WorkspaceOpksEvidenceBinding, ...] = ()

    @property
    def evidence_bindings(self) -> tuple[WorkspaceOpksEvidenceBinding, ...]:
        return self.opks_evidence

    @property
    def approved_document(self) -> ApprovedJobDocument:
        return _approved_document_from_editable(
            self.document,
            baseline_document=self.baseline_document,
        )


def _approved_document_from_editable(
    document: WorkspaceEditableDocument,
    *,
    baseline_document: ApprovedJobDocument | None = None,
) -> ApprovedJobDocument:
    baseline_tasks = {
        task.task_id: task for task in (baseline_document.tasks if baseline_document else ())
    }
    duties = tuple(
        ApprovedDuty(
            duty_id=item.duty_id,
            statement=item.statement,
            display_order=item.display_order,
        )
        for index, item in enumerate(document.duties)
    )
    tasks = tuple(
        ApprovedTask(
            task_id=item.task_id,
            duty_id=item.duty_id,
            statement=item.statement,
            action=item.action,
            object=item.object,
            purpose_result=item.purpose_result,
            context=item.context,
            frequency_text=item.frequency_text,
            responsibility_role=item.responsibility_role,
            enablers=tuple(
                ApprovedEnabler(kind=enabler.kind, name=enabler.name)
                for enabler in item.enablers
            ),
            display_order=item.display_order,
            competency_level=(
                baseline_tasks[item.task_id].competency_level
                if item.task_id in baseline_tasks
                else None
            ),
        )
        for index, item in enumerate(document.tasks)
    )
    editable_opks = tuple(
        ApprovedOpksItem(
            item_id=item.item_id,
            kind=ApprovedOpksKind(item.kind.value),
            text=item.text,
            display_order=item.display_order,
            task_ids=item.task_ids,
            indicator_ids=item.indicator_ids,
            evidence_source_ids=item.evidence_source_ids,
        )
        for index, item in enumerate(document.opks)
    )
    editable_opks_by_id = {item.item_id: item for item in editable_opks}
    editable_kinds = {
        ApprovedOpksKind.OUTPUT,
        ApprovedOpksKind.PERFORMANCE_INDICATOR,
        ApprovedOpksKind.KNOWLEDGE,
        ApprovedOpksKind.SKILL,
    }
    opks = editable_opks
    if baseline_document is not None:
        opks_in_baseline_order: list[ApprovedOpksItem] = []
        seen_ids: set[UUID] = set()
        for baseline_item in baseline_document.opks:
            if baseline_item.kind not in editable_kinds:
                opks_in_baseline_order.append(baseline_item)
                continue
            current_item = editable_opks_by_id.get(baseline_item.item_id)
            if current_item is not None:
                opks_in_baseline_order.append(current_item)
                seen_ids.add(current_item.item_id)
        opks = tuple(
            (*opks_in_baseline_order,
             *(item for item in editable_opks if item.item_id not in seen_ids))
        )
    return ApprovedJobDocument(
        schema_version=(baseline_document.schema_version if baseline_document else 1),
        document_id=document.document_id,
        job_title=document.job_title,
        occupation_category_name=document.occupation_category_name,
        occupation_name=document.occupation_name,
        occupation_code=document.occupation_code,
        industry_name=document.industry_name,
        industry_code=document.industry_code,
        work_description=document.work_description,
        competency_level=(
            baseline_document.competency_level if baseline_document else None
        ),
        notes=document.notes,
        duties=duties,
        tasks=tasks,
        opks=opks,
    )


@dataclass(frozen=True, slots=True)
class WorkspaceProjection:
    """Canonical workspace files and the identity metadata needed to reopen them."""

    files: Mapping[str, str]
    handle_registry: Mapping[str, UUID]
    resource_digest: Sha256Digest

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", MappingProxyType(dict(self.files)))
        object.__setattr__(
            self,
            "handle_registry",
            MappingProxyType(dict(self.handle_registry)),
        )


def project_workspace_files(
    document: ApprovedJobDocument,
    *,
    handle_registry: Mapping[str, UUID],
) -> WorkspaceProjection:
    """Project one approved document into the single, run-independent workspace."""

    registry = _validated_workspace_registry(handle_registry)
    files: dict[str, str] = {
        "/workspace/header.json": canonical_resource_json(_header_resource(document))
    }

    for index, duty in enumerate(_sorted_by_display_order(document.duties), start=1):
        handle = _workspace_handle_for_id(registry, duty.duty_id, "duty", index)
        files[f"/workspace/duties/{handle}.json"] = canonical_resource_json(
            WorkspaceDutyResource(
                handle=handle,
                statement=duty.statement,
                display_order=duty.display_order,
            )
        )

    for index, task in enumerate(_sorted_by_display_order(document.tasks), start=1):
        handle = _workspace_handle_for_id(registry, task.task_id, "task", index)
        files[f"/workspace/tasks/{handle}.json"] = canonical_resource_json(
            WorkspaceTaskResource(
                handle=handle,
                duty_handle=(
                    _workspace_existing_handle(registry, task.duty_id, "duty")
                    if task.duty_id is not None
                    else None
                ),
                statement=task.statement,
                action=task.action,
                object=task.object,
                purpose_result=task.purpose_result,
                context=task.context,
                frequency_text=task.frequency_text,
                responsibility_role=task.responsibility_role,
                enablers=tuple(
                    WorkspaceEnablerResource(kind=item.kind, name=item.name)
                    for item in task.enablers
                ),
                display_order=task.display_order,
            )
        )

    for kind, prefix in (
        (ApprovedOpksKind.OUTPUT, "o"),
        (ApprovedOpksKind.PERFORMANCE_INDICATOR, "p"),
        (ApprovedOpksKind.KNOWLEDGE, "k"),
        (ApprovedOpksKind.SKILL, "s"),
    ):
        for index, item in enumerate(_sorted_opks(document.opks, kind), start=1):
            handle = _workspace_handle_for_id(registry, item.item_id, kind.value, index)
            files[f"/workspace/opks/{prefix}/{handle}.json"] = canonical_resource_json(
                WorkspaceOpksResource(
                    handle=handle,
                    kind=WorkspaceOpksKind(kind.value),
                    text=item.text,
                    task_handles=tuple(
                        _workspace_existing_handle(registry, task_id, "task")
                        for task_id in item.task_ids
                    ),
                    indicator_handles=tuple(
                        _workspace_existing_handle(registry, indicator_id, "indicator")
                        for indicator_id in item.indicator_ids
                    ),
                    display_order=item.display_order,
                )
            )

    return WorkspaceProjection(
        files=files,
        handle_registry=registry,
        resource_digest=workspace_resource_digest(files),
    )


def parse_workspace_files(
    document_id: UUID,
    files: Mapping[str, str | bytes],
    *,
    handle_registry: Mapping[str, UUID],
    baseline_document: ApprovedJobDocument | None = None,
) -> WorkspaceDocumentDraft:
    """Parse canonical workspace files without deriving identity from a run."""

    parsed: dict[str, Any] = {}
    for path, raw in files.items():
        path_text = str(path)
        if not path_text.startswith("/workspace/"):
            raise WorkspaceResourceError(f"unexpected workspace resource path: {path_text}")
        relative = path_text.removeprefix("/workspace/")
        try:
            parsed[relative] = json.loads(
                raw.decode("utf-8") if isinstance(raw, bytes) else raw
            )
        except (TypeError, ValueError) as error:
            raise WorkspaceResourceError(f"invalid JSON resource: {path_text}") from error

    for relative in parsed:
        if (
            relative != "header.json"
            and not relative.startswith("duties/")
            and not relative.startswith("tasks/")
            and not relative.startswith("opks/")
        ):
            raise WorkspaceResourceError(f"unexpected workspace resource: {relative}")

    header_value = parsed.get("header.json")
    if header_value is None:
        raise WorkspaceResourceError("workspace header.json is required")
    header = _validate_resource(WorkspaceHeaderResource, header_value, "header.json")
    duty_resources = _load_entity_resources(parsed, "duties", WorkspaceDutyResource)
    task_resources = _load_entity_resources(parsed, "tasks", WorkspaceTaskResource)
    opks_resources = _load_workspace_opks_resources(parsed)

    registry = _validated_workspace_registry(handle_registry)
    duty_ids = {
        handle: _workspace_entity_id(registry, document_id, handle, "duty")
        for handle, _ in duty_resources
    }
    task_ids = {
        handle: _workspace_entity_id(registry, document_id, handle, "task")
        for handle, _ in task_resources
    }
    opks_ids = {
        handle: _workspace_entity_id(registry, document_id, handle, resource.kind.value)
        for handle, resource in opks_resources
    }
    indicator_ids = {
        handle: stable_id
        for handle, stable_id in opks_ids.items()
        if handle.startswith("p-")
    }
    source_ids = {
        handle: stable_id
        for handle, stable_id in registry.items()
        if handle.startswith("source-")
    }
    baseline_opks = {
        item.item_id: item for item in (baseline_document.opks if baseline_document else ())
    }

    duties = tuple(
        WorkspaceDraftDuty(
            duty_id=duty_ids[handle],
            statement=resource.statement,
            display_order=resource.display_order if resource.display_order is not None else index,
        )
        for index, (handle, resource) in enumerate(duty_resources)
    )
    tasks = tuple(
        WorkspaceDraftTask(
            task_id=task_ids[handle],
            duty_id=(
                _workspace_referenced_id(duty_ids, resource.duty_handle, "duty")
                if resource.duty_handle is not None
                else None
            ),
            statement=resource.statement,
            action=resource.action,
            object=resource.object,
            purpose_result=resource.purpose_result,
            context=resource.context,
            frequency_text=resource.frequency_text,
            responsibility_role=resource.responsibility_role,
            enablers=resource.enablers,
            display_order=(resource.display_order if resource.display_order is not None else index),
        )
        for index, (handle, resource) in enumerate(task_resources)
    )
    opks = tuple(
        WorkspaceDraftOpks(
            item_id=opks_ids[handle],
            kind=resource.kind,
            text=resource.text,
            task_ids=tuple(
                _workspace_referenced_id(task_ids, task_handle, "task")
                for task_handle in resource.task_handles
            ),
            indicator_ids=tuple(
                _workspace_referenced_id(
                    indicator_ids, indicator_handle, "indicator"
                )
                for indicator_handle in resource.indicator_handles
            ),
            evidence_source_ids=(
                tuple(
                    _workspace_referenced_id(source_ids, reference.source_handle, "source")
                    for reference in resource.evidence
                )
                if resource.evidence
                else (
                    baseline_opks[opks_ids[handle]].evidence_source_ids
                    if opks_ids[handle] in baseline_opks
                    else ()
                )
            ),
            display_order=(resource.display_order if resource.display_order is not None else index),
        )
        for index, (handle, resource) in enumerate(opks_resources)
    )
    evidence_references = tuple(
        reference
        for _, resource in opks_resources
        for reference in resource.evidence
    )
    opks_evidence = tuple(
        WorkspaceOpksEvidenceBinding(opks_handle=handle, references=resource.evidence)
        for handle, resource in opks_resources
        if resource.evidence
    )
    return WorkspaceDocumentDraft(
        document=WorkspaceEditableDocument(
            document_id=document_id,
            job_title=header.job_title,
            occupation_category_name=header.occupation_category_name,
            occupation_name=header.occupation_name,
            occupation_code=header.occupation_code,
            industry_name=header.industry_name,
            industry_code=header.industry_code,
            work_description=header.work_description,
            notes=header.notes,
            duties=duties,
            tasks=tasks,
            opks=opks,
        ),
        handle_registry=registry,
        baseline_document=baseline_document,
        evidence_references=evidence_references,
        opks_evidence=opks_evidence,
    )


def _validated_workspace_registry(
    handle_registry: Mapping[str, UUID],
) -> dict[str, UUID]:
    registry = dict(handle_registry)
    if len(registry.values()) != len(set(registry.values())):
        raise WorkspaceResourceError("duplicate stable ID in workspace handle registry")
    return registry


def _workspace_handle_for_id(
    registry: dict[str, UUID], stable_id: UUID, kind: str, index: int
) -> str:
    return _workspace_existing_handle(registry, stable_id, kind) or _new_workspace_handle(
        registry, stable_id, kind, index
    )


def _workspace_existing_handle(
    registry: Mapping[str, UUID], stable_id: UUID, kind: str
) -> str | None:
    for handle, registered_id in registry.items():
        if registered_id == stable_id:
            if not handle.startswith(_workspace_handle_prefix(kind)):
                raise WorkspaceResourceError(
                    f"stable ID {stable_id} has the wrong workspace handle kind"
                )
            return handle
    return None


def _new_workspace_handle(
    registry: dict[str, UUID], stable_id: UUID, kind: str, index: int
) -> str:
    prefix = _workspace_handle_prefix(kind)
    next_index = index
    while True:
        handle = f"{prefix}{next_index:03d}"
        known_id = registry.get(handle)
        if known_id is None:
            registry[handle] = stable_id
            return handle
        if known_id == stable_id:
            return handle
        next_index += 1


def _workspace_entity_id(
    registry: dict[str, UUID], document_id: UUID, handle: str, kind: str
) -> UUID:
    prefix = _workspace_handle_prefix(kind)
    if not handle.startswith(prefix):
        raise WorkspaceResourceError(f"handle {handle} is not a {kind} handle")
    stable_id = registry.get(handle)
    if stable_id is None:
        stable_id = uuid5(document_id, f"workspace:{kind}:{handle}")
        registry[handle] = stable_id
    return stable_id


def workspace_entity_id(
    document_id: UUID,
    handle: str,
    kind: str,
    *,
    handle_registry: Mapping[str, UUID],
) -> UUID:
    """Resolve one persistent workspace identity without mutating its registry."""

    return _workspace_entity_id(dict(handle_registry), document_id, handle, kind)


def _workspace_referenced_id(
    values: Mapping[str, UUID], handle: str, kind: str
) -> UUID:
    try:
        return values[handle]
    except KeyError as error:
        raise WorkspaceResourceError(f"unknown {kind} handle: {handle}") from error


def _workspace_handle_prefix(kind: str) -> str:
    try:
        return {
            "duty": "duty-",
            "task": "task-",
            "output": "o-",
            "indicator": "p-",
            "knowledge": "k-",
            "skill": "s-",
        }[kind]
    except KeyError as error:
        raise WorkspaceResourceError(f"unknown workspace entity kind: {kind}") from error


def _load_workspace_opks_resources(
    parsed: Mapping[str, Any],
) -> tuple[tuple[str, WorkspaceOpksResource], ...]:
    order = {
        WorkspaceOpksKind.OUTPUT: 0,
        WorkspaceOpksKind.PERFORMANCE_INDICATOR: 1,
        WorkspaceOpksKind.KNOWLEDGE: 2,
        WorkspaceOpksKind.SKILL: 3,
    }
    return tuple(
        sorted(
            _load_opks_resources(parsed),
            key=lambda item: (order[item[1].kind], item[0]),
        )
    )


def _header_resource(document: ApprovedJobDocument) -> WorkspaceHeaderResource:
    return WorkspaceHeaderResource(
        job_title=document.job_title,
        occupation_category_name=document.occupation_category_name,
        occupation_name=document.occupation_name,
        occupation_code=document.occupation_code,
        industry_name=document.industry_name,
        industry_code=document.industry_code,
        work_description=document.work_description,
        notes=document.notes,
    )


def _sorted_entity_groups(
    document: ApprovedJobDocument,
) -> tuple[tuple[str, tuple[UUID, ...]], ...]:
    groups: list[tuple[str, tuple[UUID, ...]]] = [
        (
            "duty",
            tuple(item.duty_id for item in _sorted_by_display_order(document.duties)),
        ),
        (
            "task",
            tuple(item.task_id for item in _sorted_by_display_order(document.tasks)),
        ),
    ]
    opks_by_prefix = (
        ("o", ApprovedOpksKind.OUTPUT),
        ("p", ApprovedOpksKind.PERFORMANCE_INDICATOR),
        ("k", ApprovedOpksKind.KNOWLEDGE),
        ("s", ApprovedOpksKind.SKILL),
        ("a", ApprovedOpksKind.ATTITUDE),
    )
    for prefix, kind in opks_by_prefix:
        groups.append(
            (
                prefix,
                tuple(item.item_id for item in _sorted_opks(document.opks, kind)),
            )
        )

    return tuple(groups)


def _sorted_by_display_order(values: Iterable[Any]) -> tuple[Any, ...]:
    return tuple(sorted(values, key=lambda item: (item.display_order, str(_identity(item)))))


def _sorted_opks(
    values: Iterable[ApprovedOpksItem], kind: ApprovedOpksKind
) -> tuple[ApprovedOpksItem, ...]:
    return tuple(
        sorted(
            (item for item in values if item.kind is kind),
            key=lambda item: (item.display_order, str(item.item_id)),
        )
    )


def _identity(value: Any) -> UUID:
    for name in ("duty_id", "task_id", "item_id"):
        if hasattr(value, name):
            return getattr(value, name)
    raise TypeError(f"unsupported workspace entity: {type(value)!r}")


def _load_entity_resources(
    parsed: Mapping[str, Any],
    collection: str,
    model: type[WorkspaceModel],
) -> tuple[tuple[str, Any], ...]:
    prefix = f"{collection}/"
    expected_prefix = {"duties": "duty-", "tasks": "task-"}[collection]
    values: list[tuple[str, Any]] = []
    for relative, payload in sorted(parsed.items()):
        if not relative.startswith(prefix):
            continue
        name = relative[len(prefix) :]
        if "/" in name or not name.endswith(".json"):
            raise WorkspaceResourceError(f"invalid {collection} resource path: {relative}")
        handle = name[:-5]
        resource = _validate_resource(model, payload, relative)
        if resource.handle != handle:
            raise WorkspaceResourceError(f"resource handle does not match path: {relative}")
        if not handle.startswith(expected_prefix):
            raise WorkspaceResourceError(f"wrong handle kind for {relative}")
        values.append((handle, resource))
    return tuple(values)


def _load_opks_resources(parsed: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    values: list[tuple[str, Any]] = []
    for relative, payload in sorted(parsed.items()):
        match = re.fullmatch(r"opks/(o|p|k|s)/([^/]+)\.json", relative)
        if match is None:
            if relative.startswith("opks/"):
                raise WorkspaceResourceError(f"invalid OPKS resource path: {relative}")
            continue
        prefix, handle = match.groups()
        resource = _validate_resource(WorkspaceOpksResource, payload, relative)
        if resource.handle != handle:
            raise WorkspaceResourceError(f"resource handle does not match path: {relative}")
        expected_kind = {
            "o": WorkspaceOpksKind.OUTPUT,
            "p": WorkspaceOpksKind.PERFORMANCE_INDICATOR,
            "k": WorkspaceOpksKind.KNOWLEDGE,
            "s": WorkspaceOpksKind.SKILL,
        }[prefix]
        if resource.kind is not expected_kind:
            raise WorkspaceResourceError(f"OPKS kind does not match path: {relative}")
        values.append((handle, resource))
    return tuple(values)


def _validate_resource(model: type[WorkspaceModel], value: Any, path: str) -> WorkspaceModel:
    try:
        return model.model_validate(value)
    except ValueError as error:
        raise WorkspaceResourceError(f"invalid resource {path}: {error}") from error
