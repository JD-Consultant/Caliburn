"""Employee-facing semantic review derived from approved and workspace state.

The workspace remains a non-authoritative draft.  This module creates an
ephemeral review projection; authority commits are performed separately by
the workspace authority service.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, cast
from uuid import UUID, uuid5

from pydantic import JsonValue

from app.consultant.document_authority import (
    DocumentAuthorityError,
    apply_document_actions,
    document_path_sha256,
    read_document_path,
)
from app.consultant.results import (
    AnalysisBasis,
    DocumentChangeOperation,
    OpksKind,
    ReviewableDocumentChange,
    SkillId,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    DocumentChangeSet,
    DocumentChangeStatus,
    DocumentPathRead,
    DocumentPatchAction,
    DocumentPatchOperation,
)
from app.consultant.workspace_state import (
    Sha256Digest,
    WorkspaceDiagnostic,
    WorkspaceDiagnosticSeverity,
    WorkspaceManifest,
    WorkspaceValidationStatus,
    approved_document_digest,
)
from app.consultant.workspace_validation import (
    WorkspacePayloadValidation,
    evidence_basis_digest,
)


_HEADER_FIELDS = (
    "job_title",
    "occupation_category_name",
    "occupation_name",
    "occupation_code",
    "industry_name",
    "industry_code",
    "work_description",
    "notes",
)
_DUTY_FIELDS = ("statement",)
_TASK_FIELDS = (
    "duty_id",
    "statement",
    "action",
    "object",
    "purpose_result",
    "context",
    "frequency_text",
    "responsibility_role",
    "enablers",
)
_OPKS_FIELDS = ("text", "task_ids", "indicator_ids")
_EDITABLE_OPKS_KINDS = {
    ApprovedOpksKind.OUTPUT,
    ApprovedOpksKind.PERFORMANCE_INDICATOR,
    ApprovedOpksKind.KNOWLEDGE,
    ApprovedOpksKind.SKILL,
}
_COLLECTION_ID_FIELDS = {
    "/duties": "duty_id",
    "/tasks": "task_id",
    "/opks": "item_id",
}
_STRUCTURAL_OPERATIONS = {
    DocumentPatchOperation.WITHDRAW,
    DocumentPatchOperation.REASSIGN,
}


class WorkspaceReviewDecisionKind(StrEnum):
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class WorkspaceReviewDecision:
    kind: WorkspaceReviewDecisionKind
    workspace_digest: Sha256Digest
    group_digest: Sha256Digest
    semantic_fingerprint: Sha256Digest
    evidence_digest: Sha256Digest
    employee_request_digest: Sha256Digest
    boundary_digest: Sha256Digest
    selected_action_ids: tuple[UUID, ...] = ()
    selected_action_fingerprints: tuple[Sha256Digest, ...] = ()

    @classmethod
    def from_group(
        cls,
        kind: WorkspaceReviewDecisionKind,
        group: WorkspaceReviewGroup,
        *,
        workspace_digest: Sha256Digest,
        selected_action_ids: tuple[UUID, ...] = (),
    ) -> WorkspaceReviewDecision:
        selected_ids = set(selected_action_ids)
        selected_actions = tuple(
            action
            for action in group.actions
            if not selected_ids or action.action_id in selected_ids
        )
        return cls(
            kind=kind,
            workspace_digest=workspace_digest,
            group_digest=group.group_digest,
            semantic_fingerprint=group.semantic_fingerprint,
            evidence_digest=group.evidence_digest,
            employee_request_digest=group.employee_request_digest,
            boundary_digest=group.boundary_digest,
            selected_action_ids=selected_action_ids,
            selected_action_fingerprints=tuple(
                workspace_action_semantic_fingerprint(action)
                for action in selected_actions
            ),
        )


@dataclass(frozen=True, slots=True)
class WorkspaceReviewGroup:
    changeset: DocumentChangeSet
    group_digest: Sha256Digest
    semantic_fingerprint: Sha256Digest
    evidence_digest: Sha256Digest
    employee_request_digest: Sha256Digest
    boundary_digest: Sha256Digest
    diagnostics: tuple[WorkspaceDiagnostic, ...] = ()

    @property
    def actions(self) -> tuple[DocumentPatchAction, ...]:
        return self.changeset.actions


@dataclass(frozen=True, slots=True)
class WorkspaceReviewProjection:
    workspace_digest: Sha256Digest
    groups: tuple[WorkspaceReviewGroup, ...] = ()
    diagnostics: tuple[WorkspaceDiagnostic, ...] = ()
    entity_ids_by_handle: Mapping[str, UUID] = field(
        default_factory=dict,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "entity_ids_by_handle",
            MappingProxyType(dict(self.entity_ids_by_handle)),
        )

    @property
    def changesets(self) -> tuple[DocumentChangeSet, ...]:
        return tuple(group.changeset for group in self.groups)

    @property
    def blocking_diagnostics(self) -> tuple[WorkspaceDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity is WorkspaceDiagnosticSeverity.ERROR
        )

    def group_containing_path(self, path: str) -> WorkspaceReviewGroup | None:
        parts = path.rstrip("/").split("/")
        if len(parts) >= 3 and parts[2] in self.entity_ids_by_handle:
            parts[2] = str(self.entity_ids_by_handle[parts[2]])
        target = "/".join(parts)
        for group in self.groups:
            if any(
                action.path.rstrip("/") == target
                or action.path.rstrip("/").startswith(f"{target}/")
                for action in group.changeset.actions
            ):
                return group
        return None


def _digest(value: Any) -> Sha256Digest:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return cast(Sha256Digest, sha256(encoded).hexdigest())


def _model_json(value: Any) -> dict[str, JsonValue]:
    return value.model_dump(mode="json")


def _entity_maps(document: ApprovedJobDocument) -> tuple[
    dict[UUID, ApprovedDuty],
    dict[UUID, ApprovedTask],
    dict[UUID, ApprovedOpksItem],
]:
    return (
        {item.duty_id: item for item in document.duties},
        {item.task_id: item for item in document.tasks},
        {item.item_id: item for item in document.opks},
    )


def _next_orders(
    document: ApprovedJobDocument,
    working_document: ApprovedJobDocument,
) -> dict[str, dict[UUID, int]]:
    result: dict[str, dict[UUID, int]] = {
        "duties": {},
        "tasks": {},
        "output": {},
        "indicator": {},
        "knowledge": {},
        "skill": {},
    }
    baseline_duties = {item.duty_id for item in document.duties}
    baseline_tasks = {item.task_id for item in document.tasks}
    for collection, values, baseline_ids in (
        ("duties", working_document.duties, baseline_duties),
        ("tasks", working_document.tasks, baseline_tasks),
    ):
        next_order = max(
            (item.display_order for item in getattr(document, collection)), default=-1
        ) + 1
        identity_name = "duty_id" if collection == "duties" else "task_id"
        for item in sorted(
            (item for item in values if getattr(item, identity_name) not in baseline_ids),
            key=lambda item: (item.display_order, str(getattr(item, identity_name))),
        ):
            result[collection][getattr(item, identity_name)] = next_order
            next_order += 1
    for kind in _EDITABLE_OPKS_KINDS:
        baseline_values = [item for item in document.opks if item.kind is kind]
        baseline_ids = {item.item_id for item in baseline_values}
        next_order = max((item.display_order for item in baseline_values), default=-1) + 1
        for item in sorted(
            (
                item
                for item in working_document.opks
                if item.kind is kind and item.item_id not in baseline_ids
            ),
            key=lambda item: (item.display_order, str(item.item_id)),
        ):
            result[kind.value][item.item_id] = next_order
            next_order += 1
    return result


def _normalized_entity_after(
    value: ApprovedDuty | ApprovedTask | ApprovedOpksItem,
    *,
    baseline: ApprovedJobDocument,
    orders: Mapping[str, Mapping[UUID, int]],
) -> dict[str, JsonValue]:
    payload = _model_json(value)
    if isinstance(value, ApprovedDuty):
        identity, collection = value.duty_id, "duties"
    elif isinstance(value, ApprovedTask):
        identity, collection = value.task_id, "tasks"
    else:
        identity, collection = value.item_id, value.kind.value
        payload.pop("evidence_source_ids", None)
    known_ids = {
        *(item.duty_id for item in baseline.duties),
        *(item.task_id for item in baseline.tasks),
        *(item.item_id for item in baseline.opks),
    }
    if identity not in known_ids:
        payload["display_order"] = orders[collection][identity]
    return payload


def _new_change(
    *,
    operation: DocumentChangeOperation,
    path: str,
    basis: AnalysisBasis,
    change_ref: str,
    after: JsonValue | None = None,
    **kwargs: Any,
) -> ReviewableDocumentChange:
    return ReviewableDocumentChange(
        operation=operation,
        path=path,
        basis=basis,
        change_ref=change_ref,
        after=after,
        **kwargs,
    )


def _resource_basis(
    *,
    handle: str,
    bindings: Mapping[str, tuple[AnalysisBasis, ...]],
    default: AnalysisBasis,
) -> AnalysisBasis:
    bound = bindings.get(handle, ())
    if not bound:
        return default
    source_ids: list[UUID] = []
    quote_anchors = []
    skill_ids: list[SkillId] = []
    for basis in bound:
        source_ids.extend(basis.source_ids)
        quote_anchors.extend(basis.quote_anchors)
        skill_ids.extend(basis.skill_ids)
    return AnalysisBasis(
        source_ids=tuple(dict.fromkeys(source_ids)),
        quote_anchors=tuple(quote_anchors),
        skill_ids=tuple(dict.fromkeys(skill_ids)),
    )


def _opks_basis(
    *,
    handle: str,
    bindings: Mapping[str, tuple[AnalysisBasis, ...]],
    default: AnalysisBasis,
    changed: bool,
) -> AnalysisBasis:
    if not changed:
        return default
    return _resource_basis(
        handle=handle,
        bindings=bindings,
        default=default,
    )


def derive_semantic_changes(
    *,
    baseline: ApprovedJobDocument,
    working_document: ApprovedJobDocument,
    workspace_handles: Mapping[UUID, str],
    evidence: Mapping[str, tuple[AnalysisBasis, ...]],
    default_basis: AnalysisBasis,
) -> tuple[ReviewableDocumentChange, ...]:
    """Return canonical semantic changes; formatting and key order are absent."""

    baseline_duties, baseline_tasks, baseline_opks = _entity_maps(baseline)
    working_duties, working_tasks, working_opks = _entity_maps(working_document)
    changes: list[ReviewableDocumentChange] = []

    def add(**kwargs: Any) -> None:
        changes.append(
            _new_change(change_ref=f"workspace-{len(changes) + 1:03d}", **kwargs)
        )

    baseline_header = baseline.model_dump(mode="json")
    working_header = working_document.model_dump(mode="json")
    for field in _HEADER_FIELDS:
        if baseline_header[field] != working_header[field]:
            add(
                operation=DocumentChangeOperation.REVISE,
                path=f"/{field}",
                after=working_header[field],
                basis=_resource_basis(
                    handle="header",
                    bindings=evidence,
                    default=default_basis,
                ),
            )

    orders = _next_orders(baseline, working_document)
    for identity in sorted(set(baseline_duties) - set(working_duties), key=str):
        add(
            operation=DocumentChangeOperation.WITHDRAW,
            path=f"/duties/{identity}",
            basis=default_basis,
        )
    for identity in sorted(set(working_duties) - set(baseline_duties), key=str):
        handle = workspace_handles.get(identity, "")
        add(
            operation=DocumentChangeOperation.ADD,
            path="/duties",
            after=_normalized_entity_after(
                working_duties[identity], baseline=baseline, orders=orders
            ),
            basis=_resource_basis(
                handle=handle,
                bindings=evidence,
                default=default_basis,
            ),
        )
    for identity in sorted(set(baseline_duties) & set(working_duties), key=str):
        handle = workspace_handles.get(identity, "")
        before, after = (
            _model_json(baseline_duties[identity]),
            _model_json(working_duties[identity]),
        )
        for field in _DUTY_FIELDS:
            if before[field] != after[field]:
                add(
                    operation=DocumentChangeOperation.REVISE,
                    path=f"/duties/{identity}/{field}",
                    after=after[field],
                    basis=_resource_basis(
                        handle=handle,
                        bindings=evidence,
                        default=default_basis,
                    ),
                )
        if before["display_order"] != after["display_order"]:
            add(
                operation=DocumentChangeOperation.REORDER,
                path=f"/duties/{identity}/display_order",
                after=after["display_order"],
                basis=default_basis,
            )

    for identity in sorted(set(baseline_tasks) - set(working_tasks), key=str):
        add(
            operation=DocumentChangeOperation.WITHDRAW,
            path=f"/tasks/{identity}",
            basis=default_basis,
        )
    for identity in sorted(set(working_tasks) - set(baseline_tasks), key=str):
        handle = workspace_handles.get(identity, "")
        add(
            operation=DocumentChangeOperation.ADD,
            path="/tasks",
            after=_normalized_entity_after(
                working_tasks[identity], baseline=baseline, orders=orders
            ),
            basis=_resource_basis(
                handle=handle,
                bindings=evidence,
                default=default_basis,
            ),
        )
    for identity in sorted(set(baseline_tasks) & set(working_tasks), key=str):
        handle = workspace_handles.get(identity, "")
        before, after = (
            _model_json(baseline_tasks[identity]),
            _model_json(working_tasks[identity]),
        )
        for field in _TASK_FIELDS:
            if before[field] == after[field]:
                continue
            add(
                operation=(
                    DocumentChangeOperation.REASSIGN
                    if field == "duty_id"
                    else DocumentChangeOperation.REVISE
                ),
                path=f"/tasks/{identity}/{field}",
                after=after[field],
                basis=(
                    default_basis
                    if field == "duty_id"
                    else _resource_basis(
                        handle=handle,
                        bindings=evidence,
                        default=default_basis,
                    )
                ),
            )
        if before["display_order"] != after["display_order"]:
            add(
                operation=DocumentChangeOperation.REORDER,
                path=f"/tasks/{identity}/display_order",
                after=after["display_order"],
                basis=default_basis,
            )

    for identity in sorted(set(baseline_opks) - set(working_opks), key=str):
        item = baseline_opks[identity]
        if item.kind in _EDITABLE_OPKS_KINDS:
            add(
                operation=DocumentChangeOperation.WITHDRAW,
                path=f"/opks/{identity}",
                basis=default_basis,
                opks_kind=OpksKind(item.kind.value),
            )
    for identity in sorted(set(working_opks) - set(baseline_opks), key=str):
        item = working_opks[identity]
        if item.kind not in _EDITABLE_OPKS_KINDS:
            continue
        basis = _opks_basis(
            handle=workspace_handles.get(identity, ""),
            bindings=evidence,
            default=default_basis,
            changed=True,
        )
        after = _normalized_entity_after(item, baseline=baseline, orders=orders)
        after["display_order"] = None
        add(
            operation=DocumentChangeOperation.ADD,
            path="/opks",
            after=after,
            basis=basis,
            opks_kind=OpksKind(item.kind.value),
            task_ids=item.task_ids,
            indicator_ids=item.indicator_ids,
        )
    for identity in sorted(set(baseline_opks) & set(working_opks), key=str):
        before_item, after_item = baseline_opks[identity], working_opks[identity]
        if before_item.kind not in _EDITABLE_OPKS_KINDS:
            continue
        before, after = _model_json(before_item), _model_json(after_item)
        changed = any(before[field] != after[field] for field in _OPKS_FIELDS)
        basis = _opks_basis(
            handle=workspace_handles.get(identity, ""),
            bindings=evidence,
            default=default_basis,
            changed=changed,
        )
        for field in _OPKS_FIELDS:
            if before[field] != after[field]:
                add(
                    operation=DocumentChangeOperation.REVISE,
                    path=f"/opks/{identity}/{field}",
                    after=after[field],
                    basis=basis,
                    opks_kind=OpksKind(after_item.kind.value),
                    task_ids=after_item.task_ids,
                    indicator_ids=after_item.indicator_ids,
                )
        if before["display_order"] != after["display_order"]:
            add(
                operation=DocumentChangeOperation.REORDER,
                path=f"/opks/{identity}/display_order",
                after=after["display_order"],
                basis=basis,
                opks_kind=OpksKind(after_item.kind.value),
                task_ids=after_item.task_ids,
                indicator_ids=after_item.indicator_ids,
            )
    return tuple(changes)


def _canonical_semantic_after(change: ReviewableDocumentChange) -> bytes:
    ignored_keys = {"evidence_source_ids"}
    if change.operation is DocumentChangeOperation.ADD:
        ignored_keys.add("display_order")
        id_field = _COLLECTION_ID_FIELDS.get(change.path)
        if id_field is not None:
            ignored_keys.add(id_field)
    semantic = (
        {
            key: item
            for key, item in change.after.items()
            if key not in ignored_keys
        }
        if isinstance(change.after, dict)
        else change.after
    )
    return json.dumps(
        semantic,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _logical_linkage_key(change: ReviewableDocumentChange) -> str:
    return json.dumps(
        {
            "indicator_ids": sorted(str(item) for item in change.indicator_ids),
            "task_ids": sorted(str(item) for item in change.task_ids),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _target_key(change: ReviewableDocumentChange) -> str:
    canonical = _canonical_semantic_after(change)
    linkage = _logical_linkage_key(change)
    axis = change.opks_kind.value if change.opks_kind is not None else "none"
    return (
        f"{change.operation.value}:{change.path}:{axis}:{linkage}:"
        f"{sha256(canonical).hexdigest()}"
    )


def _normalized_after(
    change: ReviewableDocumentChange,
    *,
    document_id: UUID,
    identity_scope: str,
    change_index: int,
    allocated_display_order: int | None,
) -> JsonValue | None:
    value = change.after
    id_field = _COLLECTION_ID_FIELDS.get(change.path)
    generated_id = str(
        uuid5(document_id, f"{identity_scope}:document-entity:{change_index}:0")
    )
    if (
        change.path in {"/duties", "/tasks"}
        and change.operation is DocumentChangeOperation.ADD
        and isinstance(value, dict)
        and value.get("display_order") is None
    ):
        if allocated_display_order is None:
            raise ValueError("new workspace entity requires an allocated order")
        value = {**value, "display_order": allocated_display_order}
    if (
        change.path == "/opks"
        and change.operation is DocumentChangeOperation.ADD
        and (isinstance(value, str) or isinstance(value, dict))
    ):
        if change.opks_kind is None:
            raise ValueError("OPKS add requires an OPKS kind")
        if allocated_display_order is None:
            raise ValueError("new OPKS item requires an allocated order")
        value = (
            {
                "item_id": generated_id,
                "text": value,
                "display_order": allocated_display_order,
            }
            if isinstance(value, str)
            else {**value, "display_order": allocated_display_order}
        )
    if (
        id_field is not None
        and change.operation is DocumentChangeOperation.ADD
        and isinstance(value, dict)
        and value.get(id_field) is None
    ):
        value = {**value, id_field: generated_id}
    if not change.path.startswith("/opks"):
        return value
    if change.operation is DocumentChangeOperation.ADD:
        if not isinstance(value, dict) or change.opks_kind is None:
            raise ValueError("OPKS add requires a complete typed object")
        return {
            **value,
            "kind": change.opks_kind.value,
            "task_ids": [str(item) for item in change.task_ids],
            "indicator_ids": [str(item) for item in change.indicator_ids],
            "evidence_source_ids": [str(source) for source in change.basis.source_ids],
        }
    return value


def _ensure_opks_axis_matches_document(
    change: ReviewableDocumentChange,
    document: ApprovedJobDocument,
) -> None:
    if not change.path.startswith("/opks") or change.opks_kind is None:
        return
    parts = change.path.strip("/").split("/")
    if len(parts) < 2:
        return
    known = {str(item.item_id): item.kind.value for item in document.opks}
    actual = known.get(parts[1])
    if actual is not None and actual != change.opks_kind.value:
        raise ValueError("workspace OPKS change does not match the existing axis")


def _read_paths(
    change: ReviewableDocumentChange,
    normalized_after: JsonValue | None,
) -> tuple[str, ...]:
    del normalized_after
    return (change.path,)


def _before_value(
    document: ApprovedJobDocument,
    change: ReviewableDocumentChange,
) -> JsonValue | None:
    if change.operation is DocumentChangeOperation.ADD:
        return None
    return read_document_path(document, change.path)


def _replacement_entities(action: DocumentPatchAction) -> tuple[dict[str, Any], ...]:
    if action.operation is DocumentPatchOperation.ADD and isinstance(action.after, dict):
        return (action.after,)
    return ()


def _entity_collection(path: str) -> str | None:
    root = "/" + path.lstrip("/").split("/", 1)[0]
    return root if root in _COLLECTION_ID_FIELDS else None


def _entity_target_from_path(path: str) -> tuple[str, str] | None:
    parts = path.strip("/").split("/")
    collection = "/" + parts[0] if parts else ""
    if collection not in _COLLECTION_ID_FIELDS or len(parts) < 2:
        return None
    try:
        UUID(parts[1])
    except ValueError:
        return None
    return collection, parts[1]


def _action_affects_entity(
    action: DocumentPatchAction,
    collection: str,
    identity: str,
) -> bool:
    return _entity_target_from_path(action.path) == (collection, identity)


def _link_required_groups(
    document_id: UUID,
    identity_scope: str,
    document: ApprovedJobDocument,
    actions: list[DocumentPatchAction],
) -> list[DocumentPatchAction]:
    creators: dict[tuple[str, str], int] = {}
    for index, action in enumerate(actions):
        collection = _entity_collection(action.path)
        id_field = _COLLECTION_ID_FIELDS.get(collection or "")
        for entity in _replacement_entities(action):
            if collection is not None and id_field is not None and entity.get(id_field) is not None:
                creators[(collection, str(entity[id_field]))] = index

    index_by_action_id = {action.action_id: index for index, action in enumerate(actions)}
    dependencies: dict[int, set[int]] = {index: set() for index in range(len(actions))}
    atomic_links: set[tuple[int, int]] = set()
    for index, action in enumerate(actions):
        for dependency_id in action.depends_on_action_ids:
            dependency_index = index_by_action_id.get(dependency_id)
            if dependency_index is not None and dependency_index != index:
                dependencies[index].add(dependency_index)
    grouped_by_explicit_id: dict[UUID, list[int]] = {}
    for index, action in enumerate(actions):
        if action.atomic_subgroup_id is not None:
            grouped_by_explicit_id.setdefault(action.atomic_subgroup_id, []).append(index)
    for members in grouped_by_explicit_id.values():
        for member in members[1:]:
            atomic_links.add((members[0], member))

    def depend(consumer: int, prerequisite: int) -> None:
        if consumer != prerequisite:
            dependencies[consumer].add(prerequisite)

    for index, action in enumerate(actions):
        if action.path.startswith("/tasks"):
            duty_id = action.after if action.operation is DocumentPatchOperation.REASSIGN else (
                action.after.get("duty_id") if isinstance(action.after, dict) else None
            )
            creator = creators.get(("/duties", str(duty_id))) if duty_id is not None else None
            if creator is not None:
                depend(index, creator)
                if action.operation is DocumentPatchOperation.REASSIGN:
                    atomic_links.add((index, creator))
        if action.path.startswith("/opks") and isinstance(action.after, (dict, list)):
            values = action.after if isinstance(action.after, list) else [action.after]
            for value in values:
                if not isinstance(value, dict):
                    continue
                for task_id in value.get("task_ids", []):
                    creator = creators.get(("/tasks", str(task_id)))
                    if creator is not None:
                        depend(index, creator)
                for indicator_id in value.get("indicator_ids", []):
                    creator = creators.get(("/opks", str(indicator_id)))
                    if creator is not None:
                        depend(index, creator)
        if action.path.endswith("/task_ids") and isinstance(action.after, list):
            for task_id in action.after:
                creator = creators.get(("/tasks", str(task_id)))
                if creator is not None:
                    depend(index, creator)
                    atomic_links.add((index, creator))
        if action.path.endswith("/indicator_ids") and isinstance(action.after, list):
            for indicator_id in action.after:
                creator = creators.get(("/opks", str(indicator_id)))
                if creator is not None:
                    depend(index, creator)
                    atomic_links.add((index, creator))

    removed: list[tuple[int, str, str]] = []
    for index, action in enumerate(actions):
        target = _entity_target_from_path(action.path)
        if action.operation is DocumentPatchOperation.WITHDRAW and target is not None:
            removed.append((index, *target))
    payload = document.model_dump(mode="json")
    for structural_index, collection, identity in removed:
        if collection == "/duties":
            dependent_entities = [
                ("/tasks", str(item["task_id"]))
                for item in payload["tasks"]
                if str(item.get("duty_id")) == identity
            ]
        elif collection == "/tasks":
            dependent_entities = [
                ("/opks", str(item["item_id"]))
                for item in payload["opks"]
                if identity in {str(value) for value in item.get("task_ids", [])}
            ]
        else:
            dependent_entities = [
                ("/opks", str(item["item_id"]))
                for item in payload["opks"]
                if identity in {str(value) for value in item.get("indicator_ids", [])}
            ]
        for collection_name, dependent_identity in dependent_entities:
            for mutator, action_item in enumerate(actions):
                if _action_affects_entity(action_item, collection_name, dependent_identity):
                    atomic_links.add((structural_index, mutator))

    adjacency: dict[int, set[int]] = {index: set() for index in dependencies}
    for left, right in atomic_links:
        adjacency[left].add(right)
        adjacency[right].add(left)
    grouped = list(actions)
    visited: set[int] = set()
    for start in range(len(actions)):
        if start in visited:
            continue
        stack = [start]
        component: set[int] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        visited.update(component)
        requires_group = len(component) > 1
        group_id = (
            uuid5(document_id, f"{identity_scope}:atomic-component:{','.join(map(str, sorted(component)))}")
            if requires_group
            else None
        )
        for index in component:
            action = grouped[index]
            grouped[index] = action.model_copy(
                update={
                    "atomic_subgroup_id": group_id,
                    "depends_on_action_ids": tuple(
                        sorted(
                            set(action.depends_on_action_ids)
                            | {grouped[prerequisite].action_id for prerequisite in dependencies[index]},
                            key=str,
                        )
                    ),
                }
            )
    return grouped


def create_workspace_changeset(
    *,
    document_id: UUID,
    summary: str,
    read_revision: int,
    document: ApprovedJobDocument,
    changes: Sequence[ReviewableDocumentChange],
    identity_scope: str,
    external_dependency_action_ids: Sequence[UUID] = (),
) -> DocumentChangeSet:
    """Build a replay-stable workspace review changeset without another lifecycle."""

    if not changes:
        raise ValueError("cannot create an empty workspace changeset")
    if document.document_id != document_id:
        raise ValueError("workspace review document scope does not match")
    next_display_orders = {
        "/duties": max((item.display_order for item in document.duties), default=-1) + 1,
        "/tasks": max((item.display_order for item in document.tasks), default=-1) + 1,
    }
    for item in document.opks:
        key = f"/opks:{item.kind.value}"
        next_display_orders[key] = max(next_display_orders.get(key, 0), item.display_order + 1)
    action_ids_by_change_ref = {
        change.change_ref: uuid5(document_id, f"{identity_scope}:patch-action:{index}")
        for index, change in enumerate(changes)
        if change.change_ref
    }
    actions: list[DocumentPatchAction] = []
    for index, change in enumerate(changes):
        _ensure_opks_axis_matches_document(change, document)
        order_key: str | None = None
        if change.operation is DocumentChangeOperation.ADD:
            if change.path in {"/duties", "/tasks"} and isinstance(change.after, dict) and change.after.get("display_order") is None:
                order_key = change.path
            elif change.path == "/opks" and change.opks_kind is not None and isinstance(change.after, (str, dict)):
                if isinstance(change.after, str) or change.after.get("display_order") is None:
                    order_key = f"/opks:{change.opks_kind.value}"
        allocated = next_display_orders.get(order_key, 0) if order_key is not None else None
        if order_key is not None:
            next_display_orders[order_key] = allocated + 1
        after = _normalized_after(
            change,
            document_id=document_id,
            identity_scope=identity_scope,
            change_index=index,
            allocated_display_order=allocated,
        )
        operation = DocumentPatchOperation(change.operation.value)
        action = DocumentPatchAction(
            action_id=uuid5(document_id, f"{identity_scope}:patch-action:{index}"),
            operation=operation,
            path=change.path,
            target_key=_target_key(change),
            before=_before_value(document, change),
            after=after,
            source_ids=tuple(sorted(change.basis.source_ids, key=str)),
            quote_anchors=change.basis.quote_anchors,
            read_set=tuple(
                DocumentPathRead(path=path, value_sha256=document_path_sha256(document, path))
                for path in _read_paths(change, after)
            ),
            depends_on_action_ids=tuple(
                sorted(
                    {
                        *(
                            action_ids_by_change_ref[change_ref]
                            for change_ref in change.depends_on_change_refs
                        ),
                        *change.depends_on_action_ids,
                    },
                    key=str,
                )
            ),
            supersedes_action_ids=change.supersedes_action_ids,
            atomic_subgroup_id=(
                uuid5(document_id, f"{identity_scope}:atomic-ref:{change.atomic_group_ref}")
                if change.atomic_group_ref
                else None
            ),
            blocks_dependent_analysis=(
                operation in _STRUCTURAL_OPERATIONS
                or change.path.endswith("/responsibility_role")
            ),
        )
        actions.append(action)
    actions = _link_required_groups(document_id, identity_scope, document, actions)
    try:
        apply_document_actions(document, tuple(actions))
    except DocumentAuthorityError as error:
        raise ValueError(f"workspace changes do not form a valid review state: {error}") from error
    return DocumentChangeSet(
        changeset_id=uuid5(document_id, f"{identity_scope}:document-changes"),
        summary=summary,
        actions=tuple(actions),
        source_ids=tuple(sorted({source_id for action in actions for source_id in action.source_ids}, key=str)),
        created_revision=read_revision,
        external_dependency_action_ids=tuple(dict.fromkeys(external_dependency_action_ids)),
    )


def _action_semantics(action: DocumentPatchAction) -> dict[str, Any]:
    return {
        "operation": action.operation.value,
        "path": action.path,
        "target_key": action.target_key,
        "before": action.before,
        "after": action.after,
    }


def workspace_action_semantic_fingerprint(
    action: DocumentPatchAction,
) -> Sha256Digest:
    """Return stable identity for one unchanged employee-facing semantic edit."""

    return _digest(_action_semantics(action))


def _group_components(
    actions: Sequence[DocumentPatchAction],
) -> tuple[tuple[DocumentPatchAction, ...], ...]:
    by_id = {action.action_id: action for action in actions}
    adjacency = {action.action_id: set() for action in actions}
    atomic_members: dict[UUID, list[UUID]] = {}
    for action in actions:
        for dependency in action.depends_on_action_ids:
            if dependency in by_id:
                adjacency[action.action_id].add(dependency)
                adjacency[dependency].add(action.action_id)
        if action.atomic_subgroup_id is not None:
            atomic_members.setdefault(action.atomic_subgroup_id, []).append(
                action.action_id
            )
    for members in atomic_members.values():
        for member in members[1:]:
            adjacency[members[0]].add(member)
            adjacency[member].add(members[0])

    components: list[tuple[DocumentPatchAction, ...]] = []
    visited: set[UUID] = set()
    for action in actions:
        if action.action_id in visited:
            continue
        pending = [action.action_id]
        member_ids: set[UUID] = set()
        while pending:
            current = pending.pop()
            if current in member_ids:
                continue
            member_ids.add(current)
            pending.extend(adjacency[current] - member_ids)
        visited.update(member_ids)
        components.append(
            tuple(action_item for action_item in actions if action_item.action_id in member_ids)
        )
    return tuple(
        component
        for component in sorted(
            components,
            key=lambda values: min(
                (action.path, action.operation.value, action.target_key)
                for action in values
            ),
        )
    )


def _review_groups(
    provisional: DocumentChangeSet,
    manifest: WorkspaceManifest,
) -> tuple[WorkspaceReviewGroup, ...]:
    components = _group_components(provisional.actions)
    old_to_component = {
        action.action_id: index
        for index, component in enumerate(components)
        for action in component
    }
    group_payloads = [
        [_action_semantics(action) for action in component]
        for component in components
    ]
    group_digests = [_digest(payload) for payload in group_payloads]
    identity_roots = [
        (
            "workspace-review:"
            f"revision={manifest.approved_baseline_revision}:"
            f"generation={manifest.generation}:"
            f"workspace={manifest.resource_digest}:group={group_digest}"
        )
        for group_digest in group_digests
    ]
    new_ids = {
        action.action_id: uuid5(
            provisional.actions[0].action_id,
            f"{identity_roots[component_index]}:action:{action_index}:"
            f"{_digest(_action_semantics(action))}",
        )
        for component_index, component in enumerate(components)
        for action_index, action in enumerate(component)
    }
    groups: list[WorkspaceReviewGroup] = []
    for component_index, component in enumerate(components):
        group_digest = group_digests[component_index]
        identity_root = identity_roots[component_index]
        atomic_ids = {
            subgroup_id: uuid5(
                provisional.changeset_id,
                f"{identity_root}:atomic:"
                + _digest(
                    [
                        _action_semantics(item)
                        for item in component
                        if item.atomic_subgroup_id == subgroup_id
                    ]
                ),
            )
            for subgroup_id in {
                item.atomic_subgroup_id
                for item in component
                if item.atomic_subgroup_id is not None
            }
        }
        actions = tuple(
            action.model_copy(
                update={
                    "action_id": new_ids[action.action_id],
                    "depends_on_action_ids": tuple(
                        sorted(
                            (new_ids[item] for item in action.depends_on_action_ids),
                            key=str,
                        )
                    ),
                    "atomic_subgroup_id": (
                        atomic_ids[action.atomic_subgroup_id]
                        if action.atomic_subgroup_id is not None
                        else None
                    ),
                }
            )
            for action in component
        )
        internal_old_ids = {action.action_id for action in component}
        external_old_ids = {
            dependency
            for action in component
            for dependency in action.depends_on_action_ids
            if dependency not in internal_old_ids
        }
        external_ids = tuple(sorted((new_ids[item] for item in external_old_ids), key=str))
        evidence_payload = [
            {
                "source_ids": sorted(str(item) for item in action.source_ids),
                "quote_anchors": [
                    anchor.model_dump(mode="json") for anchor in action.quote_anchors
                ],
            }
            for action in actions
        ]
        boundary_payload = [
            {
                "path": new_action.path,
                "operation": new_action.operation.value,
                "dependencies": sorted(
                    group_digests[old_to_component[item]]
                    for item in old_action.depends_on_action_ids
                ),
            }
            for old_action, new_action in zip(component, actions, strict=True)
        ]
        source_ids = tuple(
            sorted({item for action in actions for item in action.source_ids}, key=str)
        )
        changeset = DocumentChangeSet(
            changeset_id=uuid5(provisional.changeset_id, f"{identity_root}:changeset"),
            summary="Workspace semantic review",
            actions=actions,
            source_ids=source_ids,
            created_revision=manifest.approved_baseline_revision,
            external_dependency_action_ids=external_ids,
        )
        groups.append(
            WorkspaceReviewGroup(
                changeset=changeset,
                group_digest=group_digest,
                semantic_fingerprint=_digest(group_payloads[component_index]),
                evidence_digest=_digest(evidence_payload),
                employee_request_digest=manifest.evidence_basis_digest,
                boundary_digest=_digest(boundary_payload),
            )
        )
    return tuple(groups)


def _unavailable_diagnostics(
    validation: WorkspacePayloadValidation,
    manifest: WorkspaceManifest,
) -> tuple[WorkspaceDiagnostic, ...]:
    if validation.diagnostics:
        return validation.diagnostics
    if manifest.diagnostics:
        return manifest.diagnostics
    return (
        WorkspaceDiagnostic(
            code="workspace-not-valid",
            path="/workspace",
            message="Workspace review is unavailable until the current files validate.",
            severity=WorkspaceDiagnosticSeverity.ERROR,
        ),
    )


def _rejected_action_ids(
    decision: WorkspaceReviewDecision,
    group: WorkspaceReviewGroup,
) -> set[UUID]:
    if (
        decision.kind is not WorkspaceReviewDecisionKind.REJECT
        or decision.semantic_fingerprint != group.semantic_fingerprint
        or decision.evidence_digest != group.evidence_digest
        or decision.boundary_digest != group.boundary_digest
    ):
        return set()
    selected_fingerprints = set(decision.selected_action_fingerprints)
    if selected_fingerprints:
        return {
            action.action_id
            for action in group.actions
            if workspace_action_semantic_fingerprint(action) in selected_fingerprints
        }
    selected_ids = set(decision.selected_action_ids)
    return selected_ids & {action.action_id for action in group.actions}


def _conflict_affects_action(
    conflict_path: str,
    action: DocumentPatchAction,
    entity_ids_by_handle: Mapping[str, UUID],
) -> bool:
    """Match a Store resource diagnostic to the semantic action it affects."""

    parts = action.path.strip("/").split("/")
    if not parts or not parts[0]:
        return False
    if parts[0] not in {"duties", "tasks", "opks"}:
        if conflict_path == "/workspace/header.json":
            return True
        expected = f"/workspace/header.json/{parts[0]}"
        return conflict_path == expected or conflict_path.startswith(f"{expected}/")
    identity: UUID | None = None
    if action.operation.value == "add" and isinstance(action.after, dict):
        field = {"duties": "duty_id", "tasks": "task_id", "opks": "item_id"}[parts[0]]
        raw_identity = action.after.get(field)
        if raw_identity is not None:
            try:
                identity = UUID(str(raw_identity))
            except ValueError:
                return False
    elif len(parts) >= 2:
        try:
            identity = UUID(parts[1])
        except ValueError:
            return False
    if identity is None:
        return False
    handle = next(
        (handle for handle, stable_id in entity_ids_by_handle.items() if stable_id == identity),
        None,
    )
    if handle is None:
        return False
    resource_marker = f"/{handle}.json"
    marker_index = conflict_path.find(resource_marker)
    if marker_index < 0:
        return False
    if len(parts) < 3:
        return True
    suffix = conflict_path[marker_index:]
    if suffix == resource_marker:
        return True
    workspace_field = {
        "duty_id": "duty_handle",
        "task_ids": "task_handles",
        "indicator_ids": "indicator_handles",
    }.get(parts[2], parts[2])
    expected = f"{resource_marker}/{workspace_field}"
    return suffix == expected or suffix.startswith(f"{expected}/")


def derive_workspace_review(
    approved: ApprovedJobDocument,
    valid_workspace: WorkspacePayloadValidation,
    manifest: WorkspaceManifest,
    decisions: Sequence[WorkspaceReviewDecision],
) -> WorkspaceReviewProjection:
    """Derive review bundles from one validated after-state without persistence."""

    if (
        manifest.validation_status
        not in {
            WorkspaceValidationStatus.VALID,
            WorkspaceValidationStatus.CONFLICTED,
        }
        or valid_workspace.document is None
    ):
        return WorkspaceReviewProjection(
            workspace_digest=manifest.resource_digest,
            diagnostics=_unavailable_diagnostics(valid_workspace, manifest),
            entity_ids_by_handle=manifest.entity_ids_by_handle,
        )
    if approved.document_id != valid_workspace.document.approved_document.document_id:
        raise ValueError("workspace review document scope does not match")
    if evidence_basis_digest(valid_workspace.current_sources) != (
        manifest.evidence_basis_digest
    ):
        return WorkspaceReviewProjection(
            workspace_digest=manifest.resource_digest,
            diagnostics=(
                WorkspaceDiagnostic(
                    code="evidence-basis-stale",
                    path="/workspace",
                    message="Workspace review Evidence changed since the last validation.",
                ),
            ),
            entity_ids_by_handle=manifest.entity_ids_by_handle,
        )
    if manifest.approved_baseline_digest != approved_document_digest(approved):
        return WorkspaceReviewProjection(
            workspace_digest=manifest.resource_digest,
            diagnostics=(
                WorkspaceDiagnostic(
                    code="approved-baseline-stale",
                    path="/approved",
                    message=(
                        "Workspace review baseline no longer matches the approved document."
                    ),
                ),
            ),
            entity_ids_by_handle=manifest.entity_ids_by_handle,
        )
    if valid_workspace.default_basis is None:
        return WorkspaceReviewProjection(
            workspace_digest=manifest.resource_digest,
            diagnostics=(
                WorkspaceDiagnostic(
                    code="evidence-basis-empty",
                    path="/workspace",
                    message="Workspace review requires a validated employee Evidence basis.",
                ),
            ),
            entity_ids_by_handle=manifest.entity_ids_by_handle,
        )
    handles_by_id = {
        stable_id: handle for handle, stable_id in manifest.entity_ids_by_handle.items()
    }
    changes = derive_semantic_changes(
        baseline=approved,
        working_document=valid_workspace.document.approved_document,
        workspace_handles=handles_by_id,
        evidence=valid_workspace.evidence_by_handle,
        default_basis=valid_workspace.default_basis,
    )
    if not changes:
        return WorkspaceReviewProjection(
            workspace_digest=manifest.resource_digest,
            entity_ids_by_handle=manifest.entity_ids_by_handle,
        )
    provisional = create_workspace_changeset(
        document_id=approved.document_id,
        summary="Workspace semantic review",
        read_revision=manifest.approved_baseline_revision,
        document=approved,
        changes=changes,
        identity_scope=(
            "consultant:workspace-review:"
            f"revision={manifest.approved_baseline_revision}:"
            f"generation={manifest.generation}:"
            f"workspace={manifest.resource_digest}"
        ),
    )
    groups = _review_groups(provisional, manifest)
    diagnostics: list[WorkspaceDiagnostic] = []
    projected: list[WorkspaceReviewGroup] = []
    localized_diagnostics = tuple(
        dict.fromkeys((*valid_workspace.diagnostics, *manifest.diagnostics))
    )
    matched_diagnostics: set[WorkspaceDiagnostic] = set()
    for group in groups:
        group_conflicts = tuple(
            diagnostic
            for diagnostic in localized_diagnostics
            if any(
                _conflict_affects_action(
                    diagnostic.path,
                    action,
                    manifest.entity_ids_by_handle,
                )
                for action in group.actions
            )
        )
        if group_conflicts:
            group = replace(group, diagnostics=group_conflicts)
            matched_diagnostics.update(group_conflicts)
        rejected_action_ids = set().union(
            *(
                _rejected_action_ids(decision, group)
                for decision in decisions
            )
        )
        if rejected_action_ids:
            diagnostics.append(
                WorkspaceDiagnostic(
                    code="rejected-semantic-change",
                    path=next(
                        action.path
                        for action in group.changeset.actions
                        if action.action_id in rejected_action_ids
                    ),
                    message=(
                        "This unchanged semantic proposal remains rejected; add new "
                        "employee Evidence or change its work boundary before review."
                    ),
                    severity=WorkspaceDiagnosticSeverity.WARNING,
                )
            )
            remaining_actions = tuple(
                action
                for action in group.changeset.actions
                if action.action_id not in rejected_action_ids
            )
            if not remaining_actions:
                continue
            group = replace(
                group,
                changeset=group.changeset.model_copy(
                    update={
                        "actions": remaining_actions,
                        "source_ids": tuple(
                            sorted(
                                {
                                    source_id
                                    for action in remaining_actions
                                    for source_id in action.source_ids
                                },
                                key=str,
                            )
                        ),
                    }
                ),
            )
        projected.append(group)
    diagnostics.extend(
        diagnostic
        for diagnostic in localized_diagnostics
        if diagnostic not in matched_diagnostics
    )
    return WorkspaceReviewProjection(
        workspace_digest=manifest.resource_digest,
        groups=tuple(projected),
        diagnostics=tuple(diagnostics),
        entity_ids_by_handle=manifest.entity_ids_by_handle,
    )


def workspace_review_files(projection: WorkspaceReviewProjection) -> dict[str, str]:
    """Serialize the ephemeral review projection into mount-relative JSON files."""

    handle_by_id = {
        stable_id: handle
        for handle, stable_id in projection.entity_ids_by_handle.items()
    }

    scalar_id_fields = {"duty_id", "task_id", "item_id"}
    sequence_id_fields = {"task_ids", "indicator_ids"}

    def semantic_identifier(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return handle_by_id.get(UUID(value), value)
            except ValueError:
                return value
        return value

    def semantic_value(value: Any, *, field_name: str | None = None) -> Any:
        if field_name in scalar_id_fields:
            return semantic_identifier(value)
        if field_name in sequence_id_fields and isinstance(value, list):
            return [semantic_identifier(item) for item in value]
        if isinstance(value, list):
            return [semantic_value(item) for item in value]
        if isinstance(value, dict):
            return {
                key: semantic_value(item, field_name=key)
                for key, item in value.items()
            }
        return value

    def semantic_path(path: str) -> str:
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            try:
                parts[1] = handle_by_id.get(UUID(parts[1]), parts[1])
            except ValueError:
                pass
        return "/" + "/".join(parts)

    group_handles = {
        group.changeset.changeset_id: f"group-{index:03d}"
        for index, group in enumerate(projection.groups, start=1)
    }
    all_diagnostics = tuple(
        (*projection.diagnostics,)
        + tuple(
            diagnostic
            for group in projection.groups
            for diagnostic in group.diagnostics
        )
    )
    files = {
        "/index.json": json.dumps(
            {
                "workspace_digest": projection.workspace_digest,
                "group_handles": list(group_handles.values()),
                "diagnostic_count": len(all_diagnostics),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    }
    for group in projection.groups:
        handle = group_handles[group.changeset.changeset_id]
        files[f"/groups/{handle}.json"] = (
            json.dumps(
                {
                    "handle": handle,
                    "group_digest": group.group_digest,
                    "summary": group.changeset.summary,
                    "actions": [
                        {
                            "action_id": str(action.action_id),
                            "operation": action.operation.value,
                            "path": semantic_path(action.path),
                            "before": semantic_value(
                                action.before,
                                field_name=action.path.rstrip("/").rsplit("/", 1)[-1],
                            ),
                            "after": semantic_value(
                                action.after,
                                field_name=action.path.rstrip("/").rsplit("/", 1)[-1],
                            ),
                            "status": action.status.value,
                            "atomic_subgroup_id": (
                                str(action.atomic_subgroup_id)
                                if action.atomic_subgroup_id is not None
                                else None
                            ),
                            "evidence_quotes": [
                                anchor.quote for anchor in action.quote_anchors
                            ],
                        }
                        for action in group.actions
                    ],
                    "diagnostics": [
                        diagnostic.model_dump(mode="json")
                        for diagnostic in group.diagnostics
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
    for index, diagnostic in enumerate(all_diagnostics, start=1):
        files[f"/diagnostics/diagnostic-{index:03d}.json"] = (
            json.dumps(diagnostic.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n"
        )
    return files
