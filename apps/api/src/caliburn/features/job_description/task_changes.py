"""Pure task editing, stable identities, independent detail order and scope checks."""

from dataclasses import replace
from uuid import UUID, uuid4

from caliburn.features.job_description.tasks import (
    AddTaskDetail,
    CreateTask,
    DeleteTask,
    DetailKind,
    InvalidTaskChangeError,
    MoveTask,
    RemoveTaskDetail,
    ReorderTaskDetail,
    ReviseTask,
    ReviseTaskDetail,
    SetTaskField,
    TaskChange,
    TaskDetail,
    TaskEdit,
    TaskField,
    TaskTargetNotFoundError,
    WorkTask,
)


def _ordered_details(details: tuple[TaskDetail, ...]) -> tuple[TaskDetail, ...]:
    return tuple(detail for kind in DetailKind for detail in details if detail.kind == kind)


def order_tasks(tasks: tuple[WorkTask, ...], area_ids: tuple[UUID, ...]) -> tuple[WorkTask, ...]:
    """Canonical collection order; positions inside each group remain independent."""
    if any(task.area_id is not None and task.area_id not in area_ids for task in tasks):
        raise TaskTargetNotFoundError("Task group is not in this JD")
    return tuple(task for area_id in (None, *area_ids) for task in tasks if task.area_id == area_id)


def _revise(task: WorkTask, changes: tuple[TaskChange, ...]) -> WorkTask:
    title, description = task.title, task.description
    details = task.details
    for change in changes:
        match change:
            case SetTaskField():
                if change.field == TaskField.TITLE:
                    title = change.value
                else:
                    description = change.value
            case AddTaskDetail():
                details = (*details, TaskDetail(uuid4(), change.kind, change.text))
            case ReviseTaskDetail() | RemoveTaskDetail():
                if not any(detail.detail_id == change.detail_id for detail in details):
                    raise TaskTargetNotFoundError("Detail is not in the selected task")
                if isinstance(change, RemoveTaskDetail):
                    details = tuple(d for d in details if d.detail_id != change.detail_id)
                else:
                    details = tuple(
                        replace(d, text=change.text) if d.detail_id == change.detail_id else d
                        for d in details
                    )
    revised = replace(task, title=title, description=description, details=_ordered_details(details))
    return replace(revised, content_revision_id=uuid4()) if revised != task else task


def _reorder_detail(task: WorkTask, edit: ReorderTaskDetail) -> WorkTask:
    target = next((d for d in task.details if d.detail_id == edit.detail_id), None)
    if target is None:
        raise TaskTargetNotFoundError("Detail is not in the selected task")
    if edit.before_detail_id == target.detail_id:
        return task
    same_kind = tuple(d for d in task.details if d.kind == target.kind and d != target)
    index = len(same_kind)
    if edit.before_detail_id is not None:
        neighbour = next((d for d in task.details if d.detail_id == edit.before_detail_id), None)
        if neighbour is None:
            raise TaskTargetNotFoundError("Detail ordering neighbour is not in this task")
        if neighbour.kind != target.kind:
            raise InvalidTaskChangeError("Outcomes and requirements have separate order")
        index = same_kind.index(neighbour)
    ordered = (*same_kind[:index], target, *same_kind[index:])
    details = _ordered_details((*ordered, *(d for d in task.details if d.kind != target.kind)))
    return (
        replace(task, details=details, content_revision_id=uuid4())
        if details != task.details
        else task
    )


def apply_task_edit(
    tasks: tuple[WorkTask, ...],
    area_ids: tuple[UUID, ...],
    edit: TaskEdit,
) -> tuple[tuple[WorkTask, ...], WorkTask | None]:
    """Compute the complete next collection before writes; return changed content only."""
    if (
        isinstance(edit, CreateTask | MoveTask)
        and edit.area_id is not None
        and edit.area_id not in area_ids
    ):
        raise TaskTargetNotFoundError("Destination responsibility group is not in this JD")
    if isinstance(edit, CreateTask):
        details = tuple(
            TaskDetail(uuid4(), kind, text)
            for kind, texts in (
                (DetailKind.OUTCOME, edit.outcomes),
                (DetailKind.REQUIREMENT, edit.requirements),
            )
            for text in texts
        )
        created = WorkTask(uuid4(), uuid4(), edit.area_id, edit.title, edit.description, details)
        return order_tasks((*tasks, created), area_ids), created
    target = next((task for task in tasks if task.task_id == edit.task_id), None)
    if target is None:
        raise TaskTargetNotFoundError("Task is not in the selected JD")
    if isinstance(edit, DeleteTask):
        return tuple(task for task in tasks if task != target), None
    if isinstance(edit, MoveTask):
        revised = _revise(target, edit.changes)
        moved = replace(revised, area_id=edit.area_id)
        remaining = tuple(task for task in tasks if task.task_id != target.task_id)
        destination = tuple(task for task in remaining if task.area_id == edit.area_id)
        if edit.before_task_id == target.task_id:
            if target.area_id != edit.area_id:
                raise InvalidTaskChangeError("A moved task cannot be its own destination neighbour")
            result = tuple(moved if task == target else task for task in tasks)
        else:
            index = len(destination)
            if edit.before_task_id is not None:
                neighbour = next((t for t in destination if t.task_id == edit.before_task_id), None)
                if neighbour is None:
                    raise TaskTargetNotFoundError("Ordering neighbour must belong to destination")
                index = destination.index(neighbour)
            result = order_tasks(
                (
                    *(task for task in remaining if task.area_id != edit.area_id),
                    *destination[:index],
                    moved,
                    *destination[index:],
                ),
                area_ids,
            )
        return result, moved if revised.content_revision_id != target.content_revision_id else None
    revised = (
        _revise(target, edit.changes)
        if isinstance(edit, ReviseTask)
        else _reorder_detail(target, edit)
    )
    return (
        tuple(revised if task == target else task for task in tasks),
        revised if revised != target else None,
    )


def detach_area_tasks(tasks: tuple[WorkTask, ...], area_id: UUID) -> tuple[WorkTask, ...]:
    """Append removed group's tasks to unassigned, keeping all identities and relative order."""
    return (
        *(task for task in tasks if task.area_id is None),
        *(replace(task, area_id=None) for task in tasks if task.area_id == area_id),
        *(task for task in tasks if task.area_id is not None and task.area_id != area_id),
    )


def _change_payload(change: TaskChange) -> dict[str, object]:
    match change:
        case SetTaskField():
            return {"action": "set_field", "field": change.field.value, "value": change.value}
        case AddTaskDetail():
            return {"action": "add_detail", "kind": change.kind.value, "text": change.text}
        case ReviseTaskDetail():
            return {
                "action": "revise_detail",
                "detail_id": str(change.detail_id),
                "text": change.text,
            }
        case RemoveTaskDetail():
            return {"action": "remove_detail", "detail_id": str(change.detail_id)}


def task_edit_payload(edit: TaskEdit) -> dict[str, object]:
    """JSON-compatible original intention; generated IDs are results, never replay inputs."""
    match edit:
        case CreateTask():
            return {
                "action": "create_task",
                "area_id": str(edit.area_id) if edit.area_id else None,
                "title": edit.title,
                "description": edit.description,
                "outcomes": list(edit.outcomes),
                "requirements": list(edit.requirements),
            }
        case ReviseTask():
            return {
                "action": "revise_task",
                "task_id": str(edit.task_id),
                "changes": [_change_payload(change) for change in edit.changes],
            }
        case MoveTask():
            return {
                "action": "move_task",
                "task_id": str(edit.task_id),
                "area_id": str(edit.area_id) if edit.area_id else None,
                "before_task_id": str(edit.before_task_id) if edit.before_task_id else None,
                "changes": [_change_payload(change) for change in edit.changes],
            }
        case ReorderTaskDetail():
            return {
                "action": "reorder_detail",
                "task_id": str(edit.task_id),
                "detail_id": str(edit.detail_id),
                "before_detail_id": str(edit.before_detail_id) if edit.before_detail_id else None,
            }
        case DeleteTask():
            return {"action": "delete_task", "task_id": str(edit.task_id)}
