"""Manual task HTTP intents and projections, without storage or transaction logic."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from caliburn.contracts.generated import edit_jd_tasks_request as wire
from caliburn.contracts.generated import jd_tasks_view as view
from caliburn.features.executions.models import ExecutionBusyError
from caliburn.features.job_description import tasks
from caliburn.features.job_description.models import JdCommandConflictError, StaleJdRevisionError
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http.jd_dependencies import JdEditing

router = APIRouter(prefix="/api/job-files/{job_file_id}/jd", tags=["job-description"])


def _change_from_wire(item: wire.TaskChange) -> tasks.TaskChange:
    match item.root:
        case wire.SetField() as change:
            return tasks.SetTaskField(
                tasks.TaskField(change.field.value), change.value.root if change.value else None
            )
        case wire.AddDetail() as change:
            return tasks.AddTaskDetail(tasks.DetailKind(change.kind.value), change.text.root)
        case wire.ReviseDetail() as change:
            return tasks.ReviseTaskDetail(change.detail_id, change.text.root)
        case wire.RemoveDetail() as change:
            return tasks.RemoveTaskDetail(change.detail_id)


def _edit_from_wire(
    edit: wire.CreateTask | wire.ReviseTask | wire.MoveTask | wire.ReorderDetail | wire.DeleteTask,
) -> tasks.TaskEdit:
    match edit:
        case wire.CreateTask():
            return tasks.CreateTask(
                edit.area_id,
                edit.title.root if edit.title else None,
                edit.description.root if edit.description else None,
                tuple(text.root for text in edit.outcomes),
                tuple(text.root for text in edit.requirements),
            )
        case wire.ReviseTask():
            return tasks.ReviseTask(
                edit.task_id, tuple(_change_from_wire(item) for item in edit.changes)
            )
        case wire.MoveTask():
            return tasks.MoveTask(
                edit.task_id,
                edit.area_id,
                edit.before_task_id,
                tuple(_change_from_wire(item) for item in edit.changes),
            )
        case wire.ReorderDetail():
            return tasks.ReorderTaskDetail(edit.task_id, edit.detail_id, edit.before_detail_id)
        case wire.DeleteTask():
            return tasks.DeleteTask(edit.task_id)


def _view(result: tasks.JdTasksRevision) -> view.JdTasksView:
    return view.JdTasksView(
        revision_id=result.revision_id,
        tasks=[
            view.WorkTask(
                task_id=task.task_id,
                area_id=task.area_id,
                title=task.title,
                description=task.description,
                outcomes=[
                    view.Detail(detail_id=detail.detail_id, text=detail.text)
                    for detail in task.details
                    if detail.kind == tasks.DetailKind.OUTCOME
                ],
                requirements=[
                    view.Detail(detail_id=detail.detail_id, text=detail.text)
                    for detail in task.details
                    if detail.kind == tasks.DetailKind.REQUIREMENT
                ],
            )
            for task in result.tasks
        ],
    )


@router.get("/tasks", response_model=view.JdTasksView)
async def read_tasks(job_file_id: UUID, workflow: JdEditing) -> view.JdTasksView:
    try:
        return _view(await workflow.read_tasks(job_file_id))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error


@router.post("/tasks", response_model=view.JdTasksView)
async def edit_tasks(
    job_file_id: UUID,
    body: wire.EditJdTasksRequest,
    workflow: JdEditing,
) -> view.JdTasksView:
    try:
        command = tasks.EditJdTasks(
            body.command_id, body.expected_revision_id, _edit_from_wire(body.change)
        )
        return _view(await workflow.edit_tasks(job_file_id, command))
    except JobFileNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "job_file_not_found"}) from error
    except tasks.TaskTargetNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "jd_task_target_not_found"}) from error
    except tasks.InvalidTaskChangeError as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_task_change"}) from error
    except JdCommandConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_command_conflict"}) from error
    except StaleJdRevisionError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_revision_stale"}) from error
    except ExecutionBusyError as error:
        raise HTTPException(status_code=409, detail={"code": "consultant_turn_active"}) from error
