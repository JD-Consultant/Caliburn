"""Area commands share fixed JD revisions and a caller-selected editing scope."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    area_persistence,
    persistence,
    revision_editing,
    task_persistence,
)
from caliburn.features.job_description.area_changes import apply_area_change
from caliburn.features.job_description.areas import (
    DeleteArea,
    EditJdAreas,
    JdAreasRevision,
    area_change_payload,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.models import (
    JdProfileRevision,
    StaleJdRevisionError,
)
from caliburn.features.job_description.task_changes import detach_area_tasks


async def read_areas(session: AsyncSession, job_file_id: UUID) -> JdAreasRevision:
    head = await persistence.read_document(session, job_file_id)
    return JdAreasRevision(
        head.current_revision_id,
        await area_persistence.read_areas(session, job_file_id, head.current_revision_id),
    )


async def recover_area_result(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdAreas,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdAreasRevision | None:
    operation = await revision_editing.read_edit_operation(
        session, job_file_id, command.command_id, candidate
    )
    if operation is None:
        return None
    revision_editing.require_matching_edit_intent(
        operation,
        kind="edit_areas",
        expected_revision_id=command.expected_revision_id,
        request_payload=area_change_payload(command.change),
    )
    return JdAreasRevision(
        operation.result_revision_id,
        await area_persistence.read_areas(session, job_file_id, operation.result_revision_id),
    )


async def edit_areas(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdAreas,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdAreasRevision:
    """Call after original-result lookup, file lock and scope admission; do not commit."""
    revision_id = await revision_editing.read_edit_revision(session, job_file_id, candidate)
    current = JdAreasRevision(
        revision_id, await area_persistence.read_areas(session, job_file_id, revision_id)
    )
    if current.revision_id != command.expected_revision_id:
        raise StaleJdRevisionError("Read the current JD before submitting a new edit")
    areas, new_content = apply_area_change(current.areas, command.change)
    result = current
    if areas != current.areas:
        if new_content is not None:
            await area_persistence.insert_area_content(session, job_file_id, new_content)
        profile = await persistence.read_revision(session, job_file_id, current.revision_id)
        result = JdAreasRevision(uuid4(), areas)
        tasks = None
        if isinstance(command.change, DeleteArea):
            tasks = detach_area_tasks(
                await task_persistence.read_tasks(session, job_file_id, current.revision_id),
                command.change.area_id,
            )
        await persistence.insert_revision(
            session,
            job_file_id,
            JdProfileRevision(result.revision_id, profile.profile),
            parent_revision_id=current.revision_id,
            areas=areas,
            tasks=tasks,
        )
    await revision_editing.record_edit(
        session,
        job_file_id,
        command_id=command.command_id,
        kind="edit_areas",
        expected_revision_id=command.expected_revision_id,
        result_revision_id=result.revision_id,
        request_payload=area_change_payload(command.change),
        candidate=candidate,
    )
    return result
