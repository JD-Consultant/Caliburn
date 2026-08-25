"""Employee authority over one validated Store-backed JD workspace."""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
import json
from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID, uuid5

from pydantic import Field, JsonValue, StringConstraints, model_validator
from typing_extensions import Annotated

from app.consultant.document_authority import (
    DocumentAuthorityError,
    apply_document_actions,
    edited_action_source_payload,
)
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS
from app.consultant.state import (
    DocumentPatchAction,
    DocumentPatchOperation,
    DurableModel,
)
from app.consultant.state import (
    ApprovedJobDocument,
    CommandReceipt,
    EmployeeSource,
    EmployeeSourceKind,
    SourceReference,
    SourceProcessingStatus,
    inspect_command_receipt,
)
from app.consultant.views import ConsultantSnapshot
from app.consultant.workspace_resources import WorkspaceCatalog, project_workspace_files
from app.consultant.workspace_review import (
    WorkspaceReviewDecision,
    WorkspaceReviewDecisionKind,
    WorkspaceReviewGroup,
    WorkspaceReviewProjection,
    derive_workspace_review,
    workspace_action_semantic_fingerprint,
)
from app.consultant.workspace_state import (
    Sha256Digest,
    StoreBackedWorkspace,
    WorkspaceDiagnostic,
    WorkspaceDiagnosticSeverity,
    WorkspaceManifest,
    WorkspaceSnapshot,
    WorkspaceValidationStatus,
    approved_document_digest,
    workspace_resource_digest,
)
from app.consultant.workspace_validation import (
    active_conflict_diagnostics,
    evidence_basis_digest,
    validate_workspace_payload,
)


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class WorkspaceAuthorityError(ValueError):
    """The employee command is stale, incomplete, or structurally unsafe."""


class WorkspaceDecisionKind(StrEnum):
    ACCEPT = "accept"
    EDIT_ACCEPT = "edit_and_accept"
    REJECT = "reject"
    DEFER = "defer"


class WorkspaceReviewCommand(DurableModel):
    command_id: UUID
    document_id: UUID
    decision: WorkspaceDecisionKind
    approved_revision: int = Field(ge=0)
    workspace_generation: int = Field(ge=0)
    workspace_digest: Sha256Digest
    changeset_id: UUID
    group_digest: Sha256Digest | None = None
    selected_action_ids: tuple[UUID, ...] = Field(min_length=1)
    edited_after_by_action_id: dict[UUID, JsonValue | None] = Field(
        default_factory=dict
    )
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def command_shape_matches_decision(self) -> WorkspaceReviewCommand:
        if len(self.selected_action_ids) != len(set(self.selected_action_ids)):
            raise ValueError("workspace command requires unique action IDs")
        selected = set(self.selected_action_ids)
        if not set(self.edited_after_by_action_id) <= selected:
            raise ValueError("employee edits include an unselected action")
        if self.decision is WorkspaceDecisionKind.EDIT_ACCEPT:
            if not self.edited_after_by_action_id:
                raise ValueError("edit-and-accept requires an employee edit")
        elif self.edited_after_by_action_id:
            raise ValueError("only edit-and-accept may carry employee edits")
        if self.decision is WorkspaceDecisionKind.REJECT and self.reason is None:
            raise ValueError("reject requires an employee reason")
        return self

    def payload_digest(self) -> Sha256Digest:
        payload = self.model_dump(mode="json", exclude={"command_id"})
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return cast(Sha256Digest, sha256(encoded).hexdigest())


class WorkspaceDecisionStatus(StrEnum):
    PLANNED = "planned"
    AUTHORITY_COMMITTED = "authority_committed"
    COMPLETED = "completed"


class WorkspaceDecisionRecord(DurableModel):
    command_id: UUID
    payload_digest: Sha256Digest
    decision: WorkspaceDecisionKind
    changeset_id: UUID
    selected_action_ids: tuple[UUID, ...]
    selected_action_fingerprints: tuple[Sha256Digest, ...] = ()
    workspace_digest: Sha256Digest
    group_digest: Sha256Digest
    semantic_fingerprint: Sha256Digest
    evidence_digest: Sha256Digest
    employee_request_digest: Sha256Digest
    boundary_digest: Sha256Digest
    approved_revision: int = Field(default=0, ge=0)
    workspace_generation: int = Field(default=0, ge=0)
    employee_source_id: UUID | None = None
    result_workspace_digest: Sha256Digest | None = None
    reason: NonEmptyText | None = None
    status: WorkspaceDecisionStatus = WorkspaceDecisionStatus.PLANNED


class WorkspaceResourceChange(DurableModel):
    path: NonEmptyText
    before: str | None = None
    after: str | None = None


class WorkspaceRebasePlan(DurableModel):
    command_id: UUID
    expected_workspace_digest: Sha256Digest
    approved_revision: int = Field(ge=0)
    approved_digest: Sha256Digest
    changes: tuple[WorkspaceResourceChange, ...] = ()
    conflicted_paths: tuple[NonEmptyText, ...] = ()
    entity_ids_by_handle: dict[str, UUID] = Field(default_factory=dict)
    employee_source_id: UUID | None = None
    result_workspace_digest: Sha256Digest | None = None


_MISSING = object()


def _pointer_segment(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _three_way_value(
    old: Any,
    working: Any,
    new: Any,
    *,
    path: str,
    conflicts: list[str],
    employee_override_paths: frozenset[str],
) -> Any:
    if path in employee_override_paths:
        return new
    forced_descendant = any(
        candidate.startswith(f"{path}/")
        for candidate in employee_override_paths
    )
    if forced_descendant and all(
        value is not _MISSING and isinstance(value, dict)
        for value in (old, working, new)
    ):
        result: dict[str, Any] = {}
        for key in sorted(set(old) | set(working) | set(new)):
            merged = _three_way_value(
                old.get(key, _MISSING),
                working.get(key, _MISSING),
                new.get(key, _MISSING),
                path=f"{path}/{_pointer_segment(key)}",
                conflicts=conflicts,
                employee_override_paths=employee_override_paths,
            )
            if merged is not _MISSING:
                result[key] = merged
        return result
    if working == old:
        return new
    if new == old or working == new:
        return working
    if all(value is not _MISSING and isinstance(value, dict) for value in (old, working, new)):
        result: dict[str, Any] = {}
        for key in sorted(set(old) | set(working) | set(new)):
            merged = _three_way_value(
                old.get(key, _MISSING),
                working.get(key, _MISSING),
                new.get(key, _MISSING),
                path=f"{path}/{_pointer_segment(key)}",
                conflicts=conflicts,
                employee_override_paths=employee_override_paths,
            )
            if merged is not _MISSING:
                result[key] = merged
        return result
    conflicts.append(path)
    return working


def _parse_resource(raw: str | object) -> Any:
    if raw is _MISSING:
        return _MISSING
    try:
        return json.loads(cast(str, raw))
    except json.JSONDecodeError:
        return raw


def _render_resource(value: Any, *, original: str | object) -> str | None:
    if value is _MISSING:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if original is not _MISSING and not isinstance(_parse_resource(original), (dict, list)):
        return cast(str, value)
    return json.dumps(value, ensure_ascii=False) + "\n"


def _path_is_within(path: str, parent: str) -> bool:
    return path == parent or path.startswith(f"{parent.rstrip('/')}/")


def build_workspace_rebase_plan(
    *,
    command_id: UUID,
    old_approved_files: Mapping[str, str],
    workspace_files: Mapping[str, str],
    new_approved_files: Mapping[str, str],
    approved_revision: int,
    approved_digest: Sha256Digest,
    employee_override_paths: Sequence[str] = (),
    resolved_workspace_paths: Sequence[str] = (),
) -> WorkspaceRebasePlan:
    """Compute a deterministic per-resource three-way rebase before authority."""

    changes: list[WorkspaceResourceChange] = []
    conflicts: list[str] = []
    rebased_files: dict[str, str] = {}
    forced_paths = frozenset(employee_override_paths)
    resolved_paths = frozenset(resolved_workspace_paths)
    paths = sorted(
        set(old_approved_files) | set(workspace_files) | set(new_approved_files)
    )
    for resource_path in paths:
        old_raw = old_approved_files.get(resource_path, _MISSING)
        working_raw = workspace_files.get(resource_path, _MISSING)
        new_raw = new_approved_files.get(resource_path, _MISSING)
        working_value = _parse_resource(working_raw)
        merged = _three_way_value(
            _parse_resource(old_raw),
            working_value,
            _parse_resource(new_raw),
            path=resource_path,
            conflicts=conflicts,
            employee_override_paths=forced_paths,
        )
        rendered = (
            cast(str, working_raw)
            if working_raw is not _MISSING and merged == working_value
            else _render_resource(merged, original=working_raw)
        )
        before = None if working_raw is _MISSING else cast(str, working_raw)
        if rendered is not None:
            rebased_files[resource_path] = rendered
        if rendered != before:
            changes.append(
                WorkspaceResourceChange(
                    path=resource_path,
                    before=before,
                    after=rendered,
                )
            )
    return WorkspaceRebasePlan(
        command_id=command_id,
        expected_workspace_digest=workspace_resource_digest(workspace_files),
        approved_revision=approved_revision,
        approved_digest=approved_digest,
        changes=tuple(changes),
        conflicted_paths=tuple(
            dict.fromkeys(
                path
                for path in conflicts
                if not any(
                    _path_is_within(path, resolved_path)
                    for resolved_path in resolved_paths
                )
            )
        ),
        result_workspace_digest=workspace_resource_digest(rebased_files),
    )


def _group_for_command(
    projection: WorkspaceReviewProjection,
    command: WorkspaceReviewCommand,
):
    matches = [
        group
        for group in projection.groups
        if group.changeset.changeset_id == command.changeset_id
    ]
    if len(matches) != 1:
        raise WorkspaceAuthorityError(
            f"workspace changeset {command.changeset_id} is stale"
        )
    return matches[0]


def select_workspace_actions(
    projection: WorkspaceReviewProjection,
    command: WorkspaceReviewCommand,
) -> tuple[DocumentPatchAction, ...]:
    """Resolve selected actions without treating a visual group as atomic."""

    group = _group_for_command(projection, command)
    general_operations = {
        DocumentPatchOperation.ADD,
        DocumentPatchOperation.REVISE,
        DocumentPatchOperation.WITHDRAW,
        DocumentPatchOperation.REASSIGN,
        DocumentPatchOperation.REORDER,
    }
    unsupported = [
        action.operation.value
        for action in group.actions
        if action.operation not in general_operations
    ]
    if unsupported:
        raise WorkspaceAuthorityError(
            "workspace review contains an unsupported legacy operation: "
            + ", ".join(sorted(set(unsupported)))
        )
    conflict_diagnostics = tuple(
        diagnostic
        for diagnostic in getattr(group, "diagnostics", ())
        if diagnostic.severity is WorkspaceDiagnosticSeverity.ERROR
    )
    if conflict_diagnostics and command.decision in {
        WorkspaceDecisionKind.ACCEPT,
        WorkspaceDecisionKind.EDIT_ACCEPT,
    }:
        blocker = (
            "a rebase conflict"
            if any(
                diagnostic.code == "workspace-rebase-conflict"
                for diagnostic in conflict_diagnostics
            )
            else "a diagnostic"
        )
        raise WorkspaceAuthorityError(
            f"workspace changeset {group.changeset.changeset_id} is blocked by {blocker}"
        )
    by_id = {action.action_id: action for action in group.actions}
    all_actions = {
        action.action_id: action
        for candidate_group in projection.groups
        for action in candidate_group.actions
    }
    selected_ids = set(command.selected_action_ids)
    unknown = selected_ids - set(by_id)
    if unknown:
        raise WorkspaceAuthorityError(
            "workspace command references stale actions: "
            + ", ".join(sorted(map(str, unknown)))
        )
    selected = tuple(
        action for action in group.actions if action.action_id in selected_ids
    )

    for action in selected:
        subgroup = action.atomic_subgroup_id
        if subgroup is None:
            continue
        unresolved = {
            candidate.action_id
            for candidate in group.actions
            if candidate.atomic_subgroup_id == subgroup
        }
        if not unresolved <= selected_ids:
            raise WorkspaceAuthorityError(
                f"atomic subgroup {subgroup} must be decided together"
            )

    if command.decision in {
        WorkspaceDecisionKind.ACCEPT,
        WorkspaceDecisionKind.EDIT_ACCEPT,
    }:
        for action in selected:
            missing = {
                dependency
                for dependency in action.depends_on_action_ids
                if dependency in all_actions and dependency not in selected_ids
            }
            missing.update(
                dependency
                for dependency in action.depends_on_action_ids
                if dependency not in all_actions and dependency not in selected_ids
            )
            if missing:
                raise WorkspaceAuthorityError(
                    f"action {action.action_id} depends on "
                    + ", ".join(sorted(map(str, missing)))
                )
    elif command.decision is WorkspaceDecisionKind.REJECT:
        for action in all_actions.values():
            if action.action_id in selected_ids:
                continue
            rejected_dependencies = set(action.depends_on_action_ids) & selected_ids
            if rejected_dependencies:
                raise WorkspaceAuthorityError(
                    f"rejecting prerequisite leaves dependent {action.action_id}"
                )
    return selected


_WORKSPACE_FIELD_NAMES = {
    "duty_id": "duty_handle",
    "task_ids": "task_handles",
    "indicator_ids": "indicator_handles",
}
_COLLECTION_ID_FIELDS = {
    "duties": "duty_id",
    "tasks": "task_id",
    "opks": "item_id",
}


def workspace_path_for_action(
    action: DocumentPatchAction,
    *,
    files: Mapping[str, str],
    entity_ids_by_handle: Mapping[str, UUID],
) -> str | None:
    """Translate one general document action to its canonical workspace path."""

    parts = action.path.strip("/").split("/")
    if not parts or not parts[0]:
        return None
    if parts[0] not in _COLLECTION_ID_FIELDS:
        path = "/workspace/header.json"
        return f"{path}/{parts[0]}" if len(parts) == 1 else path

    collection = parts[0]
    identity: UUID | None = None
    if action.operation is DocumentPatchOperation.ADD and isinstance(action.after, dict):
        raw_identity = action.after.get(_COLLECTION_ID_FIELDS[collection])
        if raw_identity is not None:
            try:
                identity = UUID(str(raw_identity))
            except ValueError:
                return None
    elif len(parts) >= 2:
        try:
            identity = UUID(parts[1])
        except ValueError:
            return None
    if identity is None:
        return None
    handle = next(
        (candidate for candidate, stable_id in entity_ids_by_handle.items() if stable_id == identity),
        None,
    )
    if handle is None:
        return None
    suffix = f"/{handle}.json"
    resource_path = next((path for path in sorted(files) if path.endswith(suffix)), None)
    if resource_path is None:
        return None
    if len(parts) < 3:
        return resource_path
    field = _WORKSPACE_FIELD_NAMES.get(parts[2], parts[2])
    return f"{resource_path}/{field}"


class WorkspaceAuthorityService:
    """Apply employee decisions against one locked, Store-backed workspace."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    @staticmethod
    def _command_kind(decision: WorkspaceDecisionKind) -> str:
        return f"workspace_review_{decision.value}"

    @staticmethod
    def _plan_key(command_id: UUID) -> str:
        return f"rebase:{command_id}"

    @staticmethod
    def _direct_plan_key(command_id: UUID) -> str:
        return f"direct-rebase:{command_id}"

    @staticmethod
    def _employee_source_id(document_id: UUID, command_id: UUID) -> UUID:
        return uuid5(document_id, f"workspace-review-direct-edit:{command_id}")

    async def _load_record(
        self,
        document_id: UUID,
        command_id: UUID,
    ) -> WorkspaceDecisionRecord | None:
        item = await self.runtime.store.aget(
            self.runtime.workspace_decision_namespace(document_id),
            str(command_id),
        )
        if item is None:
            return None
        return WorkspaceDecisionRecord.model_validate(item.value)

    async def _load_records(
        self,
        document_id: UUID,
    ) -> tuple[WorkspaceDecisionRecord, ...]:
        items = await self.runtime.store.asearch(
            self.runtime.workspace_decision_namespace(document_id),
            limit=1000,
        )
        records = [WorkspaceDecisionRecord.model_validate(item.value) for item in items]
        return tuple(sorted(records, key=lambda item: str(item.command_id)))

    async def review_decisions(
        self,
        document_id: UUID,
    ) -> tuple[WorkspaceReviewDecision, ...]:
        return self._projection_decisions(await self._load_records(document_id))

    async def _put_record(self, document_id: UUID, record: WorkspaceDecisionRecord) -> None:
        await self.runtime.store.aput(
            self.runtime.workspace_decision_namespace(document_id),
            str(record.command_id),
            record.model_dump(mode="json"),
            index=False,
        )

    async def _load_plan(
        self,
        document_id: UUID,
        command_id: UUID,
    ) -> WorkspaceRebasePlan | None:
        item = await self.runtime.store.aget(
            self.runtime.workspace_metadata_namespace(document_id),
            self._plan_key(command_id),
        )
        if item is None:
            return None
        return WorkspaceRebasePlan.model_validate(item.value["plan"])

    async def _put_plan(self, document_id: UUID, plan: WorkspaceRebasePlan) -> None:
        await self.runtime.store.aput(
            self.runtime.workspace_metadata_namespace(document_id),
            self._plan_key(plan.command_id),
            {"plan": plan.model_dump(mode="json")},
            index=False,
        )

    async def _delete_plan(self, document_id: UUID, command_id: UUID) -> None:
        await self.runtime.store.adelete(
            self.runtime.workspace_metadata_namespace(document_id),
            self._plan_key(command_id),
        )

    async def _load_direct_plan(
        self,
        document_id: UUID,
        command_id: UUID,
    ) -> WorkspaceRebasePlan | None:
        item = await self.runtime.store.aget(
            self.runtime.workspace_metadata_namespace(document_id),
            self._direct_plan_key(command_id),
        )
        if item is None:
            return None
        return WorkspaceRebasePlan.model_validate(item.value["plan"])

    async def _put_direct_plan(
        self,
        document_id: UUID,
        plan: WorkspaceRebasePlan,
    ) -> None:
        await self.runtime.store.aput(
            self.runtime.workspace_metadata_namespace(document_id),
            self._direct_plan_key(plan.command_id),
            {"plan": plan.model_dump(mode="json")},
            index=False,
        )

    async def _delete_direct_plan(self, document_id: UUID, command_id: UUID) -> None:
        await self.runtime.store.adelete(
            self.runtime.workspace_metadata_namespace(document_id),
            self._direct_plan_key(command_id),
        )

    async def _review_context(
        self,
        document_id: UUID,
    ) -> tuple[
        ConsultantSnapshot,
        StoreBackedWorkspace,
        WorkspaceSnapshot,
        WorkspaceReviewProjection,
    ]:
        snapshot = await self.runtime._snapshot(document_id)
        workspace = StoreBackedWorkspace(
            store=self.runtime.store,
            document_id=document_id,
        )
        workspace_snapshot = await workspace.read_snapshot()
        sources = await self.runtime.list_sources(document_id)
        catalog = WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=sources,
            handle_registry=workspace_snapshot.manifest.entity_ids_by_handle,
        )
        validation = validate_workspace_payload(
            workspace_snapshot.files,
            catalog=catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            loaded_skill_ids=CONSULTANT_SKILL_IDS,
        )
        manifest = workspace_snapshot.manifest
        if manifest.validation_status not in {
            WorkspaceValidationStatus.VALID,
            WorkspaceValidationStatus.CONFLICTED,
        }:
            raise WorkspaceAuthorityError(
                "workspace is not reviewable until validation succeeds"
            )
        if validation.document is None:
            raise WorkspaceAuthorityError(
                "workspace validation failed: "
                + "; ".join(item.code for item in validation.diagnostics)
            )
        if manifest.approved_baseline_revision != snapshot.revision:
            raise WorkspaceAuthorityError("workspace approved revision is stale")
        if manifest.approved_baseline_digest != approved_document_digest(
            snapshot.approved_document
        ):
            raise WorkspaceAuthorityError("workspace approved baseline is stale")
        current_evidence_digest = evidence_basis_digest(validation.current_sources)
        if manifest.evidence_basis_digest != current_evidence_digest:
            raise WorkspaceAuthorityError("workspace Evidence basis is stale")
        effective_manifest = manifest
        if manifest.validation_status is WorkspaceValidationStatus.CONFLICTED:
            active_conflicts = active_conflict_diagnostics(
                files=workspace_snapshot.files,
                approved_document=snapshot.approved_document,
                manifest=manifest,
            )
            effective_manifest = manifest.model_copy(
                update={
                    "validation_status": (
                        WorkspaceValidationStatus.CONFLICTED
                        if validation.diagnostics or active_conflicts
                        else WorkspaceValidationStatus.VALID
                    ),
                    "diagnostics": tuple(
                        dict.fromkeys((*validation.diagnostics, *active_conflicts))
                    ),
                }
            )
        decisions = await self.review_decisions(document_id)
        projection = derive_workspace_review(
            snapshot.approved_document,
            validation,
            effective_manifest,
            decisions,
        )
        if projection.blocking_diagnostics:
            raise WorkspaceAuthorityError("workspace review is not available")
        return snapshot, workspace, workspace_snapshot, projection

    @staticmethod
    def _projection_decisions(
        records: Sequence[WorkspaceDecisionRecord],
    ) -> tuple[WorkspaceReviewDecision, ...]:
        decisions: list[WorkspaceReviewDecision] = []
        for record in records:
            if record.decision not in {
                WorkspaceDecisionKind.REJECT,
                WorkspaceDecisionKind.DEFER,
            }:
                continue
            decisions.append(
                WorkspaceReviewDecision(
                    kind=WorkspaceReviewDecisionKind(record.decision.value),
                    workspace_digest=record.workspace_digest,
                    group_digest=record.group_digest,
                    semantic_fingerprint=record.semantic_fingerprint,
                    evidence_digest=record.evidence_digest,
                    employee_request_digest=record.employee_request_digest,
                    boundary_digest=record.boundary_digest,
                    selected_action_ids=record.selected_action_ids,
                    selected_action_fingerprints=(
                        record.selected_action_fingerprints
                    ),
                )
            )
        return tuple(decisions)

    @staticmethod
    def _group_for_command(
        projection: WorkspaceReviewProjection,
        command: WorkspaceReviewCommand,
    ) -> WorkspaceReviewGroup:
        matches = [
            group
            for group in projection.groups
            if group.changeset.changeset_id == command.changeset_id
        ]
        if len(matches) != 1:
            raise WorkspaceAuthorityError(
                f"workspace changeset {command.changeset_id} is stale"
            )
        group = matches[0]
        if command.group_digest is not None and command.group_digest != group.group_digest:
            raise WorkspaceAuthorityError("workspace group digest is stale")
        return group

    @staticmethod
    def _record(
        command: WorkspaceReviewCommand,
        group: WorkspaceReviewGroup,
        *,
        source_id: UUID | None = None,
        plan: WorkspaceRebasePlan | None = None,
        status: WorkspaceDecisionStatus = WorkspaceDecisionStatus.PLANNED,
    ) -> WorkspaceDecisionRecord:
        selected_ids = set(command.selected_action_ids)
        return WorkspaceDecisionRecord(
            command_id=command.command_id,
            payload_digest=command.payload_digest(),
            decision=command.decision,
            changeset_id=command.changeset_id,
            selected_action_ids=command.selected_action_ids,
            selected_action_fingerprints=tuple(
                workspace_action_semantic_fingerprint(action)
                for action in group.actions
                if action.action_id in selected_ids
            ),
            workspace_digest=command.workspace_digest,
            group_digest=group.group_digest,
            semantic_fingerprint=group.semantic_fingerprint,
            evidence_digest=group.evidence_digest,
            employee_request_digest=group.employee_request_digest,
            boundary_digest=group.boundary_digest,
            approved_revision=command.approved_revision,
            workspace_generation=command.workspace_generation,
            employee_source_id=source_id,
            result_workspace_digest=None,
            reason=command.reason,
            status=status,
        )

    @staticmethod
    def _receipt(command: WorkspaceReviewCommand) -> CommandReceipt:
        return CommandReceipt(
            command_id=command.command_id,
            command_kind=WorkspaceAuthorityService._command_kind(command.decision),
            payload_sha256=command.payload_digest(),
        )

    async def _build_plan(
        self,
        *,
        command_id: UUID,
        old_approved: ApprovedJobDocument,
        workspace_files: Mapping[str, str],
        new_approved: ApprovedJobDocument,
        manifest: WorkspaceManifest,
        approved_revision: int,
        reset_actions: Sequence[DocumentPatchAction] = (),
        accepted_actions: Sequence[DocumentPatchAction] = (),
        employee_override_actions: Sequence[DocumentPatchAction] = (),
        employee_override_paths: Sequence[str] = (),
    ) -> WorkspaceRebasePlan:
        old_projection = project_workspace_files(
            old_approved,
            handle_registry=manifest.entity_ids_by_handle,
        )
        new_projection = project_workspace_files(
            new_approved,
            handle_registry=manifest.entity_ids_by_handle,
        )
        entity_ids_by_handle = dict(manifest.entity_ids_by_handle)
        entity_ids_by_handle.update(old_projection.handle_registry)
        entity_ids_by_handle.update(new_projection.handle_registry)
        all_projection_files = {
            **old_projection.files,
            **new_projection.files,
            **workspace_files,
        }
        working = dict(workspace_files)
        existing_conflicts = active_conflict_diagnostics(
            files=workspace_files,
            approved_document=old_approved,
            manifest=manifest,
        )
        derived_employee_override_paths = tuple(
            path
            for action in (*reset_actions, *employee_override_actions)
            if (
                path := workspace_path_for_action(
                    action,
                    files=all_projection_files,
                    entity_ids_by_handle=entity_ids_by_handle,
                )
            )
            is not None
        )
        resolved_workspace_paths = tuple(
            path
            for action in accepted_actions
            if (
                path := workspace_path_for_action(
                    action,
                    files=all_projection_files,
                    entity_ids_by_handle=entity_ids_by_handle,
                )
            )
            is not None
        )
        plan = build_workspace_rebase_plan(
            command_id=command_id,
            old_approved_files=old_projection.files,
            workspace_files=working,
            new_approved_files=new_projection.files,
            approved_revision=approved_revision,
            approved_digest=approved_document_digest(new_approved),
            employee_override_paths=tuple(
                dict.fromkeys(
                    (*derived_employee_override_paths, *employee_override_paths)
                )
            ),
            resolved_workspace_paths=resolved_workspace_paths,
        )
        actual_digest = workspace_resource_digest(workspace_files)
        actual_changes = tuple(
            change.model_copy(update={"before": workspace_files.get(change.path)})
            for change in plan.changes
        )
        return plan.model_copy(
            update={
                "expected_workspace_digest": actual_digest,
                "changes": actual_changes,
                "conflicted_paths": tuple(
                    dict.fromkeys(
                        (
                            *(diagnostic.path for diagnostic in existing_conflicts),
                            *plan.conflicted_paths,
                        )
                    )
                ),
                "entity_ids_by_handle": entity_ids_by_handle,
            }
        )

    async def _prepare_employee_source(
        self,
        document_id: UUID,
        payload: tuple[str, tuple[Any, ...]] | None,
        source_id: UUID | None,
    ) -> tuple[EmployeeSource | None, SourceReference | None]:
        if payload is None:
            return None, None
        if source_id is None:
            raise WorkspaceAuthorityError(
                "employee source id is required for direct-edit payload"
            )
        text, positions = payload
        requested = EmployeeSource.pending(
            source_id=source_id,
            document_id=document_id,
            kind=EmployeeSourceKind.DIRECT_EDIT,
            text=text,
            positions=tuple(positions),
        )
        source = await self.runtime._load_or_prepare_source(requested)
        if source.processing_status is SourceProcessingStatus.PENDING:
            await self.runtime._after_source_store(source)
        return source, SourceReference(
            source_id=source.source_id,
            kind=source.kind,
            created_at=source.created_at,
            supersedes_source_id=source.supersedes_source_id,
        )

    async def prepare_direct_edit_rebase(
        self,
        *,
        document_id: UUID,
        command_id: UUID,
        source_id: UUID,
        old_approved: ApprovedJobDocument,
        new_approved: ApprovedJobDocument,
        approved_revision: int,
        employee_override_paths: Sequence[str] = (),
    ) -> WorkspaceRebasePlan | None:
        """Persist a direct-edit rebase plan before its graph authority seam."""

        workspace = StoreBackedWorkspace(store=self.runtime.store, document_id=document_id)
        try:
            workspace_snapshot = await workspace.read_snapshot()
        except RuntimeError as error:
            if str(error) != "workspace is not initialized":
                raise
            return None
        plan = await self._build_plan(
            command_id=command_id,
            old_approved=old_approved,
            workspace_files=workspace_snapshot.files,
            new_approved=new_approved,
            manifest=workspace_snapshot.manifest,
            approved_revision=approved_revision,
            employee_override_paths=employee_override_paths,
        )
        plan = plan.model_copy(update={"employee_source_id": source_id})
        await self._put_direct_plan(document_id, plan)
        return plan

    async def finish_direct_edit_rebase(
        self,
        document_id: UUID,
        command_id: UUID,
    ) -> None:
        """Apply or exactly replay a direct-edit plan after graph authority."""

        plan = await self._load_direct_plan(document_id, command_id)
        if plan is None:
            return
        snapshot = await self.runtime._snapshot(document_id)
        if approved_document_digest(snapshot.approved_document) != plan.approved_digest:
            # The graph seam did not commit this plan, or a later authority command
            # superseded it.  It must not be applied to an unrelated approved state.
            await self._delete_direct_plan(document_id, command_id)
            return
        workspace = StoreBackedWorkspace(store=self.runtime.store, document_id=document_id)
        current = await workspace.read_snapshot()
        actual_digest = workspace_resource_digest(current.files)
        if actual_digest != plan.expected_workspace_digest and actual_digest != plan.result_workspace_digest:
            raise WorkspaceAuthorityError(
                "workspace changed outside the persisted direct-edit rebase"
            )
        await workspace.apply_rebase(
            plan=plan,
            approved_document=snapshot.approved_document,
            approved_revision=plan.approved_revision,
        )
        await self._validate_after_rebase(
            workspace,
            snapshot.approved_document,
            plan=plan,
        )
        if plan.employee_source_id is not None:
            source = await self.runtime.get_source_or_none(
                document_id,
                plan.employee_source_id,
            )
            if source is not None:
                await self.runtime._mark_source_committed(source)
        await self._delete_direct_plan(document_id, command_id)

    async def _validate_after_rebase(
        self,
        workspace: StoreBackedWorkspace,
        approved: ApprovedJobDocument,
        *,
        plan: WorkspaceRebasePlan,
    ) -> WorkspaceManifest:
        snapshot = await workspace.read_snapshot()
        sources = await self.runtime.list_sources(approved.document_id)
        catalog = WorkspaceCatalog.from_snapshot(
            approved,
            sources=sources,
            handle_registry=(
                plan.entity_ids_by_handle
                or snapshot.manifest.entity_ids_by_handle
            ),
        )
        validation = validate_workspace_payload(
            snapshot.files,
            catalog=catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            loaded_skill_ids=CONSULTANT_SKILL_IDS,
        )
        conflict_candidates = tuple(
            WorkspaceDiagnostic(
                code="workspace-rebase-conflict",
                path=path,
                message=(
                    "The AI working value was retained for this path; the employee "
                    "approved value is authoritative."
                ),
                severity=WorkspaceDiagnosticSeverity.ERROR,
            )
            for path in plan.conflicted_paths
        )
        active_conflicts = active_conflict_diagnostics(
            files=snapshot.files,
            approved_document=approved,
            manifest=snapshot.manifest.model_copy(
                update={"diagnostics": conflict_candidates}
            ),
        )
        status = (
            (
                WorkspaceValidationStatus.CONFLICTED
                if validation.diagnostics or active_conflicts
                else WorkspaceValidationStatus.VALID
            )
            if validation.document is not None
            else WorkspaceValidationStatus.INVALID
        )
        diagnostics_list = list(validation.diagnostics)
        for diagnostic in active_conflicts:
            if diagnostic not in diagnostics_list:
                diagnostics_list.append(diagnostic)
        diagnostics = tuple(diagnostics_list)
        return await workspace.commit_validation(
            expected_resource_digest=snapshot.manifest.resource_digest,
            evidence_basis_digest=evidence_basis_digest(validation.current_sources),
            validation_status=status,
            diagnostics=diagnostics,
            entity_ids_by_handle=(
                plan.entity_ids_by_handle or snapshot.manifest.entity_ids_by_handle
            ),
        )

    async def _finish_rebase(
        self,
        document_id: UUID,
        record: WorkspaceDecisionRecord,
    ) -> WorkspaceDecisionRecord:
        plan = await self._load_plan(document_id, record.command_id)
        if plan is None:
            raise WorkspaceAuthorityError("workspace rebase plan is missing")
        snapshot = await self.runtime._snapshot(document_id)
        if approved_document_digest(snapshot.approved_document) != plan.approved_digest:
            raise WorkspaceAuthorityError("workspace rebase approved document is stale")
        workspace = StoreBackedWorkspace(store=self.runtime.store, document_id=document_id)
        current = await workspace.read_snapshot()
        actual_digest = workspace_resource_digest(current.files)
        if (
            actual_digest != plan.expected_workspace_digest
            and actual_digest != record.result_workspace_digest
        ):
            raise WorkspaceAuthorityError(
                "workspace changed outside the persisted rebase plan"
            )
        manifest = await workspace.apply_rebase(
            plan=plan,
            approved_document=snapshot.approved_document,
            approved_revision=plan.approved_revision,
        )
        manifest = await self._validate_after_rebase(
            workspace,
            snapshot.approved_document,
            plan=plan,
        )
        if record.employee_source_id is not None:
            source = await self.runtime.get_source_or_none(
                document_id,
                record.employee_source_id,
            )
            if source is not None:
                await self.runtime._mark_source_committed(source)
        completed = record.model_copy(
            update={
                "status": WorkspaceDecisionStatus.COMPLETED,
                "result_workspace_digest": manifest.resource_digest,
            }
        )
        await self._put_record(document_id, completed)
        await self._delete_plan(document_id, record.command_id)
        return completed

    async def recover(self, document_id: UUID) -> None:
        """Finish only durable decision records whose first seam succeeded."""

        records = await self._load_records(document_id)
        raw_state = await self.runtime.raw_state(document_id)
        for record in records:
            if record.decision in {
                WorkspaceDecisionKind.ACCEPT,
                WorkspaceDecisionKind.EDIT_ACCEPT,
            }:
                if record.status is WorkspaceDecisionStatus.COMPLETED:
                    await self._delete_plan(document_id, record.command_id)
                    continue
                receipt = CommandReceipt(
                    command_id=record.command_id,
                    command_kind=self._command_kind(record.decision),
                    payload_sha256=record.payload_digest,
                )
                try:
                    committed = inspect_command_receipt(raw_state, receipt) == "replay"
                except ValueError as error:
                    raise WorkspaceAuthorityError(str(error)) from error
                if committed and record.status is not WorkspaceDecisionStatus.COMPLETED:
                    await self._finish_rebase(document_id, record)
            elif (
                record.decision is WorkspaceDecisionKind.REJECT
                and record.status is WorkspaceDecisionStatus.COMPLETED
                and record.result_workspace_digest is None
            ):
                await self._finish_rebase(document_id, record)
            elif (
                record.decision is WorkspaceDecisionKind.REJECT
                and record.status is WorkspaceDecisionStatus.COMPLETED
            ):
                await self._delete_plan(document_id, record.command_id)
        metadata_items = await self.runtime.store.asearch(
            self.runtime.workspace_metadata_namespace(document_id),
            limit=1000,
        )
        for item in metadata_items:
            key = getattr(item, "key", "")
            if not str(key).startswith("direct-rebase:"):
                continue
            plan = WorkspaceRebasePlan.model_validate(item.value["plan"])
            snapshot = await self.runtime._snapshot(document_id)
            if approved_document_digest(snapshot.approved_document) == plan.approved_digest:
                await self.finish_direct_edit_rebase(document_id, plan.command_id)
            else:
                await self._delete_direct_plan(document_id, plan.command_id)

    async def decide(self, command: WorkspaceReviewCommand) -> ConsultantSnapshot:
        """Validate and apply one employee review command; the caller holds the lock."""

        document_id = command.document_id
        await self.runtime._require_active_catalog(document_id)
        await self.recover(document_id)
        existing = await self._load_record(document_id, command.command_id)
        if existing is not None:
            if existing.payload_digest != command.payload_digest():
                raise WorkspaceAuthorityError(
                    f"command {command.command_id} was reused with another payload"
                )
            await self.recover(document_id)
            existing = await self._load_record(document_id, command.command_id)
            if existing is None:
                raise WorkspaceAuthorityError("workspace decision record disappeared")
            if existing.status is WorkspaceDecisionStatus.COMPLETED:
                return await self.runtime._snapshot(document_id)

        snapshot, workspace, workspace_snapshot, projection = await self._review_context(
            document_id
        )
        if snapshot.revision != command.approved_revision:
            raise WorkspaceAuthorityError("workspace review approved revision is stale")
        if workspace_snapshot.manifest.generation != command.workspace_generation:
            raise WorkspaceAuthorityError("workspace review generation is stale")
        if workspace_snapshot.manifest.resource_digest != command.workspace_digest:
            raise WorkspaceAuthorityError("workspace review digest is stale")
        group = self._group_for_command(projection, command)
        selected = select_workspace_actions(projection, command)
        edited = dict(command.edited_after_by_action_id)

        if command.decision is WorkspaceDecisionKind.DEFER:
            record = self._record(command, group, status=WorkspaceDecisionStatus.COMPLETED)
            await self._put_record(document_id, record)
            return await self.runtime._snapshot(document_id)

        if command.decision is WorkspaceDecisionKind.REJECT:
            plan = await self._build_plan(
                command_id=command.command_id,
                old_approved=snapshot.approved_document,
                workspace_files=workspace_snapshot.files,
                new_approved=snapshot.approved_document,
                manifest=workspace_snapshot.manifest,
                approved_revision=snapshot.revision,
                reset_actions=selected,
            )
            record = self._record(
                command,
                group,
                plan=plan,
                status=WorkspaceDecisionStatus.COMPLETED,
            )
            await self._put_plan(document_id, plan)
            await self._put_record(document_id, record)
            await self.runtime._after_workspace_decision_record()
            await self._finish_rebase(document_id, record)
            return await self.runtime._snapshot(document_id)

        text_payload = edited_action_source_payload(selected, edited)
        employee_source_id = (
            (
                (existing.employee_source_id if existing is not None else None)
                or self._employee_source_id(document_id, command.command_id)
            )
            if text_payload is not None
            else None
        )
        source, source_reference = await self._prepare_employee_source(
            document_id,
            text_payload,
            employee_source_id,
        )
        authority_actions = selected
        if source is not None:
            authority_actions = tuple(
                action.model_copy(
                    update={
                        "source_ids": tuple(
                            dict.fromkeys((*action.source_ids, source.source_id))
                        )
                    }
                )
                for action in selected
            )
        try:
            prospective = apply_document_actions(
                snapshot.approved_document,
                authority_actions,
                edited_after_by_action_id=edited,
            )
        except DocumentAuthorityError as error:
            raise WorkspaceAuthorityError(str(error)) from error
        if source is not None:
            await self.runtime._require_known_evidence_sources(
                prospective,
                pending_direct_edit_source_id=source.source_id,
            )
        plan = await self._build_plan(
            command_id=command.command_id,
            old_approved=snapshot.approved_document,
            workspace_files=workspace_snapshot.files,
            new_approved=prospective,
            manifest=workspace_snapshot.manifest,
            approved_revision=snapshot.revision + 1,
            accepted_actions=selected,
            employee_override_actions=tuple(
                action for action in selected if action.action_id in edited
            ),
        )
        record = self._record(
            command,
            group,
            source_id=(source.source_id if source is not None else None),
            plan=plan,
        )
        await self._put_plan(document_id, plan)
        await self._put_record(document_id, record)
        receipt = self._receipt(command)
        context: dict[str, Any] = {
            "action": "workspace_authority_commit",
            "document_id": str(document_id),
            "expected_revision": snapshot.revision,
            "approved_document": prospective.model_dump(mode="json"),
            "command_receipt": receipt.model_dump(mode="json"),
        }
        if source_reference is not None:
            context["source_reference"] = source_reference.model_dump(mode="json")
        try:
            await self.runtime.graph.ainvoke(
                {},
                self.runtime.graph_config(document_id),
                context=context,
            )
        except Exception:
            raise
        await self.runtime._after_workspace_authority_checkpoint()
        committed = record.model_copy(
            update={"status": WorkspaceDecisionStatus.AUTHORITY_COMMITTED}
        )
        await self._put_record(document_id, committed)
        await self._finish_rebase(document_id, committed)
        await self.runtime._touch_catalog(document_id)
        return await self.runtime._snapshot(document_id)
