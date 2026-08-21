"""Checkpointed review queue policy for model-authored document changes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import JsonValue

from app.consultant.document_authority import (
    DocumentAuthorityError,
    apply_document_actions,
    document_path_sha256,
    edited_action_source_payload,
    read_document_path,
)
from app.consultant.results import DocumentChangeOperation, ReviewableDocumentChange
from app.consultant.state import (
    ApprovedJobDocument,
    DocumentChangeSet,
    DocumentChangeStatus,
    DocumentPatchAction,
    DocumentPatchOperation,
    DocumentPathRead,
    GapItem,
    GapStatus,
    InterviewWorkItem,
    InterviewWorkStatus,
    SourceReference,
    UnderstandingItem,
    UnderstandingStatus,
)


ReviewCommand = Literal[
    "accept_changes",
    "edit_and_accept_changes",
    "reject_changes",
    "defer_changes",
]


class DocumentReviewError(ValueError):
    pass


class RejectedChangeRequiresNewEvidence(DocumentReviewError):
    pass


class AtomicSubgroupIncomplete(DocumentReviewError):
    pass


class ReviewDependencyUnresolved(DocumentReviewError):
    pass


_COLLECTION_ID_FIELDS = {
    "/duties": "duty_id",
    "/tasks": "task_id",
    "/opks": "item_id",
}
_STRUCTURAL_OPERATIONS = {
    DocumentPatchOperation.WITHDRAW,
    DocumentPatchOperation.MERGE,
    DocumentPatchOperation.SPLIT,
    DocumentPatchOperation.REASSIGN,
}
_UNRESOLVED_STATUSES = {
    DocumentChangeStatus.PENDING,
    DocumentChangeStatus.DEFERRED,
}


def _entity_identity(path: str, after: JsonValue | None) -> str:
    id_field = _COLLECTION_ID_FIELDS.get(path)
    if id_field is None or not isinstance(after, dict) or id_field not in after:
        raise DocumentReviewError(f"{path} addition requires {id_field or 'an ID'}")
    return str(after[id_field])


def _canonical_semantic_after(value: JsonValue | None) -> bytes:
    semantic = (
        {
            key: item
            for key, item in value.items()
            if key != "evidence_source_ids"
        }
        if isinstance(value, dict)
        else value
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
            "target_ids": sorted(str(item) for item in change.target_ids),
            "task_ids": sorted(str(item) for item in change.task_ids),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _target_key(change: ReviewableDocumentChange) -> str:
    canonical = _canonical_semantic_after(change.after)
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
    run_id: UUID,
    change_index: int,
    allocated_display_order: int | None,
) -> JsonValue | None:
    value = change.after
    id_field = _COLLECTION_ID_FIELDS.get(change.path)
    generated_id = str(
        uuid5(
            document_id,
            f"consultant:{run_id}:document-entity:{change_index}:0",
        )
    )
    if (
        change.path in {"/duties", "/tasks"}
        and change.operation is DocumentChangeOperation.ADD
        and isinstance(value, dict)
        and value.get("display_order") is None
    ):
        if allocated_display_order is None:
            raise DocumentReviewError("new document entity requires an allocated order")
        value = {
            **value,
            "display_order": allocated_display_order,
        }
    if (
        change.path == "/opks"
        and change.operation is DocumentChangeOperation.ADD
        and (isinstance(value, str) or isinstance(value, dict))
    ):
        if change.opks_kind is None:
            raise DocumentReviewError("OPKS add requires an OPKS kind")
        if allocated_display_order is None:
            raise DocumentReviewError("new OPKS item requires an allocated order")
        value = (
            {
                "item_id": generated_id,
                "text": value,
                "display_order": allocated_display_order,
            }
            if isinstance(value, str)
            else {
                **value,
                "display_order": allocated_display_order,
            }
        )
    if (
        id_field is not None
        and change.operation is DocumentChangeOperation.ADD
        and isinstance(value, dict)
        and value.get(id_field) is None
    ):
        value = {
            **value,
            id_field: generated_id,
        }
    if (
        id_field is not None
        and change.operation
        in {DocumentChangeOperation.MERGE, DocumentChangeOperation.SPLIT}
    ):
        replacements = value if isinstance(value, list) else [value]
        assigned: list[JsonValue] = []
        for replacement_index, item in enumerate(replacements):
            if not isinstance(item, dict):
                raise DocumentReviewError("merge or split requires replacement objects")
            assigned.append(
                item
                if item.get(id_field) is not None
                else {
                    **item,
                    id_field: str(
                        uuid5(
                            document_id,
                            "consultant:"
                            f"{run_id}:document-entity:{change_index}:"
                            f"{replacement_index}",
                        )
                    ),
                }
            )
        value = assigned if isinstance(value, list) else assigned[0]
    if not change.path.startswith("/opks"):
        return value
    if change.operation is DocumentChangeOperation.ADD:
        if not isinstance(value, dict) or change.opks_kind is None:
            raise DocumentReviewError("OPKS add requires a complete typed object")
        return {
            **value,
            "kind": change.opks_kind.value,
            "task_ids": [str(item) for item in change.task_ids],
            "indicator_ids": [str(item) for item in change.indicator_ids],
            "evidence_source_ids": [str(item) for item in change.basis.source_ids],
        }
    if change.operation in {
        DocumentChangeOperation.MERGE,
        DocumentChangeOperation.SPLIT,
    }:
        replacements = value if isinstance(value, list) else [value]
        normalized: list[JsonValue] = []
        for item in replacements:
            if not isinstance(item, dict):
                raise DocumentReviewError("OPKS replacement requires objects")
            normalized.append(
                {
                    **item,
                    "evidence_source_ids": [str(source) for source in change.basis.source_ids],
                }
            )
        return normalized
    return value


def _ensure_opks_axis_matches_document(
    change: ReviewableDocumentChange,
    document: ApprovedJobDocument,
) -> None:
    if not change.path.startswith("/opks") or change.opks_kind is None:
        return
    expected = change.opks_kind.value
    known = {str(item.item_id): item.kind.value for item in document.opks}
    identities: tuple[str, ...]
    if change.operation in {
        DocumentChangeOperation.MERGE,
        DocumentChangeOperation.SPLIT,
    }:
        identities = tuple(str(item) for item in change.target_ids)
    else:
        parts = change.path.strip("/").split("/")
        identities = (parts[1],) if len(parts) >= 2 else ()
    for identity in identities:
        actual = known.get(identity)
        if actual is not None and actual != expected:
            raise DocumentReviewError(
                "model-authored OPKS change does not match the existing axis"
            )


def _read_paths(
    change: ReviewableDocumentChange,
    normalized_after: JsonValue | None,
) -> tuple[str, ...]:
    if change.operation is DocumentChangeOperation.ADD:
        return (f"{change.path}/{_entity_identity(change.path, normalized_after)}",)
    if change.operation in {
        DocumentChangeOperation.MERGE,
        DocumentChangeOperation.SPLIT,
    }:
        paths = [f"{change.path}/{item}" for item in change.target_ids]
        replacements = normalized_after if isinstance(normalized_after, list) else [normalized_after]
        id_field = _COLLECTION_ID_FIELDS.get(change.path)
        if id_field is None:
            raise DocumentReviewError("merge or split requires a stable collection")
        for item in replacements:
            if isinstance(item, dict) and item.get(id_field) is not None:
                replacement_path = f"{change.path}/{item[id_field]}"
                if replacement_path not in paths:
                    paths.append(replacement_path)
        return tuple(paths)
    return (change.path,)


def _before_value(
    document: ApprovedJobDocument,
    change: ReviewableDocumentChange,
) -> JsonValue | None:
    if change.operation is DocumentChangeOperation.ADD:
        return None
    if change.operation in {
        DocumentChangeOperation.MERGE,
        DocumentChangeOperation.SPLIT,
    }:
        return [
            read_document_path(document, f"{change.path}/{identity}")
            for identity in change.target_ids
        ]
    return read_document_path(document, change.path)


def _affected_work_ids(
    change: ReviewableDocumentChange,
    interview_work: Mapping[str, dict[str, Any]],
) -> tuple[UUID, ...]:
    subject_ids: set[UUID] = set()
    parts = change.path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] in {"duties", "tasks", "opks"}:
        try:
            subject_ids.add(UUID(parts[1]))
        except ValueError:
            pass
    subject_ids.update(change.target_ids)
    subject_ids.update(change.task_ids)
    affected = [
        item.work_id
        for item in (
            InterviewWorkItem.model_validate(value) for value in interview_work.values()
        )
        if item.subject_id in subject_ids
    ]
    return tuple(sorted(set(affected), key=str))


def _blocks_dependent_analysis(
    change: ReviewableDocumentChange,
    operation: DocumentPatchOperation,
) -> bool:
    return (
        operation in _STRUCTURAL_OPERATIONS
        or change.path.endswith("/responsibility_role")
    )


def _read_set_key(action: DocumentPatchAction) -> tuple[tuple[str, str], ...]:
    return tuple((item.path, item.value_sha256) for item in action.read_set)


def _with_employee_source(
    action: DocumentPatchAction,
    source_id: UUID,
) -> DocumentPatchAction:
    if source_id in action.source_ids:
        return action
    return action.model_copy(update={"source_ids": (*action.source_ids, source_id)})


def _ensure_not_rejected_without_new_evidence(
    action: DocumentPatchAction,
    existing_review_queue: Mapping[str, dict[str, Any]],
) -> None:
    for raw_bundle in existing_review_queue.values():
        bundle = DocumentChangeSet.model_validate(raw_bundle)
        for previous in bundle.actions:
            new_source_ids = set(action.source_ids) - set(previous.source_ids)
            if (
                previous.status is DocumentChangeStatus.REJECTED
                and previous.target_key == action.target_key
                and _read_set_key(previous) == _read_set_key(action)
                and not new_source_ids
            ):
                raise RejectedChangeRequiresNewEvidence(
                    f"rejected target {action.target_key} requires new employee evidence"
                )


def _replacement_entities(action: DocumentPatchAction) -> tuple[dict[str, Any], ...]:
    if action.operation is DocumentPatchOperation.ADD:
        return (action.after,) if isinstance(action.after, dict) else ()
    if action.operation in {
        DocumentPatchOperation.MERGE,
        DocumentPatchOperation.SPLIT,
    }:
        values = action.after if isinstance(action.after, list) else [action.after]
        return tuple(item for item in values if isinstance(item, dict))
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
    target = _entity_target_from_path(action.path)
    if target == (collection, identity):
        return True
    return (
        action.operation
        in {DocumentPatchOperation.MERGE, DocumentPatchOperation.SPLIT}
        and action.path == collection
        and identity in {str(item) for item in action.target_ids}
    )


def _link_required_groups(
    document_id: UUID,
    run_id: UUID,
    document: ApprovedJobDocument,
    actions: list[DocumentPatchAction],
) -> list[DocumentPatchAction]:
    creators: dict[tuple[str, str], int] = {}
    for index, action in enumerate(actions):
        collection = _entity_collection(action.path)
        id_field = _COLLECTION_ID_FIELDS.get(collection or "")
        if id_field is None:
            continue
        for entity in _replacement_entities(action):
            if entity.get(id_field) is not None:
                creators[(collection, str(entity[id_field]))] = index

    index_by_action_id = {
        action.action_id: index for index, action in enumerate(actions)
    }
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
            grouped_by_explicit_id.setdefault(action.atomic_subgroup_id, []).append(
                index
            )
    for members in grouped_by_explicit_id.values():
        for member in members[1:]:
            atomic_links.add((members[0], member))

    def depend(consumer: int, prerequisite: int) -> None:
        if consumer != prerequisite:
            dependencies[consumer].add(prerequisite)

    for index, action in enumerate(actions):
        if action.path.startswith("/tasks"):
            duty_id: Any = None
            if action.operation is DocumentPatchOperation.REASSIGN:
                duty_id = action.after
            elif isinstance(action.after, dict):
                duty_id = action.after.get("duty_id")
            if duty_id is not None and ("/duties", str(duty_id)) in creators:
                creator = creators[("/duties", str(duty_id))]
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

    removed: list[tuple[int, str, str]] = []
    for index, action in enumerate(actions):
        if action.operation is DocumentPatchOperation.WITHDRAW:
            target = _entity_target_from_path(action.path)
            if target is not None:
                removed.append((index, *target))
        elif action.operation in {
            DocumentPatchOperation.MERGE,
            DocumentPatchOperation.SPLIT,
        }:
            collection = _entity_collection(action.path)
            if collection is not None:
                removed.extend(
                    (index, collection, str(identity))
                    for identity in action.target_ids
                )

    payload = document.model_dump(mode="json")
    for structural_index, collection, identity in removed:
        dependent_entities: list[tuple[str, str]] = []
        if collection == "/duties":
            dependent_entities.extend(
                ("/tasks", str(item["task_id"]))
                for item in payload["tasks"]
                if str(item.get("duty_id")) == identity
            )
        elif collection == "/tasks":
            dependent_entities.extend(
                ("/opks", str(item["item_id"]))
                for item in payload["opks"]
                if identity in {str(value) for value in item.get("task_ids", [])}
            )
        elif collection == "/opks":
            dependent_entities.extend(
                ("/opks", str(item["item_id"]))
                for item in payload["opks"]
                if identity in {
                    str(value) for value in item.get("indicator_ids", [])
                }
            )
        for dependent_collection, dependent_identity in dependent_entities:
            mutators = [
                index
                for index, candidate in enumerate(actions)
                if _action_affects_entity(
                    candidate, dependent_collection, dependent_identity
                )
            ]
            for mutator in mutators:
                atomic_links.add((structural_index, mutator))

    for index, action in enumerate(actions):
        if not action.path.endswith("/display_order"):
            continue
        target = _entity_target_from_path(action.path)
        if target is None:
            continue
        collection, identity = target
        id_field = _COLLECTION_ID_FIELDS[collection]
        current_items = payload[collection.lstrip("/")]
        collided = next(
            (
                str(item[id_field])
                for item in current_items
                if item.get("display_order") == action.after
                and str(item[id_field]) != identity
            ),
            None,
        )
        if collided is None:
            continue
        for other_index, candidate in enumerate(actions):
            if candidate.path == f"{collection}/{collided}/display_order":
                atomic_links.add((index, other_index))

    adjacency: dict[int, set[int]] = {index: set() for index in dependencies}
    for left, right in atomic_links:
        adjacency[left].add(right)
        adjacency[right].add(left)
    for index, action in enumerate(actions):
        if action.operation in {
            DocumentPatchOperation.MERGE,
            DocumentPatchOperation.SPLIT,
        }:
            adjacency[index].add(index)

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
        requires_group = len(component) > 1 or any(
            grouped[index].operation
            in {DocumentPatchOperation.MERGE, DocumentPatchOperation.SPLIT}
            for index in component
        )
        group_id = (
            uuid5(
                document_id,
                "consultant:"
                f"{run_id}:atomic-component:"
                + ",".join(map(str, sorted(component))),
            )
            if requires_group
            else None
        )
        member_work_ids = tuple(
            sorted(
                {
                    work_id
                    for index in component
                    for work_id in grouped[index].affected_work_ids
                },
                key=str,
            )
        )
        component_blocks = any(
            grouped[index].blocks_dependent_analysis for index in component
        )
        for index in component:
            action = grouped[index]
            grouped[index] = action.model_copy(
                update={
                    "atomic_subgroup_id": group_id,
                    "depends_on_action_ids": tuple(
                        sorted(
                            set(action.depends_on_action_ids)
                            | {
                                grouped[prerequisite].action_id
                                for prerequisite in dependencies[index]
                            },
                            key=str,
                        )
                    ),
                    "affected_work_ids": member_work_ids,
                    "blocks_dependent_analysis": (
                        component_blocks and bool(member_work_ids)
                    ),
                }
            )
    return grouped


def create_document_changeset(
    *,
    document_id: UUID,
    run_id: UUID,
    summary: str,
    read_revision: int,
    document: ApprovedJobDocument,
    changes: Sequence[ReviewableDocumentChange],
    existing_review_queue: Mapping[str, dict[str, Any]],
    interview_work: Mapping[str, dict[str, Any]],
    external_dependency_action_ids: Sequence[UUID] = (),
) -> DocumentChangeSet:
    """Turn verified model semantics into replay-stable application patch actions."""

    if not changes:
        raise DocumentReviewError("cannot create an empty document changeset")
    if document.document_id != document_id:
        raise DocumentReviewError("review document scope does not match")
    next_display_orders = {
        "/duties": max(
            (item.display_order for item in document.duties), default=-1
        )
        + 1,
        "/tasks": max(
            (item.display_order for item in document.tasks), default=-1
        )
        + 1,
    }
    for item in document.opks:
        key = f"/opks:{item.kind.value}"
        next_display_orders[key] = max(
            next_display_orders.get(key, 0), item.display_order + 1
        )
    action_ids_by_change_ref = {
        change.change_ref: uuid5(
            document_id,
            f"consultant:{run_id}:patch-action:{index}",
        )
        for index, change in enumerate(changes)
        if change.change_ref
    }
    actions: list[DocumentPatchAction] = []
    for index, change in enumerate(changes):
        _ensure_opks_axis_matches_document(change, document)
        order_key: str | None = None
        if change.operation is DocumentChangeOperation.ADD:
            if (
                change.path in {"/duties", "/tasks"}
                and isinstance(change.after, dict)
                and change.after.get("display_order") is None
            ):
                order_key = change.path
            elif (
                change.path == "/opks"
                and change.opks_kind is not None
                and (
                    isinstance(change.after, str)
                    or (
                        isinstance(change.after, dict)
                        and change.after.get("display_order") is None
                    )
                )
            ):
                order_key = f"/opks:{change.opks_kind.value}"
        allocated_display_order = None
        if order_key is not None:
            allocated_display_order = next_display_orders.get(order_key, 0)
            next_display_orders[order_key] = allocated_display_order + 1
        after = _normalized_after(
            change,
            document_id=document_id,
            run_id=run_id,
            change_index=index,
            allocated_display_order=allocated_display_order,
        )
        read_paths = _read_paths(change, after)
        operation = DocumentPatchOperation(change.operation.value)
        action_id = uuid5(document_id, f"consultant:{run_id}:patch-action:{index}")
        if change.atomic_group_ref:
            atomic_group = uuid5(
                document_id,
                f"consultant:{run_id}:atomic-ref:{change.atomic_group_ref}",
            )
        elif operation in {
            DocumentPatchOperation.MERGE,
            DocumentPatchOperation.SPLIT,
        }:
            atomic_group = uuid5(document_id, f"consultant:{run_id}:atomic:{index}")
        else:
            atomic_group = None
        local_dependencies = tuple(
            action_ids_by_change_ref[change_ref]
            for change_ref in change.depends_on_change_refs
        )
        action = DocumentPatchAction(
            action_id=action_id,
            operation=operation,
            path=change.path,
            target_key=_target_key(change),
            before=_before_value(document, change),
            after=after,
            source_ids=tuple(sorted(change.basis.source_ids, key=str)),
            quote_anchors=change.basis.quote_anchors,
            read_set=tuple(
                DocumentPathRead(
                    path=path,
                    value_sha256=document_path_sha256(document, path),
                )
                for path in read_paths
            ),
            target_ids=change.target_ids,
            depends_on_action_ids=tuple(
                sorted(
                    {*local_dependencies, *change.depends_on_action_ids},
                    key=str,
                )
            ),
            supersedes_action_ids=change.supersedes_action_ids,
            atomic_subgroup_id=atomic_group,
            affected_work_ids=_affected_work_ids(change, interview_work),
            blocks_dependent_analysis=_blocks_dependent_analysis(
                change,
                operation,
            ),
        )
        actions.append(action)
    actions = _link_required_groups(document_id, run_id, document, actions)
    try:
        apply_document_actions(document, tuple(actions))
    except DocumentAuthorityError as error:
        raise DocumentReviewError(
            f"model-authored document changes do not form a valid review state: {error}"
        ) from error
    for action in actions:
        _ensure_not_rejected_without_new_evidence(action, existing_review_queue)
    bundle = DocumentChangeSet(
        changeset_id=uuid5(document_id, f"consultant:{run_id}:document-changes"),
        summary=summary,
        actions=tuple(actions),
        source_ids=tuple(
            sorted(
                {source_id for action in actions for source_id in action.source_ids},
                key=str,
            )
        ),
        created_revision=read_revision,
        external_dependency_action_ids=tuple(
            dict.fromkeys(external_dependency_action_ids)
        ),
    )
    existing = existing_review_queue.get(str(bundle.changeset_id))
    if existing is not None and DocumentChangeSet.model_validate(existing) != bundle:
        raise DocumentReviewError("deterministic changeset replay changed its payload")
    return DocumentChangeSet.model_validate(existing) if existing is not None else bundle


def block_review_dependent_work(
    interview_work: Mapping[str, dict[str, Any]],
    actions: Sequence[DocumentPatchAction],
    *,
    revision: int,
) -> dict[str, dict[str, Any]]:
    blockers_by_work: dict[UUID, list[UUID]] = {}
    for action in actions:
        if not action.blocks_dependent_analysis:
            continue
        for work_id in action.affected_work_ids:
            blockers_by_work.setdefault(work_id, []).append(action.action_id)
    updated = dict(interview_work)
    for key, raw in interview_work.items():
        item = InterviewWorkItem.model_validate(raw)
        new_blockers = blockers_by_work.get(item.work_id)
        if not new_blockers:
            continue
        existing = list(item.blocked_by_decision_ids)
        for blocker in new_blockers:
            if blocker not in existing:
                existing.append(blocker)
        resume_status = item.resume_status
        if resume_status is None:
            resume_status = (
                item.status
                if item.status is not InterviewWorkStatus.BLOCKED
                else InterviewWorkStatus.AVAILABLE
            )
        updated[key] = item.model_copy(
            update={
                "status": InterviewWorkStatus.BLOCKED,
                "blocked_by_decision_ids": tuple(existing),
                "resume_status": resume_status,
                "priority_reason": "相關文件結構仍待員工決定，先暫停這個分析分支。",
                "last_changed_revision": revision,
            }
        ).model_dump(mode="json")
    return updated


def _selected_actions(
    bundle: DocumentChangeSet,
    action_ids: Sequence[UUID],
) -> tuple[DocumentPatchAction, ...]:
    if not action_ids or len(action_ids) != len(set(action_ids)):
        raise DocumentReviewError("review command requires unique action IDs")
    by_id = {item.action_id: item for item in bundle.actions}
    unknown = set(action_ids) - set(by_id)
    if unknown:
        raise DocumentReviewError(f"unknown patch action IDs: {sorted(map(str, unknown))}")
    selected = tuple(
        item for item in bundle.actions if item.action_id in set(action_ids)
    )
    unselectable = [
        item.action_id
        for item in selected
        if item.status not in _UNRESOLVED_STATUSES
    ]
    if unselectable:
        raise DocumentReviewError(
            "only pending or deferred patch actions can be selected: "
            + ", ".join(map(str, unselectable))
        )
    return selected


def _require_atomic_subgroups(
    bundle: DocumentChangeSet,
    selected: Sequence[DocumentPatchAction],
) -> None:
    selected_ids = {item.action_id for item in selected}
    for action in selected:
        if action.atomic_subgroup_id is None:
            continue
        unresolved_group = {
            item.action_id
            for item in bundle.actions
            if item.atomic_subgroup_id == action.atomic_subgroup_id
            and item.status in _UNRESOLVED_STATUSES
        }
        if not unresolved_group <= selected_ids:
            raise AtomicSubgroupIncomplete(
                f"atomic subgroup {action.atomic_subgroup_id} must be decided together"
            )


def _require_dependencies(
    review_queue: Mapping[str, dict[str, Any]],
    bundle: DocumentChangeSet,
    selected: Sequence[DocumentPatchAction],
) -> None:
    selected_ids = {item.action_id for item in selected}
    by_id: dict[UUID, DocumentPatchAction] = {}
    for raw in review_queue.values():
        candidate_bundle = DocumentChangeSet.model_validate(raw)
        for candidate in candidate_bundle.actions:
            if candidate.action_id in by_id:
                raise DocumentReviewError(
                    f"duplicate review action identity {candidate.action_id}"
                )
            by_id[candidate.action_id] = candidate
    for action in selected:
        for dependency_id in action.depends_on_action_ids:
            dependency = by_id.get(dependency_id)
            if dependency is None:
                raise ReviewDependencyUnresolved(
                    f"patch action {action.action_id} has missing dependency {dependency_id}"
                )
            if dependency_id not in selected_ids and dependency.status not in {
                DocumentChangeStatus.ACCEPTED,
                DocumentChangeStatus.EDIT_ACCEPTED,
            }:
                raise ReviewDependencyUnresolved(
                    f"patch action {action.action_id} depends on {dependency_id}"
                )


def _read_set_is_current(
    document: ApprovedJobDocument,
    action: DocumentPatchAction,
) -> bool:
    return all(
        document_path_sha256(document, item.path) == item.value_sha256
        for item in action.read_set
    )


def _stale_action(action: DocumentPatchAction, reason: str) -> DocumentPatchAction:
    return action.model_copy(
        update={
            "status": DocumentChangeStatus.STALE,
            "stale_reason": reason,
            "employee_after": None,
            "rejection_reason": None,
        }
    )


def _cascade_atomic_staleness(
    actions: tuple[DocumentPatchAction, ...],
    reason: str,
) -> tuple[DocumentPatchAction, ...]:
    stale_groups = {
        action.atomic_subgroup_id
        for action in actions
        if action.status is DocumentChangeStatus.STALE
        and action.atomic_subgroup_id is not None
    }
    if not stale_groups:
        return actions
    return tuple(
        _stale_action(action, reason)
        if action.atomic_subgroup_id in stale_groups
        and action.status in _UNRESOLVED_STATUSES
        else action
        for action in actions
    )


def revalidate_review_queue(
    document: ApprovedJobDocument,
    review_queue: Mapping[str, dict[str, Any]],
    *,
    stale_reason: str,
) -> dict[str, dict[str, Any]]:
    bundles = {
        key: DocumentChangeSet.model_validate(raw)
        for key, raw in review_queue.items()
    }
    actions_by_id: dict[UUID, DocumentPatchAction] = {}
    for bundle in bundles.values():
        for action in bundle.actions:
            if action.action_id in actions_by_id:
                raise DocumentReviewError(
                    f"duplicate review action identity {action.action_id}"
                )
            actions_by_id[action.action_id] = action

    dependency_reason = (
        "前置審核動作已被拒絕、失效或不存在，請重新建立這項建議。"
    )
    while True:
        changed = False
        next_actions = dict(actions_by_id)
        for action_id, action in actions_by_id.items():
            if action.status not in _UNRESOLVED_STATUSES:
                continue
            dependencies = tuple(
                actions_by_id.get(dependency_id)
                for dependency_id in action.depends_on_action_ids
            )
            has_failed_dependency = any(
                dependency is None
                or dependency.status
                in {
                    DocumentChangeStatus.REJECTED,
                    DocumentChangeStatus.STALE,
                }
                for dependency in dependencies
            )
            has_unresolved_dependency = any(
                dependency is not None
                and dependency.status in _UNRESOLVED_STATUSES
                for dependency in dependencies
            )
            if has_failed_dependency:
                next_actions[action_id] = _stale_action(action, dependency_reason)
                changed = True
            elif not has_unresolved_dependency and not _read_set_is_current(
                document, action
            ):
                next_actions[action_id] = _stale_action(action, stale_reason)
                changed = True

        for bundle in bundles.values():
            current_actions = tuple(
                next_actions[action.action_id] for action in bundle.actions
            )
            cascaded = _cascade_atomic_staleness(current_actions, stale_reason)
            for before, after in zip(current_actions, cascaded, strict=True):
                if before != after:
                    next_actions[after.action_id] = after
                    changed = True
        actions_by_id = next_actions
        if not changed:
            break

    updated: dict[str, dict[str, Any]] = {}
    for key, bundle in bundles.items():
        actions = tuple(actions_by_id[action.action_id] for action in bundle.actions)
        updated[key] = bundle.model_copy(update={"actions": actions}).model_dump(
            mode="json"
        )
    return updated


def stale_review_queue_for_source_correction(
    review_queue: Mapping[str, dict[str, Any]],
    *,
    superseded_source_id: UUID,
) -> dict[str, dict[str, Any]]:
    reason = "員工已更正這項建議所依據的原話，請依最新說法重新分析。"
    updated: dict[str, dict[str, Any]] = {}
    for key, raw in review_queue.items():
        bundle = DocumentChangeSet.model_validate(raw)
        actions = tuple(
            _stale_action(action, reason)
            if action.status in _UNRESOLVED_STATUSES
            and superseded_source_id in action.source_ids
            else action
            for action in bundle.actions
        )
        actions = _cascade_atomic_staleness(actions, reason)
        updated[key] = bundle.model_copy(update={"actions": actions}).model_dump(
            mode="json"
        )
    return updated


def stale_superseded_review_actions(
    review_queue: Mapping[str, dict[str, Any]],
    *,
    published_changeset: DocumentChangeSet,
) -> dict[str, dict[str, Any]]:
    """Atomically preserve and stale only explicitly superseded unresolved actions."""

    superseded_ids = {
        action_id
        for action in published_changeset.actions
        for action_id in action.supersedes_action_ids
    }
    if not superseded_ids:
        return dict(review_queue)
    known_actions = {
        action.action_id
        for raw in review_queue.values()
        for action in DocumentChangeSet.model_validate(raw).actions
    }
    unknown = superseded_ids - known_actions
    if unknown:
        raise DocumentReviewError(
            "supersession references unknown review actions: "
            + ", ".join(str(item) for item in sorted(unknown, key=str))
        )
    reason = "這項待審核建議已被同一顧問回合的新候選明確取代。"
    updated: dict[str, dict[str, Any]] = {}
    for key, raw in review_queue.items():
        bundle = DocumentChangeSet.model_validate(raw)
        actions = tuple(
            _stale_action(action, reason)
            if action.action_id in superseded_ids
            and action.status in _UNRESOLVED_STATUSES
            else action
            for action in bundle.actions
        )
        actions = _cascade_atomic_staleness(actions, reason)
        updated[key] = bundle.model_copy(update={"actions": actions}).model_dump(
            mode="json"
        )
    return updated


def _unblock_resolved_work(
    interview_work: Mapping[str, dict[str, Any]],
    review_queue: Mapping[str, dict[str, Any]],
    *,
    revision: int,
    resolved_reason: str = "員工已處理結構前提，這個工作可重新檢查。",
) -> dict[str, dict[str, Any]]:
    review_action_ids = {
        action.action_id
        for raw in review_queue.values()
        for action in DocumentChangeSet.model_validate(raw).actions
    }
    unresolved = {
        action.action_id
        for raw in review_queue.values()
        for action in DocumentChangeSet.model_validate(raw).actions
        if action.status in _UNRESOLVED_STATUSES
        and action.blocks_dependent_analysis
    }
    updated = dict(interview_work)
    for key, raw in interview_work.items():
        item = InterviewWorkItem.model_validate(raw)
        if not item.blocked_by_decision_ids:
            continue
        remaining = tuple(
            decision_id
            for decision_id in item.blocked_by_decision_ids
            if decision_id not in review_action_ids or decision_id in unresolved
        )
        if remaining:
            if remaining != item.blocked_by_decision_ids:
                updated[key] = item.model_copy(
                    update={"blocked_by_decision_ids": remaining}
                ).model_dump(mode="json")
            continue
        updated[key] = item.model_copy(
            update={
                "status": item.resume_status or InterviewWorkStatus.AVAILABLE,
                "blocked_by_decision_ids": (),
                "resume_status": None,
                "priority_reason": resolved_reason,
                "last_changed_revision": revision,
            }
        ).model_dump(mode="json")
    return updated


def revalidate_review_work(
    interview_work: Mapping[str, dict[str, Any]],
    review_queue: Mapping[str, dict[str, Any]],
    *,
    revision: int,
    resolved_reason: str,
) -> dict[str, dict[str, Any]]:
    """Remove only resolved review-action blockers, preserving other decisions."""

    return _unblock_resolved_work(
        interview_work,
        review_queue,
        revision=revision,
        resolved_reason=resolved_reason,
    )


def _revalidate_downstream_understanding(
    understanding: Mapping[str, dict[str, Any]],
    affected_work_ids: set[UUID],
) -> dict[str, dict[str, Any]]:
    updated = dict(understanding)
    for key, raw in understanding.items():
        item = UnderstandingItem.model_validate(raw)
        if (
            item.status
            in {
                UnderstandingStatus.ACTIVE,
                UnderstandingStatus.EMPLOYEE_CONFIRMED,
            }
            and set(item.work_ids) & affected_work_ids
        ):
            updated[key] = item.model_copy(
                update={"status": UnderstandingStatus.CHALLENGED}
            ).model_dump(mode="json")
    return updated


def _resolve_decision_gaps(
    gaps: Mapping[str, dict[str, Any]],
    affected_subject_ids: set[UUID],
    *,
    revision: int,
) -> dict[str, dict[str, Any]]:
    updated = dict(gaps)
    for key, raw in gaps.items():
        item = GapItem.model_validate(raw)
        if (
            item.reason == "employee_decision_pending"
            and item.status is not GapStatus.RESOLVED
            and item.subject_id in affected_subject_ids
        ):
            updated[key] = item.model_copy(
                update={
                    "status": GapStatus.RESOLVED,
                    "last_changed_revision": revision,
                }
            ).model_dump(mode="json")
    return updated


def apply_review_command(
    state: Mapping[str, Any],
    *,
    action: ReviewCommand,
    changeset_id: UUID,
    action_ids: Sequence[UUID],
    revision: int,
    edited_after_by_action_id: Mapping[UUID, JsonValue | None] | None = None,
    rejection_reason: str | None = None,
    source_reference: SourceReference | None = None,
) -> dict[str, Any]:
    review_queue = dict(state.get("review_queue", {}))
    raw_bundle = review_queue.get(str(changeset_id))
    if raw_bundle is None:
        raise DocumentReviewError(f"changeset {changeset_id} was not found")
    bundle = DocumentChangeSet.model_validate(raw_bundle)
    selected = _selected_actions(bundle, action_ids)
    _require_atomic_subgroups(bundle, selected)
    if action in {"accept_changes", "edit_and_accept_changes"}:
        _require_dependencies(review_queue, bundle, selected)
    if action in {"accept_changes", "reject_changes", "defer_changes"} and source_reference:
        raise DocumentReviewError(f"{action} must not create employee evidence")
    if source_reference is not None and source_reference.kind.value != "direct_edit":
        raise DocumentReviewError("edit-and-accept requires direct-edit evidence")
    edited = dict(edited_after_by_action_id or {})
    selected_ids = {item.action_id for item in selected}
    if not set(edited) <= selected_ids:
        raise DocumentReviewError("employee edits include an unselected patch action")
    if action == "edit_and_accept_changes" and not edited:
        raise DocumentReviewError("edit-and-accept requires an employee edit")
    if action != "edit_and_accept_changes" and edited:
        raise DocumentReviewError("only edit-and-accept may carry employee edits")
    if action == "reject_changes" and not (rejection_reason or "").strip():
        raise DocumentReviewError("rejecting a document change requires a reason")
    if action == "edit_and_accept_changes" and any(
        item.status is DocumentChangeStatus.STALE for item in selected
    ):
        raise DocumentReviewError("a stale change cannot be edit-accepted")
    if action == "edit_and_accept_changes":
        employee_text = edited_action_source_payload(selected, edited)
        if employee_text is not None and source_reference is None:
            raise DocumentReviewError(
                "employee-authored text requires a direct-edit source"
            )
        if employee_text is None and source_reference is not None:
            raise DocumentReviewError(
                "non-text edit-and-accept must not mint work-fact evidence"
            )

    document = ApprovedJobDocument.model_validate(state["approved_document"])
    changed_actions: dict[UUID, DocumentPatchAction] = {}
    affected_work_ids: set[UUID] = set()
    affected_subject_ids: set[UUID] = set()
    if action in {"accept_changes", "edit_and_accept_changes"}:
        stale = [item for item in selected if not _read_set_is_current(document, item)]
        stale_groups = {item.atomic_subgroup_id for item in stale if item.atomic_subgroup_id}
        stale_ids = {item.action_id for item in stale}
        if stale_groups:
            stale_ids.update(
                item.action_id
                for item in selected
                if item.atomic_subgroup_id in stale_groups
            )
        applicable = tuple(item for item in selected if item.action_id not in stale_ids)
        for item in selected:
            if item.action_id in stale_ids:
                changed_actions[item.action_id] = _stale_action(
                    item,
                    "核准文件在這個建議建立後已變更，請重新檢查。",
                )
        if applicable:
            employee_evidence_action_ids = {
                item.action_id
                for item in applicable
                if item.action_id in edited
                and edited_action_source_payload(
                    (item,), {item.action_id: edited[item.action_id]}
                )
                is not None
            }
            authority_actions = tuple(
                _with_employee_source(item, source_reference.source_id)
                if (
                    source_reference is not None
                    and item.action_id in employee_evidence_action_ids
                )
                else item
                for item in applicable
            )
            authority_action_by_id = {
                item.action_id: item for item in authority_actions
            }
            try:
                document = apply_document_actions(
                    document,
                    authority_actions,
                    edited_after_by_action_id=edited,
                )
            except DocumentAuthorityError as error:
                if action == "edit_and_accept_changes":
                    raise DocumentReviewError(
                        f"employee-edited document change is invalid: {error}"
                    ) from error
                for item in applicable:
                    changed_actions[item.action_id] = _stale_action(
                        item,
                        f"文件結構已不再允許這項變更：{error}",
                    )
            else:
                for item in applicable:
                    employee_after = edited.get(item.action_id)
                    changed_actions[item.action_id] = authority_action_by_id[
                        item.action_id
                    ].model_copy(
                        update={
                            "status": (
                                DocumentChangeStatus.EDIT_ACCEPTED
                                if item.action_id in edited
                                else DocumentChangeStatus.ACCEPTED
                            ),
                            "employee_after": employee_after,
                            "rejection_reason": None,
                            "stale_reason": None,
                        }
                    )
                    if item.blocks_dependent_analysis:
                        affected_work_ids.update(item.affected_work_ids)
    elif action == "reject_changes":
        for item in selected:
            changed_actions[item.action_id] = item.model_copy(
                update={
                    "status": DocumentChangeStatus.REJECTED,
                    "rejection_reason": rejection_reason.strip(),
                    "employee_after": None,
                    "stale_reason": None,
                }
            )
            if item.blocks_dependent_analysis:
                affected_work_ids.update(item.affected_work_ids)
    else:
        for item in selected:
            if item.status is DocumentChangeStatus.STALE:
                raise DocumentReviewError("a stale change cannot be deferred")
            changed_actions[item.action_id] = item.model_copy(
                update={"status": DocumentChangeStatus.DEFERRED}
            )

    updated_actions = tuple(
        changed_actions.get(item.action_id, item) for item in bundle.actions
    )
    updated_bundle = DocumentChangeSet.model_validate(
        bundle.model_copy(
            update={
                "actions": updated_actions,
                "source_ids": tuple(
                    sorted(
                        {
                            source_id
                            for item in updated_actions
                            for source_id in item.source_ids
                        },
                        key=str,
                    )
                ),
            }
        ).model_dump(mode="json")
    )
    review_queue[str(changeset_id)] = updated_bundle.model_dump(mode="json")
    review_queue = revalidate_review_queue(
        document,
        review_queue,
        stale_reason="另一項已接受或直接編輯的內容改變了這項建議的前提。",
    )
    interview_work = _unblock_resolved_work(
        state.get("interview_work", {}),
        review_queue,
        revision=revision,
    )
    for raw in interview_work.values():
        item = InterviewWorkItem.model_validate(raw)
        if item.work_id in affected_work_ids and item.subject_id is not None:
            affected_subject_ids.add(item.subject_id)
    return {
        "approved_document": document.model_dump(mode="json"),
        "review_queue": review_queue,
        "interview_work": interview_work,
        "understanding": _revalidate_downstream_understanding(
            state.get("understanding", {}), affected_work_ids
        ),
        "gaps": _resolve_decision_gaps(
            state.get("gaps", {}), affected_subject_ids, revision=revision
        ),
    }


def stale_review_queue_for_direct_edit(
    before: ApprovedJobDocument,
    after: ApprovedJobDocument,
    review_queue: Mapping[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if before.document_id != after.document_id:
        raise DocumentReviewError("direct edit crosses document scope")
    return revalidate_review_queue(
        after,
        review_queue,
        stale_reason="員工直接修改了這項建議所依賴的文件內容。",
    )


def revalidate_after_direct_edit(
    state: Mapping[str, Any],
    *,
    before: ApprovedJobDocument,
    after: ApprovedJobDocument,
    revision: int,
) -> dict[str, Any]:
    old_queue = {
        key: DocumentChangeSet.model_validate(value)
        for key, value in state.get("review_queue", {}).items()
    }
    review_queue = stale_review_queue_for_direct_edit(
        before,
        after,
        state.get("review_queue", {}),
    )
    new_queue = {
        key: DocumentChangeSet.model_validate(value)
        for key, value in review_queue.items()
    }
    newly_stale = [
        new_action
        for key, old_bundle in old_queue.items()
        for old_action, new_action in zip(
            old_bundle.actions,
            new_queue[key].actions,
            strict=True,
        )
        if old_action.status in {
            DocumentChangeStatus.PENDING,
            DocumentChangeStatus.DEFERRED,
        }
        and new_action.status is DocumentChangeStatus.STALE
    ]
    affected_work_ids = {
        work_id for action in newly_stale for work_id in action.affected_work_ids
    }
    interview_work = _unblock_resolved_work(
        state.get("interview_work", {}),
        review_queue,
        revision=revision,
    )
    affected_subject_ids = {
        item.subject_id
        for item in (
            InterviewWorkItem.model_validate(raw) for raw in interview_work.values()
        )
        if item.work_id in affected_work_ids and item.subject_id is not None
    }
    return {
        "review_queue": review_queue,
        "interview_work": interview_work,
        "understanding": _revalidate_downstream_understanding(
            state.get("understanding", {}), affected_work_ids
        ),
        "gaps": _resolve_decision_gaps(
            state.get("gaps", {}), affected_subject_ids, revision=revision
        ),
    }
