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
from typing import Any, Iterable, Literal, Mapping, Sequence
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
    DocumentChangeSet,
    DocumentPatchAction,
    DocumentPatchOperation,
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


# Temporary compatibility aliases.  Task 6 removes pre-workspace imports.
CandidateHeaderResource = WorkspaceHeaderResource
CandidateDutyResource = WorkspaceDutyResource
CandidateEnablerResource = WorkspaceEnablerResource
CandidateTaskResource = WorkspaceTaskResource
CandidateOpksKind = WorkspaceOpksKind
CandidateOpksResource = WorkspaceOpksResource


class CandidateOpksEvidenceBinding(WorkspaceModel):
    """Keep model-authored evidence attached to its owning OPKS handle."""

    opks_handle: Handle
    references: tuple[WorkspaceEvidenceReference, ...] = Field(min_length=1)


OpksEvidenceBinding = CandidateOpksEvidenceBinding


class CandidateReviewGroup(WorkspaceModel):
    handle: Handle
    action_handles: tuple[Handle, ...] = ()
    depends_on_handles: tuple[Handle, ...] = ()

    @model_validator(mode="after")
    def handles_are_unique(self) -> CandidateReviewGroup:
        for label, values in (
            ("action_handles", self.action_handles),
            ("depends_on_handles", self.depends_on_handles),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")
        return self


class CandidateReviewGroupsResource(WorkspaceModel):
    groups: tuple[CandidateReviewGroup, ...] = ()

    @model_validator(mode="after")
    def group_handles_are_unique(self) -> CandidateReviewGroupsResource:
        handles = [group.handle for group in self.groups]
        if len(handles) != len(set(handles)):
            raise ValueError("duplicate review group handle")
        return self


class CandidateDocumentDraft(WorkspaceModel):
    """The typed after-state reconstructed from candidate resources."""

    approved_document: ApprovedJobDocument
    review_groups: CandidateReviewGroupsResource = Field(
        default_factory=CandidateReviewGroupsResource
    )
    evidence_references: tuple[WorkspaceEvidenceReference, ...] = ()
    opks_evidence: tuple[CandidateOpksEvidenceBinding, ...] = ()

    @property
    def evidence_bindings(self) -> tuple[CandidateOpksEvidenceBinding, ...]:
        return self.opks_evidence


class WorkspaceResourceError(ValueError):
    """A candidate resource cannot be parsed into a valid document draft."""


@dataclass(frozen=True, slots=True)
class WorkspaceCatalog:
    """Immutable application-side mapping for one approved snapshot."""

    document: ApprovedJobDocument
    pending: tuple[DocumentChangeSet, ...] = ()
    sources: tuple[EmployeeSource, ...] = ()
    _stable_to_handle: Mapping[UUID, str] = field(default_factory=dict, repr=False)
    _handle_to_stable: Mapping[str, UUID] = field(default_factory=dict, repr=False)
    _source_by_handle: Mapping[str, EmployeeSource] = field(
        default_factory=dict, repr=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "pending", tuple(self.pending))
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
        pending: Sequence[DocumentChangeSet] | DocumentChangeSet = (),
        sources: Sequence[EmployeeSource] = (),
        *,
        employee_sources: Sequence[EmployeeSource] | None = None,
    ) -> WorkspaceCatalog:
        if isinstance(pending, EmployeeSource):
            pending_values: tuple[DocumentChangeSet, ...] = ()
            positional_sources: tuple[EmployeeSource, ...] = (pending,)
        elif isinstance(pending, Sequence) and pending and all(
            isinstance(item, EmployeeSource) for item in pending
        ):
            pending_values = ()
            positional_sources = tuple(pending)
        else:
            pending_values = (
                (pending,)
                if isinstance(pending, DocumentChangeSet)
                else tuple(pending)
            )
            positional_sources = tuple(sources)
        source_values = tuple(
            sorted(
                (
                    employee_sources
                    if employee_sources is not None
                    else positional_sources
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

        for prefix, values in _sorted_entity_groups(document, pending_values):
            for index, stable_id in enumerate(values, start=1):
                add_mapping(stable_id, f"{prefix}-{index:03d}")

        source_ids = {source.source_id for source in source_values}
        source_ids.update(
            source_id
            for item in document.opks
            for source_id in item.evidence_source_ids
        )
        for changeset in pending_values:
            source_ids.update(changeset.source_ids)
            source_ids.update(
                source_id
                for action in changeset.actions
                for source_id in action.source_ids
            )
            source_ids.update(
                anchor.source_id
                for action in changeset.actions
                for anchor in action.quote_anchors
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
            pending=pending_values,
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


class WorkspaceDraftOpks(WorkspaceModel):
    item_id: UUID
    kind: WorkspaceOpksKind
    text: NonEmptyText
    task_ids: tuple[UUID, ...] = ()
    indicator_ids: tuple[UUID, ...] = ()


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
    """Validated editable workspace content plus its durable identity registry."""

    document: WorkspaceEditableDocument
    handle_registry: dict[str, UUID]


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

    duties = tuple(
        WorkspaceDraftDuty(duty_id=duty_ids[handle], statement=resource.statement)
        for handle, resource in duty_resources
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
        )
        for handle, resource in task_resources
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
        )
        for handle, resource in opks_resources
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
    for handle, candidate_id in registry.items():
        if candidate_id == stable_id:
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
    candidate_index = index
    while True:
        handle = f"{prefix}{candidate_index:03d}"
        known_id = registry.get(handle)
        if known_id is None:
            registry[handle] = stable_id
            return handle
        if known_id == stable_id:
            return handle
        candidate_index += 1


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


def project_candidate_files(
    catalog: WorkspaceCatalog,
    *,
    run_id: UUID | str,
) -> dict[str, str]:
    run = str(_validated_run_id(run_id))
    root = f"/candidate/{run}"
    files: dict[str, str] = {
        f"{root}/header.json": canonical_resource_json(_header_resource(catalog.document))
    }

    for duty in _sorted_by_display_order(catalog.document.duties):
        resource = CandidateDutyResource(
            handle=catalog.handle_for_id(duty.duty_id),
            statement=duty.statement,
        )
        files[f"{root}/duties/{resource.handle}.json"] = canonical_resource_json(resource)

    for task in _sorted_by_display_order(catalog.document.tasks):
        resource = CandidateTaskResource(
            handle=catalog.handle_for_id(task.task_id),
            duty_handle=(
                catalog.handle_for_id(task.duty_id)
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
                CandidateEnablerResource(kind=item.kind, name=item.name)
                for item in task.enablers
            ),
        )
        files[f"{root}/tasks/{resource.handle}.json"] = canonical_resource_json(resource)

    for kind, prefix in (
        (ApprovedOpksKind.OUTPUT, "o"),
        (ApprovedOpksKind.PERFORMANCE_INDICATOR, "p"),
        (ApprovedOpksKind.KNOWLEDGE, "k"),
        (ApprovedOpksKind.SKILL, "s"),
    ):
        for item in _sorted_opks(catalog.document.opks, kind):
            resource = CandidateOpksResource(
                handle=catalog.handle_for_id(item.item_id),
                kind=CandidateOpksKind(item.kind.value),
                text=item.text,
                task_handles=tuple(
                    catalog.handle_for_id(task_id) for task_id in item.task_ids
                ),
                indicator_handles=tuple(
                    catalog.handle_for_id(indicator_id)
                    for indicator_id in item.indicator_ids
                ),
            )
            files[f"{root}/opks/{prefix}/{resource.handle}.json"] = canonical_resource_json(resource)

    files[f"{root}/review-groups.json"] = canonical_resource_json(
        _project_review_groups(catalog)
    )
    return files


def parse_candidate_files(
    catalog: WorkspaceCatalog,
    files: Mapping[str, str | bytes],
    *,
    run_id: UUID | str | None = None,
    new_entity_namespace: Literal["candidate", "workspace"] = "candidate",
) -> CandidateDocumentDraft:
    parsed: dict[str, Any] = {}
    expected_run = _validated_run_id(run_id) if run_id is not None else None
    for path, raw in files.items():
        path_text = str(path)
        match = re.fullmatch(r"/candidate/([^/]+)/(.*)", path_text)
        if match is None:
            raise WorkspaceResourceError(f"unexpected candidate resource path: {path_text}")
        path_run, relative = match.groups()
        path_run_id = _validated_run_id(path_run)
        if expected_run is not None and path_run_id != expected_run:
            raise WorkspaceResourceError("candidate resource belongs to another run")
        if expected_run is None:
            expected_run = path_run_id
        try:
            value = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (TypeError, ValueError) as error:
            raise WorkspaceResourceError(f"invalid JSON resource: {path_text}") from error
        parsed[relative] = value

    for relative in parsed:
        if (
            relative not in {"header.json", "review-groups.json"}
            and not relative.startswith("duties/")
            and not relative.startswith("tasks/")
            and not relative.startswith("opks/")
        ):
            raise WorkspaceResourceError(f"unexpected candidate resource: {relative}")

    header_value = parsed.get("header.json")
    if header_value is None:
        raise WorkspaceResourceError("candidate header.json is required")
    header = _validate_resource(CandidateHeaderResource, header_value, "header.json")
    duty_resources = _load_entity_resources(parsed, "duties", CandidateDutyResource)
    task_resources = _load_entity_resources(parsed, "tasks", CandidateTaskResource)
    opks_resources = _load_opks_resources(parsed)
    review_groups_value = parsed.get("review-groups.json")
    review_groups = (
        _validate_resource(
            CandidateReviewGroupsResource,
            review_groups_value,
            "review-groups.json",
        )
        if review_groups_value is not None
        else CandidateReviewGroupsResource()
    )
    if expected_run is None:
        raise WorkspaceResourceError("candidate run namespace must be a UUID")

    duties = _parse_duties(
        catalog,
        duty_resources,
        expected_run,
        new_entity_namespace=new_entity_namespace,
    )
    duty_ids = {item.handle: item.duty.duty_id for item in duties}
    tasks = _parse_tasks(
        catalog,
        task_resources,
        duty_ids,
        expected_run,
        new_entity_namespace=new_entity_namespace,
    )
    task_ids = {item.handle: item.task.task_id for item in tasks}
    opks, evidence_references, opks_evidence = _parse_opks(
        catalog,
        opks_resources,
        task_ids,
        expected_run,
        new_entity_namespace=new_entity_namespace,
    )
    opks = _restore_baseline_attitudes(catalog.document.opks, opks)

    try:
        document = ApprovedJobDocument(
            schema_version=catalog.document.schema_version,
            document_id=catalog.document.document_id,
            job_title=header.job_title,
            occupation_category_name=header.occupation_category_name,
            occupation_name=header.occupation_name,
            occupation_code=header.occupation_code,
            industry_name=header.industry_name,
            industry_code=header.industry_code,
            work_description=header.work_description,
            competency_level=catalog.document.competency_level,
            notes=header.notes,
            duties=tuple(item.duty for item in duties),
            tasks=tuple(item.task for item in tasks),
            opks=tuple(item.item for item in opks),
        )
    except ValueError as error:
        raise WorkspaceResourceError(str(error)) from error
    return CandidateDocumentDraft(
        approved_document=document,
        review_groups=review_groups,
        evidence_references=tuple(evidence_references),
        opks_evidence=opks_evidence,
    )


def _header_resource(document: ApprovedJobDocument) -> CandidateHeaderResource:
    return CandidateHeaderResource(
        job_title=document.job_title,
        occupation_category_name=document.occupation_category_name,
        occupation_name=document.occupation_name,
        occupation_code=document.occupation_code,
        industry_name=document.industry_name,
        industry_code=document.industry_code,
        work_description=document.work_description,
        notes=document.notes,
    )


def _project_review_groups(catalog: WorkspaceCatalog) -> CandidateReviewGroupsResource:
    pending = _sorted_pending(catalog.pending)
    action_handles = pending_action_handles(pending)
    return CandidateReviewGroupsResource(
        groups=tuple(
            CandidateReviewGroup(
                handle=f"review-{group_index:03d}",
                action_handles=tuple(
                    action_handles[action.action_id] for action in changeset.actions
                ),
                depends_on_handles=_dependency_handles(changeset, action_handles),
            )
            for group_index, changeset in enumerate(pending, start=1)
        )
    )


def _sorted_pending(
    pending: Sequence[DocumentChangeSet],
) -> tuple[DocumentChangeSet, ...]:
    return tuple(
        sorted(
            pending,
            key=lambda changeset: (
                changeset.created_revision,
                str(changeset.changeset_id),
            ),
        )
    )


def pending_action_handles(
    pending: Sequence[DocumentChangeSet],
) -> dict[UUID, str]:
    result: dict[UUID, str] = {}
    for changeset in _sorted_pending(pending):
        for action in changeset.actions:
            if action.action_id in result:
                raise WorkspaceResourceError(
                    f"duplicate pending action_id: {action.action_id}"
                )
            result[action.action_id] = f"action-{len(result) + 1:03d}"
    external_ids = sorted(
        {
            dependency_id
            for changeset in pending
            for dependency_id in changeset.external_dependency_action_ids
            if dependency_id not in result
        },
        key=str,
    )
    for dependency_id in external_ids:
        result[dependency_id] = f"action-{len(result) + 1:03d}"
    return result


def _dependency_handles(
    changeset: DocumentChangeSet,
    action_handles: Mapping[UUID, str],
) -> tuple[str, ...]:
    dependency_ids = set(changeset.external_dependency_action_ids)
    for action in changeset.actions:
        dependency_ids.update(action.depends_on_action_ids)

    result: list[str] = []
    for dependency_id in sorted(dependency_ids, key=str):
        try:
            result.append(action_handles[dependency_id])
        except KeyError as error:
            raise WorkspaceResourceError(
                f"unknown pending dependency action_id: {dependency_id}"
            ) from error
    return tuple(result)


def _sorted_entity_groups(
    document: ApprovedJobDocument,
    pending: Sequence[DocumentChangeSet],
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

    pending_ids: dict[str, list[UUID]] = {prefix: [] for prefix, _ in groups}
    known_by_prefix = {
        prefix: set(values)
        for prefix, values in groups
    }
    for changeset in pending:
        for action in changeset.actions:
            if action.operation is not DocumentPatchOperation.ADD:
                continue
            payload = action.after
            if not isinstance(payload, dict):
                continue
            prefix, stable_id = _pending_entity_identity(changeset, action, payload)
            if (
                stable_id is not None
                and stable_id not in known_by_prefix[prefix]
            ):
                pending_ids[prefix].append(stable_id)
                known_by_prefix[prefix].add(stable_id)
    opks_prefixes = {
        "output": "o",
        "indicator": "p",
        "knowledge": "k",
        "skill": "s",
        "attitude": "a",
    }
    for changeset in pending:
        for action in changeset.actions:
            parts = action.path.strip("/").split("/")
            collection = parts[0] if parts else ""
            prefix = {"duties": "duty", "tasks": "task"}.get(collection)
            if collection == "opks":
                payloads = [
                    payload
                    for value in (action.after, action.before)
                    for payload in (
                        value
                        if isinstance(value, list)
                        else [value]
                    )
                    if isinstance(payload, dict)
                ]
                prefix = next(
                    (
                        opks_prefixes.get(str(payload.get("kind")))
                        for payload in payloads
                        if opks_prefixes.get(str(payload.get("kind"))) is not None
                    ),
                    None,
                )
                if prefix is None:
                    target_key_parts = action.target_key.split(":", 3)
                    if len(target_key_parts) > 2:
                        prefix = opks_prefixes.get(target_key_parts[2])
            if prefix is None:
                continue
            historical_ids: list[UUID] = list(action.target_ids)
            if len(parts) >= 2:
                try:
                    historical_ids.append(UUID(parts[1]))
                except ValueError:
                    pass
            for stable_id in historical_ids:
                if stable_id not in known_by_prefix[prefix]:
                    pending_ids[prefix].append(stable_id)
                    known_by_prefix[prefix].add(stable_id)
    return tuple(
        (prefix, values + tuple(sorted(pending_ids[prefix], key=str)))
        for prefix, values in groups
    )


def _pending_entity_identity(
    changeset: DocumentChangeSet,
    action: DocumentPatchAction,
    payload: dict[str, Any],
) -> tuple[str, UUID | None]:
    collection = action.path.strip("/").split("/", 1)[0]
    key = {"duties": "duty_id", "tasks": "task_id", "opks": "item_id"}.get(collection)
    if key is None:
        return "duty", None
    raw_id = payload.get(key)
    if raw_id is None:
        stable_id = uuid5(changeset.changeset_id, str(action.action_id))
    else:
        try:
            stable_id = UUID(str(raw_id))
        except (TypeError, ValueError, AttributeError):
            return "duty", None
    if collection == "duties":
        return "duty", stable_id
    if collection == "tasks":
        return "task", stable_id
    return (
        {
            "output": "o",
            "indicator": "p",
            "knowledge": "k",
            "skill": "s",
            "attitude": "a",
        }.get(str(payload.get("kind")), "o"),
        stable_id,
    )


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
        resource = _validate_resource(CandidateOpksResource, payload, relative)
        if resource.handle != handle:
            raise WorkspaceResourceError(f"resource handle does not match path: {relative}")
        expected_kind = {
            "o": CandidateOpksKind.OUTPUT,
            "p": CandidateOpksKind.PERFORMANCE_INDICATOR,
            "k": CandidateOpksKind.KNOWLEDGE,
            "s": CandidateOpksKind.SKILL,
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


@dataclass(frozen=True, slots=True)
class _DutyDraft:
    handle: str
    duty: ApprovedDuty


def _parse_duties(
    catalog: WorkspaceCatalog,
    values: Sequence[tuple[str, CandidateDutyResource]],
    run_id: UUID,
    *,
    new_entity_namespace: Literal["candidate", "workspace"],
) -> tuple[_DutyDraft, ...]:
    existing = {item.duty_id: item for item in catalog.document.duties}
    next_order = max((item.display_order for item in existing.values()), default=-1) + 1
    drafts: list[_DutyDraft] = []
    for index, (handle, resource) in enumerate(values):
        stable_id = _resolve_entity_id(
            catalog,
            handle,
            "duty",
            run_id,
            new_entity_namespace=new_entity_namespace,
        )
        baseline = existing.get(stable_id)
        drafts.append(
            _DutyDraft(
                handle=handle,
                duty=ApprovedDuty(
                    duty_id=stable_id,
                    statement=resource.statement,
                    display_order=(
                        resource.display_order
                        if resource.display_order is not None
                        else baseline.display_order
                        if baseline
                        else next_order + index
                    ),
                ),
            )
        )
    return _order_drafts(drafts)


@dataclass(frozen=True, slots=True)
class _TaskDraft:
    handle: str
    task: ApprovedTask


def _parse_tasks(
    catalog: WorkspaceCatalog,
    values: Sequence[tuple[str, CandidateTaskResource]],
    duty_ids: Mapping[str, UUID],
    run_id: UUID,
    *,
    new_entity_namespace: Literal["candidate", "workspace"],
) -> tuple[_TaskDraft, ...]:
    existing = {item.task_id: item for item in catalog.document.tasks}
    next_order = max((item.display_order for item in existing.values()), default=-1) + 1
    drafts: list[_TaskDraft] = []
    for index, (handle, resource) in enumerate(values):
        stable_id = _resolve_entity_id(
            catalog,
            handle,
            "task",
            run_id,
            new_entity_namespace=new_entity_namespace,
        )
        baseline = existing.get(stable_id)
        duty_id = duty_ids.get(resource.duty_handle) if resource.duty_handle else None
        if resource.duty_handle and duty_id is None:
            raise WorkspaceResourceError(f"unknown duty handle: {resource.duty_handle}")
        drafts.append(
            _TaskDraft(
                handle=handle,
                task=ApprovedTask(
                    task_id=stable_id,
                    duty_id=duty_id,
                    statement=resource.statement,
                    action=resource.action,
                    object=resource.object,
                    purpose_result=resource.purpose_result,
                    context=resource.context,
                    frequency_text=resource.frequency_text,
                    responsibility_role=resource.responsibility_role,
                    enablers=tuple(
                        ApprovedEnabler(kind=item.kind, name=item.name)
                        for item in resource.enablers
                    ),
                    display_order=(
                        resource.display_order
                        if resource.display_order is not None
                        else baseline.display_order
                        if baseline
                        else next_order + index
                    ),
                    competency_level=(baseline.competency_level if baseline else None),
                ),
            )
        )
    return _order_drafts(drafts)


@dataclass(frozen=True, slots=True)
class _OpksDraft:
    handle: str
    item: ApprovedOpksItem


def _parse_opks(
    catalog: WorkspaceCatalog,
    values: Sequence[tuple[str, CandidateOpksResource]],
    task_ids: Mapping[str, UUID],
    run_id: UUID,
    *,
    new_entity_namespace: Literal["candidate", "workspace"],
) -> tuple[
    tuple[_OpksDraft, ...],
    tuple[WorkspaceEvidenceReference, ...],
    tuple[CandidateOpksEvidenceBinding, ...],
]:
    existing = {
        item.item_id: item
        for item in catalog.document.opks
        if item.kind is not ApprovedOpksKind.ATTITUDE
    }
    opks_ids = {
        handle: _resolve_entity_id(
            catalog,
            handle,
            resource.kind.value,
            run_id,
            new_entity_namespace=new_entity_namespace,
        )
        for handle, resource in values
    }
    indicator_ids = {
        handle: stable_id
        for handle, stable_id in opks_ids.items()
        if handle.startswith("p-")
    }
    next_orders = {
        kind: max(
            (item.display_order for item in existing.values() if item.kind is kind),
            default=-1,
        )
        + 1
        for kind in ApprovedOpksKind
        if kind is not ApprovedOpksKind.ATTITUDE
    }
    drafts: list[_OpksDraft] = []
    evidence_references: list[WorkspaceEvidenceReference] = []
    opks_evidence: list[CandidateOpksEvidenceBinding] = []
    for index, (handle, resource) in enumerate(values):
        kind = ApprovedOpksKind(resource.kind.value)
        stable_id = opks_ids[handle]
        baseline = existing.get(stable_id)
        resolved_task_ids = tuple(_resolve_task_handles(task_ids, resource.task_handles))
        resolved_indicator_ids = tuple(
            _resolve_indicator_handles(indicator_ids, resource.indicator_handles)
        )
        if resource.evidence:
            source_ids = tuple(
                _resolve_source_handle(catalog, item.source_handle)
                for item in resource.evidence
            )
            evidence_references.extend(resource.evidence)
            opks_evidence.append(
                CandidateOpksEvidenceBinding(
                    opks_handle=handle,
                    references=resource.evidence,
                )
            )
        elif baseline is not None:
            source_ids = baseline.evidence_source_ids
        else:
            source_ids = ()
        drafts.append(
            _OpksDraft(
                handle=handle,
                item=ApprovedOpksItem(
                    item_id=stable_id,
                    kind=kind,
                    text=resource.text,
                    display_order=(
                        resource.display_order
                        if resource.display_order is not None
                        else baseline.display_order
                        if baseline is not None
                        else next_orders[kind] + index
                    ),
                    task_ids=resolved_task_ids,
                    indicator_ids=resolved_indicator_ids,
                    evidence_source_ids=source_ids,
                ),
            )
        )
    return _order_drafts(drafts), tuple(evidence_references), tuple(opks_evidence)


def _restore_baseline_attitudes(
    baseline: Sequence[ApprovedOpksItem], editable: Sequence[_OpksDraft]
) -> tuple[_OpksDraft, ...]:
    by_id = {draft.item.item_id: draft for draft in editable}
    baseline_ids = {item.item_id for item in baseline}
    result: list[_OpksDraft] = []
    for item in baseline:
        if item.kind is ApprovedOpksKind.ATTITUDE:
            result.append(_OpksDraft(handle="", item=item))
        elif item.item_id in by_id:
            result.append(by_id[item.item_id])
    result.extend(
        draft for draft in editable if draft.item.item_id not in baseline_ids
    )
    return tuple(result)


def _order_drafts(drafts: Sequence[Any]) -> tuple[Any, ...]:
    def key(draft: Any) -> tuple[int, str]:
        item = draft.task if hasattr(draft, "task") else draft.duty if hasattr(draft, "duty") else draft.item
        return item.display_order, str(_identity(item))

    return tuple(sorted(drafts, key=key))


def _resolve_entity_id(
    catalog: WorkspaceCatalog,
    handle: str,
    kind: str,
    run_id: UUID,
    *,
    new_entity_namespace: Literal["candidate", "workspace"],
) -> UUID:
    expected_prefix = {
        "duty": "duty-",
        "task": "task-",
        "output": "o-",
        "indicator": "p-",
        "knowledge": "k-",
        "skill": "s-",
    }.get(kind)
    if expected_prefix is not None and not handle.startswith(expected_prefix):
        raise WorkspaceResourceError(f"handle {handle} is not a {kind} handle")
    try:
        return catalog.id_for_handle(handle)
    except KeyError:
        if new_entity_namespace == "workspace":
            return workspace_entity_id(
                catalog.document.document_id,
                handle,
                kind,
                handle_registry=catalog.handle_to_stable,
            )
        return uuid5(
            catalog.document.document_id,
            f"candidate:{run_id}:{kind}:{handle}",
        )


def _resolve_task_handles(
    task_ids: Mapping[str, UUID], handles: Sequence[str]
) -> Iterable[UUID]:
    for handle in handles:
        try:
            yield task_ids[handle]
        except KeyError as error:
            raise WorkspaceResourceError(f"unknown task handle: {handle}") from error


def _resolve_indicator_handles(
    indicator_ids: Mapping[str, UUID], handles: Sequence[str]
) -> Iterable[UUID]:
    for handle in handles:
        try:
            yield indicator_ids[handle]
        except KeyError as error:
            raise WorkspaceResourceError(f"unknown indicator handle: {handle}") from error


def _resolve_source_handle(catalog: WorkspaceCatalog, handle: str) -> UUID:
    if not handle.startswith("source-"):
        raise WorkspaceResourceError(f"not a source handle: {handle}")
    try:
        return catalog.id_for_handle(handle)
    except KeyError as error:
        raise WorkspaceResourceError(f"unknown source handle: {handle}") from error


def _validated_run_id(value: UUID | str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise WorkspaceResourceError("candidate run namespace must be a UUID") from error
