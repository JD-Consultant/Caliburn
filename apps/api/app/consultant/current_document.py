"""Server-derived authority split for edits to the one visible current JD."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import Field, JsonValue

from app.consultant.document_authority import (
    DocumentAuthorityError,
    apply_document_path_values,
    employee_authored_text_delta,
)
from app.consultant.state import (
    ApprovedJobDocument,
    DocumentPatchAction,
    DocumentPatchOperation,
    DurableModel,
    SourcePositionAnchor,
)
from app.consultant.workspace_review import WorkspaceReviewProjection
from app.consultant.workspace_state import PendingTaskCompetencyLevels


class CurrentDocumentEditError(ValueError):
    """The submitted current document is stale or attempts an unsafe edit."""


class CurrentDocumentEditPlan(DurableModel):
    approved_after: ApprovedJobDocument
    current_after: ApprovedJobDocument
    pending_paths: tuple[str, ...] = ()
    approved_paths: tuple[str, ...] = ()
    employee_source_text: str | None = None
    source_positions: tuple[SourcePositionAnchor, ...] = ()
    pending_task_competency_levels: PendingTaskCompetencyLevels = Field(
        default_factory=PendingTaskCompetencyLevels
    )


@dataclass(frozen=True, slots=True)
class _DocumentValueChange:
    path: str
    before: JsonValue | None
    after: JsonValue | None


_HEADER_FIELDS = (
    "job_title",
    "occupation_category_name",
    "occupation_name",
    "occupation_code",
    "industry_name",
    "industry_code",
    "work_description",
    "competency_level",
    "notes",
)
_TASK_EDITABLE_FIELDS = (
    "statement",
    "action",
    "object",
    "purpose_result",
    "context",
    "frequency_text",
    "responsibility_role",
    "enablers",
    "competency_level",
)
_COLLECTION_IDS = {
    "/duties": "duty_id",
    "/tasks": "task_id",
    "/opks": "item_id",
}


def _validated(document: ApprovedJobDocument, *, label: str) -> ApprovedJobDocument:
    try:
        return ApprovedJobDocument.model_validate(document.model_dump(mode="json"))
    except ValueError as error:
        raise CurrentDocumentEditError(
            f"submitted document relationship is invalid ({label}): {error}"
        ) from error


def _entity_map(values: tuple[Any, ...], id_field: str) -> dict[UUID, Any]:
    return {getattr(item, id_field): item for item in values}


def _require_same_structure(
    current: ApprovedJobDocument,
    submitted: ApprovedJobDocument,
) -> None:
    if current.document_id != submitted.document_id:
        raise CurrentDocumentEditError("submitted document changed its stable identity")
    if current.schema_version != submitted.schema_version:
        raise CurrentDocumentEditError("submitted document changed its schema identity")
    for collection, id_field in (
        ("duties", "duty_id"),
        ("tasks", "task_id"),
        ("opks", "item_id"),
    ):
        current_values = getattr(current, collection)
        submitted_values = getattr(submitted, collection)
        current_ids = {getattr(item, id_field) for item in current_values}
        submitted_ids = {getattr(item, id_field) for item in submitted_values}
        if current_ids != submitted_ids:
            raise CurrentDocumentEditError(
                f"submitted {collection} changed a stable identity"
            )

    current_duties = _entity_map(current.duties, "duty_id")
    submitted_duties = _entity_map(submitted.duties, "duty_id")
    for identity, item in current_duties.items():
        if item.display_order != submitted_duties[identity].display_order:
            raise CurrentDocumentEditError(
                "submitted duty ordering requires a typed structural command"
            )

    current_tasks = _entity_map(current.tasks, "task_id")
    submitted_tasks = _entity_map(submitted.tasks, "task_id")
    for identity, item in current_tasks.items():
        candidate = submitted_tasks[identity]
        if item.duty_id != candidate.duty_id:
            raise CurrentDocumentEditError(
                "submitted Task relationship requires a typed structural command"
            )
        if item.display_order != candidate.display_order:
            raise CurrentDocumentEditError(
                "submitted Task ordering requires a typed structural command"
            )

    current_opks = _entity_map(current.opks, "item_id")
    submitted_opks = _entity_map(submitted.opks, "item_id")
    for identity, item in current_opks.items():
        candidate = submitted_opks[identity]
        if (
            item.kind != candidate.kind
            or item.task_ids != candidate.task_ids
            or item.indicator_ids != candidate.indicator_ids
        ):
            raise CurrentDocumentEditError(
                "submitted OPKS relationship requires a typed structural command"
            )
        if item.display_order != candidate.display_order:
            raise CurrentDocumentEditError(
                "submitted OPKS ordering requires a typed structural command"
            )
        if item.evidence_source_ids != candidate.evidence_source_ids:
            raise CurrentDocumentEditError(
                "submitted document cannot author Evidence source identities"
            )


def _normalized_submitted(
    current: ApprovedJobDocument,
    submitted: ApprovedJobDocument,
) -> ApprovedJobDocument:
    submitted_duties = _entity_map(submitted.duties, "duty_id")
    submitted_tasks = _entity_map(submitted.tasks, "task_id")
    submitted_opks = _entity_map(submitted.opks, "item_id")
    return submitted.model_copy(
        update={
            "duties": tuple(
                submitted_duties[item.duty_id] for item in current.duties
            ),
            "tasks": tuple(
                submitted_tasks[item.task_id] for item in current.tasks
            ),
            "opks": tuple(submitted_opks[item.item_id] for item in current.opks),
        }
    )


def _value_changes(
    current: ApprovedJobDocument,
    submitted: ApprovedJobDocument,
) -> tuple[_DocumentValueChange, ...]:
    changes: list[_DocumentValueChange] = []

    def compare(path: str, before: Any, after: Any) -> None:
        if before != after:
            changes.append(_DocumentValueChange(path=path, before=before, after=after))

    for field in _HEADER_FIELDS:
        compare(f"/{field}", getattr(current, field), getattr(submitted, field))

    submitted_duties = _entity_map(submitted.duties, "duty_id")
    for item in current.duties:
        after = submitted_duties[item.duty_id]
        compare(
            f"/duties/{item.duty_id}/statement",
            item.statement,
            after.statement,
        )

    submitted_tasks = _entity_map(submitted.tasks, "task_id")
    for item in current.tasks:
        after = submitted_tasks[item.task_id]
        for field in _TASK_EDITABLE_FIELDS:
            before_value = getattr(item, field)
            after_value = getattr(after, field)
            compare(
                f"/tasks/{item.task_id}/{field}",
                (
                    [value.model_dump(mode="json") for value in before_value]
                    if field == "enablers"
                    else before_value
                ),
                (
                    [value.model_dump(mode="json") for value in after_value]
                    if field == "enablers"
                    else after_value
                ),
            )

    submitted_opks = _entity_map(submitted.opks, "item_id")
    for item in current.opks:
        after = submitted_opks[item.item_id]
        compare(f"/opks/{item.item_id}/text", item.text, after.text)
    return tuple(changes)


def _pending_scope(action: DocumentPatchAction) -> str:
    if action.operation is not DocumentPatchOperation.ADD:
        return action.path
    id_field = _COLLECTION_IDS.get(action.path)
    if id_field is None or not isinstance(action.after, dict):
        return action.path
    identity = action.after.get(id_field)
    return f"{action.path}/{identity}" if identity is not None else action.path


def _paths_overlap(left: str, right: str) -> bool:
    return (
        left == right
        or left.startswith(f"{right.rstrip('/')}/")
        or right.startswith(f"{left.rstrip('/')}/")
    )


def document_paths_overlap_pending_review(
    paths: tuple[str, ...],
    workspace_review: WorkspaceReviewProjection,
) -> bool:
    """Return whether a typed employee intent touches any fresh AI pending scope."""

    pending_scopes = tuple(
        _pending_scope(action)
        for group in workspace_review.groups
        for action in group.actions
    )
    return any(
        _paths_overlap(path, scope)
        for path in paths
        for scope in pending_scopes
    )


def compose_structural_current_document_edit(
    *,
    approved: ApprovedJobDocument,
    current: ApprovedJobDocument,
    current_after: ApprovedJobDocument,
    approved_after: ApprovedJobDocument,
    touched_paths: tuple[str, ...],
    remains_pending: bool,
    task_handle_by_id: Mapping[UUID, str],
) -> CurrentDocumentEditPlan:
    """Compose a typed structural after-state for the Task 3 commit seam."""

    effective_approved = approved if remains_pending else approved_after
    source_payload = employee_authored_text_delta(current, current_after)
    approved_task_ids = {item.task_id for item in effective_approved.tasks}
    pending_levels = {
        task_handle_by_id[item.task_id]: item.competency_level
        for item in current_after.tasks
        if item.task_id not in approved_task_ids
        and item.competency_level is not None
        and item.task_id in task_handle_by_id
    }
    return CurrentDocumentEditPlan(
        approved_after=effective_approved,
        current_after=current_after,
        pending_paths=(touched_paths if remains_pending else ()),
        approved_paths=(() if remains_pending else touched_paths),
        employee_source_text=(source_payload[0] if source_payload else None),
        source_positions=(source_payload[1] if source_payload else ()),
        pending_task_competency_levels=PendingTaskCompetencyLevels(
            by_task_handle=pending_levels
        ),
    )


def derive_current_document_edit(
    *,
    approved: ApprovedJobDocument,
    current: ApprovedJobDocument,
    submitted: ApprovedJobDocument,
    workspace_review: WorkspaceReviewProjection,
    task_handle_by_id: Mapping[UUID, str],
) -> CurrentDocumentEditPlan:
    """Split one employee autosave by overlap with fresh pending AI semantics."""

    approved = _validated(approved, label="approved")
    current = _validated(current, label="current")
    submitted = _validated(submitted, label="submitted")
    if not (
        approved.document_id == current.document_id == submitted.document_id
    ):
        raise CurrentDocumentEditError("documents do not share one stable identity")
    _require_same_structure(current, submitted)
    submitted = _normalized_submitted(current, submitted)

    pending_scopes = tuple(
        _pending_scope(action)
        for group in workspace_review.groups
        for action in group.actions
    )
    changes = _value_changes(current, submitted)
    pending: list[_DocumentValueChange] = []
    ordinary: list[_DocumentValueChange] = []
    for change in changes:
        target = (
            pending
            if any(_paths_overlap(change.path, scope) for scope in pending_scopes)
            else ordinary
        )
        target.append(change)

    try:
        approved_after = apply_document_path_values(
            approved,
            {change.path: change.after for change in ordinary},
        )
    except DocumentAuthorityError as error:
        raise CurrentDocumentEditError(str(error)) from error

    source_payload = employee_authored_text_delta(current, submitted)
    approved_task_ids = {item.task_id for item in approved.tasks}
    pending_levels = {
        task_handle_by_id[item.task_id]: item.competency_level
        for item in submitted.tasks
        if item.task_id not in approved_task_ids
        and item.competency_level is not None
        and item.task_id in task_handle_by_id
    }
    return CurrentDocumentEditPlan(
        approved_after=approved_after,
        current_after=submitted,
        pending_paths=tuple(change.path for change in pending),
        approved_paths=tuple(change.path for change in ordinary),
        employee_source_text=(source_payload[0] if source_payload else None),
        source_positions=(source_payload[1] if source_payload else ()),
        pending_task_competency_levels=PendingTaskCompetencyLevels(
            by_task_handle=pending_levels
        ),
    )


def attach_employee_source_to_current_edit(
    plan: CurrentDocumentEditPlan,
    source_id: UUID,
) -> CurrentDocumentEditPlan:
    """Attach exact direct-edit Evidence only to changed OPKS text."""

    changed_opks_paths = {
        position.document_path
        for position in plan.source_positions
        if position.document_path.startswith("/opks/")
        and position.document_path.endswith("/text")
    }
    if not changed_opks_paths:
        return plan

    def attach(
        document: ApprovedJobDocument,
        paths: set[str],
    ) -> ApprovedJobDocument:
        updated = []
        for item in document.opks:
            path = f"/opks/{item.item_id}/text"
            if path not in paths or source_id in item.evidence_source_ids:
                updated.append(item)
                continue
            updated.append(
                item.model_copy(
                    update={
                        "evidence_source_ids": (
                            *item.evidence_source_ids,
                            source_id,
                        )
                    }
                )
            )
        return ApprovedJobDocument.model_validate(
            document.model_copy(update={"opks": tuple(updated)}).model_dump(
                mode="json"
            )
        )

    approved_paths = changed_opks_paths & set(plan.approved_paths)
    return plan.model_copy(
        update={
            "current_after": attach(plan.current_after, changed_opks_paths),
            "approved_after": attach(plan.approved_after, approved_paths),
        }
    )


__all__ = [
    "CurrentDocumentEditError",
    "CurrentDocumentEditPlan",
    "attach_employee_source_to_current_edit",
    "compose_structural_current_document_edit",
    "derive_current_document_edit",
    "document_paths_overlap_pending_review",
]
