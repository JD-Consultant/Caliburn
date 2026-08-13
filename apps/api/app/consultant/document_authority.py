"""Deterministic authority operations over the approved job document.

LangGraph owns persistence and command replay.  This module is deliberately the
thin product-specific remainder: stable-ID document paths and invariants that a
general workflow framework cannot infer for Caliburn.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any
from uuid import UUID

from pydantic import JsonValue

from app.consultant.state import (
    ApprovedJobDocument,
    DocumentPatchAction,
    DocumentPatchOperation,
    SourcePositionAnchor,
)


class DocumentAuthorityError(ValueError):
    pass


_COLLECTION_IDS = {
    "duties": "duty_id",
    "tasks": "task_id",
    "opks": "item_id",
}
_EMPLOYEE_TEXT_FIELDS = {
    "job_title",
    "work_description",
    "notes",
    "statement",
    "action",
    "object",
    "purpose_result",
    "context",
    "frequency_text",
    "name",
    "text",
}


def _pointer_parts(path: str) -> list[str]:
    if not path.startswith("/") or path == "/":
        raise DocumentAuthorityError(f"invalid document path: {path}")
    return [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]


def _find_entity(items: list[dict[str, Any]], id_field: str, identity: str) -> int:
    for index, item in enumerate(items):
        if str(item.get(id_field)) == identity:
            return index
    return -1


def _locate(
    payload: dict[str, Any],
    path: str,
) -> tuple[bool, Any]:
    parts = _pointer_parts(path)
    current: Any = payload
    index = 0
    while index < len(parts):
        part = parts[index]
        if isinstance(current, dict):
            if part not in current:
                return False, None
            current = current[part]
            index += 1
            continue
        if isinstance(current, list):
            collection = parts[index - 1] if index else ""
            id_field = _COLLECTION_IDS.get(collection)
            if id_field is not None:
                entity_index = _find_entity(current, id_field, part)
            else:
                try:
                    entity_index = int(part)
                except ValueError:
                    return False, None
            if entity_index < 0 or entity_index >= len(current):
                return False, None
            current = current[entity_index]
            index += 1
            continue
        return False, None
    return True, deepcopy(current)


def read_document_path(document: ApprovedJobDocument, path: str) -> JsonValue | None:
    exists, value = _locate(document.model_dump(mode="json"), path)
    return value if exists else None


def document_path_sha256(document: ApprovedJobDocument, path: str) -> str:
    exists, value = _locate(document.model_dump(mode="json"), path)
    encoded = json.dumps(
        {"exists": exists, "value": value},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _collection(payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
    value = payload.get(name)
    if not isinstance(value, list):
        raise DocumentAuthorityError(f"/{name} is not a document collection")
    return value


def _set_existing_path(payload: dict[str, Any], path: str, value: Any) -> None:
    parts = _pointer_parts(path)
    if len(parts) == 1:
        if parts[0] not in payload:
            raise DocumentAuthorityError(f"unknown document field: {path}")
        payload[parts[0]] = deepcopy(value)
        return
    collection_name = parts[0]
    id_field = _COLLECTION_IDS.get(collection_name)
    if id_field is None or len(parts) < 2:
        raise DocumentAuthorityError(f"unsupported document path: {path}")
    items = _collection(payload, collection_name)
    entity_index = _find_entity(items, id_field, parts[1])
    if entity_index < 0:
        raise DocumentAuthorityError(f"document target no longer exists: {path}")
    if len(parts) == 2:
        if not isinstance(value, dict):
            raise DocumentAuthorityError("entity replacement requires an object")
        identity = value.get(id_field)
        if identity is None or str(identity) != parts[1]:
            raise DocumentAuthorityError(
                "entity replacement must preserve its stable identity"
            )
        items[entity_index] = deepcopy(value)
        return
    current: Any = items[entity_index]
    for part in parts[2:-1]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as error:
                raise DocumentAuthorityError(f"unsupported document path: {path}") from error
        else:
            raise DocumentAuthorityError(f"unsupported document path: {path}")
    final = parts[-1]
    if isinstance(current, dict):
        if final not in current:
            raise DocumentAuthorityError(f"unknown document field: {path}")
        current[final] = deepcopy(value)
        return
    if isinstance(current, list):
        try:
            current[int(final)] = deepcopy(value)
        except (ValueError, IndexError) as error:
            raise DocumentAuthorityError(f"unsupported document path: {path}") from error
        return
    raise DocumentAuthorityError(f"unsupported document path: {path}")


def _add_to_collection(payload: dict[str, Any], path: str, value: Any) -> None:
    parts = _pointer_parts(path)
    if len(parts) != 1 or parts[0] not in _COLLECTION_IDS:
        raise DocumentAuthorityError("add requires a stable document collection")
    if not isinstance(value, dict):
        raise DocumentAuthorityError("add requires one complete entity object")
    items = _collection(payload, parts[0])
    id_field = _COLLECTION_IDS[parts[0]]
    identity = value.get(id_field)
    if identity is None:
        raise DocumentAuthorityError(f"added entity requires {id_field}")
    if _find_entity(items, id_field, str(identity)) >= 0:
        raise DocumentAuthorityError(f"document entity already exists: {identity}")
    items.append(deepcopy(value))


def _withdraw_entity(payload: dict[str, Any], path: str) -> None:
    parts = _pointer_parts(path)
    if len(parts) != 2 or parts[0] not in _COLLECTION_IDS:
        raise DocumentAuthorityError("withdraw requires a stable entity path")
    items = _collection(payload, parts[0])
    entity_index = _find_entity(items, _COLLECTION_IDS[parts[0]], parts[1])
    if entity_index < 0:
        raise DocumentAuthorityError(f"document target no longer exists: {path}")
    del items[entity_index]


def _replace_entities(
    payload: dict[str, Any],
    action: DocumentPatchAction,
    value: Any,
) -> None:
    parts = _pointer_parts(action.path)
    if len(parts) != 1 or parts[0] not in _COLLECTION_IDS:
        raise DocumentAuthorityError("merge or split requires a collection path")
    replacements = value if isinstance(value, list) else [value]
    if not replacements or not all(isinstance(item, dict) for item in replacements):
        raise DocumentAuthorityError("merge or split requires replacement entities")
    items = _collection(payload, parts[0])
    id_field = _COLLECTION_IDS[parts[0]]
    target_ids = {str(item) for item in action.target_ids}
    found = {str(item[id_field]) for item in items if str(item[id_field]) in target_ids}
    if found != target_ids:
        raise DocumentAuthorityError("merge or split target no longer exists")
    items[:] = [item for item in items if str(item[id_field]) not in target_ids]
    existing = {str(item[id_field]) for item in items}
    for replacement in replacements:
        identity = replacement.get(id_field)
        if identity is None or str(identity) in existing:
            raise DocumentAuthorityError("replacement entity identity conflicts")
        items.append(deepcopy(replacement))
        existing.add(str(identity))


def _attach_opks_evidence(
    payload: dict[str, Any],
    action: DocumentPatchAction,
) -> None:
    parts = _pointer_parts(action.path)
    if not parts or parts[0] != "opks":
        return
    items = _collection(payload, "opks")
    affected_ids: set[str] = set()
    if action.operation is DocumentPatchOperation.ADD and isinstance(action.after, dict):
        affected_ids.add(str(action.after.get("item_id")))
    elif action.operation in {DocumentPatchOperation.MERGE, DocumentPatchOperation.SPLIT}:
        replacements = action.after if isinstance(action.after, list) else [action.after]
        affected_ids.update(
            str(item.get("item_id")) for item in replacements if isinstance(item, dict)
        )
    elif len(parts) >= 2:
        affected_ids.add(parts[1])
    for item in items:
        if str(item.get("item_id")) not in affected_ids:
            continue
        evidence = list(item.get("evidence_source_ids", []))
        for source_id in action.source_ids:
            if str(source_id) not in evidence:
                evidence.append(str(source_id))
        item["evidence_source_ids"] = evidence


def apply_document_actions(
    document: ApprovedJobDocument,
    actions: tuple[DocumentPatchAction, ...],
    *,
    edited_after_by_action_id: dict[UUID, JsonValue | None] | None = None,
) -> ApprovedJobDocument:
    """Apply one already-authorized action set and validate the final artifact."""

    edited = edited_after_by_action_id or {}
    payload = document.model_dump(mode="json")
    selected_ids = {item.action_id for item in actions}
    remaining = list(actions)
    ordered: list[DocumentPatchAction] = []
    applied_ids: set[UUID] = set()
    while remaining:
        ready = next(
            (
                item
                for item in remaining
                if not (
                    (set(item.depends_on_action_ids) & selected_ids)
                    - applied_ids
                )
            ),
            None,
        )
        if ready is None:
            raise DocumentAuthorityError("document patch dependency cycle")
        ordered.append(ready)
        applied_ids.add(ready.action_id)
        remaining.remove(ready)
    for action in ordered:
        value = edited.get(action.action_id, action.after)
        if action.operation is DocumentPatchOperation.ADD:
            _add_to_collection(payload, action.path, value)
        elif action.operation is DocumentPatchOperation.WITHDRAW:
            _withdraw_entity(payload, action.path)
        elif action.operation in {
            DocumentPatchOperation.MERGE,
            DocumentPatchOperation.SPLIT,
        }:
            _replace_entities(payload, action, value)
        else:
            _set_existing_path(payload, action.path, value)
        _attach_opks_evidence(payload, action)
    try:
        return ApprovedJobDocument.model_validate(payload)
    except ValueError as error:
        raise DocumentAuthorityError(str(error)) from error


def _employee_text_leaves(
    proposed: Any,
    edited: Any,
    *,
    path: str,
) -> list[tuple[str, str]]:
    if isinstance(edited, str):
        field = _pointer_parts(path)[-1]
        if field in _EMPLOYEE_TEXT_FIELDS and edited != proposed and edited.strip():
            return [(path, edited.strip())]
        return []
    if isinstance(edited, dict):
        proposed_dict = proposed if isinstance(proposed, dict) else {}
        changes: list[tuple[str, str]] = []
        for key, value in edited.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            changes.extend(
                _employee_text_leaves(
                    proposed_dict.get(key),
                    value,
                    path=f"{path}/{escaped}",
                )
            )
        return changes
    if isinstance(edited, list):
        proposed_list = proposed if isinstance(proposed, list) else []
        changes = []
        for index, value in enumerate(edited):
            before = proposed_list[index] if index < len(proposed_list) else None
            changes.extend(
                _employee_text_leaves(before, value, path=f"{path}/{index}")
            )
        return changes
    return []


def edited_action_source_payload(
    actions: tuple[DocumentPatchAction, ...],
    edited_after_by_action_id: dict[UUID, JsonValue | None],
) -> tuple[str, tuple[SourcePositionAnchor, ...]] | None:
    """Return only employee-authored textual deltas from edit-and-accept."""

    changed: list[tuple[str, str]] = []
    by_id = {item.action_id: item for item in actions}
    for action_id, edited in edited_after_by_action_id.items():
        action = by_id.get(action_id)
        if action is None:
            raise DocumentAuthorityError(f"unknown edited patch action {action_id}")
        changed.extend(_employee_text_leaves(action.after, edited, path=action.path))
    if not changed:
        return None
    chunks: list[str] = []
    positions: list[SourcePositionAnchor] = []
    cursor = 0
    for path, value in changed:
        if chunks:
            cursor += 1
        start = cursor
        chunks.append(value)
        cursor += len(value)
        positions.append(
            SourcePositionAnchor(document_path=path, start=start, end=cursor)
        )
    return "\n".join(chunks), tuple(positions)
