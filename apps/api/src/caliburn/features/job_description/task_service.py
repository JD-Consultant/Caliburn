"""Task commands share the formal JD head and caller-owned transaction."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import area_persistence, persistence, task_persistence
from caliburn.features.job_description.models import (
    JdCommandConflictError,
    JdProfileRevision,
    StaleJdRevisionError,
)
from caliburn.features.job_description.task_changes import apply_task_edit, task_edit_payload
from caliburn.features.job_description.tasks import EditJdTasks, JdTasksRevision


async def read_tasks(session: AsyncSession, job_file_id: UUID) -> JdTasksRevision:
    head = await persistence.read_document(session, job_file_id)
    return JdTasksRevision(
        head.current_revision_id,
        await task_persistence.read_tasks(session, job_file_id, head.current_revision_id),
    )


async def recover_task_result(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdTasks,
) -> JdTasksRevision | None:
    operation = await persistence.read_operation(session, job_file_id, command.command_id)
    if operation is None:
        return None
    if (
        operation.kind != "edit_tasks"
        or operation.expected_revision_id != command.expected_revision_id
        or operation.request_payload != task_edit_payload(command.change)
    ):
        raise JdCommandConflictError("command_id was already used with different JD intent")
    return JdTasksRevision(
        operation.result_revision_id,
        await task_persistence.read_tasks(session, job_file_id, operation.result_revision_id),
    )


async def edit_tasks(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdTasks,
) -> JdTasksRevision:
    """Call after file lock, original-result lookup and manual admission; do not commit."""
    current = await read_tasks(session, job_file_id)
    if current.revision_id != command.expected_revision_id:
        raise StaleJdRevisionError("Read the current JD before submitting a new edit")
    areas = await area_persistence.read_areas(session, job_file_id, current.revision_id)
    tasks, new_content = apply_task_edit(
        current.tasks, tuple(area.area_id for area in areas), command.change
    )
    result = current
    if tasks != current.tasks:
        if new_content is not None:
            await task_persistence.insert_task_content(session, job_file_id, new_content)
        profile = await persistence.read_revision(session, job_file_id, current.revision_id)
        result = JdTasksRevision(uuid4(), tasks)
        await persistence.insert_revision(
            session,
            job_file_id,
            JdProfileRevision(result.revision_id, profile.profile),
            parent_revision_id=current.revision_id,
            tasks=tasks,
        )
        document = await persistence.read_document(session, job_file_id)
        document.current_revision_id = result.revision_id
    session.add(
        persistence.JdOperationRecord(
            job_file_id=job_file_id,
            command_id=command.command_id,
            kind="edit_tasks",
            expected_revision_id=command.expected_revision_id,
            result_revision_id=result.revision_id,
            request_payload=task_edit_payload(command.change),
        )
    )
    await session.flush()
    return result
