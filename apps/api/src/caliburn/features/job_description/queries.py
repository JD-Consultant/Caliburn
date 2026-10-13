"""讀取目前正式頭或指定修訂的 JD 區段；不建立或修改資料。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    area_persistence,
    capability_persistence,
    collaborator_persistence,
    condition_persistence,
    persistence,
    task_persistence,
)
from caliburn.features.job_description.areas import JdAreasRevision
from caliburn.features.job_description.capabilities import JdCapabilitiesRevision
from caliburn.features.job_description.collaborators import JdCollaboratorsRevision
from caliburn.features.job_description.conditions import JdConditionsRevision
from caliburn.features.job_description.models import JdProfileRevision
from caliburn.features.job_description.tasks import JdTasksRevision


async def read_profile(session: AsyncSession, job_file_id: UUID) -> JdProfileRevision:
    document = await persistence.read_document(session, job_file_id)
    return await read_profile_at(session, job_file_id, document.current_revision_id)


async def read_profile_at(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdProfileRevision:
    return await persistence.read_revision(session, job_file_id, revision_id)


async def read_areas(session: AsyncSession, job_file_id: UUID) -> JdAreasRevision:
    head = await persistence.read_document(session, job_file_id)
    return await read_areas_at(session, job_file_id, head.current_revision_id)


async def read_areas_at(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdAreasRevision:
    return JdAreasRevision(
        revision_id,
        await area_persistence.read_areas(session, job_file_id, revision_id),
    )


async def read_tasks(session: AsyncSession, job_file_id: UUID) -> JdTasksRevision:
    head = await persistence.read_document(session, job_file_id)
    return await read_tasks_at(session, job_file_id, head.current_revision_id)


async def read_tasks_at(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdTasksRevision:
    return JdTasksRevision(
        revision_id,
        await task_persistence.read_tasks(session, job_file_id, revision_id),
    )


async def read_capabilities(session: AsyncSession, job_file_id: UUID) -> JdCapabilitiesRevision:
    head = await persistence.read_document(session, job_file_id)
    return await read_capabilities_at(session, job_file_id, head.current_revision_id)


async def read_capabilities_at(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdCapabilitiesRevision:
    return JdCapabilitiesRevision(
        revision_id,
        await capability_persistence.read_capabilities(session, job_file_id, revision_id),
        await capability_persistence.read_task_links(session, job_file_id, revision_id),
    )


async def read_collaborators(session: AsyncSession, job_file_id: UUID) -> JdCollaboratorsRevision:
    head = await persistence.read_document(session, job_file_id)
    return await read_collaborators_at(session, job_file_id, head.current_revision_id)


async def read_collaborators_at(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdCollaboratorsRevision:
    return JdCollaboratorsRevision(
        revision_id,
        await collaborator_persistence.read_collaborators(session, job_file_id, revision_id),
    )


async def read_conditions(session: AsyncSession, job_file_id: UUID) -> JdConditionsRevision:
    head = await persistence.read_document(session, job_file_id)
    return await read_conditions_at(session, job_file_id, head.current_revision_id)


async def read_conditions_at(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdConditionsRevision:
    return JdConditionsRevision(
        revision_id,
        await condition_persistence.read_conditions(session, job_file_id, revision_id),
    )
