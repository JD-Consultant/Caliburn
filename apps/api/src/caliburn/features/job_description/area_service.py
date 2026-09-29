"""Area commands share fixed JD revisions and a caller-selected editing scope."""

from dataclasses import replace
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    area_persistence,
    persistence,
    revision_editing,
    task_persistence,
)
from caliburn.features.job_description.areas import (
    AreaChange,
    AreaField,
    AreaNotFoundError,
    CreateArea,
    DeleteArea,
    EditJdAreas,
    JdAreasRevision,
    ReorderArea,
    ResponsibilityArea,
    ReviseArea,
    area_change_payload,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.models import (
    JdCommandConflictError,
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
    if (
        operation.kind != "edit_areas"
        or operation.expected_revision_id != command.expected_revision_id
        or operation.request_payload != area_change_payload(command.change)
    ):
        raise JdCommandConflictError("command_id was already used with different JD intent")
    return JdAreasRevision(
        operation.result_revision_id,
        await area_persistence.read_areas(session, job_file_id, operation.result_revision_id),
    )


def _apply_change(
    areas: tuple[ResponsibilityArea, ...], change: AreaChange
) -> tuple[tuple[ResponsibilityArea, ...], ResponsibilityArea | None]:
    """Return ordered membership and, only for changed text, one new fixed content revision."""
    if isinstance(change, CreateArea):
        created = ResponsibilityArea(uuid4(), uuid4(), change.title, change.scope_text)
        return (*areas, created), created
    target = next((area for area in areas if area.area_id == change.area_id), None)
    if target is None:
        raise AreaNotFoundError("Area is not in the selected JD")
    if isinstance(change, ReviseArea):
        title, scope_text = target.title, target.scope_text
        for item in change.changes:
            if item.field is AreaField.TITLE:
                title = item.value
            else:
                scope_text = item.value
        revised = replace(target, title=title, scope_text=scope_text)
        if revised == target:
            return areas, None
        revised = replace(revised, content_revision_id=uuid4())
        return tuple(revised if area.area_id == target.area_id else area for area in areas), revised
    remaining = tuple(area for area in areas if area.area_id != target.area_id)
    if isinstance(change, DeleteArea):
        return remaining, None
    if isinstance(change, ReorderArea):
        if change.before_area_id == target.area_id:
            return areas, None
        if change.before_area_id is None:
            return (*remaining, target), None
        for index, neighbour in enumerate(remaining):
            if neighbour.area_id == change.before_area_id:
                return (*remaining[:index], target, *remaining[index:]), None
        raise AreaNotFoundError("Ordering neighbour is not in this JD")
    raise TypeError("Unsupported area change")


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
    areas, new_content = _apply_change(current.areas, command.change)
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
