"""Employee-facing semantic review derived from approved and workspace state.

The workspace remains a non-authoritative draft.  This module creates an
ephemeral review projection; it never writes the workspace, review queue, or
approved document.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, cast
from uuid import UUID, uuid5

from pydantic import JsonValue

from app.consultant.document_review import create_document_changeset
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
    DocumentPatchAction,
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


class WorkspaceReviewDecisionKind(StrEnum):
    DEFER = "defer"
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

    @classmethod
    def from_group(
        cls,
        kind: WorkspaceReviewDecisionKind,
        group: WorkspaceReviewGroup,
        *,
        workspace_digest: Sha256Digest,
    ) -> WorkspaceReviewDecision:
        return cls(
            kind=kind,
            workspace_digest=workspace_digest,
            group_digest=group.group_digest,
            semantic_fingerprint=group.semantic_fingerprint,
            evidence_digest=group.evidence_digest,
            employee_request_digest=group.employee_request_digest,
            boundary_digest=group.boundary_digest,
        )


@dataclass(frozen=True, slots=True)
class WorkspaceReviewGroup:
    changeset: DocumentChangeSet
    group_digest: Sha256Digest
    semantic_fingerprint: Sha256Digest
    evidence_digest: Sha256Digest
    employee_request_digest: Sha256Digest
    boundary_digest: Sha256Digest

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
    candidate: ApprovedJobDocument,
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
        ("duties", candidate.duties, baseline_duties),
        ("tasks", candidate.tasks, baseline_tasks),
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
                for item in candidate.opks
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


def _opks_basis(
    *,
    item: ApprovedOpksItem,
    handle: str,
    bindings: Mapping[str, tuple[AnalysisBasis, ...]],
    default: AnalysisBasis,
    changed: bool,
) -> AnalysisBasis:
    if not changed:
        return default
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


def derive_semantic_changes(
    *,
    baseline: ApprovedJobDocument,
    candidate: ApprovedJobDocument,
    candidate_handles: Mapping[UUID, str],
    evidence: Mapping[str, tuple[AnalysisBasis, ...]],
    default_basis: AnalysisBasis,
) -> tuple[ReviewableDocumentChange, ...]:
    """Return canonical semantic changes; formatting and key order are absent."""

    baseline_duties, baseline_tasks, baseline_opks = _entity_maps(baseline)
    candidate_duties, candidate_tasks, candidate_opks = _entity_maps(candidate)
    changes: list[ReviewableDocumentChange] = []

    def add(**kwargs: Any) -> None:
        changes.append(
            _new_change(change_ref=f"workspace-{len(changes) + 1:03d}", **kwargs)
        )

    baseline_header = baseline.model_dump(mode="json")
    candidate_header = candidate.model_dump(mode="json")
    for field in _HEADER_FIELDS:
        if baseline_header[field] != candidate_header[field]:
            add(
                operation=DocumentChangeOperation.REVISE,
                path=f"/{field}",
                after=candidate_header[field],
                basis=default_basis,
            )

    orders = _next_orders(baseline, candidate)
    for identity in sorted(set(baseline_duties) - set(candidate_duties), key=str):
        add(
            operation=DocumentChangeOperation.WITHDRAW,
            path=f"/duties/{identity}",
            basis=default_basis,
        )
    for identity in sorted(set(candidate_duties) - set(baseline_duties), key=str):
        add(
            operation=DocumentChangeOperation.ADD,
            path="/duties",
            after=_normalized_entity_after(
                candidate_duties[identity], baseline=baseline, orders=orders
            ),
            basis=default_basis,
        )
    for identity in sorted(set(baseline_duties) & set(candidate_duties), key=str):
        before, after = (
            _model_json(baseline_duties[identity]),
            _model_json(candidate_duties[identity]),
        )
        for field in _DUTY_FIELDS:
            if before[field] != after[field]:
                add(
                    operation=DocumentChangeOperation.REVISE,
                    path=f"/duties/{identity}/{field}",
                    after=after[field],
                    basis=default_basis,
                )
        if before["display_order"] != after["display_order"]:
            add(
                operation=DocumentChangeOperation.REORDER,
                path=f"/duties/{identity}/display_order",
                after=after["display_order"],
                basis=default_basis,
            )

    for identity in sorted(set(baseline_tasks) - set(candidate_tasks), key=str):
        add(
            operation=DocumentChangeOperation.WITHDRAW,
            path=f"/tasks/{identity}",
            basis=default_basis,
        )
    for identity in sorted(set(candidate_tasks) - set(baseline_tasks), key=str):
        add(
            operation=DocumentChangeOperation.ADD,
            path="/tasks",
            after=_normalized_entity_after(
                candidate_tasks[identity], baseline=baseline, orders=orders
            ),
            basis=default_basis,
        )
    for identity in sorted(set(baseline_tasks) & set(candidate_tasks), key=str):
        before, after = (
            _model_json(baseline_tasks[identity]),
            _model_json(candidate_tasks[identity]),
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
                basis=default_basis,
            )
        if before["display_order"] != after["display_order"]:
            add(
                operation=DocumentChangeOperation.REORDER,
                path=f"/tasks/{identity}/display_order",
                after=after["display_order"],
                basis=default_basis,
            )

    for identity in sorted(set(baseline_opks) - set(candidate_opks), key=str):
        item = baseline_opks[identity]
        if item.kind in _EDITABLE_OPKS_KINDS:
            add(
                operation=DocumentChangeOperation.WITHDRAW,
                path=f"/opks/{identity}",
                basis=default_basis,
                opks_kind=OpksKind(item.kind.value),
            )
    for identity in sorted(set(candidate_opks) - set(baseline_opks), key=str):
        item = candidate_opks[identity]
        if item.kind not in _EDITABLE_OPKS_KINDS:
            continue
        basis = _opks_basis(
            item=item,
            handle=candidate_handles.get(identity, ""),
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
    for identity in sorted(set(baseline_opks) & set(candidate_opks), key=str):
        before_item, after_item = baseline_opks[identity], candidate_opks[identity]
        if before_item.kind not in _EDITABLE_OPKS_KINDS:
            continue
        before, after = _model_json(before_item), _model_json(after_item)
        changed = any(before[field] != after[field] for field in _OPKS_FIELDS)
        basis = _opks_basis(
            item=after_item,
            handle=candidate_handles.get(identity, ""),
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


def _action_semantics(action: DocumentPatchAction) -> dict[str, Any]:
    return {
        "operation": action.operation.value,
        "path": action.path,
        "target_key": action.target_key,
        "before": action.before,
        "after": action.after,
        "target_ids": sorted(str(item) for item in action.target_ids),
    }


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
            tuple(candidate for candidate in actions if candidate.action_id in member_ids)
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


def _matches_rejection(
    decision: WorkspaceReviewDecision,
    group: WorkspaceReviewGroup,
) -> bool:
    return (
        decision.kind is WorkspaceReviewDecisionKind.REJECT
        and decision.semantic_fingerprint == group.semantic_fingerprint
        and decision.evidence_digest == group.evidence_digest
        and decision.employee_request_digest == group.employee_request_digest
        and decision.boundary_digest == group.boundary_digest
    )


def derive_workspace_review(
    approved: ApprovedJobDocument,
    valid_workspace: WorkspacePayloadValidation,
    manifest: WorkspaceManifest,
    decisions: Sequence[WorkspaceReviewDecision],
) -> WorkspaceReviewProjection:
    """Derive review bundles from one validated after-state without persistence."""

    if (
        manifest.validation_status is not WorkspaceValidationStatus.VALID
        or valid_workspace.document is None
        or valid_workspace.diagnostics
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
        candidate=valid_workspace.document.approved_document,
        candidate_handles=handles_by_id,
        evidence=valid_workspace.evidence_by_handle,
        default_basis=valid_workspace.default_basis,
    )
    if not changes:
        return WorkspaceReviewProjection(
            workspace_digest=manifest.resource_digest,
            entity_ids_by_handle=manifest.entity_ids_by_handle,
        )
    provisional_run = uuid5(
        approved.document_id,
        "workspace-review-provisional:"
        f"{manifest.approved_baseline_revision}:"
        f"{manifest.generation}:{manifest.resource_digest}",
    )
    provisional = create_document_changeset(
        document_id=approved.document_id,
        run_id=provisional_run,
        summary="Workspace semantic review",
        read_revision=manifest.approved_baseline_revision,
        document=approved,
        changes=changes,
        existing_review_queue={},
        interview_work={},
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
    for group in groups:
        if any(_matches_rejection(decision, group) for decision in decisions):
            diagnostics.append(
                WorkspaceDiagnostic(
                    code="rejected-semantic-change",
                    path=group.changeset.actions[0].path,
                    message=(
                        "This unchanged semantic proposal remains rejected; add new "
                        "employee Evidence or change its work boundary before review."
                    ),
                    severity=WorkspaceDiagnosticSeverity.WARNING,
                )
            )
            continue
        deferred = any(
            decision.kind is WorkspaceReviewDecisionKind.DEFER
            and decision.workspace_digest == manifest.resource_digest
            and decision.group_digest == group.group_digest
            for decision in decisions
        )
        if deferred:
            group = WorkspaceReviewGroup(
                changeset=group.changeset.model_copy(
                    update={
                        "actions": tuple(
                            action.model_copy(
                                update={"status": DocumentChangeStatus.DEFERRED}
                            )
                            for action in group.changeset.actions
                        )
                    }
                ),
                group_digest=group.group_digest,
                semantic_fingerprint=group.semantic_fingerprint,
                evidence_digest=group.evidence_digest,
                employee_request_digest=group.employee_request_digest,
                boundary_digest=group.boundary_digest,
            )
        projected.append(group)
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
    files = {
        "/index.json": json.dumps(
            {
                "workspace_digest": projection.workspace_digest,
                "group_handles": list(group_handles.values()),
                "diagnostic_count": len(projection.diagnostics),
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
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
    for index, diagnostic in enumerate(projection.diagnostics, start=1):
        files[f"/diagnostics/diagnostic-{index:03d}.json"] = (
            json.dumps(diagnostic.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n"
        )
    return files
