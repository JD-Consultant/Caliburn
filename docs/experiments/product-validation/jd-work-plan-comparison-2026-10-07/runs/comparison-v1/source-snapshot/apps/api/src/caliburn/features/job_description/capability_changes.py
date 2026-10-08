"""Pure, bounded updates: changing a shared definition never copies it into tasks."""

from dataclasses import replace
from uuid import UUID, uuid4

from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityChange,
    CapabilityField,
    CapabilityInUseError,
    CapabilityTargetNotFoundError,
    CreateCapability,
    DeleteCapability,
    InvalidCapabilityChangeError,
    ReorderCapability,
    ReorderTaskCapability,
    ReviseCapability,
    SetTaskCapability,
    TaskCapabilityLink,
)


def _ordered_ids(ids: tuple[UUID, ...], target: UUID, before: UUID | None) -> tuple[UUID, ...]:
    if target not in ids or (before is not None and before not in ids):
        raise CapabilityTargetNotFoundError("Ordering target must belong to the same group")
    if target == before:
        return ids
    remaining = tuple(identity for identity in ids if identity != target)
    index = len(remaining) if before is None else remaining.index(before)
    return (*remaining[:index], target, *remaining[index:])


def apply_capability_change(
    capabilities: tuple[Capability, ...],
    links: tuple[TaskCapabilityLink, ...],
    task_ids: tuple[UUID, ...],
    change: CapabilityChange,
) -> tuple[tuple[Capability, ...], tuple[TaskCapabilityLink, ...], Capability | None]:
    if isinstance(change, CreateCapability):
        created = Capability(uuid4(), uuid4(), change.kind, change.name, change.description)
        return (*capabilities, created), links, created
    by_id = {item.capability_id: item for item in capabilities}
    target = by_id.get(change.capability_id)
    if target is None:
        raise CapabilityTargetNotFoundError("Capability is not selected in this JD")
    if isinstance(change, ReviseCapability):
        name, description = target.name, target.description
        for item in change.changes:
            if item.field is CapabilityField.NAME:
                name = item.value
            else:
                description = item.value
        updated = replace(target, name=name, description=description)
        if updated == target:
            return capabilities, links, None
        updated = replace(updated, content_revision_id=uuid4())
        return tuple(updated if item == target else item for item in capabilities), links, updated
    if isinstance(change, DeleteCapability):
        if any(link.capability_id == target.capability_id for link in links):
            raise CapabilityInUseError("Capability is still linked to a task")
        return tuple(item for item in capabilities if item != target), links, None
    if isinstance(change, ReorderCapability):
        group = tuple(item.capability_id for item in capabilities if item.kind == target.kind)
        ordered = iter(_ordered_ids(group, target.capability_id, change.before_capability_id))
        return (
            tuple(
                by_id[next(ordered)] if item.kind == target.kind else item for item in capabilities
            ),
            links,
            None,
        )
    if change.task_id not in task_ids:
        raise CapabilityTargetNotFoundError("Task is not selected in this JD")
    link = TaskCapabilityLink(change.task_id, target.capability_id)
    if isinstance(change, SetTaskCapability):
        if type(change.linked) is not bool:
            raise InvalidCapabilityChangeError("Choose whether this task uses the capability")
        if change.linked:
            updated_links = links if link in links else (*links, link)
        else:
            updated_links = tuple(item for item in links if item != link)
    elif isinstance(change, ReorderTaskCapability):
        group = tuple(
            item.capability_id
            for item in links
            if item.task_id == change.task_id and by_id[item.capability_id].kind == target.kind
        )
        ordered = iter(_ordered_ids(group, target.capability_id, change.before_capability_id))
        updated_links = tuple(
            TaskCapabilityLink(item.task_id, next(ordered))
            if item.task_id == change.task_id and by_id[item.capability_id].kind == target.kind
            else item
            for item in links
        )
    else:
        raise TypeError("Unsupported capability change")
    # Cross-task ordering has no semantics; keep a stable representation for no-op comparison.
    return capabilities, tuple(sorted(updated_links, key=lambda item: item.task_id)), None


def capability_change_payload(change: CapabilityChange) -> list[dict[str, str | bool | None]]:
    match change:
        case CreateCapability():
            return [
                {
                    "action": "create_capability",
                    "kind": change.kind.value,
                    "name": change.name,
                    "description": change.description,
                }
            ]
        case ReviseCapability():
            payload: list[dict[str, str | bool | None]] = [
                {"action": "revise_capability", "capability_id": str(change.capability_id)}
            ]
            for item in change.changes:
                payload.append({"field": item.field.value, "value": item.value})
            return payload
        case DeleteCapability():
            return [{"action": "delete_capability", "capability_id": str(change.capability_id)}]
        case ReorderCapability():
            return [
                {
                    "action": "reorder_capability",
                    "capability_id": str(change.capability_id),
                    "before_capability_id": str(change.before_capability_id)
                    if change.before_capability_id
                    else None,
                }
            ]
        case SetTaskCapability():
            return [
                {
                    "action": "set_task_capability",
                    "task_id": str(change.task_id),
                    "capability_id": str(change.capability_id),
                    "linked": change.linked,
                }
            ]
        case ReorderTaskCapability():
            return [
                {
                    "action": "reorder_task_capability",
                    "task_id": str(change.task_id),
                    "capability_id": str(change.capability_id),
                    "before_capability_id": str(change.before_capability_id)
                    if change.before_capability_id
                    else None,
                }
            ]
