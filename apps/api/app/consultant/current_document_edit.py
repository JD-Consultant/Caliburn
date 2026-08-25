"""Pure planning for employee edits against the Store-derived current JD."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Any
from uuid import UUID

from app.consultant.document_authority import apply_document_actions
from app.consultant.state import ApprovedJobDocument, DocumentPatchAction
from app.consultant.workspace_resources import (
    parse_workspace_files,
    project_workspace_files,
)
from app.consultant.workspace_review import WorkspaceReviewProjection
from app.consultant.workspace_authority import workspace_path_for_action


@dataclass(frozen=True, slots=True)
class CurrentDocumentEditPlan:
    """The server-derived authority delta for one current-document edit."""

    approved_after: ApprovedJobDocument
    employee_override_paths: tuple[str, ...]
    accepted_pending_action_ids: tuple[UUID, ...]
    employee_text_paths: tuple[str, ...]


_MISSING = object()


def _pointer_segment(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _json_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("workspace projection contains invalid JSON") from error


def _append_changed_paths(before: Any, after: Any, path: str, result: list[str]) -> None:
    if before == after:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child = f"{path}/{_pointer_segment(key)}"
            if key not in before or key not in after:
                result.append(child)
            else:
                _append_changed_paths(before[key], after[key], child, result)
        return
    if isinstance(before, list) or isinstance(after, list):
        result.append(path)
        return
    result.append(path)


def _changed_workspace_paths(
    before_files: Mapping[str, str],
    after_files: Mapping[str, str],
) -> tuple[str, ...]:
    changed: list[str] = []
    for resource_path in sorted(set(before_files) | set(after_files)):
        before = before_files.get(resource_path, _MISSING)
        after = after_files.get(resource_path, _MISSING)
        if before is _MISSING or after is _MISSING:
            changed.append(resource_path)
            continue
        _append_changed_paths(
            _json_value(before),
            _json_value(after),
            resource_path,
            changed,
        )
    return tuple(changed)


def _resource_path(path: str) -> tuple[str, str]:
    marker = ".json"
    end = path.find(marker)
    if end < 0:
        raise ValueError(f"invalid workspace pointer: {path}")
    end += len(marker)
    return path[:end], path[end:]


def _pointer_parts(path: str) -> tuple[str, ...]:
    if not path.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {path}")
    return tuple(
        part.replace("~1", "/").replace("~0", "~")
        for part in path[1:].split("/")
        if part != ""
    )


def _read_pointer(value: Any, path: str) -> Any:
    current = value
    for part in _pointer_parts(path):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _write_pointer(value: Any, path: str, replacement: Any) -> None:
    parts = _pointer_parts(path)
    if not parts:
        raise ValueError("resource root must be handled separately")
    current = value
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"workspace pointer target does not exist: {path}")
        current = current[part]
    if not isinstance(current, dict):
        raise ValueError(f"workspace pointer target is not an object: {path}")
    final = parts[-1]
    if replacement is _MISSING:
        current.pop(final, None)
    else:
        current[final] = replacement


def _overlay_workspace_paths(
    base_files: Mapping[str, str],
    submitted_files: Mapping[str, str],
    changed_paths: Sequence[str],
) -> dict[str, str]:
    result = dict(base_files)
    for changed_path in changed_paths:
        resource_path, suffix = _resource_path(changed_path)
        submitted_raw = submitted_files.get(resource_path, _MISSING)
        if submitted_raw is _MISSING:
            result.pop(resource_path, None)
            continue
        if not suffix:
            result[resource_path] = submitted_raw
            continue
        base_raw = result.get(resource_path)
        if base_raw is None:
            result[resource_path] = submitted_raw
            continue
        base_value = _json_value(base_raw)
        submitted_value = _json_value(submitted_raw)
        suffix_value = _read_pointer(submitted_value, suffix)
        _write_pointer(base_value, suffix, suffix_value)
        result[resource_path] = json.dumps(
            base_value,
            ensure_ascii=False,
            indent=2,
        ) + "\n"
    return result


def _employee_text_paths(
    before: ApprovedJobDocument,
    after: ApprovedJobDocument,
) -> tuple[str, ...]:
    paths: list[str] = []

    def add(path: str, before_value: object, after_value: object) -> None:
        if (
            isinstance(after_value, str)
            and after_value.strip()
            and before_value != after_value
        ):
            paths.append(path)

    for field in (
        "job_title",
        "occupation_category_name",
        "occupation_name",
        "occupation_code",
        "industry_name",
        "industry_code",
        "work_description",
        "notes",
    ):
        add(f"/{field}", getattr(before, field), getattr(after, field))

    before_duties = {item.duty_id: item for item in before.duties}
    for duty in after.duties:
        previous = before_duties.get(duty.duty_id)
        add(
            f"/duties/{duty.duty_id}/statement",
            previous.statement if previous is not None else None,
            duty.statement,
        )

    before_tasks = {item.task_id: item for item in before.tasks}
    for task in after.tasks:
        previous = before_tasks.get(task.task_id)
        task_path = f"/tasks/{task.task_id}"
        for field in (
            "statement",
            "action",
            "object",
            "purpose_result",
            "context",
            "frequency_text",
        ):
            add(
                f"{task_path}/{field}",
                getattr(previous, field) if previous is not None else None,
                getattr(task, field),
            )
        before_enablers = previous.enablers if previous is not None else ()
        for index, enabler in enumerate(task.enablers):
            previous_name = (
                before_enablers[index].name
                if index < len(before_enablers)
                else None
            )
            add(
                f"{task_path}/enablers/{index}/name",
                previous_name,
                enabler.name,
            )

    before_opks = {item.item_id: item for item in before.opks}
    for item in after.opks:
        previous = before_opks.get(item.item_id)
        add(
            f"/opks/{item.item_id}/text",
            previous.text if previous is not None else None,
            item.text,
        )
    return tuple(paths)


def _paths_overlap(left: str, right: str) -> bool:
    return (
        left == right
        or left.startswith(f"{right.rstrip('/')}/")
        or right.startswith(f"{left.rstrip('/')}/")
    )


def _matched_action_ids(
    review: WorkspaceReviewProjection,
    changed_paths: Sequence[str],
    *,
    files: Mapping[str, str],
    entity_ids_by_handle: Mapping[str, UUID],
) -> set[UUID]:
    matched: set[UUID] = set()
    for group in review.groups:
        for action in group.actions:
            action_path = workspace_path_for_action(
                action,
                files=files,
                entity_ids_by_handle=entity_ids_by_handle,
            )
            if action_path is not None and any(
                _paths_overlap(action_path, path) for path in changed_paths
            ):
                matched.add(action.action_id)
    return matched


def _action_closure(
    review: WorkspaceReviewProjection,
    seed_ids: set[UUID],
) -> set[UUID]:
    actions = {
        action.action_id: action
        for group in review.groups
        for action in group.actions
    }
    accepted = set(seed_ids)
    changed = True
    while changed:
        changed = False
        for action in actions.values():
            if action.action_id not in accepted:
                continue
            if action.atomic_subgroup_id is not None:
                subgroup_members = {
                    candidate.action_id
                    for candidate in actions.values()
                    if candidate.atomic_subgroup_id == action.atomic_subgroup_id
                }
                before = len(accepted)
                accepted.update(subgroup_members)
                changed = changed or len(accepted) != before
            dependencies = set(action.depends_on_action_ids)
            known_dependencies = dependencies & actions.keys()
            before = len(accepted)
            accepted.update(known_dependencies)
            changed = changed or len(accepted) != before
    return accepted


def plan_current_document_edit(
    approved: ApprovedJobDocument,
    current: ApprovedJobDocument,
    submitted: ApprovedJobDocument,
    workspace_files: Mapping[str, str],
    handle_registry: Mapping[str, UUID],
    review: WorkspaceReviewProjection,
) -> CurrentDocumentEditPlan:
    """Plan only the semantic delta represented by current -> submitted."""

    if not (
        approved.document_id == current.document_id == submitted.document_id
    ):
        raise ValueError("current document edit scope does not match")

    stable_registry = dict(handle_registry)
    for handle, stable_id in review.entity_ids_by_handle.items():
        existing = stable_registry.get(handle)
        if existing is not None and existing != stable_id:
            raise ValueError(f"workspace handle registry mismatch: {handle}")
        stable_registry.setdefault(handle, stable_id)
    current_projection = project_workspace_files(
        current,
        handle_registry=stable_registry,
    )
    stable_registry = dict(current_projection.handle_registry)
    submitted_projection = project_workspace_files(
        submitted,
        handle_registry=stable_registry,
    )
    stable_registry.update(submitted_projection.handle_registry)

    parse_workspace_files(
        current.document_id,
        current_projection.files,
        handle_registry=stable_registry,
        baseline_document=approved,
    )
    parse_workspace_files(
        submitted.document_id,
        submitted_projection.files,
        handle_registry=stable_registry,
        baseline_document=approved,
    )

    changed_paths = _changed_workspace_paths(
        current_projection.files,
        submitted_projection.files,
    )
    matched_ids = _matched_action_ids(
        review,
        changed_paths,
        files={
            **workspace_files,
            **current_projection.files,
            **submitted_projection.files,
        },
        entity_ids_by_handle=stable_registry,
    )
    accepted_ids = _action_closure(review, matched_ids)
    accepted_actions = tuple(
        action
        for group in review.groups
        for action in group.actions
        if action.action_id in accepted_ids
    )
    accepted = apply_document_actions(approved, accepted_actions)
    accepted_projection = project_workspace_files(
        accepted,
        handle_registry=stable_registry,
    )
    merged_files = _overlay_workspace_paths(
        accepted_projection.files,
        submitted_projection.files,
        changed_paths,
    )
    approved_after = parse_workspace_files(
        approved.document_id,
        merged_files,
        handle_registry=stable_registry,
        baseline_document=approved,
    ).approved_document
    return CurrentDocumentEditPlan(
        approved_after=approved_after,
        employee_override_paths=tuple(changed_paths),
        accepted_pending_action_ids=tuple(
            action.action_id for action in accepted_actions
        ),
        employee_text_paths=_employee_text_paths(current, submitted),
    )
