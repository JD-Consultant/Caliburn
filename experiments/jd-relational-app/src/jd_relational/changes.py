"""Fixed JD stable-ID net differences between two complete v3 snapshots.

This does not reconstruct operation history or produce an executable patch.
Ordering uses Python 3.12 SequenceMatcher on unique sibling identities, with
autojunk=False. Its matching blocks are deterministic, not a promise of minimal
edits or which item a person actually dragged. Position renumbering alone is
not a semantic update. Python reference checked 2026-09-13:
https://docs.python.org/3.12/library/difflib.html#difflib.SequenceMatcher
"""

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from .domain import SOURCE_COLUMNS
from .snapshots import SnapshotValidationError, snapshot_digest


ChangeKind = Literal["create", "update", "delete", "move", "reorder", "link", "unlink"]
EntityKind = Literal["profile", "collaborator", "duty", "task", "detail", "capability", "condition",
                     "task_capability", "source_link"]


@dataclass(frozen=True)
class ChangeRecord:
    """One net event, with complete detached rows and no writable references.

    profile has identity (). Associations use their complete stable keys.
    changed_fields is alphabetically ordered: all row keys for create/delete or
    link/unlink, exact changed non-position fields for update, and exact changed
    structural fields for move/reorder. A reorder may have no changed raw field
    when its numeric position stayed equal but its relative sibling order changed.
    The frozen record contains ordinary detached dicts for simple DTO projection.
    """

    kind: ChangeKind
    entity_kind: EntityKind
    identity: tuple[str, ...]
    before: dict | None
    after: dict | None
    changed_fields: tuple[str, ...]
    affected_task_ids: tuple[str, ...]


# Closed v3 content groups; no configurable paths, table names or patch handlers.
_GROUPS = {
    "collaborator": ("collaborators", ("collaborator_id",)),
    "duty": ("duties", ("duty_id",)),
    "task": ("tasks", ("task_id",)),
    "detail": ("task_details", ("detail_id",)),
    "capability": ("capabilities", ("capability_id",)),
    "condition": ("conditions", ("condition_id",)),
    "task_capability": ("task_capabilities", ("task_id", "capability_id")),
    "source_link": ("source_links", ("source_link_id",)),
}
_ENTITY_ORDER = {kind: i for i, kind in enumerate(("profile", *_GROUPS))}
_KIND_ORDER = {kind: i for i, kind in enumerate(("create", "link", "update", "move", "reorder", "unlink", "delete"))}


def _indexed(snapshot: dict) -> dict:
    return {kind: {tuple(row[field] for field in identity): row for row in snapshot[group]}
            for kind, (group, identity) in _GROUPS.items()}


def _container(kind: str, row: dict) -> tuple:
    if kind == "task":
        return (row["duty_id"],)
    if kind == "detail":
        return (row["task_id"], row["kind"])
    if kind in ("capability", "condition"):
        return (row["kind"],)
    if kind == "task_capability":
        return (row["task_id"],)
    if kind == "source_link":
        return tuple(row[field] for field in SOURCE_COLUMNS)
    return ()


def _reordered(kind: str, before: dict, after: dict) -> set[tuple[str, ...]]:
    stable_groups = defaultdict(set)
    for identity in before.keys() & after.keys():
        container = _container(kind, before[identity])
        if container == _container(kind, after[identity]):
            stable_groups[container].add(identity)
    changed = set()
    for identities in stable_groups.values():
        left = sorted(identities, key=lambda key: (before[key]["position"], key))
        right = sorted(identities, key=lambda key: (after[key]["position"], key))
        if left == right:
            continue
        matched = {identity for block in SequenceMatcher(None, left, right, autojunk=False).get_matching_blocks()
                   for identity in left[block.a:block.a + block.size]}
        changed.update(identities - matched)
    return changed


def compare_snapshots(before: dict, after: dict) -> tuple[ChangeRecord, ...]:
    """Validate same-document snapshots and return deterministic net events.

    Full strict codec validation precedes comparison; nothing is inferred from
    names, current DB rows, receipts or model prose. Definition changes report
    the union of explicitly linked tasks in both versions. Global text has no
    invented task relationship. No DB, source owner, refs or revisions are read.
    """
    snapshot_digest(before)
    snapshot_digest(after)
    if before["document_id"] != after["document_id"]:
        raise SnapshotValidationError("snapshot_document_mismatch")
    old, new = _indexed(before), _indexed(after)
    duty_tasks, capability_tasks, detail_tasks = defaultdict(set), defaultdict(set), defaultdict(set)
    for snapshot in (before, after):
        for row in snapshot["tasks"]:
            if row["duty_id"] is not None:
                duty_tasks[row["duty_id"]].add(row["task_id"])
        for row in snapshot["task_capabilities"]:
            capability_tasks[row["capability_id"]].add(row["task_id"])
        for row in snapshot["task_details"]:
            detail_tasks[row["detail_id"]].add(row["task_id"])

    def affected(kind, left, right):
        tasks = set()
        for row in (left, right):
            if row is None:
                continue
            if kind in ("task", "detail", "task_capability"):
                tasks.add(row["task_id"])
            elif kind == "duty":
                tasks.update(duty_tasks[row["duty_id"]])
            elif kind == "capability":
                tasks.update(capability_tasks[row["capability_id"]])
            elif kind == "source_link":
                for field in ("task_id", "linked_task_id"):
                    if row[field] is not None:
                        tasks.add(row[field])
                tasks.update(duty_tasks.get(row["duty_id"], ()))
                tasks.update(capability_tasks.get(row["capability_id"], ()))
                tasks.update(detail_tasks.get(row["detail_id"], ()))
        return tuple(sorted(tasks))

    result = []

    def emit(kind, entity_kind, identity, left, right, fields):
        result.append(ChangeRecord(kind, entity_kind, identity, deepcopy(left), deepcopy(right),
                                   tuple(sorted(fields)), affected(entity_kind, left, right)))

    fields = tuple(field for field in before["profile"] if before["profile"][field] != after["profile"][field])
    if fields:
        emit("update", "profile", (), before["profile"], after["profile"], fields)
    for entity_kind in _GROUPS:
        left, right = old[entity_kind], new[entity_kind]
        association = entity_kind in ("task_capability", "source_link")
        for identity in left.keys() - right.keys():
            emit("unlink" if association else "delete", entity_kind, identity, left[identity], None, left[identity])
        for identity in right.keys() - left.keys():
            emit("link" if association else "create", entity_kind, identity, None, right[identity], right[identity])
        for identity in left.keys() & right.keys():
            old_row, new_row = left[identity], right[identity]
            fields = {field for field in old_row if old_row[field] != new_row[field]}
            # Only tasks can move between parents in ordinary JD operations.
            # Other field changes are still reported exactly if valid historical
            # material differs; this read does not authorize such a mutation.
            moved = entity_kind == "task" and "duty_id" in fields
            updated = fields - {"position"} - ({"duty_id"} if moved else set())
            if updated:
                emit("update", entity_kind, identity, old_row, new_row, updated)
            if moved:
                emit("move", entity_kind, identity, old_row, new_row, fields & {"duty_id", "position"})
        for identity in _reordered(entity_kind, left, right):
            fields = ("position",) if left[identity]["position"] != right[identity]["position"] else ()
            emit("reorder", entity_kind, identity, left[identity], right[identity], fields)
    return tuple(sorted(result, key=lambda row: (_ENTITY_ORDER[row.entity_kind], row.identity, _KIND_ORDER[row.kind])))
